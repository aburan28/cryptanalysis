# Deferred provenance: audited initial result

The initial deferred-provenance implementation is correct on the retained
controls but has no qualified complete-query speedup on the 27-variable
frontier. Keep round35 as the accepted implementation while testing narrower
code-generation changes. Lower logical operation counts did not by themselves
produce a wall-time improvement.

These are frozen planted PDP component queries, not complete IC runs or natural
relation-yield measurements. Candidate, IC and rho fields remain null. The
timed interval includes fresh packed descent, solving, proof generation/copy/hash,
independent basis certification, original-equation checks and curve replay.
Fixture construction, invariant workspace setup and extra offline auditing are
separate. No numerical pivots or target answers are reused between queries.

## Physical timing evidence

Four complete trials on the physical Apple M4 Pro retain 8,640 verified query
records, including warmups. Both small trials and the second wide trial satisfy
the predeclared load bound of 14. The first wide trial reaches a one-minute load
of 28.474 and is ineligible; its 576 query records remain evidence, not wins.
The second wide trial has seven measured pairs and one warmup per control.

| 27-variable control | Previous symmetry CPU median | Initial deferred CPU median | Paired previous/deferred geometric ratio, bootstrap 95% interval |
| --- | ---: | ---: | ---: |
| seed201 | 840.792 ms | 851.783 ms | 1.029 [0.968, 1.115] |
| seed202 | 820.299 ms | 836.183 ms | 1.018 [0.961, 1.110] |
| seed203 | 824.479 ms | 834.585 ms | 0.981 [0.966, 0.993] |

The median and paired-geometric statistics answer different questions; retained
outliers make the first two geometric ratios exceed one despite slower medians.
Neither interval establishes a win. The third control establishes a regression
in this trial. No small-control CPU improvement repeats consistently across
both trials. Do not select individual favorable rows as a promotion claim.

For seed203, forward counted word operations decrease from 323,125,075 to
99,423,100, with a further 3,463,212 reconstruction XORs and 1,477,999 source-bit
toggles. Dependency toggles are already a subcount of forward word operations.
The same 24,855,775 coefficient-row reductions and 3,089,715 generated rows
remain. Reconstruction takes about 8.35 ms; the complete affine phase takes
about 546.26 ms versus 535.16 ms previously. These nested phase medians do not
sum to the complete-query median. CPU full wire proofs match the previous producer
byte for byte throughout all four trials.

The multiplier workspace decreases from 12,338 to 10,778 counted bytes on this
control. The 3,640-byte dependency/source storage is already included in the
new total, not additional memory. These are native allocation counts, not RSS.

## Correctness and independent audit

All 37 local test groups pass: 24 core, three independent-reference, nine audit,
and one complete-query group. They include physical Metal, portable CPU, UBSan,
equation widths through 128 bits, all 256 three-variable Boolean functions,
full proof equality, malformed evidence, workspace reuse, and forced budget
fallback. Deferred affine work remains CPU code; 24/27-variable requested Metal
explicitly falls back to CPU. This experiment establishes no wider GPU speedup.

Independent offline audits pass all four timing reports and both retained
correctness bundles. The latter contain 351 small and 216 wide query records.
The audit reconstructs original ANF identities and complete roots, checks bases
and curve witnesses, reproduces integer work counts and capacity growth, binds
source/build receipts, and reconstructs each report from its hash-chained
journal. Offline audit caches are keyed by full immutable evidence and are
never part of timed solving.

The complete external evidence is retained under
`/Volumes/SSD990/.codex/visualizations/2026/09/24/01a0d426-e9d3-7723-9d49-8cde022ba931/deferred-affine-proof/`:
`performance-v1/`, `performance-audits.json`, `phase-diagnostics.json`, source
and build records, test logs, and the reproduced correctness bundles.

## Next bounded experiment

Keep this measured source frozen. In a separate CPU pilot, compare fixed
one/two/three-word coefficient loops, packed source indices, and complete
residual-shape specialization against both existing producers. Require exact
proof, root, basis and work-count agreement before timing. Source-index packing
uses the validated equation range 1..128, not an unchecked bit-width assumption.
Measure complete queries before selecting a candidate for the full harness.
Pilot timing alone is insufficient for promotion, broad GPU claims, or a PR
asserting a confirmed improvement.

The completed exploratory pilot tests six code-generation variants against both
existing producers. All 1,968 UBSan comparisons preserve complete proof bytes,
roots, bases and integer counts. Both 144-query trials pass comparison to the
independently audited original-ANF/proof evidence. Only the first trial passes
the unchanged load gate (maximum 10.769); the second reaches 19.388 and is
ineligible. In the eligible trial, fixed-width deferred CPU medians are
764.915, 776.303 and 785.530 ms versus 813.953, 810.031 and 832.768 ms for
the paired round35 CPU. Its five-pair geometric ratios are 1.082, 1.044 and
1.084; the middle interval includes one. These exploratory results justify
full-harness follow-up, not promotion or a repeated qualified speedup claim.
Source-index packing alone does not show a useful improvement, and specializing
the entire residual shape is less effective than fixing coefficient-row width.
The archived `kernel-pilot/` contains all six sources, build receipts, binaries,
test logs, plans, reports and integrity checks.

For the structural F6 question, all nine original 21/24/27-variable ANFs have
complete variable-interaction graphs when every polynomial's full support
forms a clique. Their exact graph treewidths are 20, 23 and 26. Direct small-
separator elimination therefore has no sparsity advantage in this encoding.
[Cifuentes and Parrilo's chordal elimination](https://arxiv.org/abs/1411.1745)
is relevant prior work; a new proposal must first demonstrate a useful
reformulation and charge its construction, exceptional branches and certificate
costs. This diagnostic does not rule out reformulations or establish a general
lower bound on solving these systems.
