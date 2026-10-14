import SplitPrimeRadix

open SplitPrimeRadix

-- The coefficient action used by the terminal table is the order-three
-- automorphism of the Eisenstein lattice. Negation supplies the other three
-- images stored under each orbit code.
theorem terminal_omega_square (z : Coeff) :
    omegaMul (omegaMul z) = (-2*z.1 - 3*z.2, z.1 + z.2) := by
  cases z with
  | mk a b =>
    simp only [omegaMul]
    apply Prod.ext <;> dsimp <;> omega

theorem terminal_omega_cube (z : Coeff) :
    omegaMul (omegaMul (omegaMul z)) = z := by
  cases z with
  | mk a b =>
    simp only [omegaMul]
    apply Prod.ext <;> dsimp <;> omega

theorem terminal_omega_fixed_only_zero (z : Coeff)
    (h : omegaMul z = z) : z = (0, 0) := by
  cases z with
  | mk a b =>
    simp only [omegaMul, Prod.mk.injEq] at h
    apply Prod.ext <;> dsimp <;> omega

theorem terminal_omega_neg_fixed_only_zero (z : Coeff)
    (h : omegaMul z = (-z.1, -z.2)) : z = (0, 0) := by
  cases z with
  | mk a b =>
    simp only [omegaMul, Prod.mk.injEq] at h
    apply Prod.ext <;> dsimp <;> omega

theorem terminal_orbit_norm (z : Coeff) :
    norm z = norm (omegaMul z) ∧
    norm z = norm (omegaMul (omegaMul z)) ∧
    norm z = norm (-z.1, -z.2) := by
  constructor
  · exact (norm_omega_mul z).symm
  constructor
  · rw [norm_omega_mul, norm_omega_mul]
  · exact (norm_neg z).symm

#print axioms terminal_omega_square
#print axioms terminal_omega_cube
#print axioms terminal_omega_fixed_only_zero
#print axioms terminal_omega_neg_fixed_only_zero
#print axioms terminal_orbit_norm
