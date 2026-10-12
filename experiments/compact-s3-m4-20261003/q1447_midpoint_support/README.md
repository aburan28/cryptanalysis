# Q1447: support bound for random first-pair midpoints

Q1446 fixes a target-linked pair-intermediate x coordinate before exploring
four sparse leaves, and each ordinary N53/N83 run used its full 60-second
cap under only one such choice. Q1447 asks whether repeatedly choosing a
fresh **uniform** intermediate x could repair that coverage problem. It is
an analytic screen, not a solver or a new timing measurement. The exact
N53/N83 factor-base receipts and the exact N131 W≤6 receipt identify the
curves, actual usable point counts, folded column counts, and set digests.
The selected N131 W7 row remains a conditional size model with no actual
enumerated base or digest. The proposal has `candidate_id: null` and
`isogeny: "none"`; no `IC1` result is claimed.

## Bound for a fixed public target

Let `F` contain `B` distinct **raw signed** points represented by the
sparse-x base. The exact receipts establish that the cofactor projection
has no identity or duplicate orbit at insertion, so the raw signed count
equals the reported projected usable `B`. The base includes both signs.
Allowing repeated leaves, the support of all unordered pair sums has at
most `C(B+1,2)` group elements. Its closure under negation means at most
`ceil(C(B+1,2)/2)` x coordinates: on these ordinary binary curves, at most
one nonidentity rational point is its own negative.

Every valid four-summand witness must have its first-pair intermediate x
in that support. For **any fixed public target**, uniformly sampling `t`
raw x coordinates from the whole field has success probability at most
`t*ceil(C(B+1,2)/2)/2^n` by a union bound. This gives a necessary number
of midpoint trials for 95% success even if all second-pair, target-preimage,
sign, and verification work is free. Each trial is an abstract midpoint
sample, not a field operation or a calibrated CPU cost.

| Curve and base | Actual `B` / folded `K` | Midpoint hit probability upper bound | Midpoints needed for 95% success |
| --- | ---: | ---: | ---: |
| `EC1N53Ckb1hf77aab617904`, W≤4 | 324,042 / 3,057 | `2^-18.388` | 325,964 (`2^18.314`) |
| `EC1N83Ckb1h876c2921cb64`, W≤6 | 408,131,750 / 2,458,625 | `2^-27.791` | 220,634,018 (`2^27.717`) |
| `EC1N131Ckb1h6816f880945e`, W≤6 | 6,559,634,788 / 25,036,774 | `2^-67.778` | 240,410,652,791,667,256,959 (`2^67.704`) |
| Same N131 curve, selected W7 size model | *conditional* 11,968,916,918 / 45,682,889 | `2^-66.043` | `2^65.969` |

The W≤6 N131 lower bound alone exceeds `2^61` abstract midpoint trials
before any field arithmetic, failed-leaf search, relations, matrix work,
target descent, or replay is charged. The conditional W7 model also
exceeds it. This excludes a uniform-midpoint restart policy under the
declared factor bases. It does **not** apply to nonuniform target-guided
selection, an algebraic search over still-unfixed intermediate bits, or a
shared batch calculation that represents many midpoint choices at once.
Q1446's deterministic SAT branch is outside this probability bound; its
censored runs are separate empirical evidence.

The actionable next solver gate is a compact chained-`S3` method that keeps
the first-pair intermediate unfixed while the target and **both** sparse
pairs constrain it. It should preserve known-witness controls, then produce
an independently verified ordinary N53 and N83 relation or honest censored
rows under frozen matched workloads. A successful stage would still need a
fresh natural-query panel, useful-rank rate, and all other phase charges
before a complete N131 `2^x` exists.

The [protocol](protocol.json) and two source files were committed before
the [result](result.json) was emitted. The [independent audit](verification.json)
checks every integer threshold, all pinned receipts, and the sign-orbit
inequality on 186 symmetric subsets of small finite groups. Reproduce with
standard Python; no Sage job is launched:

```sh
python3 experiments/compact-s3-m4-20261003/q1447_midpoint_support/screen.py --check
python3 experiments/compact-s3-m4-20261003/q1447_midpoint_support/verify.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```
