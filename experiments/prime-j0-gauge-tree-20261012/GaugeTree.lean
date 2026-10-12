import Lean

namespace PrimeJ0GaugeTree

inductive Gauge where
  | zero | one | two
  deriving DecidableEq

def rotate {G : Type} (beta : G → G) : Gauge → G → G
  | .zero, x => x
  | .one, x => beta x
  | .two, x => beta (beta x)

-- The stored point is changed to the target gauge before two subtrees join.
def align {G : Type} (beta : G → G) : Gauge → Gauge → G → G
  | .zero, .zero, x => x
  | .zero, .one, x => beta (beta x)
  | .zero, .two, x => beta x
  | .one, .zero, x => beta x
  | .one, .one, x => x
  | .one, .two, x => beta (beta x)
  | .two, .zero, x => beta (beta x)
  | .two, .one, x => beta x
  | .two, .two, x => x

theorem align_correct {G : Type} (beta : G → G)
    (beta_cube : ∀ x, beta (beta (beta x)) = x)
    (source target : Gauge) (x : G) :
    rotate beta target (align beta source target x) = rotate beta source x := by
  cases source <;> cases target <;> simp [rotate, align, beta_cube]

theorem rotate_add {G : Type} (add : G → G → G) (beta : G → G)
    (beta_add : ∀ x y, beta (add x y) = add (beta x) (beta y))
    (g : Gauge) (x y : G) :
    rotate beta g (add x y) = add (rotate beta g x) (rotate beta g y) := by
  cases g <;> simp [rotate, beta_add]

theorem join_correct {G : Type} (add : G → G → G) (beta : G → G)
    (beta_add : ∀ x y, beta (add x y) = add (beta x) (beta y))
    (beta_cube : ∀ x, beta (beta (beta x)) = x)
    (left right target : Gauge) (x y : G) :
    rotate beta target (add (align beta left target x)
                            (align beta right target y)) =
      add (rotate beta left x) (rotate beta right y) := by
  rw [rotate_add add beta beta_add, align_correct beta beta_cube,
      align_correct beta beta_cube]

inductive Plan (G : Type) where
  | leaf (gauge : Gauge) (point : G)
  | join (gauge : Gauge) (left right : Plan G)

def evaluate {G : Type} (add : G → G → G) (beta : G → G) :
    Plan G → Gauge × G
  | .leaf g x => (g, x)
  | .join g left right =>
      let a := evaluate add beta left
      let b := evaluate add beta right
      (g, add (align beta a.1 g a.2) (align beta b.1 g b.2))

def meaning {G : Type} (add : G → G → G) (beta : G → G) :
    Plan G → G
  | .leaf g x => rotate beta g x
  | .join _ left right => add (meaning add beta left) (meaning add beta right)

theorem evaluate_correct {G : Type} (add : G → G → G) (beta : G → G)
    (beta_add : ∀ x y, beta (add x y) = add (beta x) (beta y))
    (beta_cube : ∀ x, beta (beta (beta x)) = x)
    (plan : Plan G) :
    rotate beta (evaluate add beta plan).1 (evaluate add beta plan).2 =
      meaning add beta plan := by
  induction plan with
  | leaf g x => rfl
  | join g left right ih_left ih_right =>
      simp only [evaluate, meaning]
      rw [join_correct add beta beta_add beta_cube,
          ih_left, ih_right]

def leaves {G : Type} (beta : G → G) : Plan G → List G
  | .leaf g x => [rotate beta g x]
  | .join _ left right => leaves beta left ++ leaves beta right

def sumList {G : Type} (zero : G) (add : G → G → G) : List G → G
  | [] => zero
  | x :: xs => add x (sumList zero add xs)

theorem sum_append {G : Type} (zero : G) (add : G → G → G)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (zero_add : ∀ x, add zero x = x) (xs ys : List G) :
    sumList zero add (xs ++ ys) =
      add (sumList zero add xs) (sumList zero add ys) := by
  induction xs with
  | nil => simp [sumList, zero_add]
  | cons x xs ih =>
      simp only [List.cons_append, sumList]
      rw [ih, ← assoc]

theorem meaning_sum {G : Type} (zero : G) (add : G → G → G)
    (beta : G → G)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (zero_add : ∀ x, add zero x = x)
    (add_zero : ∀ x, add x zero = x) (plan : Plan G) :
    meaning add beta plan = sumList zero add (leaves beta plan) := by
  induction plan with
  | leaf g x => simp [meaning, leaves, sumList, add_zero]
  | join g left right ih_left ih_right =>
      simp only [meaning, leaves, sum_append zero add assoc zero_add]
      rw [ih_left, ih_right]

theorem sum_perm {G : Type} (zero : G) (add : G → G → G)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    {xs ys : List G} (perm : xs.Perm ys) :
    sumList zero add xs = sumList zero add ys := by
  induction perm with
  | nil => rfl
  | cons x _ ih => simpa [sumList] using congrArg (add x) ih
  | swap x y l =>
      simp only [sumList]
      calc
        add y (add x (sumList zero add l)) =
            add (add y x) (sumList zero add l) := (assoc y x _).symm
        _ = add (add x y) (sumList zero add l) := by rw [comm y x]
        _ = add x (add y (sumList zero add l)) := assoc x y _
  | trans _ _ ih_left ih_right => exact ih_left.trans ih_right

theorem reordered_tree_correct {G : Type} (zero : G)
    (add : G → G → G) (beta : G → G)
    (beta_add : ∀ x y, beta (add x y) = add (beta x) (beta y))
    (beta_cube : ∀ x, beta (beta (beta x)) = x)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (zero_add : ∀ x, add zero x = x)
    (add_zero : ∀ x, add x zero = x)
    (plan : Plan G) (source : List G)
    (same_leaves : (leaves beta plan).Perm source) :
    rotate beta (evaluate add beta plan).1 (evaluate add beta plan).2 =
      sumList zero add source := by
  rw [evaluate_correct add beta beta_add beta_cube,
      meaning_sum zero add beta assoc zero_add add_zero,
      sum_perm zero add assoc comm same_leaves]

#print axioms align_correct
#print axioms rotate_add
#print axioms join_correct
#print axioms evaluate_correct
#print axioms reordered_tree_correct

end PrimeJ0GaugeTree
