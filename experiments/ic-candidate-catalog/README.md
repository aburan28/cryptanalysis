# Index-calculus candidate catalog

This directory contains **1,000 design proposals**, not 1,000 measured attacks.
The [complete N13 follow-up](measurements/2026-09-25/COMPLETE_N13.md) has an
exact candidate derived from the `Q1` axes and 20 paired one-target toy DLP
runs. Its explicit-sumset selector CNF is distinct from the earlier chained-S3
SAT probe, so the unpromoted `Q` proposal IDs keep null costs.
The [first empirical pass](measurements/2026-09-25/REPORT.md) links a
catalog-wide assessment to exact toy/N131 profile geometry, two newly
enumerated N131 normal-basis recipes, sampled polynomial-base densities,
and bounded N13 SAT stage receipts. By itself, that first pass had no
complete one-target DLP or online speedup.
Run `python3 experiments/ic-candidate-catalog/generate.py` to regenerate
`candidates.jsonl`; use `--check` to verify the committed output. Each proposal
has a `Q` ID and `candidate_id: null`. Issue a final `IC1...h...` ID only after
the exact curve, factor base, code snapshot, and any isogeny route satisfy
[`AGENTS.md`](../../AGENTS.md). No `fb` number is inferred from a dimension.

The catalog is a staged design of experiments. Each of ten anchored profiles
gets 100 combinations: five PDP methods, five witness selection policies,
two final relation-matrix algorithms, and two per-PDP time limits. The
time-limit variants test censoring and resource sensitivity; they are separate
configurations, not separate mathematical algorithms. Every row retains
activation blockers and no measured cost. The four collection policies beyond
`first` include interfaces that existing implicit PDP solvers do not yet
provide. The `bw` relation-matrix option likewise needs an adapter. These
limitations are recorded, not silently treated as completed implementations.
The 50 ms budget comes from the shifted-base solver smoke; both 50 ms and
1,000 ms N13 first-witness SAT variants now have stage receipts, but neither
produced a verified decomposition in the frozen stream.

## Evidence-linked profiles

| Profile | Field | Factor base and arity | Evidence state |
| --- | ---: | --- | --- |
| `n13_same_d3_m4` | N13 | **fb6**, two folded columns, same three-dimensional base, m=4 | Chained-S3 SAT smoke: zero verified relations in 32 ordinary queries at 50 ms per solve. A separate explicit-sumset SAT variant completed 20 paired toy DLPs. |
| `n19_shifted_d3_m5` | N19 | **fb30** across five disjoint six-point shifts, two folded columns, m=5 | Exact support geometry only; solver and useful rank costs remain open. |
| `n53_retained_m5` | N53 | Retained 23,320-point signed base, 220 folded columns, m=5 proposal | The representative-key hash and counts are replayed from a public synthetic N53 receipt; this PDP combination has not been measured. |
| `n131_poly_d7_m4` | N131 | Polynomial subspace d=7, **fb26**, m=4 | Bounded planted-query and matrix audit; no natural full-width DLP recovery. |
| `n131_onb_hw2_m4` | N131 | **fb3668**, 14 folded columns, normal-basis Hamming weight ≤2, m=4 | Exact subgroup-filtered point set materialized; PDP and target stages remain unverified. |
| `n131_onb_hw3_m5` | N131 | **fb3668**, the same 14 folded columns, normal-basis Hamming weight ≤3, m=5 | The extra weight-three coordinates add no subgroup points; PDP and target stages remain unverified. |
| `n131_poly_d28_m5` | N131 | Polynomial subspace d=28, m=5 | 1,024-x uniform density sample estimates about 66.1 million usable points (95% interval 56.0–77.6 million); exact base and end-to-end costs unknown. |
| `n131_poly_d24_m6` | N131 | Polynomial subspace d=24, m=6 | 1,024-x uniform density sample estimates about 3.90 million usable points (95% interval 3.29–4.61 million); exact base and end-to-end costs unknown. |
| `n131_iso2_d28_m5` | N131 | Proposed degree-2 isogeny search, codomain d=28, m=5 | Screened: the degree-2 codomain is isomorphic to the source; no different-curve route. |
| `n131_iso3_d28_m5` | N131 | Proposed degree-3 isogeny search, codomain d=28, m=5 | Screened: no rational degree-3 isogeny over `GF(2^131)`. |

`N131` is the field degree for ECC2K-130; its subgroup order has 130 bits.
`fb6`, `fb30`, `fb23320`, `fb26`, and `fb3668` count distinct usable points before orbit
folding. The N13 and N19 point lists are frozen in
[`toy_base_anchors.json`](toy_base_anchors.json); `fb30` is the **union** of
five distinct six-point bases, not six points in each PDP slot. The
N53 count is tied to a retained receipt with representative-key BLAKE3
`d859319015ea405fd18aee41b51396ce4edcab64ef66265d8edcdeb5e040eb71`.
That digest covers the folded representative keys, not the full 23,320-point
set; a complete factor-base point digest is still required for a final ID.
The N131 `fb26` count is tied to the encoded point list in
`experiments/nonfrobenius-ic/results/ecc2k130-run01.json`.
The newly enumerated N131 normal-basis `fb3668` point list is frozen in
[`measurements/2026-09-25/n131_onb_hw2_hw3_usable_points.json`](measurements/2026-09-25/n131_onb_hw2_hw3_usable_points.json).
Both HW2 and HW3 recipes produce that same set. On this curve, the
x-coordinate of a double is `lambda^2+lambda`, whose field trace is zero.
Every point in the odd-order DLP subgroup is a double, and ONB trace equals
Hamming-weight parity. Therefore the newly admitted weight-three x values
cannot add subgroup points. This does not make the m=4 and m=5 PDP proposals
equivalent: their decomposition systems and costs still differ.
None of these counts licenses copying a base to another curve, isogeny codomain,
field representation, or factor-base recipe.

## Code reviewed for the design axes

| Stage | Existing code and evidence | What can be reused / what is missing |
| --- | --- | --- |
| Exact small-base construction and pair lookup | `experiments/nonfrobenius-ic/index_calculus.py`, `README.md` | Subgroup-filtered points, pair witnesses, rank diagnostics; no imported target or full DLP. |
| Frobenius-folded base and Semaev/SAT pipeline | `ecc2k130/codegen/indexcalc_e2e.py`, `indexcalc.py` | Audited toy DLP path and N131 stage controls; the code explicitly forbids full N131 recovery claims. |
| PDP solvers | [`pdp-scaling/solve.py`](../pdp-scaling/solve.py), `boolean_f5b_native.cpp`, `boolean_f5b_m4ri.cpp` | SAT, F5B, hybrid, PolyBoRi and other stage references; published timings exclude complete IC costs. |
| F4 research kernel | `crypto/src/cryptanalysis/koblitz_groebner.rs`, `experiments/groebner-perf-20260924/README.md` | A Matrix-F4-style implementation and kernel evidence; treat it as its actual implementation, not a certified general F4 engine. |
| Witness selection and useful rank | `experiments/factor-base-yield-v2/engine.py`, `REPORT.md` | Exact finite first/uniform/rank-scan controls; bounded degree-131 materialization failed its admission gate. |
| Shifted-base geometry | `experiments/shifted-base-geometry/README.md`, `FOLLOWUP.md` | Support gains on toy fields, then zero solved smoke queries; no full-width speed claim. |
| Isogeny discovery | `crypto/src/cryptanalysis/binary_isogeny.rs` | Degree-2/3 neighboring `j` search; it explicitly lacks the point map needed for DLP transport. Prime-field volcano code in `crypto/src/isogeny/` does not supply a binary ECC2K-130 route. |
| Boundary measurements | `crypto/docs/ic/boundary_targets.json`, `round24-run-20260923/research/ic_candidate_tournament_20260915/protocol.example.json` | Stage schema, matched controls and rho gate; map new receipts to these contracts when running comparisons. |

The axes are **hypotheses motivated by these components**. A combination is
not asserted to run merely because its pieces appear in different programs.
In particular, the current native Boolean F5B backend is bounded to 12
variables, whereas the illustrative N131 `m=5,d=28` leaf encoding alone has
140 Boolean coordinates. Existing N131 full-DLP code paths and bounded
materialization controls do not bridge that gap. The `bw` matrix option is
likewise an algorithm proposal, not a measured backend in this catalog.
Paths beginning `crypto:` refer to the sibling `crypto` repository. The
measurement PR includes the small source snapshots needed to replay its toy,
N131 base, and SAT receipts under `experiments/shifted-base-geometry/`,
`experiments/factor-base-yield-v2/`, `experiments/factor-base-yield/`,
`experiments/nonfrobenius-ic/`, and `ecc2k130/codegen/`. The bundled
[`N53 receipt`](measurements/2026-09-25/n53_prior_receipt.json) lets catalog
checks run without the sibling checkout; the generator checks an additional
N131 receipt when that separate file is available.
The [measurement protocol](MEASUREMENT.md) defines activation, stage costs,
comparison cells, and promotion gates.

Future run receipts follow [`measurement_contract.json`](measurement_contract.json).
`analyze.py` validates exclusive phase operation counts and produces a
per-configuration, per-workload stage summary. Given `--baseline IC1... --candidate IC1...`,
it pairs independent blocks on the same frozen one-target workload and reports
online wall-time speedup only when **every** pair finished with a verified
scalar and exact online timing. Cold operation speedup is supplementary when
all phases are priced. It preserves incomplete pairs and leaves the online
speedup `null`.
For example:

```sh
python3 experiments/ic-candidate-catalog/analyze.py runs.jsonl \
  --baseline IC1baseline --candidate IC1challenger
```

## Isogeny links

[`isogeny_routes.json`](isogeny_routes.json) is a graph registry: exact curve
nodes, explicit directed edges, and ordered routes through edge IDs. An edge
can be marked `verified` only with a map artifact, kernel certificate, and
subgroup transport certificate. A verified route must be contiguous and join
its declared endpoints. The two retained `search_only` records request degree-2
and degree-3 exploration; they have no edges or target curve. Their 200
proposals are blocked from final candidate IDs and IC-versus-rho comparisons.
The [exact small-degree screen](../koblitz-polynomial-w-pair-20260925/ecc2k130_small_isogeny_gate.json)
and [independent Sage replay](../koblitz-polynomial-w-pair-20260925/ecc2k130_small_isogeny_gate_sage_replay.json)
now rule out these specific searches as routes to a different isomorphism
class: the degree-2 quotient is source-isomorphic, and no degree-3 kernel is
rational. The registry keeps the original search-only records as proposal
history, with no invented edge or map. The [Lucas-factor extension](../koblitz-polynomial-w-pair-20260925/ecc2k130_first_new_isogeny_degree.json)
finds degree **263** as the first prime degree with a new rational kernel
over `GF(2^131)`; its [Sage replay](../koblitz-polynomial-w-pair-20260925/ecc2k130_first_new_isogeny_degree_sage_replay.json)
checks the factorization and kernel-line count. An [explicit degree-263 map,
dual, curve pair, and transport certificate](../koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json)
now support verified route `IW1E263d1hadee4e69fa3d` in the registry.
The [independent Sage replay](../koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_isogeny_sage_replay.json)
checks both cyclic kernels and dual composition. This adds a verified
isogeny route, not an `IC1` candidate: the codomain has no exact factor
base, PDP, relation matrix, recovered target, or paired rho comparison.
Record endomorphism-order conductors and prime-specific volcano levels on
each exact curve when proved; unknown stays `null`.
The [volcano naming rule](VOLCANO_NAMING.md) gives each proved position a
prime-specific level alias and each verified ordered route its own walk ID.
It also reserves degree-2 edges over the binary field as characteristic-prime
isogenies without a conventional `2`-volcano up/down label.

## Choosing what to run

Screen the 1,000 proposals in stages rather than launch 1,000 complete DLPs.
First materialize and replay factor bases, then benchmark PDPs on identical
ordinary and planted-control corpora. Advance only variants with verified
output and enough uncensored solves to estimate yield. Compare collection
policies on the same ordinary streams and frozen row-space checkpoints.
Build the final relation matrix and target descent only for survivors. N131
and isogeny cells require their explicit feasibility and route gates before
expensive runs. Preserve every rejected and censored proposal in the catalog.
