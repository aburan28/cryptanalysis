import HornerRadix

namespace DigitGraph

open HornerRadix

/-- The signed lattice displacement from a constructed digit to its target. -/
def displacement (parent target : Pair) : Pair :=
  (target.1 - parent.1, target.2 - parent.2)

theorem parent_plus_displacement (parent target : Pair) :
    pairAdd parent (displacement parent target) = target := by
  apply Prod.ext
  · simp [pairAdd, displacement]
    omega
  · simp [pairAdd, displacement]
    omega

/-- Any point evaluation preserving pair addition can extend a digit graph
from a previously constructed parent by synthesizing its displacement. -/
theorem mapped_graph_edge {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (parent target : Pair) :
    add (evaluate parent) (evaluate (displacement parent target)) =
      evaluate target := by
  rw [← map_add, parent_plus_displacement]

/-- The direct root edge is available for every target. -/
theorem root_displacement (target : Pair) :
    displacement (0, 0) target = target := by
  apply Prod.ext
  · simp [displacement]
  · simp [displacement]

#print axioms parent_plus_displacement
#print axioms mapped_graph_edge
#print axioms root_displacement

end DigitGraph
