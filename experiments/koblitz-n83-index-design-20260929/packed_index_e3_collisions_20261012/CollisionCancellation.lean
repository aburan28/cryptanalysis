import Lean

namespace N83Collision

variable {G : Type} [Add G] [Sub G] [Zero G]

-- A duplicated ordered pair contributes the zero difference row.
theorem same_pair_cancels
    (cancel : ∀ a : G, a - a = 0) (p q : G) :
    (p + q) - (p + q) = 0 := by
  exact cancel (p + q)

-- Reversing the two leaves also contributes the zero difference row.
theorem swapped_pair_cancels
    (comm : ∀ a b : G, a + b = b + a)
    (cancel : ∀ a : G, a - a = 0) (p q : G) :
    (p + q) - (q + p) = 0 := by
  rw [comm p q]
  exact cancel (q + p)

#print axioms same_pair_cancels
#print axioms swapped_pair_cancels

end N83Collision
