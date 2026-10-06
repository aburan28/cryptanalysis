# gpu-health chart: the GPU check in front of the device plugin

This chart makes a new GPU node prove its GPUs before it offers them to the
scheduler. A MutatingAdmissionPolicy (evaluated inside the API server, with no
webhook to run) appends the [GPU health check](../../gpu-health/README.md) to
the init containers of the NVIDIA device plugin's pods. The device plugin is
what advertises `nvidia.com/gpu` to the kubelet. So a node has no GPUs to
schedule onto until every GPU on it has run the self-checking ECC2K-130 load
and passed.

```sh
helm install gpu-health deploy/helm/gpu-health -n gpu-health --create-namespace \
    --set image.digest=sha256:...            # the image you tested; see "Rolling it out"
```

The device plugin's pod is the natural host for the check:

- it already tolerates the GPU taints and runs on every GPU node;
- in the GPU Operator, its own init containers wait for the driver and the
  container toolkit, so the check starts once the GPUs are ready to use;
- nothing can be scheduled onto the GPUs before it finishes, because the
  plugin that would advertise them has not started.

## What happens on a node

```text
node boots ─► driver and container toolkit (GPU Operator) ─► device plugin pod created
   init containers: toolkit-validation ─► config-manager-init ─► gpu-health ─┐
                                                                             │ pass or skip (exit 0)
   nvidia-device-plugin starts ─► node advertises nvidia.com/gpu ◄───────────┘
                                                                  fail (exit 1): plugin held back,
                                                                  kubelet retries the check
```

The policy acts only when a pod is **created**. It matches a pod in one of
`inject.namespaces` that runs a container named in `inject.containers`
(`nvidia-device-plugin` for the GPU Operator, `nvidia-device-plugin-ctr` for
the standalone plugin chart) and does not already carry the check. Pods that
existed before the policy keep their spec until they are recreated. The
check is appended with JSON Patch, so it runs **after** the pod's own init
containers. An apply-configuration merge would have put it first, ahead of
the driver wait. The policy also adds a hostPath volume (`check.stateDir`,
default `/run/gpu-health`) for the node's record. Its `failurePolicy` is
`Ignore`: if the API server cannot evaluate the policy, the pod is admitted
unchanged rather than not at all.

### When the check loads the GPUs

The check keeps a record of the current boot in `boot.json` on the node,
keyed on the kernel's boot id. From that record it decides whether anything
could be using the GPUs:

| on this node | the check | because |
|---|---|---|
| no record of this boot, up less than `check.maxUptimeSeconds` (1 h) | **runs** | the node has just come up |
| it failed or was interrupted earlier this boot | **runs** | the plugin has not started since the boot, so the GPUs are idle |
| it passed earlier this boot | skips | a plugin restart (rollout, upgrade) must not load GPUs that may be running work |
| it let the plugin start without a pass (a skip, or `reportOnly`) | skips | the plugin may have handed out the GPUs |
| no record of this boot, up longer than `check.maxUptimeSeconds` | skips | the node was in service before the check reached it; it is checked at its next boot |
| another process shows in nvidia-smi on one of its GPUs | skips | a second guard; from inside a container nvidia-smi may not see other containers' processes |
| no NVIDIA GPU on its PCI bus | skips | a plugin scheduled onto a CPU node has nothing to advertise |
| only GPUs below compute capability 8.0 (T4, V100) | skips | the walk needs `clmad` (sm_80); on a mixed node those GPUs are left out, with a warning |

A skip exits 0 within seconds and records itself. A check that runs
takes `check.seconds` (90) of load plus 10-30 s of setup, and in that time
the node has no advertised GPUs.

### When it fails

The init container exits 1, and the device plugin does not start. The node
keeps no advertised `nvidia.com/gpu`, so no GPU pod is scheduled onto it.
The kubelet reruns the check with its crash-loop backoff (at most five
minutes apart, by default). Every rerun is a full load, so a node whose
fault clears is released by the first rerun that passes. The pod shows
`Init:Error` or `Init:CrashLoopBackOff`, and the reason is the check's
termination message:

```sh
kubectl get pods -n gpu-operator -l app=nvidia-device-plugin-daemonset -o wide
kubectl logs -n gpu-operator POD -c gpu-health --tail=3
kubectl get pod -n gpu-operator POD \
    -o jsonpath='{.status.initContainerStatuses[?(@.name=="gpu-health")].lastState.terminated.message}'
```

Exit 2 means the check could not run as configured, for example an unusable
`stateDir`. That holds the plugin back too, so a misconfiguration shows on
the first node rather than silently turning the check off.

## Installing

**NVIDIA GPU Operator.** The defaults fit it: namespace `gpu-operator`,
container `nvidia-device-plugin`. If the operator runs in another
namespace, set `inject.namespaces`. The injected container is privileged,
like the operator's device plugin. The namespace must therefore already
admit privileged pods; NVIDIA's instructions label it
`pod-security.kubernetes.io/enforce=privileged`.

**Standalone NVIDIA device plugin chart.** Point the policy at the plugin's
namespace:

```sh
helm install gpu-health deploy/helm/gpu-health -n gpu-health --create-namespace \
    --set 'inject.namespaces={nvidia-device-plugin}'
```

Its container, `nvidia-device-plugin-ctr`, is matched by default. The
gpu-feature-discovery pods carry the same labels but not that container, so
they are left alone. The standalone plugin does not wait for the driver, so
the check does: `check.waitSeconds` (900) covers a driver that loads after
the pod starts. The pod must run under the NVIDIA container runtime, which
the plugin needs anyway: `runtimeClassName: nvidia` in the plugin's values,
or `nvidia` as the node's default runtime.

**Anything else that advertises GPUs.** `inject.containers` is a list of
container names, and `inject.objectSelector` narrows by pod label. The check
holds back whichever pod it is injected into.

**Kubernetes version.** MutatingAdmissionPolicy is served at
`admissionregistration.k8s.io/v1` from Kubernetes 1.36, which is enabled
by default. Earlier releases have it as v1beta1 (1.34-1.35) and v1alpha1
(1.32-1.33). Both are off by default: enable them on the API server with the
`MutatingAdmissionPolicy` feature gate and `--runtime-config`. The chart
picks the newest version the cluster serves. Set `inject.apiVersion` to
override that choice, or to choose one when rendering without a cluster
(`helm template` renders v1).

## Rolling it out

1. **Pin the image.** Build it from the repository root
   (`docker build -f deploy/gpu-health/Dockerfile .`), or take the image the
   `gpu-health` workflow publishes for a `gpu-health-v*` tag. Mirror it into
   the registry your GPU nodes already pull from, and set `image.digest`.
   Every new GPU node pulls this image before its device plugin can start,
   so an unreachable image keeps new nodes from offering GPUs. Give it the
   same availability as the GPU Operator's own images.
2. **Report only.** Install with `check.reportOnly=true`. The check then runs
   and records its verdict, but the plugin always starts. A verdict that
   would have held the plugin back ends with "(report only: not enforced)".
   Leave it on while nodes boot or join, and read the verdicts (see below). This catches
   a misconfiguration, such as no GPUs visible to the check or the wrong
   namespace, before it can hold a node back. It also collects throughput
   for calibration.
3. **Calibrate** baselines per GPU model, as in
   [the check's README](../../gpu-health/README.md#calibrating-baselines),
   and pass them inline as `check.baselines`. Without baselines, throughput
   is still compared with the node's other GPUs of the same model and with
   the run's own first window.
4. **Enforce.** Set `check.reportOnly=false`. Like every change to the
   check's settings, this reaches a node when its device plugin pod is next
   created.

Installing the chart loads no GPU by itself, because existing device plugin
pods are not changed. When a pod is recreated on a node that has been up
longer than `check.maxUptimeSeconds`, the check skips the load, and that node
is checked at its next boot. The exposure is a node that booted within the
last `check.maxUptimeSeconds` and already runs GPU work when its plugin pod
is recreated. There the busy guard is all that stands between the check and
the work. Lower `check.maxUptimeSeconds` if your nodes start taking work
faster than that.

## Operating it

- **Verdicts.** The last line of the check's log is its verdict, or its
  reason to skip. With `inject.labelNode=true` and
  `rbac.labelNodes.enabled=true`, it is also recorded on the node:
  `kubectl get nodes -L gpu-health/verdict`. That setting grants the
  device plugin's service account `get` and `patch` on nodes, which is why
  it is off by default. The node keeps the full report of the last load in
  `last.json` and the record of the boot in `boot.json`:
  `kubectl debug node/NODE -it --image=busybox -- cat /host/run/gpu-health/boot.json`.
- **A node that fails.** It stays without GPUs, and the kubelet keeps
  retrying the check. Cordon it and replace it or send it for service.
  After a repair, reboot it: a reboot starts a new record.
- **Checking a node again.** Reboot it. Deleting `boot.json` and then the
  device plugin pod also works, but only do that on a node whose GPUs are
  idle.
- **Turning it off.** `helm upgrade ... --set inject.enabled=false`, or
  `kubectl delete mutatingadmissionpolicybinding -l app.kubernetes.io/instance=RELEASE`,
  stops new injections at once. A node whose device plugin pod is stuck on the
  check is released by deleting that pod; its replacement comes back
  without the check:
  `kubectl delete pod -n gpu-operator -l app=nvidia-device-plugin-daemonset --field-selector spec.nodeName=NODE`.

## Values

| value | default | |
|---|---|---|
| `image.repository`, `image.tag`, `image.digest` | `ghcr.io/aburan28/gpu-health`, appVersion, none | a digest wins over the tag |
| `check.seconds` | 90 | load on every GPU of the node, all at once |
| `check.expectGpus` | `"0"` | fail unless this many GPUs are visible: a number, 0 for any, or `pci` for as many NVIDIA GPUs as the PCI bus shows (catches a GPU the driver lost; not for MIG nodes) |
| `check.waitSeconds` | 900 | how long to wait for the driver to show the GPUs |
| `check.maxUptimeSeconds` | 3600 | a node up longer than this with no record of this boot is left alone until it reboots; 0 for no limit |
| `check.reportOnly` | false | record the verdict, never hold the plugin back |
| `check.baselines`, `check.thresholds`, `check.strict` | none, none, false | throughput baselines, pass/fail ratios, warnings as failures |
| `check.stateDir` | `/run/gpu-health` | host directory for `boot.json`, `last.json` and the lock |
| `check.privileged`, `check.runAsUser` | true, 0 | how the check reaches every GPU and writes `stateDir` |
| `check.resources` | requests 100m CPU and 1Gi, limit 16Gi | an init container's requests count toward its pod's for the pod's lifetime, so they stay small; with no CPU limit, the host checks use idle cores |
| `check.extraEnv` | none | more environment for the check (the settings table in the check's README) |
| `inject.enabled` | true | the policy and its binding |
| `inject.namespaces`, `inject.containers`, `inject.objectSelector` | `gpu-operator`; `nvidia-device-plugin`, `nvidia-device-plugin-ctr`; none | which pods get the check |
| `inject.apiVersion` | the newest served | MutatingAdmissionPolicy API version |
| `inject.failurePolicy` | Ignore | what the API server does if it cannot evaluate the policy |
| `inject.labelNode`, `rbac.labelNodes` | off | record verdicts on nodes; bind `get`/`patch` on nodes for the listed service accounts |
| `nodeGate.*` | off | the alternative below |

## The alternative: a node gate

With `nodeGate.enabled=true` (and usually `inject.enabled=false`), the
chart runs the check in a DaemonSet of its own, which never touches the
device plugin. GPU nodes join with the taint `gpu-health/pending:NoSchedule`
(set in the node group's or NodePool's taints, or with the kubelet's
`--register-with-taints`). The DaemonSet tolerates that taint and the GPU
taints and checks the node. On a pass it labels the node and lifts the
taint. On a failure it keeps the taint and labels the node `fail`. Use it
where the device plugin's pods must not be modified, or where you want the
taint as the signal. A node without the taint is never loaded again.

## Limits

- **What the check covers.** It checks the SMs' integer datapath and
  throughput, not tensor cores, HBM or interconnect. See
  [what it establishes](../../gpu-health/README.md#is-this-a-good-way-to-check-a-gpus-health).
- **MIG.** On a node with MIG enabled, CUDA lets one process use only one
  MIG device, so the check reaches one slice, and says so.
- **Admission policies.** Other admission controllers see the injected
  container: a MutatingAdmissionPolicy runs before validation. A policy
  engine that forbids privileged containers or hostPath volumes needs the
  same exemption for the check as for the device plugin.
- **Upgrades.** Injection depends on the device plugin's container names.
  After an upgrade of the GPU Operator or the plugin chart, confirm that new
  plugin pods still list `gpu-health` among their init containers.

## Tests

- `tests/test_admission.py` runs the policy on a real kube-apiserver and
  etcd (the Kubernetes envtest binaries; no kubelet). The server type-checks
  every expression. A GPU Operator plugin pod gets the check after its own
  init containers. A standalone plugin pod, which has no init containers or
  volumes, gets both lists created. Other pods, other namespaces and a pod
  that already has the check come back unchanged. Values reach the pod. The
  API version follows the cluster.
- `tests/e2e/run.sh` runs on kind, with the real image and the scripted
  stand-ins for `ec2k-gpu` and nvidia-smi, so no GPU is needed. It checks
  that the plugin starts only after the check has passed, and that a
  restart in the same boot skips the load. After a reboot the check runs
  again, and a failure holds the plugin back and says why. It also covers
  the busy guard and a node that was in service before the check reached
  it. CI runs both in `.github/workflows/gpu-health.yml`.

No GPU is involved in any of this. Whether the check itself tells a good
GPU from a bad one is the question
[the check's README](../../gpu-health/README.md) takes up.
