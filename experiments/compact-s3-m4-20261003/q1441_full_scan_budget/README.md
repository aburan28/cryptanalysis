# Q1441: full-base-scan affordability screen for N131

Q1441 is a **necessary budget screen for specified solver families**, not a
point-decomposition measurement or complete-solve estimate. It uses the
exact Q1413/Q1414 W≤6 base and uniform-query rank-supply bound, plus Q1437's
conditional W≤7 sampled base on `EC1N131Ckb1h6816f880945e`. The W≤7
actual `B`, folded `K`, and set digest remain null. This is a `Q` proposal
with `candidate_id: null` and `isogeny: "none"`.

The screen declares one abstract countable action as its unit and asks what
happens if each relation query scans **every** usable point in a base of size
`B`. It sets construction, query generation, matrix work, descent, and
verification to zero to give that scan family the most generous possible
budget. Its `2^61` comparison is within that one declared unit; no SAT
conflict, field operation, logical row action, or CPU second is silently
converted to another. A solver with guided queries, multiple verified rows
per target, or a compressed scan is outside the corresponding policy.

For exact W≤6, Q1414 proves a necessary **209,828,278 uniform nonidentity
queries** for 95% probability of rank `K=25,036,774` under its stated
marginal and row-source assumptions. A full `B=6,559,634,788` point scan on
every query takes at least `1.3764×10^18 = 2^60.256` actions at one action
per point. The entire `2^61` budget then allows only **1.675 actions per
scanned point**, even when every other phase is free. Two actions per point
alone take `2^61.256`, over budget.

For conditional W≤7, the one-row-per-query policy used by the current
first-witness solvers needs at least `ceil(K)` queries. At Q1437's sample
center, `B≈118.636` billion and `K≈452.809` million, so one full scan per
query takes about `2^65.542` actions. Its most generous per-point allowance
is **0.0429 actions**. The Q1437 Wilson endpoint calculations remain above
`2^65.525`; they inherit its unproved no-collision assumption and do not
bound every possible factor base.

| Base and policy | Minimum queries | One-action full-scan total | Maximum actions per scanned point, all other costs zero |
| --- | ---: | ---: | ---: |
| Exact W≤6, Q1414 uniform 95% rank floor | 209,828,278 | `2^60.256` | 1.675 |
| Conditional W≤7, one row/query, Wilson lower B/K | 450,169,294 | `2^65.525` | 0.0434 |
| Conditional W≤7, one row/query, sample center | 452,809,356 | `2^65.542` | 0.0429 |
| Conditional W≤7, one row/query, Wilson upper B/K | 455,449,278 | `2^65.559` | 0.0424 |

The [result](result.json) also shows an **optional matrix scenario**: if the
Q1437 optimistic `4K²` logical row-action proxy were calibrated into the
same abstract unit, subtracting it would leave about `2^31.612` actions per
one-row W≤7 query at the sample center. That proxy is neither a measured
matrix solve nor a lower bound. The zero-other-cost columns above are the
actual necessary gate for the declared scan family.

This screen rules out a full W≤7 base traversal per query for one-row
solvers even at one action per point. It does not rule out target-conditioned
sparse-pair witness methods that avoid scanning the base, and it does not
supply a natural useful-row rate, calibrated cost per relation, or a complete
N131 `2^x`. The [main ledger](../work_ledger.json) retains those as null and
keeps challenge dispatch disallowed.

Reproduce with the checked Sage launcher (the runtime check is outside the
screen calculation):

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1441_full_scan_budget/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1441_full_scan_budget/screen.py --freeze
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1441_full_scan_budget/screen.py --emit
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1441_full_scan_budget/screen.py --check
```

The freeze and emit commands refuse to overwrite evidence. Use a fresh
worktree for replay.
