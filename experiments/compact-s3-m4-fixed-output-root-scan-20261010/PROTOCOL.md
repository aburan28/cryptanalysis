# Q20261010103500: complete fixed-output right-pair root scan

Q1429's three SAT encodings remained bounded with two right leaves free.
For each fixed outer S3 root `v`, this experiment enumerates every
nonzero x coordinate of normal-basis weight at most `w`, computes both
exact roots of `S3(x,v,y)=0`, and retains `y` if it has the same weight
bound. A complete scan decides whether **that one fixed output** has a
weight-bounded right pair. Up to 16 recorded pairs per cell are checked
against the exact curve, subgroup, base, four-point sum, and folded
columns before any relation claim. The scan uses Montgomery inversion
batching and counts
all visited masks, root calls, top-level field operations, conversions,
wall time, peak RSS, and retained pair hits.

The frozen inputs are the known right-pair output and the first
ordinary anchor-0 output from Q1429 at each degree. N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 actual subgroup
points, K=227 signed-Frobenius columns, parent ordinary workload
`74f2979b3e68`. N83 uses `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5,
B=30,977,592/K=186,612, parent ordinary workload `bab50a1e5f66`.
Each new control and ordinary workload ID hashes its exact target,
input law, frozen source receipt, anchor, and fixed output. The raw search
domains contain exactly 24,857 and 30,967,383 nonzero x masks.
The proposal is `Q20261010103500`, with null candidate and run IDs
and `isogeny: "none"` (`ISO0`). The curve/base input policy and
output values stay matched to Q1429.

The batch-window search compares 4,096 and 16,384 x masks per inverse.
Each of the eight cells (two degrees, control/ordinary, two windows)
has a 120-second native scan cap, a 512-MiB peak RSS cap, and records
up to 16 distinct unordered weight-pair hits while counting all hits.
The ordinary output is chosen without a witness. A completed zero-hit
scan proves absence of a weight-bounded right pair for this one output;
it does not rule out other outer roots, lifts, or left anchors. A
bounded scan retains its prefix and cap reason. All binary and input
hashes are frozen before the eight measured runs. The checked Sage
launcher performs independent replay of any recorded pair hits, and
its runtime receipt is saved outside native timing.

This point-decomposition stage remains separate from relation-matrix
construction, final linear algebra, target descent, and scalar replay.
The N131 challenge gate requires a complete work estimate in one
declared unit; the fixed-output scan alone cannot supply it. The
conditional uniform-output root-call screen is reported separately
from measured N53/N83 work and from the Q1422 indexed-pair family. It
uses the exact N131 W≤6 raw mask count `D=6,559,349,863` and folded
column count `K=25,036,774`. For a uniform field-output marginal, each
unordered raw x pair contributes at most two S3 outputs, giving mean
pair hits at most `D(D+1)/2^131` per fixed-output scan. If a pair gives
at most one novel row and all K rows come from complete scans, Markov's
inequality gives a 95%-rank root-call requirement above `2^122.89`.
This is a condition on this complete-scan collector and its output law;
the measurements do not establish that ordinary outer roots have this
law. The fully charged N131 cold and one-target online exponents remain
null until relation yield, rank, final LA, and target descent are measured
in one declared work unit.
