import EisensteinResidue

namespace Secp256k1TauFormula

def rootPoly (b : Int) : Int := b*b+b+1
def denominator (b x : Int) : Int := x-b*x
def nativeX (x y : Int) : Int := 4*y*y-3*x*x*x
def nativeY (x y : Int) : Int := (3*x*x*x-2*nativeX x y)*y

/-- The native projective x numerator differs from the affine chord
formula's cross product by a multiple of the cube-root polynomial. -/
theorem x_cross (b x y : Int) :
    4*y*y-(1+b)*x*denominator b x*denominator b x-nativeX x y =
      (2-b)*rootPoly b*x*x*x := by
  simp only [denominator,nativeX,rootPoly]
  simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

/-- The native projective y numerator obeys the same chord formula. -/
theorem y_cross (b x y : Int) :
    (2*x*denominator b x*denominator b x-2*nativeX x y-
      denominator b x*denominator b x*denominator b x)*y-nativeY x y =
      (b-2)*rootPoly b*x*x*x*y := by
  simp only [denominator,nativeX,nativeY,rootPoly]
  simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

/-- The x numerator of the executed τ formula satisfies the affine
`P - ωP` chord equation modulo the secp256k1 field prime. -/
theorem native_x_chord_mod (x y : Int) :
    nativeX x y % EisensteinResidue.prime =
      (4*y*y-(1+EisensteinResidue.beta)*x*
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x) % EisensteinResidue.prime := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : nativeX x y-
      (4*y*y-(1+EisensteinResidue.beta)*x*
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x) =
      -((2-EisensteinResidue.beta)*rootPoly EisensteinResidue.beta*x*x*x) := by
    have h := x_cross EisensteinResidue.beta x y
    omega
  rw [hdiff]
  have hroot : rootPoly EisensteinResidue.beta % EisensteinResidue.prime = 0 := by
    simpa [rootPoly] using EisensteinResidue.beta_cubic
  obtain ⟨q,hq⟩ := (Int.dvd_iff_emod_eq_zero).mpr hroot
  rw [hq]
  apply (Int.dvd_iff_emod_eq_zero).mp
  refine ⟨-((2-EisensteinResidue.beta)*q*x*x*x), ?_⟩
  simp only [Int.mul_assoc,Int.mul_comm,Int.mul_left_comm,
             Int.mul_neg,Int.neg_mul]

/-- The y numerator of the executed τ formula satisfies the matching
affine chord equation modulo the secp256k1 field prime. -/
theorem native_y_chord_mod (x y : Int) :
    nativeY x y % EisensteinResidue.prime =
      ((2*x*denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x-2*nativeX x y-
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x)*y) % EisensteinResidue.prime := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : nativeY x y-
      ((2*x*denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x-2*nativeX x y-
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x*
        denominator EisensteinResidue.beta x)*y) =
      -((EisensteinResidue.beta-2)*rootPoly EisensteinResidue.beta*x*x*x*y) := by
    have h := y_cross EisensteinResidue.beta x y
    omega
  rw [hdiff]
  have hroot : rootPoly EisensteinResidue.beta % EisensteinResidue.prime = 0 := by
    simpa [rootPoly] using EisensteinResidue.beta_cubic
  obtain ⟨q,hq⟩ := (Int.dvd_iff_emod_eq_zero).mpr hroot
  rw [hq]
  apply (Int.dvd_iff_emod_eq_zero).mp
  refine ⟨-((EisensteinResidue.beta-2)*q*x*x*x*y), ?_⟩
  simp only [Int.mul_assoc,Int.mul_comm,Int.mul_left_comm,
             Int.mul_neg,Int.neg_mul]

#print axioms x_cross
#print axioms y_cross
#print axioms native_x_chord_mod
#print axioms native_y_chord_mod

end Secp256k1TauFormula
