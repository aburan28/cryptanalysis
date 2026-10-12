# Q1509: eight exact-blocked N83 first pairs yield three usable pairs per target

Extending the Q1508 three-CNF exclusion sequence from two to **eight distinct
first pairs** on each frozen ordinary N83 point exposes the same ordered eight
coordinate pairs on the selected and holdout targets. Pair indices **0, 2,
and 6** each have two rational, subgroup-usable leaves in the exact W≤5 base.
The other five pairs have an unrational second x coordinate and are rejected
before scanning. Each usable pair received all four signed-complement scans;
the resulting **24 complete scans have zero exact-base hits**. This depth
sweep measures exact-base survival and charged screening cost over rejected
and accepted first pairs.

| Curve `EC1N83Ckb1h876c2921cb64`, phase-2 point | Workload ID | Distinct pair indices | Usable indices | Total CNF/XOR calls across eight restarted searches | Complete signed scans | Exact-base hits |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Selected | `2eb250a29072` | 0–7 | 0, 2, 6 | 434,996 | 12 | 0 |
| Holdout | `394256b9f901` | 0–7 | 0, 2, 6 | 453,588 | 12 | 0 |

The twelve new Q1509 searches (indices 2–7 on both points) cost 669,954
combined CNF/XOR calls. The sixteen new complete scans cost
**1,239,103,680 = 2^30.207** batch multiplication calls, excluding
batch-inversion internals. Including Q1508's first two indices gives
**1,858,655,520 = 2^30.792** such calls across both targets. Individual
searches exposed the next pair in roughly 54–57 thousand combined calls;
each restarted search pays that prefix again. Their CPU and wall records are
preserved per row, with wall times exploratory because the host has no CPU
isolation receipt.

The exact base has **B=30,977,592** points before sign/Frobenius folding and
**K=186,612** columns. The empirical usable fraction is 3/8 within this
deterministic solver order. The two points share the same pair sequence, so
the sixteen rows are not independent samples of base survival and no
binomial confidence interval is assigned. Matching sequences on two points
also give no evidence that this particular first-pair order uses the target
to enrich its selected pairs. A later target-conditioned order could behave
differently.

For comparison to the 2^61 challenge, Q1505's conditional
independent-uniform-first-pair model remains **2^123.289** batch
multiplication calls for N131 relation supply, a **62.289-bit model gap**.
The N131 W≤6 full four-sign scan transfer remains **2^35.933** batch
multiplications, 5.333 bits above the prior 2^30.6 per-decomposition
allowance. These are specified-model and operation-transfer figures,
respectively; the complete charged N131 solve exponent is still unset because
this deterministic N83 sequence produced no exact-base relation or rank
novelty. The next improvement needs an indexed or target-conditioned
second-pair query, or a first-pair policy whose ordinary relation yield
beats this measured scan route.

This is proposal `Q1509`, stage `PDP4hybrid`, `isogeny: "none"`. Candidate
and run IDs are null for this stage-only sweep. The new binary raises the
WDSat static variable, clause, and implication-buffer limits to hold seven
simultaneous exact three-CNF exclusions. The [protocol](protocol.json),
[build receipt](build_receipt.json), [run result](result.json),
[accounting](analysis.json), and [validator](validate.py) bind the frozen
source and inputs, every restarted search, each exact-base filter, all
signed-complement outputs, and their operation counts. Recheck with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n83_pair_depth_sweep/validate.py
```
