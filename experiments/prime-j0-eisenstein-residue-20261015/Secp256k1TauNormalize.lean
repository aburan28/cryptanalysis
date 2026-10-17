import Secp256k1TauFormula

namespace Secp256k1TauNormalize

open Secp256k1TauFormula

def p : Int := EisensteinResidue.prime
def b : Int := EisensteinResidue.beta
def w (x : Int) : Int := denominator b x

theorem inverse_square_mod (x inv : Int)
    (hinv : (w x*inv)%p=1) :
    (w x*w x*inv*inv)%p=1 := by
  calc
    (w x*w x*inv*inv)%p = ((w x*inv)*(w x*inv))%p := by
      congr 1
      ac_rfl
    _ = (((w x*inv)%p)*((w x*inv)%p))%p := by
      rw [Int.mul_emod]
    _ = 1 := by
      rw [hinv]
      decide

theorem inverse_square_times_mod (x inv : Int)
    (hinv : (w x*inv)%p=1) :
    (w x*w x*inv*inv*inv)%p=inv%p := by
  calc
    (w x*w x*inv*inv*inv)%p =
        (((w x*w x*inv*inv)%p)*(inv%p))%p := by
          rw [Int.mul_emod]
    _ = inv%p := by
      rw [inverse_square_mod x inv hinv]
      simp

theorem inverse_cube_mod (x inv : Int)
    (hinv : (w x*inv)%p=1) :
    (w x*w x*w x*inv*inv*inv)%p=1 := by
  calc
    (w x*w x*w x*inv*inv*inv)%p =
        ((w x*w x*inv*inv)*(w x*inv))%p := by
          congr 1
          ac_rfl
    _ = (((w x*w x*inv*inv)%p)*((w x*inv)%p))%p := by
      rw [Int.mul_emod]
    _ = 1 := by
      rw [inverse_square_mod x inv hinv, hinv]
      decide

/-- Normalizing the native projective x coordinate by a modular inverse
gives the affine `P - ωP` chord coordinate. -/
theorem normalized_x_mod (x y inv : Int)
    (hinv : (w x*inv)%p=1) :
    (nativeX x y*inv*inv)%p =
      (4*y*y*inv*inv-(1+b)*x)%p := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hcross : (nativeX x y-
      (4*y*y-(1+b)*x*w x*w x))%p=0 := by
    exact (Int.emod_eq_emod_iff_emod_sub_eq_zero).mp
      (native_x_chord_mod x y)
  have hsquare := inverse_square_mod x inv hinv
  have hfactor : (1-w x*w x*inv*inv)%p=0 := by
    rw [Int.sub_emod,hsquare]
    decide
  have hdiff : nativeX x y*inv*inv-(4*y*y*inv*inv-(1+b)*x) =
      (nativeX x y-(4*y*y-(1+b)*x*w x*w x))*inv*inv+
      (1+b)*x*(1-w x*w x*inv*inv) := by
    simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul]
    grind
  rw [hdiff]
  simp [Int.add_emod,Int.mul_emod,hcross,hfactor]

/-- Normalizing the native projective y coordinate by a modular inverse
gives the affine `P - ωP` chord coordinate. -/
theorem normalized_y_mod (x y inv : Int)
    (hinv : (w x*inv)%p=1) :
    (nativeY x y*inv*inv*inv)%p =
      (2*x*y*inv-2*nativeX x y*y*inv*inv*inv-y)%p := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hcross : (nativeY x y-
      ((2*x*w x*w x-2*nativeX x y-w x*w x*w x)*y))%p=0 := by
    exact (Int.emod_eq_emod_iff_emod_sub_eq_zero).mp
      (native_y_chord_mod x y)
  have hsquare := inverse_square_times_mod x inv hinv
  have hcube := inverse_cube_mod x inv hinv
  have hfactor1 : (w x*w x*inv*inv*inv-inv)%p=0 := by
    exact (Int.emod_eq_emod_iff_emod_sub_eq_zero).mp hsquare
  have hfactor2 : (w x*w x*w x*inv*inv*inv-1)%p=0 := by
    apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).mp
    simpa [p,EisensteinResidue.prime] using hcube
  have hdiff : nativeY x y*inv*inv*inv-
      (2*x*y*inv-2*nativeX x y*y*inv*inv*inv-y) =
      (nativeY x y-(2*x*w x*w x-2*nativeX x y-w x*w x*w x)*y)*
        inv*inv*inv+
      2*x*y*(w x*w x*inv*inv*inv-inv)-
      y*(w x*w x*w x*inv*inv*inv-1) := by
    simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul]
    grind
  rw [hdiff]
  simp [Int.add_emod,Int.sub_emod,Int.mul_emod,hcross,hfactor1,hfactor2]

#print axioms inverse_square_mod
#print axioms inverse_square_times_mod
#print axioms inverse_cube_mod
#print axioms normalized_x_mod
#print axioms normalized_y_mod

end Secp256k1TauNormalize
