#!/usr/bin/env bash
# Build the model, generate its vectors, and run every testbench against them.
#
#   scripts/run_sim.sh [DIGIT] [DP_WEIGHT] [CASES]
#
# The distinguished-point weight defaults to 60 rather than the campaign's 34
# for one reason: at 34 a point turns up about once in 2^25 steps, so a
# simulation would run for days before exercising the path that reports one.
# The cutoff is a parameter of both the model and the RTL, so both sides are
# still comparing the same rule -- what changes is how often the rule fires.
set -euo pipefail

digit=${1:-4}
dpw=${2:-60}
cases=${3:-64}

here=$(cd "$(dirname "$0")/.." && pwd)
build=${BUILD:-$here/build}
vec=$build/vec
mkdir -p "$build" "$vec"

cc=${CC:-cc}
$cc -O2 -std=c11 -Wall -Wextra -o "$build/ec2k_test" "$here/model/ecc2k130.c" \
    "$here/model/ecc2k130_test.c"
$cc -O2 -std=c11 -Wall -Wextra -o "$build/gen_vectors" "$here/model/ecc2k130.c" \
    "$here/model/gen_vectors.c"
$cc -O2 -std=c11 -Wall -Wextra -o "$build/ec2k" "$here/model/ecc2k130.c" \
    "$here/host/ec2k_tool.c"

echo "== model self-test"
"$build/ec2k_test"

echo "== vectors (dp weight $dpw)"
"$build/gen_vectors" "$vec" "$cases" "$dpw"

rtl=("$here"/rtl/*.v)
run_tb() {
    local name=$1 vecfile=$2
    local exe="$build/$name"
    iverilog -g2012 -DTB_DIGIT="$digit" -DTB_DPW="$dpw" -I "$here/rtl" \
        -o "$exe" "${rtl[@]}" "$here/tb/$name.v"
    "$exe" +vec="$vec/$vecfile"
}

echo "== testbenches (DIGIT=$digit)"
run_tb tb_onb131_mul   mul.vec
run_tb tb_onb131_inv   inv.vec
run_tb tb_ecc2k130_step  step.vec
run_tb tb_ecc2k130_core  chain.vec
run_tb tb_ecc2k130_top   step.vec

echo "== host tooling"
"$build/ec2k" start --seed 7 >/dev/null
"$build/ec2k" walk --seed 7 --steps 4000 --dp-weight "$dpw" --out "$build/walk7.bin" >/dev/null
"$build/ec2k" verify --seed 7 --steps 4000 --dp-weight "$dpw" "$build/walk7.bin"
# A record from a different walk must not verify against this seed: the
# check has to be able to fail, or it is not a check.
"$build/ec2k" walk --seed 8 --steps 4000 --dp-weight "$dpw" --out "$build/walk8.bin" >/dev/null
if "$build/ec2k" verify --seed 7 --steps 4000 --dp-weight "$dpw" "$build/walk8.bin" >/dev/null 2>&1; then
    echo "FAIL: verify accepted records from another walk" >&2
    exit 1
fi
"$build/ec2k" merge "$build/walk7.bin" "$build/walk8.bin"
echo "all simulations passed"
