#!/usr/bin/env bash
# Pull the latest main (or REF) on a RunPod and build the GLV/faster-rho stack
# with CUDA when nvcc is available.
#
# Required: RUNPOD_API_KEY
# Optional: POD_NAME (default solar_ivory_canidae), REF (default origin/main),
#           SSH_KEY
set -euo pipefail

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY is required}"
POD_NAME="${POD_NAME:-solar_ivory_canidae}"
REF="${REF:-origin/main}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
REPO_DIR="${REPO_DIR:-/root/cryptanalysis}"
export PATH="${HOME}/.local/bin:${PATH}"

command -v runpodctl >/dev/null || {
  echo "runpodctl required" >&2
  exit 1
}
[[ -f "$SSH_KEY" ]] || { echo "missing $SSH_KEY" >&2; exit 1; }

POD_JSON="$(runpodctl pod list --name "$POD_NAME" -o json)"
POD_ID="$(POD_JSON="$POD_JSON" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["POD_JSON"])
pods = data if isinstance(data, list) else data.get("pods") or []
if not pods:
    sys.exit("no running pod with that name")
print(pods[0]["id"])
PY
)"
INFO_JSON="$(runpodctl ssh info "$POD_ID" -o json)"
SSH_HOST=""
SSH_PORT=""
SSH_USER=""
eval "$(INFO_JSON="$INFO_JSON" python3 - <<'PY'
import json, os, shlex
info = json.loads(os.environ["INFO_JSON"])
print(f"SSH_HOST={shlex.quote(str(info.get('ip') or ''))}")
print(f"SSH_PORT={shlex.quote(str(info.get('port') or 22))}")
print(f"SSH_USER={shlex.quote(str(info.get('user') or 'root'))}")
PY
)"

ssh -i "$SSH_KEY" -p "$SSH_PORT" \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="${HOME}/.ssh/known_hosts_runpod" \
  -o IdentitiesOnly=yes -o BatchMode=yes \
  "${SSH_USER}@${SSH_HOST}" \
  env REF="$REF" REPO_DIR="$REPO_DIR" bash -s <<'EOS'
set -euo pipefail
export PATH="/usr/local/cuda/bin:${HOME}/.local/bin:${PATH}"
export DEBIAN_FRONTEND=noninteractive
command -v cmake >/dev/null || { apt-get update -qq && apt-get install -y -qq cmake g++ ninja-build pkg-config; }
command -v ninja >/dev/null || apt-get install -y -qq ninja-build
cd "$REPO_DIR"
git -c core.filemode=false fetch --prune origin
git -c core.filemode=false checkout -B deploy "$REF"
git -c core.filemode=false reset --hard "$REF"
git log -1 --oneline
CUDA_FLAG=OFF
command -v nvcc >/dev/null && CUDA_FLAG=ON
rm -rf build
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCA_NATIVE=ON \
  -DCA_CUDA="$CUDA_FLAG" -DCA_BUILD_TOOLS=ON -DCA_BUILD_TESTS=ON
cmake --build build -j"$(nproc)"
export LD_LIBRARY_PATH="$REPO_DIR/build:${LD_LIBRARY_PATH:-}"
./build/ca curve --name glv-j0-26
./build/ca_bench glv | tee /tmp/ca_bench_glv.txt
ctest --test-dir build -R 'curve|rho|precomp|gpu' --output-on-failure
echo "deployed $(git rev-parse --short HEAD) CA_CUDA=$CUDA_FLAG"
EOS
