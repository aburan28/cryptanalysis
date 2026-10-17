import RotatedRadixStep

namespace Radix4033

open HornerRadix RotatedRadixStep

/-- Hexagonal norm in the basis (1, τ), with τ² = 3τ - 3. -/
def norm (x : Pair) : Int := x.1*x.1 + 3*x.1*x.2 + 3*x.2*x.2

/-- π = 65 - τ = 64 + ω. -/
def radix : Pair := (65, -1)

theorem radix_norm : norm radix = 4033 := by
  decide

/-- Matrix of multiplication by 65 - τ. -/
def mulRadix (x : Pair) : Pair := (65*x.1 + 3*x.2, -x.1 + 62*x.2)

theorem adjugate_first (x : Pair) :
    62*(mulRadix x).1 - 3*(mulRadix x).2 = 4033*x.1 := by
  simp [mulRadix]
  omega

theorem adjugate_second (x : Pair) :
    (mulRadix x).1 + 65*(mulRadix x).2 = 4033*x.2 := by
  simp [mulRadix]
  omega

/-- The congruence used by the digit selector suffices for exact quotient
construction. This is the structural bridge from a selected digit to a valid
next lattice state. -/
theorem exact_quotient (a b k : Int) (h : a + 65*b = 4033*k) :
    mulRadix (62*k-b, k) = (a,b) := by
  apply Prod.ext
  · simp [mulRadix]
    omega
  · simp [mulRadix]
    omega

theorem radix_as_rotation (x : Pair) :
    pairAdd (pairScale 64 x) (omegaPair x) =
      pairSub (pairScale 65 x) (tauPair x) := by
  apply Prod.ext
  · simp [pairAdd, pairScale, omegaPair, pairSub, tauPair]
    omega
  · simp [pairAdd, pairScale, omegaPair, pairSub, tauPair]
    omega

#print axioms radix_norm
#print axioms adjugate_first
#print axioms adjugate_second
#print axioms exact_quotient
#print axioms radix_as_rotation

end Radix4033
