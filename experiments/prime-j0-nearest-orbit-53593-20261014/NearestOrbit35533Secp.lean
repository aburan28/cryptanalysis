import NearestOrbit35533Lattice

namespace NearestOrbit35533Secp
open SplitPrime12211Nearest NearestOrbit35533Complete NearestOrbit35533Lattice

def fieldPrime : Int :=
  115792089237316195423570985008687907853269984665640564039457584007908834671663
def beta : Int :=
  55594575648329892869085402983802832744385952214688224221778511981742606582254
def generatorX : Int :=
  55066263022277343669578718895168534326250603453777594175500187360389116729240
def generatorY : Int :=
  32670510020758816978083085130507043184471273380659243275938904335757337482424

theorem beta_cube : (beta * beta * beta) % fieldPrime = 1 := by decide
theorem beta_quadratic : (beta * beta + beta + 1) % fieldPrime = 0 := by decide
theorem beta_nontrivial : beta % fieldPrime ≠ 1 := by decide
theorem generator_on_curve :
    (generatorY * generatorY - generatorX * generatorX * generatorX - 7) %
      fieldPrime = 0 := by decide

theorem beta_curve_identity (x y : Int) :
    y*y - (beta*x)*(beta*x)*(beta*x) - 7 =
      (y*y - x*x*x - 7) - (beta*beta*beta - 1)*(x*x*x) := by
  grind

theorem beta_preserves_curve (x y : Int)
    (hcurve : (y*y - x*x*x - 7) % fieldPrime = 0) :
    (y*y - (beta*x)*(beta*x)*(beta*x) - 7) % fieldPrime = 0 := by
  rw [beta_curve_identity]
  have hcube : (beta*beta*beta - 1) % fieldPrime = 0 := by
    have hb := beta_cube
    dsimp [fieldPrime] at *
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hcube
  rw [hk]
  simp only [Int.mul_assoc] at hcurve ⊢
  simpa only [Int.sub_mul_emod_self_left] using hcurve

-- This is the point-update equation used by the native radix loop. The
-- hypotheses are the scalar laws to instantiate for the secp256k1 subgroup.
def pointRadix {P : Type} (pointAdd : P → P → P) (pointNeg : P → P)
    (times190 tauPoint : P → P) (p : P) : P :=
  pointAdd (times190 p) (pointNeg (tauPoint p))

theorem point_radix_scalar {P : Type}
    (pointAdd : P → P → P) (pointNeg : P → P)
    (times190 tauPoint : P → P) (eval : Int → P)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hneg : ∀ x, eval (-x) = pointNeg (eval x))
    (h190 : ∀ x, times190 (eval x) = eval (190*x))
    (htau : ∀ x, tauPoint (eval x) = eval (tauEigen*x))
    (t : Int) :
    pointRadix pointAdd pointNeg times190 tauPoint (eval t) =
      eval ((190-tauEigen)*t) := by
  have hs : (190-tauEigen)*t = 190*t + -(tauEigen*t) := by
    dsimp [tauEigen]
    omega
  rw [hs, hadd, hneg]
  simp [pointRadix, h190, htau]

theorem selected_scalar_point_replay {P : Type}
    (pointAdd : P → P → P) (pointNeg : P → P)
    (times190 tauPoint : P → P) (eval : Int → P)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hneg : ∀ x, eval (-x) = pointNeg (eval x))
    (h190 : ∀ x, times190 (eval x) = eval (190*x))
    (htau : ∀ x, tauPoint (eval x) = eval (tauEigen*x))
    (hmod : ∀ x y, (x-y) % order = 0 → eval x = eval y)
    (scalar : Int) :
    eval scalar = NearestOrbit35533Action.pointFold pointAdd
      (pointRadix pointAdd pointNeg times190 tauPoint)
      (fun z => eval (scalarValue z))
      (stateAt (selectedCandidate scalar))
      (digitAt (selectedCandidate scalar)) 0 16 := by
  exact NearestOrbit35533Lattice.selected_scalar_point_replay
    pointAdd (pointRadix pointAdd pointNeg times190 tauPoint)
    eval hadd hmod
    (point_radix_scalar pointAdd pointNeg times190 tauPoint eval
      hadd hneg h190 htau) scalar

#print axioms beta_cube
#print axioms beta_quadratic
#print axioms generator_on_curve
#print axioms beta_preserves_curve
#print axioms selected_scalar_point_replay
end NearestOrbit35533Secp
