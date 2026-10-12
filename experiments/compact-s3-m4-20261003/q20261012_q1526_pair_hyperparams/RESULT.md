# Q1526: the 84-cell pair-index sweep selects W7 among matrix-eligible bases

Sweeping 21 binary table fractions for each N131 weight bound W≤5 through
W≤8 selects the **full available quotient index** in all four rows of the
recorded optimistic pair-index model. Among rows whose `4K²` matrix proxy
is below an abstract `2^61` modular-event reference, conditional W≤7 has
the least modeled query work: **`2^86.185` counted pair-add attempts**,
**25.185 bits** above an abstract `2^61` pair-add reference. Its sampled
base-count interval moves that exponent only to `2^86.170`–`2^86.200`.
W≤8 reduces the pair-add model to `2^82.222`, while its separate matrix
proxy is `2^67.426` modular events. These units are reported separately;
neither column is a complete solve estimate.

| Bound | Base status | Usable `B` | Folded `K` | Best tested table fraction | Pair-add attempts, log₂ | Full-table query-addition floor, log₂ | `4K²` modular proxy, log₂ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| W≤5 | exact | 309,633,434 | 1,181,807 | 1 | 94.761 | 94.761 | 42.345 |
| W≤6 | exact | 6,559,634,788 | 25,036,774 | 1 | 90.356 | 90.356 | 51.155 |
| W≤7 | sampled conditional | 118,153,819,312 | 450,968,776 | 1 | **86.185** | 86.185 | 59.497 |
| W≤8 | sampled conditional | 1,844,590,711,506 | 7,040,422,563 | 1 | 82.222 | 82.220 | **67.426** |

The exact curve is `EC1N131Ckb1h6816f880945e`; the subgroup order is
`680564733841876926932320129493409985129`. W5 and W6 use Q1506's
enumerated usable counts and set digests. W7 and W8 retain Q1447's
sampled conditional counts and intervals. All rows obey `B=262K`; a
nominal normal-basis weight is never used as the `fb` count. Q1526 is a
`PDP4mitm` **model sweep**, with `candidate_id` and `run_id` null and
`isogeny: "none"`. It has no new N53 or N83 solver measurement.

## Charged model and search boundary

For a full index of `T_max=nK²` states and a tested fraction `f=2^-j`,
Q1462's optimistic uniform-query law gives `Q(f)=K·2r/(B²f)` queries for
`K` useful matches. Q1526 charges `T=fT_max` table pair additions and
**two** pair additions per target query, so the finite-screen value is
`T+2Q(f)`. It evaluates every `j=0,…,20`, charging failed queries as well
as successful ones. The W7 `f=1` row reproduces Q1462's
`2^86.184702` result. The full-table query-addition floor alone exceeds
`2^61` in all four rows; the six Lean declarations in
[FORMALIZATION.md](FORMALIZATION.md) check the finite boundary comparisons.

This is a conditional operation model: uniform independent query support,
proportional hit probability for a partial table, and one new rank row per
useful match are optimistic assumptions. W7/W8 base counts are sampled
projections. The source-record hashes, input formulas, tested fractions, and
stop rule were frozen in [protocol.json](protocol.json) before the calculator
ran. [analysis.json](analysis.json) retains all 84 cells and the W7/W8
interval endpoints. [validate.py](validate.py) checks every cell against
the original records and independently cross-checks Q1462.

The prior **complete-scan** route is a different algorithm:
Q1505 conditionally models N131 relation supply at `2^123.289` batch multiplication
calls. Q1526 prices the **pair-index** route in pair-add attempts. Neither
figure includes all target-independent preparation, final relation-matrix
solving, target descent, and replay in a common unit. The fully charged
N131 one-target exponent remains unset, and this sweep does not authorize
a challenge run.

The next algorithmic experiment should reduce target-conditioned second-pair
work or return substantially more novel rows per ordinary query. Table
fraction and weight tuning within this frozen pair-index family leave a
large modeled gap. Test any new search on the exact N53 and N83 bases and
ordinary points, preserving verified relation yield, rank novelty, and
failed attempts before transferring its model to N131.

Reproduce the frozen arithmetic and proof checks with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1526_pair_hyperparams/validate.py
cd experiments/compact-s3-m4-20261003/q20261012_q1526_pair_hyperparams/lean && lean PairBudget.lean
```
