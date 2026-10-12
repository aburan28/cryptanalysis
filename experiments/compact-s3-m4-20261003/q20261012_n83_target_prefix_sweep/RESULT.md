# Q1510: a 64-midpoint prefix exposes a new usable N83 first pair at 2.1–2.2× search work

Placing 64 target-side S3 midpoint variables before the four-summand pair
leaves changes WDSat's first completed pair on both frozen ordinary N83
points. The new pair is rational, subgroup-usable, and in the exact W≤5
factor base on both sides. It was absent from the eight distinct pairs in
Q1508–Q1509. Four signed-complement scans of that pair completed on each
point with zero exact-base hits. Prefixes 0, 4, and 16 all selected the same
earlier pair; prefix 83 reached the frozen CPU cap before a pair marker.

| Target-midpoint prefix `k` | Selected: first-pair CNF+XOR calls | Holdout: calls | Pair and exact-base status | Four-sign scans per target |
| ---: | ---: | ---: | --- | --- |
| 0 | 53,498 | 55,822 | earlier pair, usable | 4 complete, zero hits |
| 4 | 54,330 | 56,654 | earlier pair, usable | 4 complete, zero hits |
| 16 | 56,838 | 59,162 | earlier pair, usable | 4 complete, zero hits |
| **64** | **117,155** | **119,479** | **new pair, usable** | **4 complete, zero hits** |
| 83 | 10-second CPU cap | 10-second CPU cap | no first-pair marker by cap | 0 |

The prefix-64 call ratios to prefix 0 are **2.190** on the selected point and
**2.140** on the holdout, or 1.131 and 1.098 additional work bits at the
first-pair search stage. The eight completed usable cells produced **32 full
signed-complement scans**. Their measured batch multiplication count is
**2,478,207,360 = 2^31.207**, excluding inversion internals. This sums all
experimental cells: prefixes 0, 4, and 16 repeat the same pair on each
target, and their scans are charged separately as executed. The prefix-64
pair is also identical across the two targets. Thus this screen changes
which pair is exposed, but does not demonstrate target-conditioned pair
selection on these inputs. The two target points and deterministic order do
not support an independent-sample confidence interval for relation yield.

The curve is `EC1N83Ckb1h876c2921cb64`. The exact W≤5 factor base has
**B=30,977,592** distinct usable points before sign/Frobenius folding and
**K=186,612** folded columns; its enumerated-set SHA-256 is
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The selected and holdout workload IDs are `2eb250a29072` and
`394256b9f901`. This is proposal `Q1510`, SAT first-pair stage `PDP4sat`,
`isogeny: "none"`, with `candidate_id` and `run_id` null. The run applies
the exact Q1488 phase-2 mask and differs only in the branch-priority prefix.
Both resource-capped rows have status `CPU_CAP_SEARCH_STARTED`; they are
censored observations, with the last search checkpoints retained in stderr.

## Work comparison to degree 131

The measured prefix change improves pair diversity, with zero verified
ordinary relations in these cells. It does not supply an empirical relation
rate or a fully charged N131 solve exponent. On the exact N131 W≤6 base,
transferring the current zero-hit scanner gives **2^35.933** batch
multiplications for one complete four-sign scan. That is **5.333 bits over**
the prior 2^30.6 per-decomposition allowance within a 2^61 full-solve
budget. Under Q1505's separately stated independent-uniform-first-pair input
law, relation supply remains modeled at **2^123.289** batch
multiplications, a **62.289-bit conditional gap** to 2^61. The N131 complete
cost stays null: relation yield, rank novelty, final matrix solving, target
descent, and recovery replay have not been observed together for this method.

The next solver change should use the target when selecting or querying the
**second** pair, then measure ordinary exact-base hits and rank-increasing
relations on matched N53 and N83 inputs. More static first-pair priorities
can be screened cheaply, but a different first pair with zero complement
hits does not close the relation-supply gap.

The [protocol](protocol.json), [build receipt](build_receipt.json),
[result](result.json), [operation accounting](analysis.json),
[hardware manifest](hardware.json), and [read-only validator](validate.py)
bind exact sources and inputs, CPU caps, peak RSS, operation counts, and all
scan receipts. CPU wall times remain exploratory: the host did not provide an
isolation receipt or an accessible exact CPU-model query. Recheck with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n83_target_prefix_sweep/validate.py
```

This is a retrospective exploratory parameter screen on already frozen
public targets. It makes a first-pair-stage comparison, not a single-target
online IC-versus-rho comparison.
