import SplitPrimeRadix
import SplitPrime12211GlobalMin

namespace NearestOrbit12211
open SplitPrimeRadix

def negate (z : Coeff) : Coeff := (-z.1, -z.2)

def orbit (z : Coeff) : List Coeff :=
  [z, negate z, omegaMul z, negate (omegaMul z),
   omegaMul (omegaMul z), negate (omegaMul (omegaMul z))]

theorem omega_cube (z : Coeff) :
    omegaMul (omegaMul (omegaMul z)) = z := by
  cases z
  simp [omegaMul]
  constructor <;> omega

theorem orbit_preserves_norm (seed image : Coeff)
    (h : image ∈ orbit seed) : norm image = norm seed := by
  simp only [orbit, List.mem_cons, List.not_mem_nil, or_false] at h
  rcases h with h | h | h | h | h | h <;> subst image
  · rfl
  · exact norm_neg seed
  · exact norm_omega_mul seed
  · rw [show negate (omegaMul seed) =
        (-(omegaMul seed).1, -(omegaMul seed).2) from rfl,
        norm_neg, norm_omega_mul]
  · rw [norm_omega_mul, norm_omega_mul]
  · rw [show negate (omegaMul (omegaMul seed)) =
        (-(omegaMul (omegaMul seed)).1,
         -(omegaMul (omegaMul seed)).2) from rfl,
        norm_neg, norm_omega_mul, norm_omega_mul]

def residue (z : Coeff) : Int := z.1 + 112*z.2

theorem omega_residue (z : Coeff) :
    (residue (omegaMul z) - 12100*residue z) % 12211 = 0 := by
  cases z with
  | mk a b =>
    simp only [residue, omegaMul]
    omega

theorem negate_residue (z : Coeff) :
    residue (negate z) = -residue z := by
  cases z
  simp [residue, negate]
  omega

theorem omega_add (x y : Coeff) :
    omegaMul (add x y) = add (omegaMul x) (omegaMul y) := by
  cases x
  cases y
  simp [omegaMul, add]
  constructor <;> omega

-- Processing classes 2, 1, 0 with two aggregate rotations produces
-- the same sum as rotating each class's terms individually.
theorem rolling_three_classes (plain first second : Coeff) :
    add plain (omegaMul (add first (omegaMul second))) =
      add (add plain (omegaMul first)) (omegaMul (omegaMul second)) := by
  rw [omega_add]
  cases plain
  cases first
  cases second
  simp [add]
  constructor <;> omega

def rotationCount (class0 class1 class2 : Bool) : Nat :=
  (if class2 && (class1 || class0) then 1 else 0) +
  (if class1 && class0 then 1 else 0) +
  (if !class0 && (class1 || class2) then 1 else 0)

theorem rotation_count_le_two (class0 class1 class2 : Bool) :
    rotationCount class0 class1 class2 ≤ 2 := by
  cases class0 <;> cases class1 <;> cases class2 <;> decide

#print axioms omega_cube
#print axioms orbit_preserves_norm
#print axioms omega_residue
#print axioms negate_residue
#print axioms omega_add
#print axioms rolling_three_classes
#print axioms rotation_count_le_two
end NearestOrbit12211
