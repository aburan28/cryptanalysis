# Selector-weighted W24 products make fixed z releases solvable

Replacing the W24 `w*z` multiplier with the exact selector-weighted sum
`sum_j s_j*(b_j*z)` returned independently verified SAT for **three of eight**
previously bounded single-coordinate releases: source z0/z5 and descendant
z0. Rewriting `u*(x+alpha)` as a second selector-weighted sum returned SAT
for those three and descendant z5, for **four of eight**. All four x releases
per variant remained `BOUNDED_UNKNOWN` under the frozen 120-second internal
and 150-second external limits. Each SAT model reconstructs the same six
distinct leaves and unique all-plus signed target as the fixed witness. These
cells measure inverse-equation propagation with all selectors fixed; they do
not generate a new relation row. The [archive audit](runs/R1/audit.json)
verified all 24 exact inputs and solver transcripts.

The [precommitted protocol](PROTOCOL.md) and source commit `721165315` define
two circuits: `wz_only` changes the sparse W24 `w*z` product, and
`both_products` also changes the halftrace-derived `u*(x+alpha)` product.
Field bilinearity proves both identities for every 24-bit selector and
GF(2^131) input. An [equivalence receipt](runs/R1/equivalence.json) checks
all 263 leaf equations against direct field arithmetic for 64 masks/values
per curve, including zero, full, all singleton, six archived witness, and
32 seeded random cases. The exact source and degree-263 descendant curves,
six finite-intermediate witnesses, target points, and target-mux choices
are inherited by hash from the [parent control](../ecc2k130-263-distinct-s3-control-20261010/RESULT.md).
The checked fourfold subgroup bases each have `B=16,772,828` usable points.
Formula archives, named-input maps, and all 24 unit-clause deltas were
committed as `cbb24aaf0` before the first solver launch. An independent
derivation matched each semantic unit delta before measurement.

| Curve | Circuit | Variables | Ordinary clauses | Native XORs | Total constraints | Raw XCNF bytes | Build wall s | Build RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Source | parent | 340,590 | 334,948 | 227,701 | 562,649 | 11,611,565 | 4.732 | 284.61 |
| Source | `wz_only` | 345,702 | 357,412 | 225,325 | 582,737 | 11,878,410 | 6.087 | 283.61 |
| Source | `both_products` | 533,100 | 327,622 | 422,653 | 750,275 | 16,163,425 | 9.530 | 366.73 |
| Descendant | parent | 345,041 | 334,390 | 232,290 | 566,680 | 11,739,676 | 5.148 | 285.72 |
| Descendant | `wz_only` | 350,141 | 356,854 | 229,902 | 586,756 | 12,004,279 | 6.323 | 286.33 |
| Descendant | `both_products` | 533,633 | 327,064 | 423,324 | 750,388 | 16,152,242 | 9.271 | 369.03 |

The `wz_only` rewrite increases total constraints by 3.570% on the source
and 3.543% on the descendant. `both_products` increases them by 33.347%
and 32.418%, respectively. Its extra descendant z5 SAT is therefore paired
with a substantially larger formula. Formula construction and the one-thread
CryptoMiniSat solver used the same source snapshots and semantic inputs
across all three circuits; the [base](runs/R1/source_wz_only_base.json) and
[cell](runs/R1/source_wz_only_cells.json) receipts bind every new XCNF and
run input by SHA-256. The parent [base](../ecc2k130-263-distinct-s3-control-20261010/runs/R1/source_base.json)
and [cell](../ecc2k130-263-distinct-s3-control-20261010/runs/R1/source_cells.json)
receipts provide the corresponding frozen baseline.

Each entry below is the audited status followed by solver wall seconds.
`SAT_VERIFIED_GROUP` means full ordinary-clause/native-XOR replay and exact
signed point-sum replay passed; `BOUNDED_UNKNOWN` is a capped search with
recorded restart progress. Fixed positive controls were
`SAT_VERIFIED_GROUP` on both curves for both variants (0.522–0.794 s), and
their one-bit target changes were explicit `UNSAT` (0.266–0.535 s). Every
fixed positive uses 2,246 unit clauses; each coordinate release uses 2,115.

| Curve | Released word | Parent | `wz_only` | `both_products` |
| --- | --- | --- | --- | --- |
| Source | x0 | `BOUNDED_UNKNOWN` 122.141 | `BOUNDED_UNKNOWN` 150.088 | `BOUNDED_UNKNOWN` 148.357 |
| Source | z0 | `BOUNDED_UNKNOWN` 150.197 | `SAT_VERIFIED_GROUP` 1.078 | `SAT_VERIFIED_GROUP` 1.358 |
| Source | x5 | `BOUNDED_UNKNOWN` 149.202 | `BOUNDED_UNKNOWN` 140.708 | `BOUNDED_UNKNOWN` 135.723 |
| Source | z5 | `BOUNDED_UNKNOWN` 150.119 | `SAT_VERIFIED_GROUP` 17.057 | `SAT_VERIFIED_GROUP` 18.705 |
| Descendant | x0 | `BOUNDED_UNKNOWN` 122.039 | `BOUNDED_UNKNOWN` 121.378 | `BOUNDED_UNKNOWN` 121.216 |
| Descendant | z0 | `BOUNDED_UNKNOWN` 121.804 | `SAT_VERIFIED_GROUP` 1.804 | `SAT_VERIFIED_GROUP` 2.350 |
| Descendant | x5 | `BOUNDED_UNKNOWN` 122.335 | `BOUNDED_UNKNOWN` 130.284 | `BOUNDED_UNKNOWN` 121.009 |
| Descendant | z5 | `BOUNDED_UNKNOWN` 124.591 | `BOUNDED_UNKNOWN` 150.249 | `SAT_VERIFIED_GROUP` 128.572 |

The auditor rebuilt each complete XCNF from its deterministic gzip base and
precommitted unit delta, matched the full-input hash, checked every reported
SAT assignment, and replayed the unique all-plus raw group sum. For example,
the source `wz_only` SAT models satisfy 359,658 ordinary clauses and 225,325
native XORs; the descendant `both_products` models satisfy 329,310 ordinary
clauses and 423,324 native XORs. Four fixed negative controls terminated
`UNSAT`. Every bounded cell has live solver restart rows; the source
`wz_only` x0 and descendant `wz_only` z5 used the external wall guard, while
the others exited with `s INDETERMINATE`. All raw stdout/stderr and receipts
are in [runs/R1](runs/R1). No sampled 4-GiB RSS guard fired.

The [environment receipt](runs/R1/environment.json) records macOS 26.6,
arm64, Python 3.13.1, CryptoMiniSat 5.14.7 binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
one thread, the solver timing interval, and the sampled-RSS policy. Host-wide
CPU isolation was not established and each cell ran once, so the wall values
are exploratory solver-stage diagnostics without a timing confidence
interval. The status change from bounded to verified SAT is the observed
result. Natural ordinary-query relation yield, novel rank, final relation
matrix work, target descent, and one-target online IC/rho time remain
unmeasured for this proposal (`candidate_id: null`).

The next comparison should use the smaller `wz_only` circuit first with all
six selectors free on frozen ordinary Q1420 walk queries, retaining the
parent circuit as a matched control and charging all attempts, verified
relations, and novel rank. Keep `both_products` as a second circuit because
it resolved descendant z5, but measure its larger construction/search cost
separately. The persistent x-side bounded cells motivate a targeted
`u*(x+alpha)` encoding or pivot strategy before scaling ordinary-query
volume. An ordinary verified relation and its rank contribution are the
gate for advancing this solver-stage result toward an IC candidate.
