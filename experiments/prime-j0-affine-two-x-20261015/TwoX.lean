import Lean

namespace TwoX

-- The field additive laws are explicit hypotheses so this file uses the
-- repository's pinned Lean toolchain without an external algebra dependency.
theorem recover_rotated_x
    {F : Type} (add sub : F → F → F) (neg : F → F) (zero : F)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (zero_add : ∀ a, add zero a = a)
    (add_neg : ∀ a, add a (neg a) = zero)
    (sub_def : ∀ a b, sub a b = add a (neg b))
    (x beta_x beta2_x : F)
    (orbit : add (add x beta_x) beta2_x = zero) :
    sub (add x beta_x) x = beta_x ∧
      neg (add x beta_x) = beta2_x := by
  have neg_add : ∀ a, add (neg a) a = zero := by
    intro a
    rw [comm]
    exact add_neg a
  have add_zero : ∀ a, add a zero = a := by
    intro a
    rw [comm, zero_add]
  constructor
  · rw [sub_def, comm x beta_x, assoc, add_neg, add_zero]
  · calc
      neg (add x beta_x) = add (neg (add x beta_x)) zero := by
        rw [add_zero]
      _ = add (neg (add x beta_x)) (add (add x beta_x) beta2_x) := by
        rw [orbit]
      _ = add (add (neg (add x beta_x)) (add x beta_x)) beta2_x := by
        exact (assoc (neg (add x beta_x)) (add x beta_x) beta2_x).symm
      _ = beta2_x := by rw [neg_add, zero_add]

#print axioms recover_rotated_x
end TwoX
