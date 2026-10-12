# Q1506 proof map

The central algebraic implication is checked in Lean 4:

| Mathematical statement | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| The model expression `K(r−1)(10B)/(4(B(B+1)/2))` simplifies to `5K(r−1)/(B+1)` | `Q1506.scan_work_identity` | rational `B≠0`, `B+1≠0` | checked |
| If all usable points lie in full signed-Frobenius orbits, `B=2nK`, the expression equals `(5(r−1)/(2n))·B/(B+1)` | `Q1506.full_orbit_scan_work` | previous nonzero hypotheses, `n≠0`, `B=2nK` | checked |

The readable proof cancels the nonzero `B` and the two factors of two in
the unordered-pair denominator, leaving `5K(r−1)/(B+1)`. Substituting
`K=B/(2n)` gives the second identity. The factor `B/(B+1)` is near one
for the recorded bases, explaining the nearly equal work exponents.

The declaration names and statement are in [ScanWork.lean](lean/ScanWork.lean).
The [proof receipt](lean/proof_receipt.json) pins Lean
`v4.35.0-rc4`, Mathlib revision
`021c46bdd042f67b538b9f9871d556a93713a9a9`, the source and built
`.olean` hashes, command, exit code, and `#print axioms` output. The module
built successfully. Both declarations use only `propext`, `Classical.choice`,
and `Quot.sound`; neither contains `sorry`, `admit`, custom research axioms,
or native evaluation. `lean4checker` was unavailable.

The probability step is an explicit model assumption: for an independently
chosen fixed first x-pair and a uniform nonidentity target, each of the
four signed complements can hit at most `B(B+1)/2` unordered signed-base
second-pair sums, so both the union bound on any match and the linearity
bound on expected unordered-pair matches are `4·B(B+1)/(2(r−1))`. The
expected-match bound permits multiple raw x-key hits in one scan. This finite
group sum-set counting statement and its query-independence premise are not
encoded in `ScanWork.lean`; formalization of that bridge is open. The
`B=262K` values for W5/W6 are checked against their exact base receipts.
For W7/W8, `B=262K` is part of the conditional projection-count method,
and no exact enumerated-set theorem is claimed.
