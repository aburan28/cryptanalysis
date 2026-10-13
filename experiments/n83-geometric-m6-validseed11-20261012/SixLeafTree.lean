import Lean

namespace N83SixLeaf

variable {G : Type} [Add G]

def leftSum (a b c d e f : G) : G := (((((a + b) + c) + d) + e) + f)

theorem pairTree_eq_leftSum
    (assoc : ∀ x y z : G, (x + y) + z = x + (y + z))
    (a b c d e f : G) :
    ((a + b) + (c + d)) + (e + f) = leftSum a b c d e f := by
  simp only [leftSum]
  calc
    ((a + b) + (c + d)) + (e + f)
        = (((a + b) + c) + d) + (e + f) := by
            rw [← assoc (a + b) c d]
    _ = ((((a + b) + c) + d) + e) + f := by
            rw [← assoc (((a + b) + c) + d) e f]

theorem s3_tree_group_sum
    (assoc : ∀ x y z : G, (x + y) + z = x + (y + z))
    (a b c d e f u0 u1 u2 u3 target : G)
    (h0 : u0 = a + b) (h1 : u1 = c + d) (h2 : u2 = e + f)
    (h3 : u3 = u0 + u1) (ht : target = u3 + u2) :
    target = leftSum a b c d e f := by
  rw [ht, h3, h0, h1, h2]
  exact pairTree_eq_leftSum assoc a b c d e f

#print axioms pairTree_eq_leftSum
#print axioms s3_tree_group_sum

end N83SixLeaf
