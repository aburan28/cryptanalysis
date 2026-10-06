#!/usr/bin/env bash
#
# Campaign rehearsal on a curve small enough to finish in seconds.
#
# The ECC2K-95 run is many container-hours, and the parts that only matter at
# the end -- a collision spanning two workers' corpora, and recovering k from
# it -- are exactly the parts a short test never reaches.  This drives the whole
# shape on a small curve: several workers with disjoint seed spaces, one of them
# stopped and resumed from its checkpoint, and a merge that has to find the
# collision across files because no single worker holds both halves.
#
# The useful budget is a narrow window.  Too much work per worker and one solves
# alone, which exercises nothing; too little and the union holds no collision.
# Where the window sits is random, so try a few budgets rather than reporting a
# pass or a failure that is really just the draw.

set -euo pipefail
cd "$(dirname "$0")"

CURVE=${CURVE:-41}
WORKERS=${WORKERS:-4}
DIR=${DIR:-$(mktemp -d)}
CLIENT=./ecc2k130-cpu
STEPLIST=${STEPLIST:-"6 5 7 4 8 3"}

[ -x "$CLIENT" ] || { echo "build first: make cpu" >&2; exit 1; }
mkdir -p "$DIR"
echo "rehearsal: curve $CURVE, $WORKERS workers, budgets [$STEPLIST], in $DIR"

for STEPS in $STEPLIST; do
    rm -f "$DIR"/*.bin "$DIR"/*.ck
    solo=0
    for i in $(seq 1 "$WORKERS"); do
        out=$($CLIENT --curve "$CURVE" --threads 2 --steps "$STEPS" --launches 1 \
                      --verify 0 --run-id "$i" --dp-file "$DIR/w$i.bin" \
                      --checkpoint "$DIR/w$i.ck" 2>&1)
        if echo "$out" | grep -q "verified \[k\]P == Q"; then solo=1; break; fi
    done
    if [ "$solo" = "1" ]; then
        echo "  steps=$STEPS: a worker solved alone, too much work per worker"
        continue
    fi

    res=$($CLIENT --curve "$CURVE" --threads 2 --steps "$STEPS" --launches 1 --verify 0 \
                  --run-id 1 --dp-file "$DIR/w1.bin" --checkpoint "$DIR/w1.ck" 2>&1)
    echo "$res" | grep -q "resumed from" || { echo "RESUME FAILED"; echo "$res" | head -3; exit 1; }

    loads=""
    for i in $(seq 1 "$WORKERS"); do loads="$loads --load $DIR/w$i.bin"; done
    merged=$($CLIENT --curve "$CURVE" --threads 1 --steps 1 --launches 1 --verify 0 \
                     --run-id 65535 $loads 2>&1)
    if echo "$merged" | grep -q "verified \[k\]P == Q"; then
        pts=0
        for i in $(seq 1 "$WORKERS"); do
            pts=$(( pts + $(stat -c%s "$DIR/w$i.bin") / 32 ))
        done
        echo "  steps=$STEPS: $WORKERS workers, $pts points, none solved alone"
        echo "  worker 1 resumed from its checkpoint"
        echo "$merged" | grep -E "reloaded|collision found" | sed 's/^/  /'
        echo "  $(echo "$merged" | grep 'k = ' | head -1 | sed 's/^ *//')"
        echo "REHEARSAL PASSED: cross-corpus collision recovered and verified"
        exit 0
    fi
    echo "  steps=$STEPS: none solved alone, but no collision spanned the corpora"
done
echo "REHEARSAL INCONCLUSIVE: no budget in [$STEPLIST] hit the window" >&2
exit 3
