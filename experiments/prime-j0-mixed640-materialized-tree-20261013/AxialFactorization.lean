import Lean

namespace PrimeJ0AxialFactorization

-- A selected digit is represented by its two coordinate-axis points.
-- The runtime accumulates those axes separately, then applies tau once.
def foldPoints {P : Type} (zero : P) (add : P → P → P) : List P → P
  | [] => zero
  | x :: xs => add x (foldPoints zero add xs)

theorem tau_fold {P : Type} (zero : P) (add : P → P → P) (tau : P → P)
    (tau_zero : tau zero = zero)
    (tau_add : ∀ x y, tau (add x y) = add (tau x) (tau y))
    (xs : List P) :
    tau (foldPoints zero add xs) =
      foldPoints zero add (xs.map tau) := by
  induction xs with
  | nil => simp [foldPoints, tau_zero]
  | cons x xs ih => simp [foldPoints, tau_add, ih]

theorem axial_fold {P : Type} (zero : P) (add : P → P → P)
    (tau : P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (left_zero : ∀ a, add zero a = a)
    (tau_zero : tau zero = zero)
    (tau_add : ∀ x y, tau (add x y) = add (tau x) (tau y))
    (rows : List (P × P)) :
    foldPoints zero add (rows.map (fun row => add row.1 (tau row.2))) =
      add (foldPoints zero add (rows.map Prod.fst))
          (tau (foldPoints zero add (rows.map Prod.snd))) := by
  have left_comm (a b c : P) :
      add a (add b c) = add b (add a c) := by
    rw [← assoc, comm a b, assoc]
  induction rows with
  | nil => simp [foldPoints, tau_zero, left_zero]
  | cons row rows ih =>
      cases row with
      | mk ordinary axis =>
          simp [foldPoints, ih, tau_add, assoc, left_comm]

theorem axial_scalar_fold {P : Type} (zero : P) (add : P → P → P)
    (tau : P → P) (smul : Int → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (left_zero : ∀ a, add zero a = a)
    (tau_zero : tau zero = zero)
    (tau_add : ∀ x y, tau (add x y) = add (tau x) (tau y))
    (tau_smul : ∀ n p, tau (smul n p) = smul n (tau p))
    (digits : List (Int × Int × P)) :
    foldPoints zero add (digits.map (fun (a, b, base) =>
      add (smul a base) (smul b (tau base)))) =
    add (foldPoints zero add (digits.map (fun (a, _, base) => smul a base)))
        (tau (foldPoints zero add (digits.map (fun (_, b, base) => smul b base)))) := by
  have h := axial_fold zero add tau assoc comm left_zero
    tau_zero tau_add
    (digits.map (fun (a, b, base) => (smul a base, smul b base)))
  simpa [List.map_map, Function.comp_def, tau_smul] using h

#print axioms tau_fold
#print axioms axial_fold
#print axioms axial_scalar_fold

end PrimeJ0AxialFactorization
