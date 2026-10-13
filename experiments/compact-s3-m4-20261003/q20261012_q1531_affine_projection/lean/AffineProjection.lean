/-!
Structural Boolean step used by Q1531: a variable that is absent from every
nonlinear monomial can be solved from an affine row and substituted into all
remaining equations. Repeating this theorem justifies sequential pivots.
-/

namespace Q1531

theorem affine_existential_elimination (p b : Bool) (F : Bool → Prop) :
    (∃ x, Bool.xor x p = b ∧ F x) ↔ F (Bool.xor p b) := by
  cases p <;> cases b <;> simp [Bool.xor]

theorem signed_literal_normalization (x : Bool) :
    (!x) = Bool.xor x true := by
  cases x <;> rfl

theorem xor_row_replacement (a b : Bool) :
    (a = false ∧ b = false) ↔ (a = false ∧ Bool.xor a b = false) := by
  cases a <;> cases b <;> simp [Bool.xor]

#print axioms affine_existential_elimination
#print axioms signed_literal_normalization
#print axioms xor_row_replacement

end Q1531
