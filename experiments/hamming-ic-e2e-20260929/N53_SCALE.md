# N53 scale gate: FC-Hamming versus unary, 2026-09-29

This is the first larger-curve check after the complete N9 toy DLP. It keeps
the five-summand S3 circuit and compares only the exact-weight predicate.
The two encodings use one ordinary, previously unplanted subgroup point and
one separate known-witness planted control. Both variants see the same point,
base, solver binary, one thread, memory guard, and limits within each pair.

## Instance and accounting

The field is `GF(2^53)` in polynomial basis with modulus
`x^53 + x^6 + x^2 + x + 1`. The curve is `y^2 + xy = x^3 + 1`, with subgroup
order `21044858204113`, cofactor `428`, and curve ID
`EC1N53Ckb1hb75cbed53fce`. The deterministic normal element `3` has rank
53. Its weight-two masks yield 848 rational `x` values, 1,696 distinct
subgroup-usable points after cofactor projection, and 16 signed Frobenius
columns. The exact projected-set digest is
`3d5e838e9ecc07b20cc752f00ff5296cf0828dc527add294c01cfeb249e1454a`.
The base was recomputed from the curve; it is distinct from the older
23,320-point N53 base used by another method.

The ordinary target is the published subgroup point
`(7764671419819752, 2542564920656034)`; its previously published scalar
`596471236405` is used **only** for independent fixture replay. It was not
constructed from the new weight-two base. The planted control is a different
point, `(4325695624671797, 2325491084968461)`, formed from five retained
weight-two curve points. Its known group witness and all four S3 equations
were independently replayed. A planted result is a search control, not an
estimate of ordinary relation yield.

The ordinary pair has a declared 30-second CryptoMiniSat time limit,
200,000-conflict limit, and a 50-second external watchdog. The planted pair
has 10 seconds, 100,000 conflicts, and a 30-second watchdog. All four have
one solver thread and a sampled 2 GiB child-RSS guard. The solver did not
exit at its internal time limit; every attempt was killed by its external
watchdog. No internal conflict total was reported, so these rows are
**externally censored**. Formula build, XCNF write, solver launch, solver
wall, and memory are recorded separately in each [receipt](runs/n53_scale_v1).

| Workload | Encoding | Variables | CNF clauses | XOR rows | Solver wall | Sampled solver RSS | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ordinary | FC-Hamming | 41,116 | 117,441 | 2,510 | 50.039 s | 97.3 MiB | external watchdog, no model |
| Ordinary | Unary | 39,696 | 115,036 | 1,965 | 50.059 s | 101.3 MiB | external watchdog, no model |
| Planted | FC-Hamming | 41,116 | 117,441 | 2,510 | 30.040 s | 88.4 MiB | external watchdog, no model |
| Planted | Unary | 39,696 | 115,036 | 1,965 | 30.046 s | 133.1 MiB | external watchdog, no model |

The compact [summary](runs/n53_scale_v1/summary.json) retains all four rows,
the curve and base identity, distinct workload IDs, limits, source hashes,
XCNF hashes, and the null downstream measurements. Each complete XCNF is
stored as `system.xcnf.gz` next to its receipt; the hash in the receipt is
over its uncompressed bytes. The [summarizer](summarize_n53_stage.py) checks
every archived formula and source hash. The [checked-Sage replay](runs/n53_scale_v1/sage_replay.json)
passes curve, subgroup, normal-basis, ordinary-scalar, planted-group, and
S3-equation checks; its runtime identity was saved [before the replay](runs/n53_scale_v1/sage_runtime_info.json).

## Decision

Neither encoding produced one verified PDP relation on the ordinary point;
neither found the planted witness under its smaller matched bound. There is
no relation matrix, recovered target log, IC online wall, or IC/rho speedup
for this N53 method. `candidate_id` remains null because this is a PDP stage
experiment, and censored solve times are not treated as performance wins.
The observed N53 gate does not justify advancing this exact FC-Hamming S3
pipeline to N83 yet.

## Follow-up: pinned planted-witness diagnosis

The original planted attempts showed that the known group witness satisfies
the four S3 equations, but did not prove that the emitted XCNF accepts it.
The [witness diagnostic](diagnose_n53_witness.py) now reads each archived
planted formula and its receipt, appends unit clauses for the known witness,
and independently checks every CNF and XOR row in any returned model. It
keeps the original XCNF hash, source hashes, solver-binary hash, and exact
pin count in [separate receipts](runs/n53_witness_v3). The complete solver
models are stored as deterministic gzip archives beside those receipts.

| Encoding | Pinned input | Units | Diagnostic wall | Result |
| --- | --- | ---: | ---: | --- |
| FC-Hamming | all five x values and three middle x values | 424 | 0.204 s | SAT, complete XCNF model verified |
| Unary | all five x values and three middle x values | 424 | 0.194 s | SAT, complete XCNF model verified |
| FC-Hamming | five x values only | 265 | 20.113 s | external timeout, no model |
| Unary | five x values only | 265 | 20.021 s | external timeout, no model |

These are **known-witness controls**. The all-pinned rows establish that both
archived formulas encode the planted witness; the x-only rows show that the
current solver did not recover the intermediate coordinates within 20
seconds, even with all five base x values supplied. The diagnostic wall
includes formula extraction, unit-clause writing, solver execution, and model
checking; it is not an IC online time or a natural relation-yield estimate.
The unpinned N53 gate remains negative. A next solver variant needs to handle
the middle-coordinate chain before an ordinary-target or N83 promotion.

An [exact S3 root control](n53_s3_root_control.py) handles that chain once
the five base x values are supplied. Writing S3 as
`(a+b)^2 c^2 + ab c + (ab)^2 + 1 = 0` gives at most two roots for each
middle x coordinate. On the frozen planted x values, the oracle explored
2, then 4, then 8 chains; exactly one passed the final target-x equation,
and it was the independently replayed group witness. A separate 128-pair
control checked that the root set contains the actual group-sum x value for
every sampled factor-base pair. The [receipt](runs/n53_s3_root_v1/receipt.json)
binds the exact source, seed, inputs, and results. This is a control with
five supplied x values, not a natural-target search or a complete IC method.

To regenerate a new immutable stage directory on this host:

Use a Python environment with `psutil` installed and the recorded
`/opt/homebrew/bin/cryptominisat5` binary available.

```sh
python3 run_n53_stage.py --encoding fc --out /tmp/n53-fc-new --seconds 30 --conflicts 200000
python3 run_n53_stage.py --encoding unary --out /tmp/n53-unary-new --seconds 30 --conflicts 200000
```

These Python jobs invoke the recorded CryptoMiniSat binary and do not invoke
Sage. For a new Sage replay, save
`/Volumes/SSD990/cryptanalysis/sage --runtime-info` beside the results
first, then use that same checked launcher with `-python sage_replay_n53.py`.
