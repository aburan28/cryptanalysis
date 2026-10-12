# Q1513: one-link S3 handoff measures exact second-pair search at N53 and N83

Fixing a verified first pair reduces four-summand point decomposition to one
factored S3 link, `S3(x3,x4,x(T-P1-P2))=0`. The new runner builds the two
remaining factor-base leaves directly. At N53 it selects x from the exact
227 canonical signed-Frobenius columns; at N83 it encodes the exact
cofactor-four, weight-at-most-five raw-x construction. Boolean assignments
are checked against every CNF and native-XOR row, then replayed by field and
curve arithmetic. The planted controls pass at both degrees.

This retrospective exploratory stage proposal is `Q1513`, `PDP4sat`,
`isogeny: "none"`, with null candidate and run IDs. The exact N53 curve is
`EC1N53Ckb1hf77aab617904`, B=24,062, K=227, base digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Its subgroup cofactor is 428. The N83 curve is
`EC1N83Ckb1h876c2921cb64`, B=30,977,592, K=186,612, base digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Its subgroup cofactor is 4. The [protocol](protocol.json) identifies the
frozen base sources, first pairs, selected and holdout public workloads, and
solver caps. The protocol and results were published together, so the runs
are exploratory and cannot support a tuned speedup claim.

| Fixed complement | Formula variables / CNF / XOR | CryptoMiniSat outcome | Charged solver wall, exploratory | Peak child RSS | Reported conflicts |
| --- | ---: | --- | ---: | ---: | ---: |
| N53 generator, base indices 17880 and 23519 | 4,246 / 15,144 / 365 | INDETERMINATE | 45.58 s | unavailable | 633,438 |
| N53 generator, base indices 14 and 4689 | 4,246 / 15,144 / 365 | INDETERMINATE | 10.72 s | 148,324,352 B | 691,547 |
| N53 known relation complement, unpinned | 4,246 / 15,144 / 365 | WALL_TIMEOUT | 25.11 s | 83,443,712 B | unavailable |
| N53 known relation complement, projected leaves pinned | 4,246 / 15,250 / 365 | SAT, independently verified | 0.065 s | unavailable | 2,619 |
| N83 selected, workload `2eb250a29072` | 43,566 / 125,716 / 1,247 | INDETERMINATE | 11.50 s | 208,207,872 B | 278,466 |
| N83 holdout, workload `394256b9f901` | 43,566 / 125,716 / 1,247 | INDETERMINATE | 11.49 s | 250,101,760 B | 263,105 |
| N83 planted raw x masks 3 and 9 pinned | 43,566 / 125,882 / 1,247 | SAT, independently verified | 1.08 s | unavailable | 2,987 |

A bounded N53 polarity sweep held the known-satisfiable complement and
formula hash `7644b17ed952` fixed. `--polar false` reached 384,611 conflicts
and `--polar true` reached 400,900 conflicts in their respective ten-second
caps; both returned `INDETERMINATE`. The first exploratory spelling,
`--polar 1`, was rejected before search with `unknown polarity-mode` and is
preserved as `SOLVER_FAILURE`. No polarity setting produced an unpinned
relation within these caps, so conflicts per cap do not rank the settings by
cost to a successful relation.

The ordinary N53 generator complements are reconstructed from the archived
base binary and its SHA-256 receipt. The N83 complements are reconstructed
from Q1501's signed first-pair receipts; their full curve coordinates pass
`onCurve`. Each N83 selected/holdout run used a 10-second solver time cap and
25-second outer wall cap. The first N53 run preceded the outer cap and took
45.58 wall seconds under contention; its solver returned `INDETERMINATE`.
The N53 known-satisfiable complement reached the outer wall cap. These
statuses are censored observations, not evidence that a complement has no
matching pair. CPU isolation was not recorded, so wall ratios are exploratory.

The N83 direct handoff has 33.4% fewer variables and 34.0% fewer CNF clauses
than the archived four-leaf transformed XCNF (65,381 variables and 190,568
clauses) on the same base policy. Both encodings retain roughly 1,245 native
XOR rows. This measures encoding size, not solved-query throughput. The
existing N53 quotient-pair run on the same curve, exact base, and generator
collected a full-rank 227-column relation system from 62,741,802 charged
pair additions; the present handoff has no verified ordinary relation within
its caps. The collectors use different first-pair schedules, so their wall
times are not a controlled solver speed comparison.

For context, a uniformly sampled nonidentity complement has expected
unordered second-pair representation count `B²/(2(r-1))` for these
sign-symmetric bases: `1.375585e-5 = 2^-16.150` at N53 and
`1.984429e-10 = 2^-32.231` at N83. This is a combinatorial uniform-input
calculation; first-pair search can produce a different distribution. It
shows that faster Boolean search must be evaluated together with first-pair
production and verified relation yield.

All ordinary attempts have zero verified relations under their stated caps,
so cost per useful relation is censored. The N131 complete work exponent,
uncertainty interval, and distance to `2^61` remain null: ordinary N83 yield,
rank novelty, N131 solver scaling, final matrix, and target descent are not
measured for this handoff. The next gate is to use the N53 known-satisfiable
complement for a bounded solver-parameter sweep, then carry any winning
setting unchanged to both ordinary N83 complements. Charge first-pair
production and every second-pair attempt, and report verified relation and
rank outcomes before fitting an N131 exponent.

Recompute exact inputs, formula hashes, solver receipts, and SAT replays with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_fixed_pair_s3_handoff/validate.py
```
