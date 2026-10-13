# Q1531 proof map

Q1531 removes variables that occur only as linear terms by solving an
affine equation and substituting it into every remaining equation. The
solver sees a formula over the retained variables. A model is lifted through
the saved pivot rows in reverse order before the original ANF, XCNF,
elliptic-curve, and group-sum checks.

| Result | Lean declaration | Scope | Status |
| --- | --- | --- | --- |
| Existential elimination of one affine pivot | `Q1531.affine_existential_elimination` | arbitrary Boolean surrounding predicate `F`, pivot `x`, affine parity `p`, RHS `b` | checked |
| Negative literal normalization | `Q1531.signed_literal_normalization` | Boolean complement as XOR with true | checked |
| XOR row operation preserves a paired constraint | `Q1531.xor_row_replacement` | arbitrary Boolean rows `a`, `b` | checked |

The first theorem can be applied in pivot order because the converter
selects pivots absent from every nonlinear monomial and eliminates them
from all remaining rows. `project.py` checks the absence and saves a basis
for model reconstruction. The theorem does not formalize the complete
DIMACS parser, the 83-bit field, or the curve/group replay; those bridges
are checked by source hashing, deterministic formula regeneration, and
the pinned model's original Q1528 verifier. This formalization is partial
at the file-format and group bridge, while the structural projection
step itself is checked.

The [proof receipt](lean/proof_receipt.json) pins Lean 4.35.0-rc4 and
source/output hashes. `#print axioms` reports only standard Lean
`propext`/`Quot.sound` for the proposition equivalences and no axioms for
the literal identity. There are no custom axioms, sorry, or admits.
`lean4checker --fresh` was unavailable.
