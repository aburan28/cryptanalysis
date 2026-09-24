# Index-calculus candidate catalog

This directory contains **1,000 design proposals**, not 1,000 measured attacks.
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
The 50 ms budget comes from the shifted-base solver smoke; 1,000 ms is a
prospective screening cap, not an observed performance result.

## Evidence-linked profiles

| Profile | Field | Factor base and arity | Evidence state |
| --- | ---: | --- | --- |
| `n13_same_d3_m4` | N13 | **fb6**, two folded columns, same three-dimensional base, m=4 | Chained-S3 SAT smoke: zero verified relations in 32 ordinary queries at 50 ms per solve. |
| `n19_shifted_d3_m5` | N19 | **fb30** across five disjoint six-point shifts, two folded columns, m=5 | Exact support geometry only; solver and useful rank costs remain open. |
| `n53_retained_m5` | N53 | Retained 23,320-point signed base, 220 folded columns, m=5 proposal | The representative-key hash and counts are replayed from a public synthetic N53 receipt; this PDP combination has not been measured. |
| `n131_poly_d7_m4` | N131 | Polynomial subspace d=7, **fb26**, m=4 | Bounded planted-query and matrix audit; no natural full-width DLP recovery. |
| `n131_onb_hw2_m4` | N131 | Normal-basis Hamming weight ≤2, m=4 | Construction code exists; exact base count for this proposal is unresolved. |
| `n131_onb_hw3_m5` | N131 | Normal-basis Hamming weight ≤3, m=5 | Construction code exists; exact base count for this proposal is unresolved. |
| `n131_poly_d28_m5` | N131 | Polynomial subspace d=28, m=5 | Illustrative large-base budget in PDP scaling; full-width factor base and end-to-end costs unmeasured. |
| `n131_poly_d24_m6` | N131 | Polynomial subspace d=24, m=6 | Same status; the bounded materialization ledger admitted no degree-131 candidate. |
| `n131_iso2_d28_m5` | N131 | Proposed degree-2 isogeny search, codomain d=28, m=5 | Search only: no explicit map or codomain base. |
| `n131_iso3_d28_m5` | N131 | Proposed degree-3 isogeny search, codomain d=28, m=5 | Search only: no explicit map or codomain base. |

`N131` is the field degree for ECC2K-130; its subgroup order has 130 bits.
`fb6`, `fb30`, `fb23320`, and `fb26` count distinct usable points before orbit
folding. The N13 and N19 point lists are frozen in
[`toy_base_anchors.json`](toy_base_anchors.json); `fb30` is the **union** of
five distinct six-point bases, not six points in each PDP slot. The
N53 count is tied to a retained receipt with representative-key BLAKE3
`d859319015ea405fd18aee41b51396ce4edcab64ef66265d8edcdeb5e040eb71`.
That digest covers the folded representative keys, not the full 23,320-point
set; a complete factor-base point digest is still required for a final ID.
The N131 `fb26` count is tied to the encoded point list in
`experiments/nonfrobenius-ic/results/ecc2k130-run01.json`.
Neither count licenses copying that base to another curve, isogeny codomain,
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
Paths beginning `crypto:` refer to the sibling `crypto` repository; several
other experiment trees are present in this workspace but are not part of the
current published base branch. The generator works without those trees and
checks the pinned N53/N131 receipt hashes whenever the files are available.
The [measurement protocol](MEASUREMENT.md) defines activation, stage costs,
comparison cells, and promotion gates.

Future run receipts follow [`measurement_contract.json`](measurement_contract.json).
`analyze.py` validates exclusive phase operation counts and produces a
per-configuration, per-workload stage summary. Given `--baseline IC1... --candidate IC1...`,
it pairs independent blocks on the same frozen workload and reports a complete
DLP speedup only when **every** pair finished with a verified scalar and every
phase priced. It preserves incomplete pairs and leaves the speedup `null`.
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
its declared endpoints. The two current `search_only` records request degree-2
and degree-3 exploration; they have no edges or target curve. Their 200
proposals are blocked from final candidate IDs and IC-versus-rho comparisons.
Record endomorphism-order conductors and prime-specific volcano levels on
each exact curve when proved; unknown stays `null`.

## Choosing what to run

Screen the 1,000 proposals in stages rather than launch 1,000 complete DLPs.
First materialize and replay factor bases, then benchmark PDPs on identical
ordinary and planted-control corpora. Advance only variants with verified
output and enough uncensored solves to estimate yield. Compare collection
policies on the same ordinary streams and frozen row-space checkpoints.
Build the final relation matrix and target descent only for survivors. N131
and isogeny cells require their explicit feasibility and route gates before
expensive runs. Preserve every rejected and censored proposal in the catalog.
