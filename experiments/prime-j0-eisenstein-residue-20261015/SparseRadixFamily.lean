import SparseTauRadix

namespace SparseRadixFamily

open SparseTauRadix

def familyNorm (t : Int) : Int := 7*t*t - 5*t + 1

/-- Multiplication by `(t-1)+tτ` in the basis `(1,τ)`, where `τ²=3τ-3`. -/
def familyPair (t : Int) (x : Pair) : Pair :=
  ((t-1)*x.1-3*t*x.2,t*x.1+(4*t-1)*x.2)

/-- A power-of-two `t` makes the point action one `τ`, `log₂(t)` doublings,
two additions, and one negation. -/
theorem family_shortcut (t : Int) (x : Pair) :
    familyPair t x = pairSub (pairScale t (pairAdd x (tauPair x))) x := by
  apply Prod.ext
  · simp only [familyPair,pairSub,pairScale,pairAdd,tauPair,
               Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
               Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    grind
  · simp only [familyPair,pairSub,pairScale,pairAdd,tauPair,
               Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
               Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    grind

theorem family_norm (t : Int) :
    AlternateRadix.pairNorm (t-1) t = familyNorm t := by
  simp only [AlternateRadix.pairNorm,familyNorm,
             Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
             Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
  grind

/-- The quotient by `(t-1)+tτ` has the explicit root `τ = 4-7t`. -/
theorem family_residue (t : Int) :
    (t-1)+t*(4-7*t) = -familyNorm t := by
  simp only [familyNorm,Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

theorem family_residue_polynomial (t : Int) :
    (4-7*t)*(4-7*t) - 3*(4-7*t) + 3 = 7*familyNorm t := by
  simp only [familyNorm,Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

theorem family_norm_scaling (t : Int) (x : Pair) :
    AlternateRadix.pairNorm (familyPair t x).1 (familyPair t x).2 =
      familyNorm t * AlternateRadix.pairNorm x.1 x.2 := by
  simp only [familyPair,familyNorm,AlternateRadix.pairNorm,
             Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

#print axioms family_shortcut
#print axioms family_norm
#print axioms family_residue
#print axioms family_residue_polynomial
#print axioms family_norm_scaling

end SparseRadixFamily
