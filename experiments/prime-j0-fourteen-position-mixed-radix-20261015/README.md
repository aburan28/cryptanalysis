# Ordered fourteen-position prime-norm scalar format

The fixed `371−τ` fourteen-position native evaluator measured **1.0200× sustained hot-table throughput** against the fifteen-position `268−τ` format on a frozen same-point Tier 1 panel. All 96 arms and 48 pairs verified, every adjacent A/A control passed [0.90,1.11], and the repeat-bootstrap interval was **[1.0167,1.0237]** on this allocation. Its direct point payload is 22,313,920 bytes and its retained native table is 26,035,988 bytes. The ordered schedule `394−τ, 380−τ, 380−τ, (371−τ)×11` reduces the exact direct point payload to **22,267,136 bytes**; its native execution remains to be measured.

| Evidence | Artifact |
| --- | --- |
| Exact 50-prime-norm fixed sweep, four-start coordinate search, radius and orbit counts | [`screen14.py`](screen14.py), [`screen14.json`](screen14.json) |
| Integer reversal and independent affine secp256k1 replay on 164 scalars | [`replay14.py`](replay14.py), [`replay14.json`](replay14.json) |
| Conditional ordered-radix radius theorem and axiom audit | [`OrderedPrimeNorm14Bound.lean`](OrderedPrimeNorm14Bound.lean), [`check_lean14.sh`](check_lean14.sh), [`lean-check.log`](lean-check.log) |
| Fixed `371−τ` native timing gate | [`native371_overlay.py`](native371_overlay.py), [`linux-test.log`](linux-test.log), [`linux-build.log`](linux-build.log), [`linux-preflight.stdout`](linux-preflight.stdout), [`tier1-fixed14-rules.json`](tier1-fixed14-rules.json), [`tier1-fixed14-manifest.json`](tier1-fixed14-manifest.json) |
| Complete 14-versus-15 Tier 1 panel and independent A/A audit | [`3a7f28ad0dfa4444bf3b141421ccba16`](3a7f28ad0dfa4444bf3b141421ccba16), [`radix136531-panel.tar.gz`](radix136531-panel.tar.gz), [`analyze_fixed14_tier1.py`](analyze_fixed14_tier1.py), [`tier1-fixed14-analysis.json`](tier1-fixed14-analysis.json) |

The fixed sweep covers `T=300…600` with prime norm `T²−3T+3`. For each of the 50 rows, the screen enumerates every residue, chooses the minimum-score six-candidate digit, checks sign and six-unit covariance, and counts the terminal lattice and orbit seeds exactly. Four coordinate descents from uniform `T∈{371,380,394,400}` use prime-norm choices in `330…430` and preserve all four local outcomes in the JSON. The selected schedule is the smallest found by that declared local search; no global optimum over ordered schedules is asserted.

The replay uses the pinned 128-scalar fixture and 36 fresh or boundary scalars. It reverses all fourteen quotient steps exactly, checks the scalar's τ-eigenvalue relation, and compares the point assembled from the fourteen window bases and terminal base with independent binary multiplication on every scalar. The largest observed terminal norm is 37,363, below the proven bound `200²`.

Lean 4.34.1 checks the polynomial norm identity for a variable radix, the fourteen exact radius inequalities, and `OrderedPrimeNorm14.selected_terminal_bound`: for the canonical integer-scalar lattice representative, any fourteen radix steps whose digits meet the recorded per-position norm bounds finish with norm below `200²`. The `#print axioms` audit uses only `propext`, `Classical.choice`, and `Quot.sound`. A full selected-digit certificate for each of the three distinct radices and the concrete secp256k1 point-action bridge remain the next formalization steps; the finite screen and affine replay cover those implementations computationally.

| Result | Lean declaration | Hypotheses and verification |
| --- | --- | --- |
| Variable radix norm identity | `OrderedPrimeNorm14.radix_norm_identity` | All integer `t,x,y`; checked |
| Fourteen radius inequalities | `OrderedPrimeNorm14.numeric_checks` | Exact ordered schedule and digit radii; checked |
| Selected initial state to terminal radius | `OrderedPrimeNorm14.selected_terminal_bound` | Canonical scalar representative, exact fourteen radix recurrences, stated per-position digit norm bounds; checked |
| Chosen-digit admissibility | Candidate-specific theorem pending | Exact selector checked for all residues by `screen14.py`; Lean certificate pending |
| Concrete point action | Candidate-specific theorem pending | 164 independent affine point replays passed |

The fixed `371−τ` native evaluator tests fourteen positions before changing the table structure to support the ordered schedule. A hash-guarded overlay of the checked 15-position Rust source passed the exhaustive 136,531-residue test and the 128-case independent binary point holdout. The standalone 96-pass preflight verified all 12,288 outputs and recorded resource diagnostics. The paired panel then ran sixteen alternating repetitions on the same 128 frozen points, with reference/reference controls immediately before and after each comparison. The archive SHA-256 is `36d1056993d52c1e267d0e271647835f0865327de2892faf0f97016c4a3ccf8c`.

| Frozen Tier 1 result, 12,288 scalars per arm | Fixed 14-position `371−τ` | Reference 15-position `268−τ` |
| --- | ---: | ---: |
| Mean online interval per arm | 135.822 ms | 138.354 ms |
| Mean online time per scalar | 11.053 μs | 11.259 μs |
| Mean preparation | 3,953.993 ms | 2,103.098 ms |
| Retained native bytes | 26,035,988 | 12,336,756 |

The paired median reference/candidate online ratio is **1.020033**, with repeat-bootstrap 95% interval **[1.016715,1.023710]**. The exact online interval is Rust `Instant` around 96 passes over the same 128 point multiplications and affine recovery after table preparation; all outputs were checked after that interval. This is a sustained hot-table throughput result on one cloud allocation. It does not transfer to one-call latency or the unimplemented ordered schedule. The physical host isolation requirements of Tier 0 were not established by this Pod.
