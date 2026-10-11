#!/usr/bin/env bash
# run.sh - the chart against a real API server: kind, Kubernetes 1.36+, no GPU.
#
#   deploy/helm/gpu-health/tests/e2e/run.sh [BASE_IMAGE]   (default gpu-health:ci)
#
# Builds a test image from BASE_IMAGE, the image deploy/gpu-health/Dockerfile
# builds, plus the scripted ec2k-gpu and nvidia-smi of
# deploy/gpu-health/tests/fakes.  Then it starts a kind cluster, installs the
# chart with the check pointed at those stand-ins, and holds the
# MutatingAdmissionPolicy to what it is for:
#
#   1. a device plugin pod gets the check as its last init container, with the
#      state volume, and the plugin starts only after the check has passed
#   2. the next device plugin pod on the node, in the same boot, skips the load
#   3. pods that are not a device plugin, or not in its namespace, are untouched
#   4. after a reboot the check runs again, and a failure keeps the plugin from
#      starting and says why
#   5. GPUs that already run other processes are not loaded
#   6. a node that was in service before the check reached it is left alone
#
# The node's PCI bus is a stand-in with two NVIDIA GPUs (pci/).  The reboot and
# the node long in service are played with stand-in /proc files (proc/NAME:
# another boot id and uptime); the other steps read the node's own.
# Needs docker, kind, kubectl and helm on PATH.  KIND_NODE picks the node image
# (default kindest/node:v1.37.0); KEEP=1 keeps the cluster afterwards.
set -euo pipefail
cd "$(dirname "$0")/../../../../.."

BASE=${1:-gpu-health:ci}
CLUSTER=gpu-health-e2e
NODE="$CLUSTER-control-plane"
HERE=deploy/helm/gpu-health/tests/e2e
NS=gpu-operator
DS=nvidia-device-plugin-daemonset
WORK=$(mktemp -d "${TMPDIR:-/tmp}/gpu-health-e2e.XXXXXX")

step() { printf '\n== %s\n' "$*"; }
fail() {
    printf 'FAIL: %s\n' "$*" >&2
    kubectl get pods -A -o wide >&2 || true
    kubectl -n "$NS" describe pods -l app="$DS" >&2 || true
    exit 1
}
cleanup() {
    if [ "${KEEP:-0}" != 1 ]; then kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true; fi
    rm -rf "$WORK"
}
trap cleanup EXIT

# The chart's values for one step: its name, a scripted scenario
# (scenarios/NAME.json) and optionally a stand-in /proc (proc/NAME).
values() {
    local step=$1 scenario=$2 proc=${3:-}
    {
        echo "check:"
        echo "  extraEnv:"
        echo "    - {name: GPU_HEALTH_BINARY, value: /fakes/ec2k-gpu}"
        echo "    - {name: GPU_HEALTH_NVIDIA_SMI, value: /fakes/nvidia-smi}"
        echo "    - {name: FAKE_GPU_STATE, value: /tmp}"
        echo "    - {name: GPU_HEALTH_SYSFS_PCI, value: /fakes/pci}"
        echo "    - {name: FAKE_GPU_SCENARIO, value: /fakes/scenarios/$scenario.json}"
        echo "    - {name: E2E_STEP, value: e2e-step-$step}"
        if [ -n "$proc" ]; then
            echo "    - {name: GPU_HEALTH_PROC, value: /fakes/proc/$proc}"
        fi
    } >"$WORK/values-$step.yaml"
    echo "$WORK/values-$step.yaml"
}

# Install or upgrade the chart for a step, and wait until the policy injects
# that step's check into a pod the server admits (server-side dry run:
# admission runs, nothing is stored).  A new or changed policy takes a moment
# to reach the admission chain.
chart() {
    local step=$1 i
    shift
    helm upgrade --install gh deploy/helm/gpu-health -n gpu-health --create-namespace \
        -f "$HERE/values.yaml" -f "$(values "$step" "$@")" "${SET[@]}" --wait >/dev/null
    for i in $(seq 60); do
        if kubectl -n "$NS" run probe --dry-run=server -o json --restart=Never \
            --image=gpu-health:e2e --image-pull-policy=Never \
            --overrides='{"spec":{"containers":[{"name":"nvidia-device-plugin","image":"gpu-health:e2e"}]}}' \
            2>/dev/null | grep -q "\"e2e-step-$step\""; then
            return 0
        fi
        sleep 1
    done
    fail "the policy did not inject step $step's check within 60 s (attempts: $i)"
}

# The device plugin's pod that is not on its way out.
pod() {
    kubectl -n "$NS" get pods -l app="$DS" -o json | python3 -c '
import json, sys
live = [p for p in json.load(sys.stdin)["items"] if not p["metadata"].get("deletionTimestamp")]
print(live[0]["metadata"]["name"] if live else "")'
}

# The check's last non-zero exit: "code<TAB>termination message", or nothing.
check_failure() {
    kubectl -n "$NS" get pod "$1" -o json | python3 -c '
import json, sys
for s in json.load(sys.stdin)["status"].get("initContainerStatuses", []):
    if s["name"] != "gpu-health":
        continue
    for k in ("state", "lastState"):
        t = (s.get(k) or {}).get("terminated")
        if t and t.get("exitCode"):
            print("%d\t%s" % (t["exitCode"], " ".join(t.get("message", "").split())))
            sys.exit(0)'
}

# Replace the device plugin's pod, as a reboot or a rollout would, and print
# the new pod's name.
new_pod() {
    local old i p
    old=$(pod)
    kubectl -n "$NS" delete pod "$old" --wait=true >/dev/null
    for i in $(seq 60); do
        p=$(pod)
        if [ -n "$p" ] && [ "$p" != "$old" ]; then
            echo "$p"
            return 0
        fi
        sleep 1
    done
    fail "no new device plugin pod after deleting $old (waited ${i} s)"
}

init_names() { kubectl -n "$1" get pod "$2" -o jsonpath='{range .spec.initContainers[*]}{.name}{" "}{end}'; }
check_log() { kubectl -n "$NS" logs "$1" -c gpu-health 2>/dev/null || true; }

# The node's record of the boot, as "bootId verdict released attempts".
record() {
    docker exec "$NODE" cat /run/gpu-health/boot.json 2>/dev/null | python3 -c '
import json, sys
try:
    r = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
print(r.get("bootId"), r.get("verdict"), str(r.get("released")).lower(), r.get("attempts"))'
}
boot_of() { docker exec "$NODE" cat "/proc/sys/kernel/random/boot_id"; }
REBOOTED=e2e0rebo-0000-4000-8000-000000000001
UP_FOR_DAYS=e2e0days-0000-4000-8000-000000000002

# Wait for the device plugin's pod to be ready, and print the check's verdict
# line.  Not simply the log's last line: the JSON report goes to stdout and the
# verdict to stderr, and the runtime may interleave the two.
ready() {
    kubectl -n "$NS" wait --for=condition=Ready pod/"$1" --timeout=120s >/dev/null ||
        fail "$2"
    check_log "$1" | grep -E '^\[gpu-health\] (PASS|FAIL|SKIP|ERROR) ' | tail -1
}

step "test image from $BASE"
docker build -q -f "$HERE/Dockerfile" --build-arg BASE="$BASE" -t gpu-health:e2e . >/dev/null

step "kind cluster ${KIND_NODE:-kindest/node:v1.37.0}"
# Kubelets from 1.35 refuse cgroup v1 unless told otherwise; CI runners have
# v2, some development VMs do not.
config=()
if [ "$(stat -fc %T /sys/fs/cgroup)" != cgroup2fs ]; then
    cat >"$WORK/kind.yaml" <<'EOF2'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
kubeadmConfigPatches:
  - |
    kind: KubeletConfiguration
    failCgroupV1: false
EOF2
    config=(--config "$WORK/kind.yaml")
fi
kind create cluster --name "$CLUSTER" --image "${KIND_NODE:-kindest/node:v1.37.0}" "${config[@]}" --wait 180s
kind load docker-image gpu-health:e2e --name "$CLUSTER"
kubectl get --raw /apis/admissionregistration.k8s.io/v1 | grep -q '"mutatingadmissionpolicies"' ||
    fail "the API server does not serve admissionregistration.k8s.io/v1 MutatingAdmissionPolicy"

step "install the chart; stand-in device plugin"
kubectl create namespace "$NS"
SET=()
chart 1 healthy
kubectl apply -f "$HERE/cluster.yaml"

step "1. the check runs last among the init containers, and gates the plugin"
kubectl -n "$NS" rollout status ds/"$DS" --timeout=180s || fail "the device plugin did not become ready"
P=$(pod)
names=$(init_names "$NS" "$P")
[ "$names" = "toolkit-validation gpu-health " ] || fail "init containers are '$names'"
kubectl -n "$NS" get pod "$P" -o jsonpath='{range .spec.volumes[*]}{.name}={.hostPath.path}{" "}{end}' |
    grep -q "gpu-health-state=/run/gpu-health" || fail "no gpu-health-state hostPath volume"
log=$(check_log "$P")
grep -q "PASS 2/2 GPU(s) healthy" <<<"$log" || fail "no pass in the check's log: $log"
rec=$(record)
[[ "$rec" == "$(boot_of) pass true "* ]] || fail "the node's record is '$rec'"
started=$(kubectl -n "$NS" get pod "$P" -o jsonpath='{.status.containerStatuses[0].state.running.startedAt}')
checked=$(kubectl -n "$NS" get pod "$P" \
    -o jsonpath='{.status.initContainerStatuses[?(@.name=="gpu-health")].state.terminated.finishedAt}')
if [ -z "$started" ] || [ -z "$checked" ] || [[ "$started" < "$checked" ]]; then
    fail "the plugin started ($started) before the check finished ($checked)"
fi
echo "ok: $names; check finished $checked, plugin started $started; record: $rec"

step "2. the same boot skips the load"
P=$(new_pod)
line=$(ready "$P" "the replacement pod did not become ready")
grep -q "SKIP passed this boot" <<<"$line" || fail "the replacement did not skip: $(check_log "$P")"
[ "$(record)" = "$rec" ] || fail "a skip changed the record to '$(record)'"
echo "ok: $line"

step "3. other pods are untouched"
for p in "$NS not-a-device-plugin" "default device-plugin-elsewhere"; do
    read -r ns name <<<"$p"
    kubectl -n "$ns" wait --for=condition=Ready pod/"$name" --timeout=120s >/dev/null
    names=$(init_names "$ns" "$name")
    [ -z "$names" ] || fail "$ns/$name was injected: '$names'"
    echo "ok: $ns/$name has no init containers"
done

step "4. after a reboot the check runs again; a failure keeps the plugin from starting"
chart 4 corrupt rebooted
P=$(new_pod)
failure=""
for _ in $(seq 120); do
    failure=$(check_failure "$P")
    [ -n "$failure" ] && break
    sleep 1
done
code=${failure%%$'\t'*}
msg=${failure#*$'\t'}
[ "$code" = 1 ] || fail "the failing check exited '$code', not 1 ($failure)"
running=$(kubectl -n "$NS" get pod "$P" -o jsonpath='{.status.containerStatuses[0].state.running}')
[ -z "$running" ] || fail "the plugin is running although its GPUs failed"
grep -q "silent data corruption" <<<"$msg" || fail "termination message: $msg"
# The kubelet retries the check after a backoff; the record may already say so.
rec=$(record)
[[ "$rec" =~ ^$REBOOTED\ (fail|running)\ false\  ]] || fail "the node's record is '$rec'"
echo "ok: plugin held back; $msg"

step "5. GPUs in use are left alone"
chart 5 busy rebooted
P=$(new_pod)
line=$(ready "$P" "the plugin did not start on a node whose GPUs are in use")
grep -q "SKIP 1 of 2 GPU(s) are running other processes" <<<"$line" ||
    fail "no busy skip: $(check_log "$P")"
rec=$(record)
[[ "$rec" == "$REBOOTED skip true "* ]] || fail "the node's record is '$rec'"
echo "ok: $line"

step "6. a node that was in service before the check reached it is left alone"
SET=(--set check.maxUptimeSeconds=3600)
chart 6 corrupt up-for-days
P=$(new_pod)
line=$(ready "$P" "the plugin did not start on a node long in service")
grep -q "SKIP no check has run since this node booted 10 d 0 h ago" <<<"$line" ||
    fail "no uptime skip: $(check_log "$P")"
rec=$(record)
[ "$rec" = "$UP_FOR_DAYS skip true 0" ] || fail "the node's record is '$rec'"
echo "ok: $line"

printf '\nall end-to-end checks passed\n'
