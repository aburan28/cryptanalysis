# Q1511: exact N53 quotient-pair prefix search saves 2,633,230 pair additions

The frozen Q1457 N53 four-point relation stream reaches full **227-column**
quotient rank after **2,615,354 table states and 28,747,216 target query
representatives**. Stopping at that point charges **60,108,572 = 2^25.841**
pair-add attempts, versus **62,741,802 = 2^25.903** for the original full
table and 30-million-query cap. The saved **2,633,230 pair additions** are
4.20% of the full-run stage count, or **0.0619 work bits**. This is the least
charged full-rank prefix among all 20 feasible table-state thresholds in the
frozen stream, not a new timed native execution.

| N53 table states retained | Verified relations by 30M queries | Quotient rank / 227 |
| ---: | ---: | ---: |
| 500,000 | 71 | 67 |
| 1,000,000 | 149 | 133 |
| 1,500,000 | 219 | 185 |
| 2,000,000 | 289 | 223 |
| 2,500,000 | 362 | 225 |
| 2,600,000 | 380 | 226 |
| **2,615,354** | **at least 362 by the stopping query** | **227** |
| 2,743,068 | 400 | 227 |

The exact curve is `EC1N53Ckb1hf77aab617904`, with **B=24,062** distinct
usable W≤3 factor-base points before signed-Frobenius folding, **K=227**
columns, and enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
There is no isogeny transport. This is proposal `Q1511`, stage policy
`PDP4mitm/RCenum`; `candidate_id` and `run_id` are null because the result
replays a stage parameter frontier rather than executing a complete new
candidate. Q1457's generator-anchored setup query is the frozen input law.

For each of the 400 Q1457 independently group-verified relations,
[`analyze.py`](analyze.py) reconstructs its four signed-Frobenius column
coefficients, checks the transformed points and solved-log equation, and
computes exact modular rank over the declared subgroup order. It tests every
table ordinal at which a relation appears, then stops each feasible table
prefix at the first query that completes rank. Identity queries are counted
from the hashed 30-million-pair stream; the executable can regenerate that
stream from Q1457's frozen seed if the local input file is absent. The
operation boundary charges one addition per table state and two per
nonidentity query, matching Q1457. It excludes field-operation internals,
factor-base construction, final LA, fresh-target descent, and scalar replay.
Those separately recorded Q1457/Q1461 stages are required for a complete
single-target comparison. CPU wall-time ratios require an isolated host
receipt and a new early-stop implementation; this offline prefix result is
an exact operation-count counterfactual for the frozen stream.

The N83 comparison must retain its own base identity. The fresh-target Q1091
pair-table run on the same curve `EC1N83Ckb1h876c2921cb64` verified one
natural four-point relation and scalar `1228047131163538399404643` on its
**seeded known-log base**, B=8,000,204, K=48,194, digest
`7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02`,
candidate
`IC1N83Ckb1fb8000204PDP4qtableRCdirectLAnoneTDdirectISO0h49b47d79e9e3`,
workload `9ccc27baec79`. Its terminal reconciliation credits 38,654,705,664
disjoint query representatives and a **2^45.541 regular-path field API-call
model** for completed receipts and bounded controls. Canceled attempts have
unknown actual operations. The compact S3 N83 W≤5 base is a different set:
B=30,977,592, K=186,612, digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Its Q1510 first-pair scan has zero exact-base completions, so Q1091's yield
and known-log direct recovery cannot be assigned to that W≤5 pipeline.

## Distance to the degree-131 challenge

The new N53 stopping policy saves **0.0619 bits of measured stage work** on
its frozen relation stream. It does not change Q1462's conditional N131 W≤7
pair-index estimate of **2^86.18 pair-add attempts**, 25.18 bits above an
abstract 2^61 pair-add reference: that model already chooses the full
available index, and shrinking it increases expected query work. Q1505's
separate W≤6 first-pair scan model is **2^123.289 batch multiplications**
under its independent-uniform-first-pair law. These are distinct algorithms
and operation units. The fully charged N131 single-target solve exponent
remains null until relation yield, rank novelty, matrix work, and target
descent are measured on one exact candidate with one common unit.

The next parameter search should optimize **target-conditioned second-pair
lookup** on frozen N53 and N83 ordinary points. It should report verified
relations per charged table/query operation and novel rank per query, then
transfer only a model whose input law and base construction match the N131
candidate. The Q1511 stopping threshold can be implemented in that lookup
as an exact N53 regression control.

Reproduce the frontier and check its frozen inputs:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_n53_pair_frontier/analyze.py
python3 experiments/compact-s3-m4-20261003/q20261012_n53_pair_frontier/validate.py
```

The [machine-readable frontier](result.json) retains all 20 feasible prefix
costs and the input/source hashes. N83 Q1091's receipts and independent Sage
replay are in
[`n83_fresh_terminal_evidence.tar.gz`](../../koblitz-pair-claw-20260929/n83_fresh_terminal_evidence.tar.gz)
with the [terminal reconciliation](../../koblitz-pair-claw-20260929/n83_q1091_terminal_reconciliation.json).
