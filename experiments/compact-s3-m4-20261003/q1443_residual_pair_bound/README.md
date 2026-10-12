# Q1443: residual-pair support bound

Q1443 checks a specific four-summand search pattern: choose first-pair sums
without using the target, then ask even a **free, exact oracle** whether the
target minus each first pair is the sum of two factor-base points. It uses
the exact N53/N83 Q1438 bases, the exact N131 W≤6 Q1414 base, and Q1442's
**conditional** selected-W7 N131 size. This is a counting bound, not a new
point-decomposition solver or an ordinary-query measurement. `candidate_id`
is null and `isogeny` is `"none"` throughout.

## Bound and scope

For a base of `B` distinct subgroup-usable points, its pair-sum support has
at most `S=C(B+1,2)` values, allowing repeated points and making the bound
generous. If a nonidentity target is uniform in a subgroup of order `r`, a
fixed first-pair sum chosen independently of that target leaves a residual
in this support with probability at most `S/(r-1)`. A list of `t` first-pair
sums fixed independently of the target covers at most `t*S` target values,
so 95% chance of *one* relation requires at least
`ceil(0.95*(r-1)/S)` tested first pairs. The result charges **one abstract
first-pair-trial action** per candidate and sets the residual oracle's cost
to zero. It does not convert that action to a field operation or CPU time.

For a uniform-target relation stream, if each trial returns at most one
verified row, the expected number of rows from `T` trials is at most
`T*S/(r-1)`. Since rank cannot exceed verified rows, Markov's inequality
gives `P(rank>=K) <= T*S/(K*(r-1))`. Thus 95% rank success needs at least
`ceil(0.95*K*(r-1)/S)` total trials in this declared family. This permits
every returned row to be novel and sets all matrix, setup, descent, and
verification costs to zero.

| Curve and base | Geometry status | `B` / folded `K` used | Pair-support probability upper bound | First pairs for 95% chance of one relation | Total first pairs for 95% chance of `K` rows, one-row policy |
| --- | --- | ---: | ---: | ---: | ---: |
| `EC1N53Ckb1hf77aab617904`, W≤4 | exact Q1438 | 324,042 / 3,057 | `2^-8.647` | 381 (`2^8.574`) | `2^20.151` |
| `EC1N83Ckb1h876c2921cb64`, W≤6 | exact Q1438 | 408,131,750 / 2,458,625 | `2^-24.791` | 27,579,253 (`2^24.717`) | `2^45.947` |
| `EC1N131Ckb1h6816f880945e`, W≤6 | exact Q1414 | 6,559,634,788 / 25,036,774 | `2^-64.778` | `2^64.704` | `2^89.282` |
| Same N131 curve, selected W7 | conditional Q1442 model | 11,968,916,918 / 45,682,889 | `2^-63.043` | `2^62.969` | `2^88.414` |

The first three base counts and set digests are inherited from the frozen
exact receipts and checked against them in the [result](result.json). The
selected-W7 row is **not** an enumerated factor base: actual B, actual K,
and its set digest stay null. Its bound is conditional on Q1442's base-size
model. The [independent audit](verification.json) recomputes the integer
ceilings without importing the producer and tests the union bound in a
small group.

At the conditional selected-W7 size, `2^61` target-oblivious first-pair
trials can have at most **0.243** probability of producing even one relation
under this law, despite a free oracle. The exact W≤6 base gives at most
**0.073**. Consequently, a solver that first enumerates candidate pairs
without target guidance and then invokes a residual-pair oracle cannot give
a credible sub-`2^61` complete-work claim in this action unit. Its much
larger `K`-row trial bounds reinforce that conclusion under the one-row
policy.

This result does **not** bound a search that jointly constrains both pairs
using the target before choosing a first pair, a compressed batch-pair
algorithm, target-guided nonuniform queries, or a method returning multiple
rows per trial. The target-conditioned *joint four-point witness* is the
next solver gate. An isolated fixed-residual pair oracle is useful for
correctness and kernel calibration, but its speed alone cannot close the
ECDLP work budget. No ordinary N83 relation, useful-row rate, final matrix
solve, target descent, or complete N131 `2^x` has been produced here.

The [protocol](protocol.json) and source were committed before result
emission. Reproduce the mathematical screen with standard Python; it does
not launch Sage:

```sh
python3 experiments/compact-s3-m4-20261003/q1443_residual_pair_bound/screen.py --check
python3 experiments/compact-s3-m4-20261003/q1443_residual_pair_bound/verify.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```
