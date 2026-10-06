# Q1469: ordinary N53 four-point relation supply

Q1469 measures natural relation yield and early matrix rank for Q1468's exact
four-point pair oracle. It uses curve `EC1N53Ckb1hf77aab617904`, the same
2,756 usable subgroup points and 26 signed Frobenius columns as Q1467/Q1468,
and enumerated-set digest
`cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70`.
The [frozen protocol](protocol.json) specifies `PDP4mitm`, `isogeny: "none"`,
and `candidate_id: null` / `run_id: null`: this is a decomposition-stage
proposal, not a complete IC method. The [panel](panel.json) freezes 128
distinct seeded pseudorandom public subgroup targets, their individual
workload IDs, and panel workload ID `4757ddafd5b2`.

Q1468 completed the primary matched single-target controls before this
secondary panel. Each Q1469 target starts with a fresh complete table of
3,651,700 cross-column pair sums. Table setup is target independent; the
target-dependent interval starts with the native query and ends when it
returns a witness or exhaustive absence. These are stage timings: no target
discrete logarithm was recovered. All 128 target runs finished without a
timeout or native error.

| Ordinary target outcome | Count | Evidence |
| --- | ---: | --- |
| Four-distinct-column relation found | 13 | Each witness independently replays to its public point. |
| No admissible relation after complete pair scan | 115 | Each query examined all 3,651,700 pair sums; complement hits sharing columns were rejected. |
| Censored or error | 0 | Preserved in each run receipt. |

The observed relation yield is **13/128 = 10.156%**. A model-based Wilson
95% interval is **6.032%–16.602%** for the target-generation law. This is
consistent with Q1467's exact four-point counting *upper bound* of 11.447%
on this base. The [independent archive audit](panel_audit.json) maps each
witness into signed Frobenius columns, verifies the coefficients by scalar
replay, regenerates each known collection-target scalar from the frozen seed,
checks its public point, and inserts its row over the prime subgroup order.
Those scalars are fixture data outside the timed query; they are not target
DLP recoveries. A separate Sage finite-field matrix rank agrees with the
auditor's incremental elimination. All 13 rows
increase rank, reaching **13 of 26 columns**. The observed novel-rank rate
of 13/128 applies to these early rows; it does not predict the rate near
full rank. The source-bound native complete enumeration has arithmetic
spot checks and a recovered planted control from Q1468, but there is no
second full oracle implementation.

## Charged stage costs

Every target's query work, including the 115 absences, is charged. The
following sums and ratios come from the archived native operation counters;
`mul`, `sqr`, and `inv` are distinct binary-field primitive calls and are
not collapsed into an uncalibrated common unit.

| Phase | All 128 targets | Per verified relation or early novel row |
| --- | ---: | ---: |
| Target query field multiplications | 2,128,617,090 | 163,739,776 |
| Target query field squarings | 430,964,487 | 33,151,114 |
| Target query field inversions | 103,989 | 7,999 |
| Target-independent table field multiplications | 2,339,801,600 | 179,984,738 if freshly rebuilt for each target |

The target-query intervals sum to **700.832 s**, or **53.910 s per verified
relation** including failed queries. A seeded target-level bootstrap gives a
95% interval of **32.636–107.655 s** per verified relation; the
multiplication-call interval is **100.665–318.389 million**. Fresh table
builds add **637.666 s** across the panel. The child-process intervals sum
to **1,341.299 s**, including launch and receipt overhead. Peak child RSS
observed by the runner was **91,340,800 bytes** on this Darwin host. All CPU
wall times are exploratory because there is no host isolation receipt.
These stage ratios are not a single-target IC online time or a speedup over
rho. The full 128 receipts retain the status and exclusive table/query
field-call and wall intervals for each target.

## Degree-131 implication and next gate

Q1413's exact N131 W≤6 base on `EC1N131Ckb1h6816f880945e` has
`B = 6,559,634,788` usable points and `K = 25,036,774` folded columns,
with 262 points per column. Its enumerated-set digest is
`e5f66c3944069924b9af7b8c22887e216702c8ac11a3a2ad072437e7d81ecb3b`.
Building the
same **complete explicit** cross-column table would require

`C(25,036,774, 2) × 262² = 21,514,403,416,657,745,244 ≈ 2^64.222`

pair entries before a target query. In a unit that charges at least one
entry materialization per pair, this particular complete-table method
exceeds `2^61` in setup alone. That conditional barrier does not bound a
compact target-guided quotient-summation solver. The N83 ordinary successful
solve cost, N83 natural yield/rank, late-rank collection cost, final matrix
solve, target descent, and scalar replay are still missing. A fully charged
N131 `2^x` therefore remains **unknown**, and no challenge run is admitted.

The next goal is an ordinary N83 four-point relation and measured work for
its recovery on Q1467's exact W≤4 base, curve
`EC1N83Ckb1h876c2921cb64`, enumerated-set digest
`1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325`.
Even there, the same complete
cross-column table has **1,870,145,118,700 ≈ 2^40.766** entries, which
explains why the N53 implementation is not a practical full-table N83
measurement on this host. A target-guided method must avoid that table while
returning a witness or a correctly bounded failure. Keep the Q1467 chain-S3
controls and this pair oracle on matched
inputs for stage comparisons; measure N83 yield and rank only after a
successful ordinary relation.

## Reproduce the audit

From the repository worktree:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/make_panel.py --check
python3 experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/audit_panel.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The [producer](run_panel.py) preserves every run receipt and its native
stdout/stderr under `runs/`. The audit reconstructs targets and hashes those
artifacts; it does not launch new measured queries.
