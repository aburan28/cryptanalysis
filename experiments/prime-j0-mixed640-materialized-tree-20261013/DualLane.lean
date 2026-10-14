import Lean

namespace PrimeJ0DualLane

-- The two runtime lanes receive alternating nonidentity selected points.
-- This statement is independent of the curve representation and covers
-- any number of selected points, including empty lanes.
def weave {P : Type} : List P → List P → List P
  | [], ys => ys
  | xs, [] => xs
  | x :: xs, y :: ys => x :: y :: weave xs ys

def split {P : Type} : List P → List P × List P
  | [] => ([], [])
  | x :: xs =>
      let (even, odd) := split xs
      (x :: odd, even)

def sum {P : Type} (zero : P) (add : P → P → P) : List P → P
  | [] => zero
  | x :: xs => add x (sum zero add xs)

theorem weave_cons_swap {P : Type} (x : P) (left right : List P) :
    weave (x :: left) right = x :: weave right left := by
  induction right generalizing x left with
  | nil => simp [weave]
  | cons y ys ih =>
      cases left with
      | nil => simp [weave]
      | cons z zs => simp [weave, ih]

theorem weave_split {P : Type} (xs : List P) :
    weave (split xs).1 (split xs).2 = xs := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
      cases h : split xs with
      | mk even odd =>
          simp only [split, h] at ih ⊢
          rw [weave_cons_swap]
          exact congrArg (List.cons x) ih

theorem sum_weave {P : Type} (zero : P) (add : P → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (left_zero : ∀ a, add zero a = a)
    (right_zero : ∀ a, add a zero = a)
    (xs ys : List P) :
    sum zero add (weave xs ys) =
      add (sum zero add xs) (sum zero add ys) := by
  have left_comm (a b c : P) :
      add a (add b c) = add b (add a c) := by
    rw [← assoc, comm a b, assoc]
  induction xs generalizing ys with
  | nil => simp [weave, sum, left_zero]
  | cons x xs ih =>
      cases ys with
      | nil => simp [weave, sum, right_zero]
      | cons y ys =>
          simp [weave, sum, ih, assoc, left_comm]

theorem dual_lane_sum {P : Type} (zero : P) (add : P → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (left_zero : ∀ a, add zero a = a)
    (right_zero : ∀ a, add a zero = a)
    (xs : List P) :
    sum zero add xs =
      add (sum zero add (split xs).1) (sum zero add (split xs).2) := by
  have h := sum_weave zero add assoc comm left_zero right_zero
    (split xs).1 (split xs).2
  rw [weave_split xs] at h
  exact h

theorem foldl_acc {P : Type} (zero : P) (add : P → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (right_zero : ∀ a, add a zero = a)
    (xs : List P) (acc : P) :
    xs.foldl add acc = add acc (sum zero add xs) := by
  induction xs generalizing acc with
  | nil => simp [sum, right_zero]
  | cons x xs ih =>
      simp [List.foldl, sum, ih, assoc]

theorem foldl_sum {P : Type} (zero : P) (add : P → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (left_zero : ∀ a, add zero a = a)
    (right_zero : ∀ a, add a zero = a)
    (xs : List P) :
    xs.foldl add zero = sum zero add xs := by
  rw [foldl_acc zero add assoc right_zero xs zero, left_zero]

theorem dual_lane_foldl {P : Type} (zero : P) (add : P → P → P)
    (assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (comm : ∀ a b, add a b = add b a)
    (left_zero : ∀ a, add zero a = a)
    (right_zero : ∀ a, add a zero = a)
    (xs : List P) :
    xs.foldl add zero =
      add ((split xs).1.foldl add zero) ((split xs).2.foldl add zero) := by
  rw [foldl_sum zero add assoc left_zero right_zero xs,
      foldl_sum zero add assoc left_zero right_zero (split xs).1,
      foldl_sum zero add assoc left_zero right_zero (split xs).2]
  exact dual_lane_sum zero add assoc comm left_zero right_zero xs

#print axioms weave_cons_swap
#print axioms weave_split
#print axioms sum_weave
#print axioms dual_lane_sum
#print axioms foldl_acc
#print axioms foldl_sum
#print axioms dual_lane_foldl

end PrimeJ0DualLane
