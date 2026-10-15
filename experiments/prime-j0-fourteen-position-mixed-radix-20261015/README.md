# Ordered fourteen-position prime-norm scalar format

The ordered radix schedule `394−τ, 380−τ, 380−τ, (371−τ)×11` reduces the direct point payload to **22,267,136 bytes** while retaining fourteen scalar positions. Its terminal lattice radius is 200 and contains 145,045 lattice points, or 24,175 sign-and-unit orbit seeds. The 323,749 digit orbit seeds and terminal seeds sum to 347,924 stored affine points. In the declared fixed-radix sweep, `371−τ` is the smallest 14-position point payload at 22,313,920 bytes; ordering the radices saves 46,784 bytes. The comparison is an exact table-shape result, with native timing as the next measurement.

| Evidence | Artifact |
| --- | --- |
| Exact 50-prime-norm fixed sweep, four-start coordinate search, radius and orbit counts | [`screen14.py`](screen14.py), [`screen14.json`](screen14.json) |
| Integer reversal and independent affine secp256k1 replay on 164 scalars | [`replay14.py`](replay14.py), [`replay14.json`](replay14.json) |
| Conditional ordered-radix radius theorem and axiom audit | [`OrderedPrimeNorm14Bound.lean`](OrderedPrimeNorm14Bound.lean), [`check_lean14.sh`](check_lean14.sh), [`lean-check.log`](lean-check.log) |

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
