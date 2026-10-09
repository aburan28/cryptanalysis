# IC lead solver gates, 2026-10-08

At N53, a multiplier-closed factor base and Frobenius-quotiented pair index
recovered the frozen public target's discrete logarithm as
**6,141,872,670,687**. Checked Sage independently replayed the scalar on
the declared curve and verified the target's three-summand x-coordinate
witness. The 60 independent seed logs were solved from 111 verified ordinary
relations in 128 queries and independently replayed in Sage. At the same
63,600-point geometry, the seed-only base also gave 111 hits in 128 paired
queries but its relation matrix had 600 independent log columns.

The other decisions are a failed one-target symbolic F4 trace reuse test, a
degree-four obstruction for exact N23 cyclotomic-sparse membership, and an
augmentation obstruction for homogeneous sparse group-algebra S3 lifts.

All JSON receipts in this directory carry a source hash, input or prior-receipt
hashes, a frozen seed when sampling is involved, and `candidate_id: null`.
They record the research implementation and its component gates; a frozen
candidate manifest and matched isolated rho run are needed for a controlled
IC speed comparison. CPU times here are exploratory because no host-isolation
receipt accompanies these runs.
The checked Sage runtime is recorded in
[`sage_runtime_info.json`](sage_runtime_info.json). The preceding geometry,
rank, and lifting receipts are in
[`../ic-ideas-completion-20261008/README.md`](../ic-ideas-completion-20261008/README.md).

## Frozen N53 target stage

| Parameter or result | Recorded value |
| --- | --- |
| Curve ID | `EC1N53Ckb1h888961ed110e` |
| Field and curve | `F₂[z]/(z⁵³+z⁶+z²+z+1)`; `y²+xy=x³+1` |
| Subgroup | order `21,044,858,204,113`, cofactor `428` |
| Public target `Q=(x,y)` | `(7457337616192165, 7124961216379939)` in polynomial-basis bit encoding |
| Recovered `log_G Q` | `6,141,872,670,687`; independent Sage scalar replay and frozen fixture agree |
| Base and relation preparation | 63,600 usable points, 600 geometric columns, 60 independent seed logs; 111 verified rows in 128 ordinary queries gave rank 60 |
| Target decomposition | three factor-base points, 4,488 pair-index lookups; Rust signed group sum and independent Sage x-coordinate witness replay agree |
| Target-dependent interval, exploratory | `4.884333 ms` charged; query validation `0.100291`, PDP `4.650833`, relation check `0.051125`, log combination `0.024417`, scalar replay `0.057667` ms |
| Reusable pair-index build in this target process | `54.942 s`, outside the target-dependent interval; 19,020,826 distinct canonical x-orbit keys |
| Equal-geometry pair-index peak RSS | seed `585.974 MB`; closure `586.187 MB` in separate one-query processes, a `0.036%` difference |

The target point came from the frozen public-point list. Its known fixture
scalar was withheld from the relation and target-decomposition programs and
checked after recovery. See
[`a1_n53_target0_recovery.json`](a1_n53_target0_recovery.json),
[`a1_n53_target0_sage_verify.json`](a1_n53_target0_sage_verify.json), and
[`a1_n53_rank_replay.json`](a1_n53_rank_replay.json). The preparation and
target runs are separate exploratory processes, so their stage timings are
recorded individually rather than combined into a cold-start total.

## Lead decisions

| Lead | Measured or proved result | Decision and next gate |
| --- | --- | --- |
| G1 | The actual F4 producer learned 2 matrices / 26 symbolic multiples for N31, m=2, and 16 matrices / 1,357 multiples for m=3. Replay on the 16 frozen targets gave exact fresh-basis agreement on 10/16 and 2/16 respectively. Every completed replay passed exhaustive Boolean truth-set comparison; four selected fresh bases also passed independent algebraic certificates. | A single frozen symbolic reduction schedule is target-dependent. A union or adaptive trace needs a separate implementation and measured cost before trace reuse can be promoted. See [`g1_f4_symbolic.json`](g1_f4_symbolic.json), [`g1_f4_audit.json`](g1_f4_audit.json). |
| G2 | Degree-three character blocks reconstruct binary Macaulay ranks 8,399 at N19 and 14,767 at N23. The full invariant N19 barrel input has 191 generators on 57 Boolean variables; fresh F4 exhausted 50-million, 1-billion, and 5-billion native work caps. At N131, one dense nontrivial block has a 34.4 GB coefficient floor. | The cyclic row-space decomposition is exact at degree three. Block F4 needs a completed baseline and an implementation that preserves equivariance across symbolic preprocessing. See [`g2_f4_qualification.json`](g2_f4_qualification.json) and the prior block receipts. |
| G3 | N41 degree four has 2,017,933 rows, 100,315,659 ambient columns, and 247,444,987 nonzeros. A conventional 64-vector Wiedemann sequence would traverse 4-byte indices for about 124.8 TB. | The sampled matrix-free transpose check establishes operator consistency; the full sparse solve requires a stated storage and bandwidth design. The byte count is a conditional cost estimate, not a measured solve. See [`../ic-ideas-completion-20261008/g3_krylov_budget.json`](../ic-ideas-completion-20261008/g3_krylov_budget.json). |
| G4 | N19 rationality equations remove eight algebraic-closure false roots across twelve exhaustive cells. Checked Sage accepts the small extension-field example with `libsingular:std`; `msolve` reports the base field unsupported. | The mixed-field encoding has an exact rationality condition. A matched extension-field F4 backend is needed to measure the intended solver comparison. See [`g4_backend_gate.json`](g4_backend_gate.json) and the prior chain receipt. |
| A1 | N53 equal geometry gives 63,600 usable points in each arm. On the same 128 SplitMix64-derived nonzero subgroup queries, each base produced 111 verified triple hits. Paired outcomes: 94 both, 17 seed-only, 17 closure-only, 0 neither (exact two-sided p=1.0). The seed-only relation rank was 111/600; ten-class closure reached 60/60. Pair-index peak RSS was 585.974 versus 586.187 MB. Sage solved and replayed all 60 seed logs. Those logs and the pair index recovered and verified the frozen public target scalar 6,141,872,670,687. At N23 with 230 points per arm, five independent seed orbits yielded 156/256 hits versus 74/256 for the five-class closure. | The closure lowered the final relation-matrix dimension tenfold at equal N53 point count and essentially equal measured peak memory, reaching full rank in the frozen 128-query sequence. The paired hit sample showed equal yield. The original four-summand S3 index path hit a 600-second cap before one query completed; the direct pair index is a separate three-summand PDP method. See [`a1_n53_pair_comparison_128.json`](a1_n53_pair_comparison_128.json), [`a1_n53_rank_replay.json`](a1_n53_rank_replay.json), [`a1_n53_target0_sage_verify.json`](a1_n53_target0_sage_verify.json), [`a1_n53_memory_seed.json`](a1_n53_memory_seed.json), [`a1_n53_memory_closure.json`](a1_n53_memory_closure.json). |
| A2 | All 17,296 N23 sparse weight-two/three sums have distinct encodings. No nonzero degree-at-most-three Boolean polynomial vanishes on the entire family; the quartic vanishing space has dimension 3,289. An exhaustive pass over all 2²³ field elements found 53 false positives for the first 256 quartics. One more quartic rejects five; 48 values (0, 1, and two complete 23-element Frobenius orbits) satisfy every quartic vanishing on the family. | Degree-four equations cannot define this sparse factor base exactly in these coordinates. A degree-five or indexed membership encoding must be tested inside the PDP solver. See [`a2_full_quartic_audit.json`](a2_full_quartic_audit.json), [`a2_quartic_relations.json`](a2_quartic_relations.json). |
| N1 | S3 augmentation vanishes exactly when two of three leaf augmentations are one. Thus homogeneous weight-two or weight-three sparse sections cannot lift exactly. Among 128 valid mixed (2,3,3) identities, raw sparse sections lifted 0 times; fixing the first two leaves allowed an exact third lift in 64, whose minimum support was 15–29. | CRT lifting is exact but the sparse additive shortcut fails for these sections. A new lift would need to control the second CRT component and support simultaneously. See [`n1_parity_classes.json`](n1_parity_classes.json), [`n1_mixed_sparse_lifts.json`](n1_mixed_sparse_lifts.json). |

The N53 pair index enumerates unordered geometric orbit pairs, all 53 relative
Frobenius shifts, and both relative signs: 19,111,200 valid pair sums per arm.
It indexes canonical x-coordinate orbits. For each query, it searches
`Q − P₃` across the factor base, reconstructs the three points, checks their
sum on the curve, and inserts the verified weighted row over the prime
subgroup order. Across 128 paired ordinary queries, the seed arm made
2,149,763 lookups and closure made 1,908,500. Both 111/128 hit rates have
Wilson 95% interval [0.798, 0.915]. The first 64 queries are also preserved
as separate receipts: 56 seed hits and 57 closure hits, with all 113
x-coordinate witnesses independently replayed in Sage. The one-target stage
above then charges descent and scalar recovery on the frozen public point.
The N53 query law is precisely a SplitMix64 word reduced modulo `r−1`, plus
one; it has negligible modulo bias but is not an exact uniform sampler.

The G1 replay compares exact reduced bases only when both runs complete.
`trace-mismatch`, work-cap, and timeout statuses remain in the per-target
records. The A1 N23 queries are 256 frozen uniform known-scalar subgroup
points; the scalar is used to construct and verify a query, not to find its
factor-base decomposition. The original N53 S3-index stage uses the frozen
public target point and one relation worker; its 600-second cap includes base
construction, index construction, and attempted ordinary queries. Its two
frozen seed-policy attempts, with caps of 64 and 1 query, both timed out
before the first recorded query completion.

The preceding A2 matched-base comparison used 230 usable points per arm on
the same 16 planted N23 targets: the cyclotomic base had 8 three-summand
hits and the normal-basis Hamming-weight base had 11. Those controls test
coverage and correctness; the quartic audit here tests whether the sparse
family has a low-degree exact membership description.

## Reproducibility

Run `python3 experiments/ic-ideas-solver-gates-20261008/validate_results.py`
from the repository root to check receipt invariants, source hashes, and
compressed equation artifacts. New Sage jobs for this suite must use the
repository launcher, for example
`./sage -python experiments/ic-ideas-solver-gates-20261008/a2_full_quartic_audit.py`.
The drivers preserve existing outputs and require a fresh output location for
a rerun.
