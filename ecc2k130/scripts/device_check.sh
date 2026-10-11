#!/usr/bin/env bash
# device_check.sh - what the host test cannot check: the campaign build on a
# real card.  Run from ecc2k130/ on a machine with an NVIDIA GPU (sm_80+,
# driver for CUDA 13.3).  Prints one JSON line per stage and exits non-zero on
# the first failure.
#
#   1. make test                    the host test, with the campaign's known answers
#   2. make gpu                     the sigma client (fetches CUDA 13.3 if no nvcc)
#   3. make verify                  collect at weight 46 from the challenge
#                                   points; 300 reports re-walked on the model
#   4. stop and resume              one run straight through, one stopped by
#                                   SIGTERM and resumed from its checkpoint:
#                                   the two corpora must hold the same records
#   5. bench                        the sigma build's rate on this card
#
# Stage 4 is the checkpoint's proof.  Lanes are reseeded deterministically and
# a stop lands on a launch boundary, so a resumed run takes exactly the steps
# an uninterrupted one would; if restore dropped or changed any lane state,
# the two sets of records would differ.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK=${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/ec2k-check.XXXXXX")}
ARCH=${ARCH:-}
step() { printf '{"stage":"%s","status":"%s"%s}\n' "$1" "$2" "${3:+,$3}"; }

make test CXX="${CXX:-g++}" >"$WORK/test.log" 2>&1 || { tail -20 "$WORK/test.log"; step test fail; exit 1; }
step test ok "\"detail\":\"$(grep -o 'known answers: [0-9]* of [0-9]*' "$WORK/test.log")\""

if ! command -v "${NVCC:-nvcc}" >/dev/null || ! "${NVCC:-nvcc}" --version | grep -q "release 13\.[3-9]"; then
    NVCC="$(scripts/fetch_cuda.sh)/bin/nvcc"
fi
make gpu NVCC="$NVCC" ${ARCH:+ARCH="$ARCH"} | tee "$WORK/gpu.log"
step gpu ok

make verify >"$WORK/verify.log" 2>&1 || { tail -20 "$WORK/verify.log"; step verify fail; exit 1; }
step verify ok "\"summary\":$(tail -1 "$WORK/verify.log")"

# Weight 40: a point about every 2^18 steps, thousands per launch.  The
# stopped run is signalled once it has printed two progress lines (every 8
# launches), so the signal lands mid-run and after the handler is installed.
STEPS=1024
LAUNCHES=${LAUNCHES:-400}
common=(walk --run-id 4243 --dp-weight 40 --steps "$STEPS" --dp-cap 1048576)
build/ec2k-gpu "${common[@]}" --launches "$LAUNCHES" --dp-file "$WORK/straight.bin" \
    >"$WORK/straight.log" 2>&1
build/ec2k-gpu "${common[@]}" --launches "$LAUNCHES" --dp-file "$WORK/resumed.bin" \
    --checkpoint "$WORK/state.ck" >"$WORK/first.log" 2>&1 &
pid=$!
until (( $(grep -c ' M it/s ' "$WORK/first.log" || true) >= 2 )) || ! kill -0 "$pid" 2>/dev/null; do
    sleep 0.2
done
kill -TERM "$pid" 2>/dev/null || true
wait "$pid" || true
grep -q '"stopped":true' "$WORK/first.log" || { cat "$WORK/first.log"; step resume fail '"why":"the SIGTERM run did not stop cleanly"'; exit 1; }
done1=$(python3 -c "import struct,sys; h=open(sys.argv[1],'rb').read(40); print(struct.unpack_from('<Q',h,32)[0]//int(sys.argv[2]))" "$WORK/state.ck" "$STEPS")
if (( done1 >= LAUNCHES )); then
    step resume fail "\"why\":\"the first run finished all $LAUNCHES launches before the signal; lengthen it\""
    exit 1
fi
build/ec2k-gpu "${common[@]}" --launches $((LAUNCHES - done1)) --dp-file "$WORK/resumed.bin" \
    --checkpoint "$WORK/state.ck" >"$WORK/second.log" 2>&1
grep -q "resumed from" "$WORK/second.log" || { cat "$WORK/second.log"; step resume fail '"why":"did not resume"'; exit 1; }
python3 - "$WORK/straight.bin" "$WORK/resumed.bin" "$done1" "$LAUNCHES" <<'PY'
import sys
def records(path):
    b = open(path, 'rb').read()
    assert len(b) % 32 == 0, path + " is not whole 32-byte records"
    return sorted(b[i:i + 32] for i in range(0, len(b), 32))
a, b = records(sys.argv[1]), records(sys.argv[2])
ok = a == b and len(a) > 0 and all(int.from_bytes(r[:8], 'little') >> 48 == 4243 for r in a)
print('{"stage":"resume","status":"%s","straight":%d,"resumed":%d,"stoppedAfterLaunch":%s,"launches":%s}'
      % ("ok" if ok else "fail", len(a), len(b), sys.argv[3], sys.argv[4]))
sys.exit(0 if ok else 1)
PY

build/ec2k-gpu bench --steps 1024 --launches 64 >"$WORK/bench.log" 2>&1
step bench ok "\"summary\":$(tail -1 "$WORK/bench.log")"
echo "logs: $WORK"
