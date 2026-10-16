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

/-- A rotated parent and a precomputed Q or tau(Q) power produce a valid
edge when the six-unit action agrees on coefficient and curve points. -/
theorem extend_unit_edge {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (unitPair : Pair → Pair) (unitPoint : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_unit : ∀ x, evaluate (unitPair x) = unitPoint (evaluate x))
    (vertices : List (Pair × Point)) (parent step : Pair) (parentPoint : Point)
    (valid : ValidGraph evaluate vertices)
    (parent_mem : (parent,parentPoint) ∈ vertices) :
    ValidGraph evaluate
      ((pairAdd (unitPair parent) step,
        add (unitPoint parentPoint) (evaluate step)) :: vertices) := by
  intro coefficient point member
  simp only [List.mem_cons] at member
  rcases member with head | tail
  · cases head
    rw [valid parent parentPoint parent_mem, ← map_unit]
    exact (map_add (unitPair parent) step).symm
  · exact valid coefficient point tail

/-- The two-parent fallback forms a requested coefficient as a sum of two
earlier unit rotations, again with one group addition. -/
theorem extend_unit_sum {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (leftUnit rightUnit : Pair → Pair)
    (leftPoint rightPoint : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_left : ∀ x, evaluate (leftUnit x) = leftPoint (evaluate x))
    (map_right : ∀ x, evaluate (rightUnit x) = rightPoint (evaluate x))
    (vertices : List (Pair × Point))
    (left right : Pair) (leftValue rightValue : Point)
    (valid : ValidGraph evaluate vertices)
    (left_mem : (left,leftValue) ∈ vertices)
    (right_mem : (right,rightValue) ∈ vertices) :
    ValidGraph evaluate
      ((pairAdd (leftUnit left) (rightUnit right),
        add (leftPoint leftValue) (rightPoint rightValue)) :: vertices) := by
  intro coefficient point member
  simp only [List.mem_cons] at member
  rcases member with head | tail
  · cases head
    rw [valid left leftValue left_mem, valid right rightValue right_mem,
        ← map_left, ← map_right]
    exact (map_add (leftUnit left) (rightUnit right)).symm
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
#print axioms extend_unit_edge
#print axioms extend_unit_sum
#print axioms four_neighbor_steps

end JointSeedGraph
