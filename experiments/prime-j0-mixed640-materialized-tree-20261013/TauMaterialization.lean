import Lean

namespace PrimeJ0TauMaterialization

-- The hypotheses are the exact algebraic obligations for moving the
-- degree-three tau map from a bucket sum into the affine table entries.
def foldPoints {P : Type} (zero : P) (add : P → P → P) : List P → P
  | [] => zero
  | x :: xs => add x (foldPoints zero add xs)

theorem tau_fold {P : Type} (zero : P) (add : P → P → P) (tau : P → P)
    (tau_zero : tau zero = zero)
    (tau_add : ∀ x y, tau (add x y) = add (tau x) (tau y))
    (xs : List P) :
    tau (foldPoints zero add xs) = foldPoints zero add (xs.map tau) := by
  induction xs with
  | nil => simp [foldPoints, tau_zero]
  | cons x xs ih => simp [foldPoints, tau_add, ih]

theorem tau_unit_fold {P : Type} (zero : P) (add : P → P → P)
    (tau unit : P → P)
    (tau_zero : tau zero = zero)
    (tau_add : ∀ x y, tau (add x y) = add (tau x) (tau y))
    (commute : ∀ x, tau (unit x) = unit (tau x))
    (xs : List P) :
    tau (foldPoints zero add (xs.map unit)) =
      foldPoints zero add (xs.map (fun x => unit (tau x))) := by
  rw [tau_fold zero add tau tau_zero tau_add]
  congr 1
  induction xs with
  | nil => rfl
  | cons x xs ih => simp [commute, ih]

#print axioms tau_fold
#print axioms tau_unit_fold

end PrimeJ0TauMaterialization
