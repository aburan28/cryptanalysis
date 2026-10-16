import Secp256k1TauNormalize

namespace Secp256k1TauDenominator

open Secp256k1TauNormalize

def delta : Int := 1 - b
def deltaInv : Int :=
  95726251374320761238742457667059549483641973848656450766897893332520091975194

/-- The concrete prime parameter is 15 modulo 28. -/
theorem prime_mod_28 : p % 28 = 15 := by decide

/-- The fixed coefficient of the native tau denominator is a unit modulo p. -/
theorem delta_inverse_mod : (delta * deltaInv) % p = 1 := by decide

/-- The native projective denominator factors through the affine x coordinate. -/
theorem denominator_factor (x : Int) : w x = delta * x := by
  simp [w, Secp256k1TauFormula.denominator, delta, Int.sub_mul]

/-- The native tau denominator vanishes exactly at x = 0 modulo p. -/
theorem denominator_zero_iff_x_zero (x : Int) :
    w x % p = 0 ↔ x % p = 0 := by
  constructor
  · intro hw
    calc
      x % p = ((delta * deltaInv) * x) % p := by
        rw [Int.mul_emod, delta_inverse_mod]
        simp [Int.mul_emod]
      _ = (w x * deltaInv) % p := by
        rw [denominator_factor]
        congr 1
        ac_rfl
      _ = 0 := by
        rw [Int.mul_emod, hw]
        simp
  · intro hx
    rw [denominator_factor, Int.mul_emod, hx]
    simp

/-- On y² = x³+7, a point with zero tau denominator has y² = 7.
This isolates the exceptional-locus question from the coordinate formulas. -/
theorem zero_denominator_curve_locus (x y : Int)
    (hcurve : (y*y-(x*x*x+7))%p=0)
    (hw : w x%p=0) : (y*y-7)%p=0 := by
  have hx := (denominator_zero_iff_x_zero x).mp hw
  have hcube : (x*x*x)%p=0 := by
    simp [Int.mul_emod, hx]
  have hrewrite : y*y-7 = (y*y-(x*x*x+7))+x*x*x := by omega
  rw [hrewrite, Int.add_emod, hcurve, hcube]
  simp

#print axioms prime_mod_28
#print axioms delta_inverse_mod
#print axioms denominator_factor
#print axioms denominator_zero_iff_x_zero
#print axioms zero_denominator_curve_locus

end Secp256k1TauDenominator
