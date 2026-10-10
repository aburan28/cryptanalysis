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
| `n131_poly_d24_m6` | N131 | Polynomial subspace d=24, m=6 | One exact trace-zero W24 policy has 16,786,464 source or 16,772,828 first-descendant usable points. Its [source W24/m6 SAT control](../ecc2k130-w24-natural-pdp-20261005/RESULT.md) hit 100,002 conflicts unpinned; [witness localization](../ecc2k130-w24-natural-pdp-20261005/DIAGNOSTIC_RESULT.md) verified SAT only with both inverse and intermediate values pinned. The [functional S3 follow-up](../ecc2k130-w24-functional-s3-20261006/RESULT.md) did not pass the bounded planted solver gate and has an independently verified satisfying XCNF assignment. The natural target was not run. Natural yield and a complete IC run remain unmeasured. Other d24 bases remain unresolved. |
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

The [degree-263 order and two-summand screen](../ecc2k130-263-endo-degree-20261008/RESULT.md)
proves the descendant's smallest nonscalar endomorphism degree is 121,046
and gives an exact 1% uniform-target two-sum threshold of
3,689,348,814,741,910,323 usable points. Even a fully closed 262-point
orbit policy needs at least 14,081,484,025,732,483 columns at that
threshold. This focuses the four-policy experiment on the higher-arity
PDP and priced transported action, using the frozen actual-base inputs.

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
The [exact source/descendant W24 m6 circuit gate](../ecc2k130-263-native-w24-m6-20261010/RESULT.md)
now instantiates the same Q1420 public point on both equal-size bases. An
independent checked-Sage and Boolean replay certifies their four raw target
lifts, degree-263 transport, native leaf equations, and balanced S3 controls.
Both native-XOR CryptoMiniSat cells at the precommitted 120-second cap ended
`BOUNDED_UNKNOWN` after 753,756 source and 757,597 descendant conflicts;
the [audit](../ecc2k130-263-native-w24-m6-20261010/runs/R1/audit.json)
binds exact formulas, solver transcripts, resource receipts, and source/input
hashes. The next gate is chart-complete point/sign decoding on the same
public point before opening more target queries. Q1420 remains a proposal
with `candidate_id: null` and no measured relation rank.
The [projective-S3 Q1420 gate](../ecc2k130-263-projective-s3-20261010/RESULT.md)
now supplies that chart extension for identity intermediates. Its homogeneous
equation matches the rational group law on 497,084 exhaustively checked
small-field x-class triples, and checked Sage plus independent Boolean
evaluation certify cancellation branches on both N131 curves. Exact paired
projective source/descendant XCNFs add 26,129/26,630 variables over the
finite parent formulas; guarded 120-second CryptoMiniSat cells ended
`BOUNDED_UNKNOWN` after 148,225/303,145 conflicts. The
[independent audit](../ecc2k130-263-projective-s3-20261010/runs/R1/audit.json)
binds lossless formulas, controls, raw solver transcripts, failures, and
resource receipts. The next gate is a full SAT solve of the archived
cancellation witness with sign decoding and group replay, followed by a
matched ordinary-query chart comparison. Q1420 remains a proposal with
natural relation yield and rank unset.
The [full-SAT exceptional-control gate](../ecc2k130-263-projective-s3-sat-20261010/RESULT.md)
then solves the archived cancellation witness on both curves and independently
checks every ordinary clause, native XOR, decoded intermediate x class, leaf
sign, and exact group target. The two one-bit target mutations return explicit
UNSAT. Fixing only the six leaf masks instead gives `BOUNDED_UNKNOWN` at the
120-second internal cap on both curves. The
[archive-only replay](../ecc2k130-263-projective-s3-sat-20261010/runs/R1/audit.json)
separates the complete fixed-witness correctness result from the remaining
search gap; natural relation yield and rank remain unset.
The [paired block-isolation result](../ecc2k130-263-projective-s3-blocks-20261010/RESULT.md)
does so on both curves using the exact parent control XCNFs: leaving only the
four projective states or only the six leaf x/z pairs free gives active search
but `BOUNDED_UNKNOWN` at the 150-second external cap in all four cells.
The [independent replay](../ecc2k130-263-projective-s3-blocks-20261010/runs/R1/audit.json)
checks the input partition, source/binary hashes, archived transcripts, and
printed restart progress. This favors a sign-lift/projective-addition encoding
test plus a frozen ordinary query; it does not establish natural yield or rank.
The [single-block frontier](../ecc2k130-263-projective-s3-frontier-20261010/RESULT.md)
then releases one leaf x/z pair or one projective state at a time from that
same exceptional witness. On both curves, leaf 0 and leaf 5 each reached the
120-second internal cap with `BOUNDED_UNKNOWN` and 782,430–955,100 final
conflicts, while state 0 and state 3 each returned independently verified
SAT group models with 0–13 conflicts. The [archive-only audit](../ecc2k130-263-projective-s3-frontier-20261010/runs/R1/audit.json)
checks all eight exact inputs, raw solver transcripts, clauses, native XORs,
and signed point sums. This moves the next encoding test to the leaf inverse
constraints: split x-only and z-only releases before selectively changing
either subcircuit. These are witness diagnostics on the Q1420 W24 bases;
equal-B ordinary-query yield and rank remain open, with `candidate_id: null`.
The [single-coordinate leaf frontier](../ecc2k130-263-leaf-inverse-frontier-20261010/RESULT.md)
keeps that exceptional witness fixed while freeing only `x` or only `z` at
leaf 0 or leaf 5 on both curves. Only leaf-0 `x` returned verified SAT under
the frozen cap; the other six cells were `BOUNDED_UNKNOWN` after 768,859 to
1,063,899 final conflicts. Both SAT models exactly recall the archived
duplicate first pair and identity intermediate, so the fast branch adds no
new relation row. The [audit](../ecc2k130-263-leaf-inverse-frontier-20261010/runs/R1/audit.json)
checks exact inputs, transcripts, XCNF, and group sums. Next isolate leaf
inverse propagation with a six-distinct-leaf finite-state witness before a
selective encoding change. Ordinary-query yield and rank remain unmeasured.
The [finite six-distinct S3 control](../ecc2k130-263-distinct-s3-control-20261010/RESULT.md)
replaces that cancellation fixture with the six archived native-W24 leaves
on each curve. Sage and the independent binary group law verify distinct
fourfold subgroup projections, finite intermediates, five S3 links, and the
exact raw-sum control target. Fixed positive/bit-flipped negative SAT
controls pass on both curves; all eight x0/z0/x5/z5 single-coordinate
releases reach `BOUNDED_UNKNOWN` with live restart progress under the frozen
120/150-second limits. The
[archive audit](../ecc2k130-263-distinct-s3-control-20261010/runs/R1/audit.json)
reconstructs all twelve inputs and checks every SAT clause, XOR, and signed
group sum. This supports treating the earlier half-second x0 model as a
fixture-specific recall rather than evidence of easy x-leaf inversion. Next
compare an exact selector-weighted bilinear encoding of the W24 leaf
inverse equations on
these same inputs before opening another ordinary-query gate.
The [selector-weighted W24 leaf comparison](../ecc2k130-263-bilinear-leaf-20261010/RESULT.md)
completed that gate on both curves. With the same six finite-state witnesses,
the sparse `w*z` rewrite returned fully audited SAT for source z0/z5 and
descendant z0, while both-product rewriting additionally returned SAT for
descendant z5; the parent circuit had eight bounded coordinate releases.
All x0/x5 cells remain `BOUNDED_UNKNOWN`. The first rewrite adds about 3.5%
total XCNF constraints and the second adds 32–33%; positive/negative
controls and all 24 solver inputs pass archive replay. Since selectors stay
fixed in these cells, the SAT assignments reconstruct the archived relation
and measure leaf propagation. Next compare the smaller `w*z` rewrite and
parent on frozen ordinary queries with all selectors free, recording verified
relation yield and novel rank before promoting a candidate ID.
The [functional W24/m6 solver gate](../ecc2k130-w24-functional-s3-20261006/RESULT.md)
removed free inverse and S3-intermediate witnesses but enlarged the planted
XCNF 20.448-fold; CryptoMiniSat timed out at 30 seconds while an independent
full-clause/XOR certificate and Sage group replay proved that exact planted
formula satisfiable. This is a bounded solver-stage result only. It favors
smaller algebraic or target-adaptive PDP formulations before another N131
ordinary-query attempt, without ranking the four frozen factor-base policies.

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
The [normal-basis barrel gate](../ecc2k130-w24-normal-barrel-20261006/RESULT.md)
now supplies a checked 8-layer exponent-selector circuit and both full
conversion matrices for that implicit W24/m5 proposal. Its 120 round trips
and 1,200 Frobenius rotations pass independent Sage replay, but the five-leaf
front end alone costs 5,240 muxes and 49,115 direct conversion XORs. The
exponent-range constraint and complete Boolean/Semaev solver remain absent;
there is no ordinary PDP yield or target-online result.
The [unknown-witness orbit-closed W24/m5 SAT gate](../ecc2k130-orbit-w24-m5-sat-20261006/RESULT.md)
then built a complete 142,303-variable native-XOR formula from five hidden
seed masks and exponents. The frozen planted target's known witness satisfies
every archived clause and XOR row, but CryptoMiniSat returned
`INDETERMINATE` after 100,001 conflicts without a model. The ordinary
single-target gate remained closed. This is a bounded failure of that SAT
encoding, not a natural-yield estimate or a no-go for other PDP methods.
The [first-leaf Frobenius-gauge follow-up](../ecc2k130-orbit-w24-m5-gauge-20261006/RESULT.md)
added exactly eight unit clauses to the byte-matched parent XCNF. An
independent row check confirms the archived planted witness still satisfies
the formula, yet CryptoMiniSat recovered no unknown witness at either
100,000 or 2,000,000 conflicts. The ordinary-query gate therefore remains
closed; prioritize a structurally different, bounded implicit PDP screen
over further expansion of this exact SAT encoding.

The [Q1421 normal-weight-four source-base result](../ecc2k130-normal-weight4-base-20261009/RESULT.md)
replays all 89,440 cyclic orbits of 11,716,640 weight-four field parameters
on the exact polynomial-basis ECC2K-130 source curve. It finds 44,824
rational orbits, no in-base reciprocal pairs, `B=11,743,888` actual usable
subgroup points, and `K=44,824` potential signed-Frobenius columns. Checked
Sage independently matches every count and digest and verifies sampled group
and Frobenius actions. Both frozen count gates pass; the next test is a
matched ordinary-query six-summand PDP comparison at equal `B` of Q1421
against the four Q1420 geometries. The [protocol](../ecc2k130-normal-weight4-base-20261009/PROTOCOL.md)
and result remain proposal `Q1421` with `candidate_id: null` until the full
pipeline is specified and measured.

The [Q1420/Q1421 equal-B six-policy input gate](../ecc2k130-normal4-equalb-m6-20261010/PROTOCOL.md)
fixes `B=11,743,888` for source W24, transported W24, descendant-native
W24, its pullback, normal4 source, and transported normal4. It binds the
verified degree-263 route and Q1420 one-target public point, specifies
deterministic W24 mask prefixes and 65,536 target-independent ordinary
queries, and requires checked-Sage point/map replay before a paired
six-summand PDP screen. The [verified input result](../ecc2k130-normal4-equalb-m6-20261010/RESULT.md)
records both W24 prefix digests, all 256 fixed point/map controls, a matched
65,536-query source/descendant public-point stream with independent checked-Sage
replay, and the bound one-target point. Its
[configuration](../ecc2k130-normal4-equalb-m6-20261010/CONFIG.json)
retains `candidate_id: null` while PDP, rank, final matrix, and target stages
are pending.

The [exact equal-B source-leaf m6 gate](../ecc2k130-equalb-m6-leaf-circuit-20261010/RESULT.md)
now constructs matched native-XOR six-summand circuits for source W24 and
normal4 with two multiplication equations and one trace equation per exact
rational leaf. Checked Sage replays all 192 frozen source-point controls and
both planted six-point chains; pinned SAT positive/negative controls also
pass. On the first frozen ordinary public query, both CryptoMiniSat attempts
entered search and reached their 150-second external cap with
`BOUNDED_UNKNOWN` status. The checked order-four torsion witness gives four
distinct raw x-target lifts of the same projected `[4]Q` relation. The next
paired gate must charge all four lifts per query and compare independently
verified relations and novel rank, with this exact circuit as its control.
This is a PDP-stage proposal with `candidate_id: null`.

The [exact four-lift equal-B m6 gate](../ecc2k130-equalb-four-lift-pdp-20261010/RESULT.md)
puts all four checked raw x-preimages of one projected ordinary query into
one native-XOR formula for each source geometry. Four SAT and four UNSAT
target-mux controls and independent Sage lift replay pass. Both W24 and
normal4 entered CryptoMiniSat search and returned `BOUNDED_UNKNOWN` at the
frozen internal cap; the raw conflict and restart counts are retained. An
exact restriction of the verified W24 orbit map gives 5,869,878 potential
source columns at the common `B=11,743,888`, versus 44,824 for normal4.
This prioritizes a verified ordinary normal4 relation/rank gate with a W24
control while preserving all target-dependent attempts and the final-matrix
cost. The complete IC pipeline remains an unactivated proposal.

The [balanced-S3 equal-B m6 gate](../ecc2k130-equalb-balanced-s3-20261010/RESULT.md)
reorganizes those six exact leaves into three pair sums and a final two-link
tree. Independent checked Sage replay passes both planted point chains and
Boolean-root controls. Each all-lift formula saves 1,030 variables, 131
ordinary clauses, and 899 native XORs against the target-first circuit.
The normal4 and W24 ordinary-query searches both entered live search and
reached their frozen external wall cap with `BOUNDED_UNKNOWN`; raw restart
tables and independent audits distinguish this from a solver launch failure.
The static reduction is small, so the next PDP gate compares exact four-hot
encodings of normal4's weight-four supports, with W24 retained as a paired
reference. Verified ordinary relations and novel rank remain the promotion
measure; `candidate_id` is still `null`.

The [normal4 selector gate](../ecc2k130-normal4-support-index-20261010/RESULT.md)
corrects the support-position width to eight bits and compares both an exact
four-threshold counter and four ordered support indices against the frozen
balanced formula. Checked Sage passes 128 frozen points and a position-130
leaf; 11 native-XOR SAT controls pass. The counter saves 93,654 variables
(17.451%) and 181,914 ordinary clauses (30.320%) in the full m6 formula,
without adding XORs. Its formula is smaller than the support-index formula
in all three XCNF dimensions. Both ordinary query-zero searches reached the
150-second external guard with `BOUNDED_UNKNOWN` and independent live-search
audits. The counter becomes the normal4 circuit baseline, while relation
yield and rank remain unmeasured; held-out N131 four-policy prefixes await a
relation-producing PDP. The next independent gates are the degree-263
exceptional-input transport proof and charged n53 compact-orbit recovery.

The [equal-B Gaussian-matrix gate](../ecc2k130-equalb-gauss-gate-20261010/RESULT.md)
replayed the exact normal4-counter and W24-balanced four-lift query under
matched CryptoMiniSat default and raised Gaussian limits. The raised limit
admitted 8,262-by-13,084 components and recorded active elimination, while
peak RSS rose 3.6–3.9-fold and all four guarded searches remained
`BOUNDED_UNKNOWN`. The first sandboxed launch is preserved as four
`PRODUCER_FAILURE` rows; the corrected R2 launch and independent raw-log
audit are linked from the result. That observation motivated the controlled
two-versus-five matrix-count gate below. `candidate_id` remains `null`
pending verified relations and rank.

The [two-repeat Gaussian matrix-count result](../ecc2k130-equalb-gauss-count-20261010/RESULT.md)
kept those exact XCNFs, four raw lifts of public query zero, large
row/column limits, solver binary, and resource caps fixed. Two/five paired
sampled-RSS ratios were 0.695 and 0.473 for normal4, and 0.614 and 0.525
for W24. All eight cells reached the external guard with `BOUNDED_UNKNOWN`;
W24/two printed positive elimination calls once, while normal4/two had no
elimination summary, leaving the full activity gate unresolved. The next
separately frozen gate is a longer single-Q0 normal4/two run with a complete
five-matrix control. The held-out 16/256-query screen remains gated on a
verified ordinary relation or an independently justified solver-policy change.

The [80,000-conflict normal4 follow-up](../ecc2k130-equalb-normal4-long-20261010/RESULT.md)
resolved that activity observation: the two-matrix cell printed `108K`
elimination calls on an 8,262-by-13,084 component. The five-matrix control
printed the same calls on that component and `2039` on one additional
component. Both ended naturally at the conflict budget with
`BOUNDED_UNKNOWN`, and their 282 printed restart rows were identical. Peak
sampled RSS was 774.641 versus 1,267.250 MiB (two/five ratio 0.611277).
These single-query stage results motivate a component-aware Gaussian
selection test; the held-out relation-yield and rank gate remains closed.

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
