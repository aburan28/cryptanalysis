import HornerRadix

namespace JointSeedGraph

open HornerRadix

/-- Each graph vertex stores the point represented by its Eisenstein
coefficient pair. The concrete curve bridge is the homomorphism premise. -/
def ValidGraph {Point : Type} (evaluate : Pair → Point)
    (vertices : List (Pair × Point)) : Prop :=
  ∀ coefficient point, (coefficient, point) ∈ vertices →
    point = evaluate coefficient

/-- A new vertex obtained from a previous vertex and a coefficient step
preserves the exact point represented by the graph. -/
theorem extend_edge {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (vertices : List (Pair × Point)) (parent step : Pair) (parentPoint : Point)
    (valid : ValidGraph evaluate vertices)
    (parent_mem : (parent, parentPoint) ∈ vertices) :
    ValidGraph evaluate
      ((pairAdd parent step, add parentPoint (evaluate step)) :: vertices) := by
  intro coefficient point member
  simp only [List.mem_cons] at member
  rcases member with head | tail
  · cases head
    rw [valid parent parentPoint parent_mem]
    exact (map_add parent step).symm
  · exact valid coefficient point tail

/-- A directly checked seed can be inserted into the same graph. -/
theorem extend_direct {Point : Type} (evaluate : Pair → Point)
    (vertices : List (Pair × Point)) (seed : Pair)
    (valid : ValidGraph evaluate vertices) :
    ValidGraph evaluate ((seed, evaluate seed) :: vertices) := by
  intro coefficient point member
  simp only [List.mem_cons] at member
  rcases member with head | tail
  · cases head
    rfl
  · exact valid coefficient point tail

/-- The four searched neighbors in the implementation are the two basis
directions and their negatives. -/
theorem four_neighbor_steps (a b : Int) :
    pairAdd (a-1,b) (1,0) = (a,b) ∧
    pairAdd (a,b-1) (0,1) = (a,b) ∧
    pairAdd (a+1,b) (-1,0) = (a,b) ∧
    pairAdd (a,b+1) (0,-1) = (a,b) := by
  simp [pairAdd]
  omega

#print axioms extend_edge
#print axioms extend_direct
#print axioms four_neighbor_steps

end JointSeedGraph
