"""The chart's MutatingAdmissionPolicy against a real kube-apiserver.

A policy is evaluated entirely inside the API server, so this needs no
kubelet, no node and no GPU: it starts etcd and kube-apiserver from the
Kubernetes envtest binaries, applies what `helm template` renders, creates
pods shaped like the device plugins' and reads back what the server stored.
It holds the policy to its contract:

  - a device plugin pod (GPU Operator or standalone chart) gets the check as
    its last init container, with the state volume and the configured
    environment; the server type-checks every expression doing it
  - nothing else is touched: other containers in the same namespace, device
    plugins in other namespaces, a pod that already has the check
  - values reach the pod: namespaces, label selector, thresholds, inline
    baselines, extra environment, security context
  - the policy's API version is the newest the cluster serves (rendered
    without a server, so this one runs without ENVTEST_BIN)

    ENVTEST_BIN=/path/to/envtest/bin HELM=helm \\
        python3 -m unittest discover -s deploy/helm/gpu-health/tests -p 'test_admission.py' -v

The server tests are skipped when ENVTEST_BIN is unset.  The binaries are the ones controller-tools
publishes (envtest-v1.37.0-linux-amd64.tar.gz); the chart's e2e/run.sh runs the
same chart on a kind cluster, where the check actually gates the plugin.
"""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CHART = os.path.dirname(HERE)
BIN = os.environ.get("ENVTEST_BIN", "")
HELM = os.environ.get("HELM", "helm")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pod(name, namespace, containers, init=(), labels=None, volumes=None):
    spec = {"containers": [{"name": c, "image": "registry.example/plugin:1"} for c in containers]}
    if init:
        spec["initContainers"] = [{"name": c, "image": "registry.example/init:1"} for c in init]
    if volumes:
        spec["volumes"] = volumes
    return {"apiVersion": "v1", "kind": "Pod",
            "metadata": {"name": name, "namespace": namespace, "labels": labels or {}},
            "spec": spec}


@unittest.skipUnless(BIN, "ENVTEST_BIN (etcd, kube-apiserver, kubectl) is not set")
class Policy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="gpu-health-apiserver-")
        cls.procs, cls.logs = [], []
        try:
            cls.start_server()
        except BaseException:
            # unittest skips tearDownClass when this fails: stop what started.
            cls.tearDownClass()
            raise

    @classmethod
    def start_server(cls):
        d = cls.dir
        subprocess.run(["openssl", "genrsa", "-out", os.path.join(d, "sa.key"), "2048"],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "rsa", "-in", os.path.join(d, "sa.key"), "-pubout", "-out",
                        os.path.join(d, "sa.pub")], check=True, capture_output=True)
        with open(os.path.join(d, "tokens.csv"), "w") as f:
            f.write("admin-token,admin,admin,system:masters\n")
        etcd, peer, api = free_port(), free_port(), free_port()
        log = open(os.path.join(d, "etcd.log"), "w")
        cls.logs.append(log)
        cls.procs.append(subprocess.Popen([
            os.path.join(BIN, "etcd"), "--data-dir", os.path.join(d, "etcd"), "--unsafe-no-fsync",
            "--listen-client-urls", "http://127.0.0.1:%d" % etcd,
            "--advertise-client-urls", "http://127.0.0.1:%d" % etcd,
            "--listen-peer-urls", "http://127.0.0.1:%d" % peer], stdout=log, stderr=log))
        log = open(os.path.join(d, "apiserver.log"), "w")
        cls.logs.append(log)
        cls.procs.append(subprocess.Popen([
            os.path.join(BIN, "kube-apiserver"),
            "--etcd-servers", "http://127.0.0.1:%d" % etcd,
            "--cert-dir", os.path.join(d, "certs"), "--bind-address", "127.0.0.1",
            "--secure-port", str(api), "--service-cluster-ip-range", "10.0.0.0/24",
            "--service-account-issuer", "https://kubernetes.default.svc.cluster.local",
            "--service-account-key-file", os.path.join(d, "sa.pub"),
            "--service-account-signing-key-file", os.path.join(d, "sa.key"),
            "--token-auth-file", os.path.join(d, "tokens.csv"), "--authorization-mode", "RBAC",
            # No controller-manager creates service accounts here.
            "--disable-admission-plugins", "ServiceAccount", "--allow-privileged=true"],
            stdout=log, stderr=log))
        cls.kubeconfig = os.path.join(d, "kubeconfig")
        # The server makes itself a CA and a serving certificate for, among
        # others, 127.0.0.1, and writes both to this file as it starts.
        cert = os.path.join(d, "certs", "apiserver.crt")
        with open(cls.kubeconfig, "w") as f:
            json.dump({"apiVersion": "v1", "kind": "Config", "current-context": "t",
                       "clusters": [{"name": "t", "cluster": {
                           "server": "https://127.0.0.1:%d" % api,
                           "certificate-authority": cert}}],
                       "users": [{"name": "t", "user": {"token": "admin-token"}}],
                       "contexts": [{"name": "t", "context": {"cluster": "t", "user": "t"}}]}, f)
        deadline = time.time() + 90
        while time.time() < deadline:
            if os.path.exists(cert):
                r = cls.kubectl("get", "--raw", "/readyz", check=False)
                if r.returncode == 0:
                    break
            time.sleep(0.5)
        else:
            with open(os.path.join(d, "apiserver.log")) as f:
                tail = f.read()[-3000:]
            raise RuntimeError("kube-apiserver did not become ready:\n" + tail)
        for ns in ("gpu-operator", "nvidia-device-plugin", "other"):
            cls.kubectl("create", "namespace", ns)

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.procs):
            p.terminate()
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
        for f in cls.logs:
            f.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def kubectl(cls, *args, stdin=None, check=True):
        r = subprocess.run([os.path.join(BIN, "kubectl"), "--kubeconfig", cls.kubeconfig] +
                           list(args), input=stdin, capture_output=True, text=True, timeout=60)
        if check and r.returncode != 0:
            raise AssertionError("kubectl %s: %s" % (" ".join(args), r.stderr))
        return r

    def install(self, *values):
        """Render the chart with `values` (--set/-f arguments) and apply it,
        replacing whatever an earlier test installed; wait until it acts."""
        self.kubectl("delete", "mutatingadmissionpolicies,mutatingadmissionpolicybindings",
                     "--all", "--wait=true")
        out = subprocess.run([HELM, "template", "gh", CHART, "--kube-version", "1.37.0"] +
                             list(values), capture_output=True, text=True, check=True).stdout
        self.kubectl("apply", "-f", "-", stdin=out)
        self.rendered = out

    def create(self, obj, wait_for_policy=True):
        """Create a pod and return what the server stored.  A new policy
        takes a moment to reach the admission chain, so the first pod of a
        test is retried (under a dry run) until a device plugin is mutated."""
        if wait_for_policy:
            probe = pod("probe", obj["metadata"]["namespace"], ["nvidia-device-plugin"])
            deadline = time.time() + 30
            while True:
                got = json.loads(self.kubectl("create", "--dry-run=server", "-o", "json", "-f",
                                              "-", stdin=json.dumps(probe)).stdout)
                if any(c["name"] == "gpu-health" for c in got["spec"].get("initContainers", [])):
                    break
                self.assertLess(time.time(), deadline, "the policy never took effect")
                time.sleep(0.5)
        return json.loads(self.kubectl("create", "--dry-run=server", "-o", "json", "-f", "-",
                                       stdin=json.dumps(obj)).stdout)

    def inits(self, stored):
        return [c["name"] for c in stored["spec"].get("initContainers", [])]

    def check_container(self, stored):
        return [c for c in stored["spec"]["initContainers"] if c["name"] == "gpu-health"][0]

    def env(self, container):
        return {e["name"]: e.get("value", e.get("valueFrom")) for e in container["env"]}

    # ---- the defaults -------------------------------------------------------------

    def test_gpu_operator_device_plugin(self):
        self.install()
        stored = self.create(pod(
            "nvidia-device-plugin-daemonset-x", "gpu-operator", ["nvidia-device-plugin",
                                                                 "config-manager"],
            init=["toolkit-validation", "config-manager-init"],
            labels={"app": "nvidia-device-plugin-daemonset"},
            volumes=[{"name": "run-nvidia-validations",
                      "hostPath": {"path": "/run/nvidia/validations"}}]))
        self.assertEqual(self.inits(stored),
                         ["toolkit-validation", "config-manager-init", "gpu-health"])
        c = self.check_container(stored)
        self.assertEqual(c["image"], "ghcr.io/aburan28/gpu-health:0.1.0")
        self.assertEqual(c["imagePullPolicy"], "IfNotPresent")
        env = self.env(c)
        self.assertEqual(env["GPU_HEALTH_SECONDS"], "90")
        self.assertEqual(env["GPU_HEALTH_STATE_DIR"], "/run/gpu-health")
        self.assertEqual(env["GPU_HEALTH_SKIP_IF_BUSY"], "1")
        self.assertEqual(env["GPU_HEALTH_MAX_UPTIME"], "3600")
        self.assertEqual(env["GPU_HEALTH_SKIP_WITHOUT_GPUS"], "1")
        self.assertEqual(env["GPU_HEALTH_SKIP_UNSUPPORTED"], "1")
        self.assertEqual(env["GPU_HEALTH_WAIT_SECONDS"], "900")
        self.assertNotIn("GPU_HEALTH_REPORT_ONLY", env)
        self.assertEqual(env["NVIDIA_VISIBLE_DEVICES"], "all")
        self.assertEqual(env["NVIDIA_DRIVER_CAPABILITIES"], "compute,utility")
        self.assertEqual(env["NODE_NAME"], {"fieldRef": {"apiVersion": "v1",
                                                         "fieldPath": "spec.nodeName"}})
        self.assertNotIn("GPU_HEALTH_LABEL_NODE", env)
        self.assertEqual(c["resources"], {"requests": {"cpu": "100m", "memory": "1Gi"},
                                          "limits": {"memory": "16Gi"}})
        self.assertEqual(c["securityContext"], {"privileged": True, "runAsUser": 0})
        self.assertEqual(c["volumeMounts"], [{"name": "gpu-health-state",
                                              "mountPath": "/run/gpu-health"}])
        self.assertEqual(c["terminationMessagePolicy"], "FallbackToLogsOnError")
        volumes = {v["name"]: v for v in stored["spec"]["volumes"]}
        self.assertIn("run-nvidia-validations", volumes)
        self.assertEqual(volumes["gpu-health-state"]["hostPath"],
                         {"path": "/run/gpu-health", "type": "DirectoryOrCreate"})

    def test_standalone_plugin_without_init_containers_or_volumes(self):
        self.install()
        stored = self.create(pod("nvidia-device-plugin-y", "gpu-operator",
                                 ["nvidia-device-plugin-ctr"]))
        self.assertEqual(self.inits(stored), ["gpu-health"])
        self.assertEqual([v["name"] for v in stored["spec"]["volumes"]], ["gpu-health-state"])

    def test_other_pods_are_untouched(self):
        self.install()
        self.create(pod("warm-up", "gpu-operator", ["nvidia-device-plugin"]))
        for obj in [pod("gfd", "gpu-operator", ["gpu-feature-discovery-ctr"]),
                    pod("dcgm", "gpu-operator", ["nvidia-dcgm-exporter"], init=["init"]),
                    pod("elsewhere", "other", ["nvidia-device-plugin"])]:
            stored = self.create(obj, wait_for_policy=False)
            self.assertNotIn("gpu-health", self.inits(stored), obj["metadata"])

    def test_not_injected_twice(self):
        self.install()
        self.create(pod("warm-up", "gpu-operator", ["nvidia-device-plugin"]))
        stored = self.create(pod("already", "gpu-operator", ["nvidia-device-plugin"],
                                 init=["gpu-health"]), wait_for_policy=False)
        self.assertEqual(self.inits(stored), ["gpu-health"])
        self.assertNotIn("volumes", stored["spec"])

    def test_the_server_type_checks_the_policy_cleanly(self):
        self.install()
        self.create(pod("warm-up", "gpu-operator", ["nvidia-device-plugin"]))
        for kind in ("mutatingadmissionpolicies", "mutatingadmissionpolicybindings"):
            items = json.loads(self.kubectl("get", kind, "-o", "json").stdout)["items"]
            self.assertEqual(len(items), 1, kind)
            warnings = (items[0].get("status") or {}).get("typeChecking", {}).get(
                "expressionWarnings", [])
            self.assertEqual(warnings, [], "%s: %s" % (kind, warnings))

    def test_node_gate_manifests_are_accepted(self):
        out = subprocess.run([HELM, "template", "gh", CHART, "--kube-version", "1.37.0",
                              "--namespace", "gpu-health", "--set", "inject.enabled=false",
                              "--set", "nodeGate.enabled=true",
                              "--set", "rbac.labelNodes.enabled=true"],
                             capture_output=True, text=True, check=True).stdout
        self.kubectl("create", "namespace", "gpu-health", check=False)
        r = self.kubectl("apply", "--dry-run=server", "-f", "-", stdin=out)
        for kind in ("serviceaccount", "clusterrole", "clusterrolebinding", "daemonset"):
            self.assertIn(kind, r.stdout.lower(), r.stdout)

    # ---- values ---------------------------------------------------------------------

    def test_values_reach_the_pod(self):
        baselines = {"entries": [{"name": "NVIDIA H100 80GB HBM3", "sms": 132,
                                  "iterationsPerSecond": 7.1e9}]}
        path = os.path.join(self.dir, "values.json")
        with open(path, "w") as f:
            json.dump({"image": {"digest": "sha256:" + "ab" * 32},
                       "check": {"seconds": 120, "expectGpus": "pci", "strict": True,
                                 "maxUptimeSeconds": 0, "reportOnly": True,
                                 "thresholds": {"baseline_fail": 0.93, "peer_fail": 0.9},
                                 "baselines": baselines, "privileged": None,
                                 "extraEnv": [{"name": "X_TEST",
                                               "value": 'a "quoted" \\ <value>'}]},
                       "inject": {"namespaces": ["nvidia-device-plugin"], "labelNode": True,
                                  "objectSelector": {"matchLabels": {
                                      "app.kubernetes.io/name": "nvidia-device-plugin"}}}}, f)
        self.install("-f", path)
        labels = {"app.kubernetes.io/name": "nvidia-device-plugin"}
        # create()'s probe carries no labels, so wait on a labelled pod here.
        deadline = time.time() + 30
        while True:
            stored = self.create(pod("dp", "nvidia-device-plugin", ["nvidia-device-plugin-ctr"],
                                     labels=labels), wait_for_policy=False)
            if "gpu-health" in self.inits(stored):
                break
            self.assertLess(time.time(), deadline, "the policy never took effect")
            time.sleep(0.5)
        c = self.check_container(stored)
        self.assertEqual(c["image"], "ghcr.io/aburan28/gpu-health@sha256:" + "ab" * 32)
        env = self.env(c)
        self.assertEqual(env["GPU_HEALTH_SECONDS"], "120")
        self.assertEqual(env["GPU_HEALTH_EXPECT_GPUS"], "pci")
        self.assertEqual(env["GPU_HEALTH_STRICT"], "1")
        self.assertEqual(env["GPU_HEALTH_LABEL_NODE"], "1")
        self.assertEqual(env["GPU_HEALTH_MAX_UPTIME"], "0")
        self.assertEqual(env["GPU_HEALTH_REPORT_ONLY"], "1")
        self.assertEqual(sorted(env["GPU_HEALTH_THRESHOLDS"].split(",")),
                         ["baseline_fail=0.93", "peer_fail=0.9"])
        self.assertEqual(json.loads(env["GPU_HEALTH_BASELINES_JSON"]), baselines)
        self.assertEqual(env["X_TEST"], 'a "quoted" \\ <value>')
        self.assertEqual(c["securityContext"], {"runAsUser": 0})
        unlabelled = self.create(pod("nolabel", "nvidia-device-plugin",
                                     ["nvidia-device-plugin-ctr"]), wait_for_policy=False)
        self.assertNotIn("gpu-health", self.inits(unlabelled), "the label selector was ignored")
        default_ns = self.create(pod("oldns", "gpu-operator", ["nvidia-device-plugin"],
                                     labels=labels), wait_for_policy=False)
        self.assertNotIn("gpu-health", self.inits(default_ns), "the namespace list was ignored")


class Render(unittest.TestCase):
    """What the chart renders without a server to ask."""

    def api_versions(self, *args):
        out = subprocess.run([HELM, "template", "gh", CHART] + list(args), capture_output=True,
                             text=True, check=True).stdout
        return sorted({line.split(":", 1)[1].strip() for line in out.splitlines()
                       if line.startswith("apiVersion: admissionregistration")})

    @unittest.skipUnless(shutil.which(HELM), "helm is not on PATH")
    def test_the_policy_api_follows_the_cluster(self):
        map_ = "admissionregistration.k8s.io/%s/MutatingAdmissionPolicy"
        self.assertEqual(self.api_versions(), ["admissionregistration.k8s.io/v1"])
        self.assertEqual(self.api_versions("--api-versions", map_ % "v1beta1"),
                         ["admissionregistration.k8s.io/v1beta1"])
        self.assertEqual(self.api_versions("--api-versions", map_ % "v1alpha1",
                                           "--api-versions", map_ % "v1beta1"),
                         ["admissionregistration.k8s.io/v1beta1"])
        self.assertEqual(self.api_versions("--api-versions", map_ % "v1beta1",
                                           "--api-versions", map_ % "v1"),
                         ["admissionregistration.k8s.io/v1"])
        self.assertEqual(self.api_versions("--api-versions", map_ % "v1", "--set",
                                           "inject.apiVersion=admissionregistration.k8s.io/"
                                           "v1alpha1"),
                         ["admissionregistration.k8s.io/v1alpha1"])


if __name__ == "__main__":
    unittest.main()
