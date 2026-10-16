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

/-- A graph instruction is certified against the vertices already built.
Unit-edge instructions rotate both the stored parent and the shared power;
unit-sum instructions rotate both stored parents. -/
inductive CertifiedStep {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y)) :
    List (Pair × Point) → List (Pair × Point) → Prop where
  | direct (vertices : List (Pair × Point)) (seed : Pair) :
      CertifiedStep evaluate add map_add vertices
        ((seed, evaluate seed) :: vertices)
  | unitEdge (vertices : List (Pair × Point))
      (parent power : Pair) (parentValue : Point)
      (parentUnit powerUnit : Pair → Pair)
      (parentPointUnit powerPointUnit : Point → Point)
      (parent_mem : (parent, parentValue) ∈ vertices)
      (map_parent : ∀ x, evaluate (parentUnit x) = parentPointUnit (evaluate x))
      (map_power : ∀ x, evaluate (powerUnit x) = powerPointUnit (evaluate x)) :
      CertifiedStep evaluate add map_add vertices
        ((pairAdd (parentUnit parent) (powerUnit power),
          add (parentPointUnit parentValue)
              (powerPointUnit (evaluate power))) :: vertices)
  | unitSum (vertices : List (Pair × Point))
      (left right : Pair) (leftValue rightValue : Point)
      (leftUnit rightUnit : Pair → Pair)
      (leftPointUnit rightPointUnit : Point → Point)
      (left_mem : (left, leftValue) ∈ vertices)
      (right_mem : (right, rightValue) ∈ vertices)
      (map_left : ∀ x, evaluate (leftUnit x) = leftPointUnit (evaluate x))
      (map_right : ∀ x, evaluate (rightUnit x) = rightPointUnit (evaluate x)) :
      CertifiedStep evaluate add map_add vertices
        ((pairAdd (leftUnit left) (rightUnit right),
          add (leftPointUnit leftValue) (rightPointUnit rightValue)) :: vertices)

/-- Every certified instruction preserves the coefficient-to-point relation,
including instructions that construct auxiliary vertices. -/
theorem certifiedStep_valid {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    {before after : List (Pair × Point)}
    (step : CertifiedStep evaluate add map_add before after)
    (valid : ValidGraph evaluate before) : ValidGraph evaluate after := by
  cases step with
  | direct seed =>
      exact extend_direct evaluate _ seed valid
  | unitEdge parent power parentValue parentUnit powerUnit
      parentPointUnit powerPointUnit parent_mem map_parent map_power =>
      rw [← map_power power]
      exact extend_unit_edge evaluate add parentUnit parentPointUnit
        map_add map_parent _ parent (powerUnit power) parentValue
        valid parent_mem
  | unitSum left right leftValue rightValue leftUnit rightUnit
      leftPointUnit rightPointUnit left_mem right_mem map_left map_right =>
      exact extend_unit_sum evaluate add leftUnit rightUnit
        leftPointUnit rightPointUnit map_add map_left map_right
        _ left right leftValue rightValue valid left_mem right_mem

/-- A topological schedule is a sequence of certified instructions beginning
with an empty graph. Membership premises enforce parent-before-child order. -/
inductive CertifiedTrace {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y)) :
    List (Pair × Point) → Prop where
  | empty : CertifiedTrace evaluate add map_add []
  | extend {before after : List (Pair × Point)}
      (prior : CertifiedTrace evaluate add map_add before)
      (step : CertifiedStep evaluate add map_add before after) :
      CertifiedTrace evaluate add map_add after

/-- Every point in a certified topological graph, requested or auxiliary,
evaluates to its declared Eisenstein coefficient pair. -/
theorem certifiedTrace_valid {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    {vertices : List (Pair × Point)}
    (trace : CertifiedTrace evaluate add map_add vertices) :
    ValidGraph evaluate vertices := by
  induction trace with
  | empty =>
      intro coefficient point member
      simp at member
  | extend prior step ih =>
      exact certifiedStep_valid evaluate add map_add step ih

/-- Auxiliary vertices do not change the values of covered requested seeds.
The coverage premise is checked separately by the frozen-plan validator. -/
theorem requested_seed_values {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    {vertices : List (Pair × Point)}
    (trace : CertifiedTrace evaluate add map_add vertices)
    (requested : List Pair)
    (covers : ∀ seed, seed ∈ requested →
      ∃ value, (seed, value) ∈ vertices) :
    ∀ seed, seed ∈ requested →
      ∃ value, (seed, value) ∈ vertices ∧ value = evaluate seed := by
  intro seed member
  obtain ⟨value, in_graph⟩ := covers seed member
  exact ⟨value, in_graph,
    certifiedTrace_valid evaluate add map_add trace seed value in_graph⟩

/-- Selecting only requested vertices for affine normalization preserves
their certified values and excludes auxiliary coefficients from that batch. -/
theorem requested_projection {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    {vertices : List (Pair × Point)}
    (trace : CertifiedTrace evaluate add map_add vertices)
    (requested : List Pair)
    (covers : ∀ seed, seed ∈ requested →
      ∃ value, (seed, value) ∈ vertices) :
    let selected := vertices.filter (fun entry => decide (entry.1 ∈ requested))
    ValidGraph evaluate selected ∧
    (∀ seed, seed ∈ requested →
      ∃ value, (seed, value) ∈ selected ∧ value = evaluate seed) ∧
    (∀ coefficient value, (coefficient, value) ∈ selected →
      coefficient ∈ requested) := by
  dsimp
  have valid := certifiedTrace_valid evaluate add map_add trace
  constructor
  · intro coefficient value member
    exact valid coefficient value (List.mem_filter.mp member).1
  constructor
  · intro seed member
    obtain ⟨value, in_graph⟩ := covers seed member
    have in_selected : (seed, value) ∈
        vertices.filter (fun entry => decide (entry.1 ∈ requested)) := by
      apply List.mem_filter.mpr
      exact ⟨in_graph, by simpa using member⟩
    exact ⟨value, in_selected, valid seed value in_graph⟩
  · intro coefficient value member
    have chosen := (List.mem_filter.mp member).2
    simpa using chosen

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
#print axioms certifiedStep_valid
#print axioms certifiedTrace_valid
#print axioms requested_seed_values
#print axioms requested_projection
#print axioms four_neighbor_steps

end JointSeedGraph
