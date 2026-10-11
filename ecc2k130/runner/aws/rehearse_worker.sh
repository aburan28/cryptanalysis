#!/usr/bin/env bash
#
# Rehearse worker.py without AWS: a directory stands in for S3 and DynamoDB,
# the host client stands in for the GPU client.  Two scenarios:
#
#   resume  curve 83 (hours to solve, so it will not): run, SIGTERM, check the
#           store holds a checkpoint and point deltas and the slot was released,
#           run again on the same slot and require "resumed from".
#   solve   curve 41 (seconds to solve): run until the client prints k, require
#           solution.json in the store and the slot marked solved.
#
#   ./rehearse_worker.sh

set -euo pipefail
cd "$(dirname "$0")"
CLIENT=${CLIENT:-$PWD/../ecc2k130-cpu}
[ -x "$CLIENT" ] || { echo "build the host client first: (cd .. && make cpu)" >&2; exit 1; }
BASE=${BASE:-$(mktemp -d)}
mkdir -p "$BASE"
echo "rehearsal in $BASE"

config() {  # curve steps checkpointEvery
    python3 - "$1" "$2" "$3" > "$STORE/campaign.json" <<'EOF'
import json, sys
curve, steps, every = sys.argv[1:]
print(json.dumps({"curve": int(curve), "packed": False, "workers": 2, "steps": int(steps),
                  "checkpointEvery": float(every), "uploadEvery": 2, "verify": 0, "dpWeight": -1,
                  "loadMax": 100000, "restartHours": 0, "binaryKey": "local"}))
EOF
}

runWorker() {  # seconds-before-SIGTERM (0 = wait for exit) logfile
    ECC_LOCAL_STORE="$STORE" ECC_ROOT="$ROOT" ECC_CLIENT="$CLIENT" ECC_GPU=0 \
        python3 worker.py > "$2" 2>&1 &
    local pid=$!
    if [ "$1" -gt 0 ]; then
        sleep "$1"
        kill -TERM "$pid"
    fi
    wait "$pid" || { echo "worker exited $? -- log:"; cat "$2"; exit 1; }
}

# ---- resume ------------------------------------------------------------------
STORE=$BASE/store-resume; ROOT=$BASE/root-resume; mkdir -p "$STORE" "$ROOT"
config 83 8 1
runWorker 6 "$BASE/run1.log"
grep -q "claimed slot 0" "$BASE/run1.log" || { echo "FAIL: no slot claim"; cat "$BASE/run1.log"; exit 1; }
[ -s "$STORE/ckpt/slot-00000.ck" ] || { echo "FAIL: no checkpoint in the store"; ls -R "$STORE"; exit 1; }
n=$(ls "$STORE/dp/slot-00000/" 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -ge 1 ] || { echo "FAIL: no point deltas uploaded"; ls -R "$STORE"; exit 1; }
python3 -c "
import json,sys; s=json.load(open('$STORE/slots.json'))['0']; sys.exit(0 if s['leaseUntil']==0 and s['state']=='idle' else 1)" \
    || { echo "FAIL: slot not released"; cat "$STORE/slots.json"; exit 1; }
# Every uploaded byte is whole records, and no record was uploaded twice.
python3 - "$STORE/dp/slot-00000" "$ROOT/gpu0/dp.bin" <<'EOF' || exit 1
import hashlib, os, sys
d, local = sys.argv[1:]
parts = sorted(os.listdir(d), key=lambda name: int(name.rsplit("-", 2)[1]))
total = sum(os.path.getsize(os.path.join(d, p)) for p in parts)
assert all(os.path.getsize(os.path.join(d, p)) % 32 == 0 for p in parts), "partial record uploaded"
size = os.path.getsize(local)
assert total == size - size % 32, "uploaded %d bytes but local file holds %d" % (total, size)
chunks = []
offset = 0
for name in parts:
    digest, start, end = name[:-4].rsplit("-", 2)
    data = open(os.path.join(d, name), "rb").read()
    assert int(start) == offset and int(end) == offset + len(data), "gap or overlap in deltas"
    assert hashlib.sha256(data).hexdigest() == digest, "delta digest mismatch"
    chunks.append(data)
    offset = int(end)
up = b"".join(chunks)
assert up == open(local, "rb").read()[:len(up)], "uploaded bytes differ from the local file"
print("  %d deltas, %d records uploaded, byte-identical to the local corpus" % (len(parts), total // 32))
EOF
first=$(python3 -c "
import struct; d=open('$STORE/ckpt/slot-00000.ck','rb').read(40); print(struct.unpack_from('<Q', d, 32)[0])")
echo "  first run: checkpoint in store at iteration $first, slot released"
runWorker 6 "$BASE/run2.log"
grep -q "resumed from" "$BASE/run2.log" || { echo "FAIL: second run did not resume"; cat "$BASE/run2.log"; exit 1; }
grep -q "claimed slot 0" "$BASE/run2.log" || { echo "FAIL: second run took a different slot"; exit 1; }
second=$(python3 -c "
import struct; d=open('$STORE/ckpt/slot-00000.ck','rb').read(40); print(struct.unpack_from('<Q', d, 32)[0])")
[ "$second" -gt "$first" ] || { echo "FAIL: checkpoint did not advance ($first -> $second)"; exit 1; }
echo "  second run: resumed slot 0, checkpoint advanced $first -> $second"
# A stale local checkpoint must lose to a newer one in the store.
rm -rf "$ROOT"; mkdir -p "$ROOT"
runWorker 4 "$BASE/run3.log"
grep -q "downloaded checkpoint at iteration $second" "$BASE/run3.log" || { echo "FAIL: fresh instance did not download the store checkpoint"; cat "$BASE/run3.log"; exit 1; }
grep -q "resumed from" "$BASE/run3.log" || { echo "FAIL: fresh instance did not resume"; exit 1; }
echo "  fresh work dir: downloaded the store checkpoint and resumed"
echo "RESUME PASSED"

# ---- solve -------------------------------------------------------------------
STORE=$BASE/store-solve; ROOT=$BASE/root-solve; mkdir -p "$STORE" "$ROOT"
config 41 4 1
runWorker 0 "$BASE/solve.log"
grep -q "SOLVED on slot 0" "$BASE/solve.log" || { echo "FAIL: not solved"; cat "$BASE/solve.log"; exit 1; }
[ -s "$STORE/solution.json" ] || { echo "FAIL: no solution.json in store"; exit 1; }
python3 -c "
import json,sys; s=json.load(open('$STORE/slots.json'))['0']; sys.exit(0 if s['state']=='solved' else 1)" \
    || { echo "FAIL: slot not marked solved"; exit 1; }
echo "  $(grep 'SOLVED' "$BASE/solve.log" | head -1)"
# A worker started after the solution must decline to walk.
runWorker 0 "$BASE/after.log"
grep -q "already has a solution" "$BASE/after.log" || { echo "FAIL: worker walked after the solution"; exit 1; }
echo "SOLVE PASSED"
rm -rf "$BASE"
