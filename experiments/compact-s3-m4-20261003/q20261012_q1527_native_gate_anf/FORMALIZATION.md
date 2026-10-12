# Q1527 proof map

The converter replaces the three Tseitin clauses for each exact AND gate
with one native quadratic ANF equation. The solver's row convention is XOR
value one, so the emitted row `z XOR (a AND b) XOR 1 = 1` requires
`z = a AND b`, including signed input literals.

| Result | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| Three AND clauses hold exactly when `z = a AND b` | `Q1527.and_gate_equivalence` | arbitrary Boolean `a`, `b`, `z` | checked |
| Replacing this gate preserves any conjunctive surrounding constraint | `Q1527.replace_gate_in_context` | arbitrary Boolean context and gate values | checked |

The declarations are in [Gate.lean](lean/Gate.lean), pinned to Lean 4
`v4.35.0-rc4` with Lean core only. The [proof receipt](lean/proof_receipt.json)
records the build and source/output hashes. Both `#print axioms` checks
report no axioms. There is no `sorry`, `admit`, `sorryAx`, custom axiom, or
native evaluation; `lean4checker` was unavailable.

The converter independently regenerates and hash-checks each original
XCNF file, identifies every AND gate from its unique output variable,
checks that the three source clauses are contiguous and exact, then emits
one quadratic row. Non-gate clauses and XOR rows keep their Q1525
conversion. The validator checks the local gate truth table for every
instance and byte-compares each archived transformed formula against a
fresh conversion. These implementation checks bridge the Lean Boolean
identity to the exact emitted circuits. Solver model and elliptic-curve
checks are separate in the run receipts.
