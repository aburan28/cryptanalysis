import Lean

namespace N83OrderedLeaves

variable {G : Type} [Add G]

def fourSum (a b c d : G) : G := ((a + b) + c) + d

theorem swap12
    (comm : ∀ x y : G, x + y = y + x)
    (a b c d : G) :
    fourSum a b c d = fourSum b a c d := by
  simp only [fourSum]
  rw [comm a b]

theorem swap23
    (assoc : ∀ x y z : G, (x + y) + z = x + (y + z))
    (comm : ∀ x y : G, x + y = y + x)
    (a b c d : G) :
    fourSum a b c d = fourSum a c b d := by
  simp only [fourSum]
  calc
    ((a + b) + c) + d = (a + (b + c)) + d := by rw [assoc a b c]
    _ = (a + (c + b)) + d := by rw [comm b c]
    _ = ((a + c) + b) + d := by rw [← assoc a c b]

theorem swap34
    (assoc : ∀ x y z : G, (x + y) + z = x + (y + z))
    (comm : ∀ x y : G, x + y = y + x)
    (a b c d : G) :
    fourSum a b c d = fourSum a b d c := by
  simp only [fourSum]
  calc
    ((a + b) + c) + d = (a + b) + (c + d) := assoc (a + b) c d
    _ = (a + b) + (d + c) := by rw [comm c d]
    _ = ((a + b) + d) + c := (assoc (a + b) d c).symm

#print axioms swap12
#print axioms swap23
#print axioms swap34

end N83OrderedLeaves
