import Lean

namespace PrimeJ0OrbitCompression

-- The additive law is stated explicitly so this module needs no external algebra package.
-- In the intended field, beta is multiplication by a primitive cube root of unity.
theorem reconstruct_beta {A : Type} (add : A → A → A) (neg : A → A)
    (zero : A) (beta : A → A)
    (add_assoc : ∀ a b c, add (add a b) c = add a (add b c))
    (add_comm : ∀ a b, add a b = add b a)
    (add_zero : ∀ a, add a zero = a)
    (add_neg : ∀ a, add a (neg a) = zero)
    (x : A) :
    add (add x (beta x)) (neg x) = beta x := by
  calc
    add (add x (beta x)) (neg x)
        = add (add (beta x) x) (neg x) := by rw [add_comm x (beta x)]
    _ = add (beta x) (add x (neg x)) := add_assoc _ _ _
    _ = add (beta x) zero := by rw [add_neg x]
    _ = beta x := add_zero _

theorem reconstruct_beta_sq {A : Type} (add : A → A → A) (neg : A → A)
    (zero : A) (beta : A → A)
    (add_neg : ∀ a, add a (neg a) = zero)
    (add_left_cancel : ∀ a b c, add a b = add a c → b = c)
    (root_relation : ∀ a, add (add a (beta a)) (beta (beta a)) = zero)
    (x : A) :
    neg (add x (beta x)) = beta (beta x) := by
  apply add_left_cancel (add x (beta x))
  calc
    add (add x (beta x)) (neg (add x (beta x))) = zero := add_neg _
    _ = add (add x (beta x)) (beta (beta x)) := (root_relation x).symm

inductive JoinTree where
  | leaf : JoinTree
  | join : JoinTree → JoinTree → JoinTree

def leaves : JoinTree → Nat
  | .leaf => 1
  | .join a b => leaves a + leaves b

def affineChild : JoinTree → Int
  | .leaf => 1
  | .join _ _ => 0

-- A join consumes 6, 10, or 14 field-kernel calls according to whether
-- it has two, one, or zero affine children.
def joinWork : JoinTree → Int
  | .leaf => 0
  | .join a b => joinWork a + joinWork b + 14 -
                 4 * affineChild a - 4 * affineChild b

theorem join_work_formula (t : JoinTree) :
    joinWork t = 10 * (leaves t : Int) - 14 + 4 * affineChild t := by
  induction t with
  | leaf => simp [joinWork, leaves, affineChild]
  | join a b ha hb =>
      change joinWork a + joinWork b + 14 - 4 * affineChild a -
        4 * affineChild b = 10 * ((leaves a + leaves b : Nat) : Int) - 14 + 4 * 0
      rw [ha, hb]
      omega

theorem join_work_nonleaf (a b : JoinTree) :
    joinWork (.join a b) = 10 * (leaves (.join a b) : Int) - 14 := by
  simpa [affineChild] using join_work_formula (.join a b)

#print axioms reconstruct_beta
#print axioms reconstruct_beta_sq
#print axioms join_work_formula
#print axioms join_work_nonleaf

end PrimeJ0OrbitCompression
