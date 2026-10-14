# Q1476: expose the trace syndrome in the compact S3 search

For the exact Koblitz model `y^2+xy=x^3+1`, the rational-point map
`P -> Tr(x(P))` is additive. In the declared type-II normal basis, field
trace is the parity of the coordinate bits. Q1476 appends that necessary
parity relation to both pair `S3` links and the final target `S3` link of
Q1475's ordered-leaf CNFs. The final relation is gated by the existing
target-preimage selector. This exposes one target-conditioned bit to the SAT
solver without constructing `S5`. The group-theoretic source is
[Kosters and Yeo, Section 4.2](https://arxiv.org/html/1503.08001v3).

The [design](design_protocol.json) was committed and published before the
six CNFs were created. The [frozen protocol](protocol.json) and all source,
input, binary, and checked Sage runtime hashes were committed before any
solver run. The Q1475 native solver binary, target points, exact bases,
decision policy, 250,000 pair-candidate cap, one-million conflict cap, and
60-second native wall cap are unchanged. Only exact CNF clauses were added.

| Degree | Exact curve ID | Actual usable base `B` | Folded columns `K` | Enumerated-set SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 2,756 | 26 | `cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 1,934,066 | 11,651 | `1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325` |

The stage IDs are `PS1N53Ckb1fb2756PDP4hybridhe1441044990a` and
`PS1N83Ckb1fb1934066PDP4hybridh2bcfa22989e6`. Each case has a
`PS1...W...R1` run ID. This is still proposal `Q1476`, with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`: no complete
`IC1` candidate is measured.

## Correctness and frozen result

The [independent trace validation](trace_validation.json) checks all 53 and
83 normal-basis vectors against a Frobenius-sum trace, ten independently
constructed rational-point additions at each degree, sign invariance, and
the three parity relations on both pinned witnesses. The parity-gate truth
table is exhaustive. The [archive audit](archive_audit.json) regenerates
all six CNFs, confirms every parent clause and source hash, checks the two
SAT models against every CNF clause, and replays their exact `S3` links,
signed raw group sums, four distinct folded columns, and public subgroup
points.

| Frozen case | Result | Verified relation | SAT propagations, Q1475 → Q1476 | Exact target joins, Q1475 → Q1476 | Q1476 field mul / sqr / inv |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 sorted pinned control | SAT | 1 | 82,667 → 83,088 | 0 → 0 | 209 / 1,236 / 18 |
| N83 sorted pinned control | SAT | 1 | 218,650 → 219,467 | 0 → 0 | 258 / 2,180 / 20 |
| N53 known-representable full public coset | 60 s cap | 0 | 328,558,707 → 316,804,552 | 213 → 218 | 12,152,406 / 51,405,860 / 9,821 |
| N83 known-representable unpinned | 60 s cap | 0 | 360,690,656 → 400,862,456 | 1 → 1 | 382,810 / 2,573,942 / 7,691 |
| N53 ordinary | 60 s cap | 0 | 338,294,876 → 342,691,971 | 214 → 213 | 12,052,776 / 50,989,212 / 11,211 |
| N83 ordinary | 60 s cap | 0 | 318,703,689 → 333,907,257 | 1 → 1 | 382,810 / 2,573,942 / 7,691 |

Every free-leaf case is censored, including both known-representable
controls. The N83 pair-root and exact-join counts are unchanged on the
matched targets. The extra parity equations changed SAT search prefixes
but did not deliver an unpinned relation or measurable successful-solve
cost. The N53 positive target was selected after the Q1469 pair-table
witness was known; planted and selected controls do not estimate ordinary
relation yield. One ordinary target per degree cannot estimate yield or
novel-rank cost. Host wall intervals remain exploratory without an
isolation receipt.

## Degree-131 implication

Q1414's exact N131 W≤6 base has `B=6,559,634,788` and `K=25,036,774`.
Under its stated uniformly marginal query and optimistic novel-row
assumptions, 95% full-rank success requires at least 209,828,278 ordinary
queries. A `2^61` total-work target then leaves less than `2^33.3554`
abstract work units per query **with every other phase set to zero**. This
is a necessary affordability ceiling, not a measured PDP cost or complete
DLP projection. The older `2^30.6` figure used a different balanced-base
and rho-parity model; it is not this exact-base threshold. The explicit
complete pair-table comparator needs `2^64.222` N131 entries before a
query. None of these bounds excludes a compact, target-guided solver.

Q1476 supplies no successful unpinned N83 work, natural N83 yield/rank,
final relation-matrix cost, target descent, or scalar replay. The complete
N131 `2^x` remains `null`; challenge dispatch remains closed. A next method
needs substantially more target information than this single trace bit
while pair domains are still broad.

## Reproduce the checks

```sh
python3 experiments/compact-s3-m4-20261003/q1476_trace_syndrome/prepare_inputs.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1476_trace_syndrome/validate_trace.py --check
python3 experiments/compact-s3-m4-20261003/q1476_trace_syndrome/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1476_trace_syndrome/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

These checks replay the archived evidence and do not rerun the native
60-second cases. Each case preserves raw stdout, stderr, any SAT model,
source-bound receipt, primitive operation counts, wall interval, and peak
child RSS under `runs/`.
