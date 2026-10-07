# Index-calculus candidate catalog

[Curve and artifact storage](CURVE_STORAGE.md) and
[typed curve links](curve-links/README.md) explain the ICV1/EC1 crosswalk,
large factor bases, exact isogeny links, and explicit unknown trait statuses.
The [curve YAML](curves.yaml) is mirrored in crypto's `docs/curves/ic/`.

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

The [quotient-pair stage proposal registry](../ecc2k130-quotient-pair-probe-20260926/stage_proposals.json)
reserves `Q1001`–`Q1006` for a matched canonicalization comparison on exact
N53, N83, and N131 curves. These six records are separate from the generated
1,000-proposal design matrix. Their full IC collection, matrix, and target
descent stages remain unresolved; the [stage runs](../ecc2k130-quotient-pair-probe-20260926/stage_runs.jsonl)
have `candidate_id: null` and do not issue an `IC1` result.

## Evidence-linked profiles

| Profile | Field | Factor base and arity | Evidence state |
| --- | ---: | --- | --- |
| `n13_same_d3_m4` | N13 | **fb6**, two folded columns, same three-dimensional base, m=4 | Chained-S3 SAT smoke: zero verified relations in 32 ordinary queries at 50 ms per solve. |
| `n19_shifted_d3_m5` | N19 | **fb30** across five disjoint six-point shifts, two folded columns, m=5 | Exact support geometry only; solver and useful rank costs remain open. |
| `n53_retained_m5` | N53 | Retained 23,320-point signed base, 220 folded columns, m=5 proposal | The representative-key hash and counts are replayed from a public synthetic N53 receipt; this PDP combination has not been measured. |
| `n131_poly_d7_m4` | N131 | Polynomial subspace d=7, **fb26**, m=4 | Bounded planted-query and matrix audit; no natural full-width DLP recovery. |
| `n131_onb_hw2_m4` | N131 | Normal-basis Hamming weight ≤2, m=4 | Construction code exists; exact base count for this proposal is unresolved. |
| `n131_onb_hw3_m5` | N131 | Normal-basis Hamming weight ≤3, m=5 | Construction code exists; exact base count for this proposal is unresolved. |
| `n131_poly_d28_m5` | N131 | Polynomial subspace d=28, m=5 | One exact trace-zero W28 policy has 268,436,324 source or 268,465,880 first-descendant usable points and roughly 134 million sign-folded columns; natural m5 PDP yield and end-to-end costs remain unknown. |
| `n131_poly_d24_m6` | N131 | Polynomial subspace d=24, m=6 | One exact trace-zero W24 policy has 16,786,464 source or 16,772,828 first-descendant usable points, but no natural m6 PDP yield or complete IC run. Other d24 bases remain unresolved. |
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

The [exact ECC2K-130 degree-263 capacity gate](../ecc2k130-263-capacity-gate-20261004/RESULT.md)
puts necessary actual-base thresholds next to the `n131_poly_d28_m5` and
`n131_poly_d24_m6` proposals. At 1% one-shot uniform-target support, even
the collision-free multiset bound requires 60,591,280 points for m5 or
4,121,293 for m6. These are prerequisites, not actual `fb` counts or
measured relation yields. The gate leaves both proposals unactivated and
identifies actual `B`, orbit columns and held-out natural PDP/rank cost as
the next measurements.

The [exact paired W24 census](../ecc2k130-263-w24-exact-base-20261005/RESULT.md)
now supplies actual `B` and sign-folded columns for one explicit trace-zero
base on both source and first degree-263 descendant. Both pass the W24/m6
1% *necessary* size gate; neither has a measured ordinary-query yield or
rank. The same exact counts tighten the W24/m5 one-shot support upper bound
to about `1.63e-5`, below the 1% objective. The records remain proposals
with `candidate_id: null` until the missing stages and exact manifest are
resolved.

The [exact paired W28 census](../ecc2k130-263-w28-exact-base-20261005/RESULT.md)
now supplies actual `B` and sign-folded columns for the competing W28/m5
policy. Both curves pass its 1% *necessary* size threshold; the exact
descendant density gain is only +0.005505234 percentage points, far below
the predeclared two-point material-gain gate. The same counts bound W28/m4
one-shot uniform-target support near `3.18e-7`. At W28/m5, a raw
17-byte-per-column log vector would exceed 2.28 GB before matrix or solver
costs. These remain counting-only proposals with `candidate_id: null`.

The [equal-size W24 four-policy input gate](../ecc2k130-263-equal-w24-workload-20261005/RESULT.md)
freezes `Q1420` on the exact degree-263 route: source-prefix and native
descendant bases each have `B=16,772,828` before sign folding, and the
primary workload ID `eee7f6ee5f6b` contains exactly one target. Full mask
streams, sampled point maps, and public fixture scalars have independent
replays. Natural W24/m6 PDP yield, useful rank, and complete DLP costs remain
unmeasured; this is an input activation gate, not an `IC1` result.

The [equal-size W24 orbit-column audit](../ecc2k130-equal-w24-orbit-columns-20261005/RESULT.md)
restricts the full source Frobenius partition to the separately frozen
8,386,414-class source prefix. It saves only 2,066 potential columns
(0.0246351%). Checked Sage confirms the degree-263 native codomain has
`j != j²`, so direct coordinate Frobenius is not its endomorphism; any
transport-induced quotient still needs a priced implementation. This is
matrix geometry for proposal `Q1420`, not a PDP or IC speed result.

The [exact W24/m6 tuple-capacity screen](../ecc2k130-263-w24-mitm-capacity-20261005/RESULT.md)
parks a **full materialized raw-point** 2+4 pair index and 3+3 triple index
for all four equal-size policies under the 4-GiB envelope. Even a fictional
one-bit slot for each distinct-point tuple exceeds that memory by 4,094×
for pairs and 22,888,519,604× for triples. This is a count of enumeration
states, not distinct sums or an algebraic-solver lower bound. Implicit and
target-adaptive PDP methods, natural-query yield, and full-rank recovery
remain the active gates; `candidate_id` stays null.

The [degree-263 transport-cost stage](../ecc2k130-263-transport-cost-20261005/RESULT.md)
then checked 256 point maps on that frozen workload. The primary target's
forward and inverse route calls took 45.721 and 42.531 ms in the checked
Sage path on an unisolated host; these are stage observations, not complete
IC online times. Future four-policy PDP comparisons must charge the needed
target map and independently account for factor-base transport or pullback
construction. Source/transported and native/pullback preserve sum membership
exactly; only two base choices offer distinct yield hypotheses.

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
The [volcano naming rule](VOLCANO_NAMING.md) gives each proved position a
prime-specific level alias and each verified ordered route its own walk ID.
It also reserves degree-2 edges over the binary field as characteristic-prime
isogenies without a conventional `2`-volcano up/down label.

## Choosing what to run

The [exact W24 Frobenius-orbit scan](../ecc2k130-263-w24-orbit-columns-20261005/RESULT.md)
found only 2,066 potential column savings among 8,393,232 signed columns
of the original source base (0.0246151%). The source-transported copy has
the same group partition. Explicitly closing W24 under Frobenius would
instead form a different, mathematically 2,198,485,492-point base with
8,391,166 orbit representatives. The [seed-plus-exponent gate](../ecc2k130-orbit-closed-w24-seed-20261006/RESULT.md)
now verifies field-coordinate membership on 120 frozen controls and eight
cofactor-projected group controls, with exact operation counts. Arbitrary
subgroup-point recognition and m5 PDP/rank costs remain unmeasured. The
unchanged W24 quotient is deprioritized;
the orbit-closed W24/m5 policy remains a `candidate_id: null` proposal,
separate from both the original W24/m6 and W28/m5 policies.

The [preregistered cold full-rank one-target control](../ecc2k130-cold-fullrank-20261006/RESULT.md)
assigns canonical `IC1`/workload/run IDs to independently replayed n37 and n41
four-summand exact-support recoveries; its n53 cell is a preserved 180-second
timeout with no emitted target. On the unisolated host, corrected exclusive cold
costs were 556.629 ms (n37) and 28,308.249 ms (n41), while the n41 support
index alone cost 25,902.961 ms. The pinned producer's published online timer
double-counted final solving and solution validation; the archived verifier
recomputes exclusive phase costs. These are stage diagnostics, not controlled
speedups or evidence for n131. Next test a compact-orbit n53 support index with
streaming setup receipts and corrected producer timers before any cold claim.

Screen the 1,000 proposals in stages rather than launch 1,000 complete DLPs.
First materialize and replay factor bases, then benchmark PDPs on identical
ordinary and planted-control corpora. Advance only variants with verified
output and enough uncensored solves to estimate yield. Compare collection
policies on the same ordinary streams and frozen row-space checkpoints.
Build the final relation matrix and target descent only for survivors. N131
and isogeny cells require their explicit feasibility and route gates before
expensive runs. Preserve every rejected and censored proposal in the catalog.
