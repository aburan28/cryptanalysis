# Q1528 proof map

The central substitution removes every shared AND output variable from
Q1519's chained-S3 Boolean circuit and replaces each occurrence in an XOR
row with its quadratic monomial. The conversion is exact because no gate
output occurs inside another gate or in a retained CNF clause. The
converter checks both conditions on each frozen input.

| Result | Lean declaration | Hypotheses | Status |
| --- | --- | --- | --- |
| Three Tseitin clauses define `z = a AND b` | `Q1528.gate_equivalence` | arbitrary Boolean gate values, including signed literal values passed as `a` and `b` | checked |
| Eliminating one gate preserves any surrounding Boolean condition | `Q1528.eliminate_gate` | an arbitrary predicate `rest` of the gate output | checked |
| Replacing a gate output by its monomial preserves XOR evaluation | `Q1528.xor_substitution` | `z = a AND b`, arbitrary XOR remainder | checked |

The declarations are in [Eliminate.lean](lean/Eliminate.lean). The
[proof receipt](lean/proof_receipt.json) pins Lean 4 `v4.35.0-rc4`, the
source and output hashes, and the exact command. All three `#print axioms`
checks report no axioms. The module uses Lean core only, with no `sorry`,
`admit`, `sorryAx`, custom axiom, or native evaluation. `lean4checker` was
unavailable. Two initial failed Lean drafts are retained with their
diagnostics; the final module builds successfully.

The implementation bridge checks all 2,809 N53 or 41,251 N83 gate triples,
asserts that gate outputs occur only in XOR rows, renumbers exactly the
surviving variables, and reconstructs every eliminated gate from any solver
model. The validator compares each archived ANF row to its original clause
or XOR row under four assignments, byte-compares regenerated formulas,
and replays any positive solver model against the complete original XCNF
and curve group. The formalization is about Boolean circuit equivalence;
it does not assert an ordinary relation rate or an N131 solver bound.
