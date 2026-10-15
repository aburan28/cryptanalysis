import SplitPrimeRadix

namespace NearestOrbit53593
open SplitPrimeRadix

def radixMul (z : Coeff) : Coeff :=
  (233 * z.1 + 3 * z.2, -z.1 + 230 * z.2)

def residue (z : Coeff) : Int := z.1 + 233 * z.2

theorem radix_norm : norm (233, -1) = 53593 := by decide

theorem norm_radix_mul (z : Coeff) :
    norm (radixMul z) = 53593 * norm z := by
  rcases z with ⟨a, b⟩
  simp only [radixMul, norm]
  grind

theorem residue_radix_mul (z : Coeff) :
    residue (radixMul z) = 53593 * z.2 := by
  rcases z with ⟨a, b⟩
  simp only [residue, radixMul]
  omega

theorem digit_step_identity (a b da db k : Int)
    (h : 53593 * k = (a - da) + 233 * (b - db)) :
    add (da, db) (radixMul (230 * k - (b - db), k)) = (a, b) := by
  simp only [add, radixMul]
  apply Prod.ext <;> dsimp <;> omega

theorem omega_residue (z : Coeff) :
    (residue (omegaMul z) + 232 * residue z) % 53593 = 0 := by
  rcases z with ⟨a, b⟩
  simp only [residue, omegaMul]
  omega

#print axioms radix_norm
#print axioms norm_radix_mul
#print axioms residue_radix_mul
#print axioms digit_step_identity
#print axioms omega_residue
end NearestOrbit53593
