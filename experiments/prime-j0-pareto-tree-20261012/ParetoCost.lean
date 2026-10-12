import Lean

namespace PrimeJ0ParetoCost

-- Every leaf is an affine table point. The join costs are the ordinary XYZZ
-- formula counts used by the source model: 6, 10, and 14 field products.
inductive Shape where
  | leaf
  | join (left right : Shape)

def leaves : Shape → Nat
  | .leaf => 1
  | .join left right => leaves left + leaves right

def leafFlag : Shape → Nat
  | .leaf => 1
  | .join _ _ => 0

def joinProducts (left right : Shape) : Nat :=
  match left, right with
  | .leaf, .leaf => 6
  | .leaf, .join _ _ => 10
  | .join _ _, .leaf => 10
  | .join _ _, .join _ _ => 14

def baseProducts : Shape → Nat
  | .leaf => 0
  | .join left right =>
      baseProducts left + baseProducts right + joinProducts left right

theorem joinProducts_identity (left right : Shape) :
    joinProducts left right + 4 * leafFlag left + 4 * leafFlag right = 14 := by
  cases left <;> cases right <;> simp [joinProducts, leafFlag]

theorem baseProducts_identity (shape : Shape) :
    baseProducts shape + 14 = 10 * leaves shape + 4 * leafFlag shape := by
  induction shape with
  | leaf => decide
  | join left right ihLeft ihRight =>
      have h := joinProducts_identity left right
      simp only [baseProducts, leaves, leafFlag, Nat.mul_zero, Nat.add_zero]
      omega

theorem joinedTree_cost (left right : Shape) (rotations : Nat) :
    baseProducts (.join left right) + rotations + 14 =
      10 * leaves (.join left right) + rotations := by
  have h := baseProducts_identity (.join left right)
  simp only [leafFlag, Nat.mul_zero, Nat.add_zero] at h
  omega

-- Replacing a subtree by one that uses no more work or depth cannot worsen
-- either coordinate of any parent join. This justifies Pareto pruning.
theorem dominatedSubtree_replacement
    (workFast depthFast workSlow depthSlow siblingWork siblingDepth
     joinCost leftRotation rightRotation : Nat)
    (hWork : workFast ≤ workSlow) (hDepth : depthFast ≤ depthSlow) :
    workFast + siblingWork + joinCost + leftRotation + rightRotation ≤
      workSlow + siblingWork + joinCost + leftRotation + rightRotation ∧
    max (depthFast + leftRotation) (siblingDepth + rightRotation) + joinCost ≤
      max (depthSlow + leftRotation) (siblingDepth + rightRotation) + joinCost := by
  constructor
  · omega
  · omega

#print axioms joinProducts_identity
#print axioms baseProducts_identity
#print axioms joinedTree_cost
#print axioms dominatedSubtree_replacement

end PrimeJ0ParetoCost
