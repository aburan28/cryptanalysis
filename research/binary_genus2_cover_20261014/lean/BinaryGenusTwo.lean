import Lean

/- No external dependencies. This proves the characteristic-two equation
   theorem, including its nonzero-denominator hypothesis. It does not define
   smooth projective curves, genus, Picard pullback, or Jacobians. -/
namespace BinaryGenusTwo

open Lean.Grind

variable {K : Type} [Field K] [IsCharP K 2]

theorem cleared_map_identity (u v a : K) :
    (u * (u+1) * v + u^2+u+1)^2
      + u^3*(u+1)*(u*(u+1)*v+u^2+u+1)
      + u^9 + a*u^6*(u+1)^2 + (u+1)^6
    = u^2*(u+1)^2*(v^2+u^2*v+u^5+a*u^4+u^3+u) := by
  grind

theorem map_affine_point (u v a : K)
    (hu : u+1 ≠ 0)
    (hc : v^2+u^2*v = u^5+a*u^4+u^3+u) :
    let t := (u+1)⁻¹
    let x := u^3*t^2
    let y := (u*(u+1)*v+u^2+u+1)*t^3
    y^2+x*y = x^3+a*x^2+1 := by
  have ht := Field.mul_inv_cancel hu
  dsimp
  grind

theorem image_constants_recover_point (x y : K) :
    (x, (x+y+1)+x+1) = (x,y) := by
  apply Prod.ext
  · rfl
  · grind

#print axioms cleared_map_identity
#print axioms map_affine_point
#print axioms image_constants_recover_point

end BinaryGenusTwo
