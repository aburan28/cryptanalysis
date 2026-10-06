#!/bin/sh
# run_paired.sh - paired reference/fast measurements behind RESULT.md.
#
#   experiments/f4-gpu-20260925/run_paired.sh [SUITE_DIR]
#
# Both arms run the same ca-ic / groebner_stage_bench binaries; the arm is
# selected by F4_F2_RREF (reference = the kernel this repository shipped
# with, unset = f4_gf2 with F5).  Blocks alternate the arm order, one CPU,
# nothing else running.  Every raw report is kept under receipts/.
set -eu

HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
SUITE=${1:-"$HERE/../../suite"}
IC="$SUITE/target/release/ca-ic"
BENCH="$SUITE/target/release/examples/groebner_stage_bench"
OUT="$HERE/receipts"
mkdir -p "$OUT/e2e" "$OUT/stage"

run_e2e() { # arm degree curve_a block
    file="$OUT/e2e/k$3-n$2-$1-block$4.json"
    [ -e "$file" ] && return 0
    if [ "$1" = reference ]; then
        F4_F2_RREF=reference taskset -c 0 "$IC" run --degree "$2" --curve-a "$3" \
            --solver groebner --batch 1 --json >"$file"
    else
        taskset -c 0 "$IC" run --degree "$2" --curve-a "$3" \
            --solver groebner --batch 1 --json >"$file"
    fi
    echo "e2e $1 K_$3/2^$2 block $4 done"
}

for block in 1 2 3; do
    for spec in "23 1" "23 0"; do
        # shellcheck disable=SC2086 # split "degree curve_a" on purpose
        set -- $spec
        if [ $((block % 2)) -eq 1 ]; then
            run_e2e reference "$1" "$2" "$block"
            run_e2e fast "$1" "$2" "$block"
        else
            run_e2e fast "$1" "$2" "$block"
            run_e2e reference "$1" "$2" "$block"
        fi
    done
done

for rep in 1 2 3; do
    if [ $((rep % 2)) -eq 1 ]; then order="reference fast"; else order="fast reference"; fi
    for k in $order; do
        dir="$OUT/stage/$k-rep$rep"
        [ -e "$dir/stage.json" ] && continue
        if [ "$k" = reference ]; then
            F4_F2_RREF=reference taskset -c 0 "$BENCH" --label "$k" --out "$dir" >/dev/null
        else
            taskset -c 0 "$BENCH" --label "$k" --out "$dir" >/dev/null
        fi
        echo "stage $k rep $rep done"
    done
done
echo PAIRED_DONE
