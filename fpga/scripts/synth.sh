#!/usr/bin/env bash
# Synthesise the core with yosys and report what it costs.
#
#   scripts/synth.sh [CORES] [DIGIT]
#
# What this is: a technology-independent synthesis followed by a mapping to
# 4-input LUTs, which gives a defensible count of logic elements and flip
# flops and lets the DIGIT sweep be compared against itself.
#
# What this is NOT: a vendor place-and-route.  There is no timing here, no
# fmax, no routing congestion, and no device utilisation percentage -- those
# need Vivado or Quartus and a real part, and any number quoted without them
# is a guess.  The LUT4 count is a lower bound on a real FPGA's usage, not an
# estimate of it.
set -euo pipefail

cores=${1:-1}
digit=${2:-4}
here=$(cd "$(dirname "$0")/.." && pwd)
out=${OUT:-$here/build/synth}
mkdir -p "$out"

cat > "$out/synth.ys" <<YS
read_verilog -sv -I$here/rtl $here/rtl/onb131_frob.v $here/rtl/onb131_frob_j.v \
    $here/rtl/onb131_mul.v $here/rtl/onb131_inv.v $here/rtl/ecc2k130_step.v \
    $here/rtl/ecc2k130_core.v $here/rtl/ecc2k130_top.v
chparam -set CORES $cores -set DIGIT $digit ecc2k130_top
hierarchy -top ecc2k130_top
proc; opt; fsm; opt; memory; opt
techmap; opt
abc -lut 4
opt_clean
stat -width
YS

yosys -q -l "$out/synth-c${cores}-d${digit}.log" "$out/synth.ys" || {
    tail -40 "$out/synth-c${cores}-d${digit}.log" >&2
    exit 1
}
sed -n '/Printing statistics/,$p' "$out/synth-c${cores}-d${digit}.log"
