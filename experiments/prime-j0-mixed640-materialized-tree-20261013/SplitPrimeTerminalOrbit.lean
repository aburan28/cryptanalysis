import SplitPrimeRadix
import SplitPrimeLatticeCell
import SplitPrimeComplete

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

theorem terminal_ball_square_bounds (z : Coeff)
    (h : norm z < 46*46) :
    z.1*z.1 < 92*92 ∧ 3*z.2*z.2 < 92*92 := by
  have ha := coordinate_a_bound z.1 z.2
  have hb := coordinate_b_bound z.1 z.2
  have hnorm : norm (z.1, z.2) = norm z := by cases z; rfl
  rw [hnorm] at ha hb
  omega

theorem terminal_ball_coordinate_bounds (z : Coeff)
    (h : norm z < 46*46) :
    -91 ≤ z.1 ∧ z.1 ≤ 91 ∧ -53 ≤ z.2 ∧ z.2 ≤ 53 := by
  obtain ⟨ha, hb⟩ := terminal_ball_square_bounds z h
  have hmul : 3*z.2*z.2 = 3*(z.2*z.2) := by grind
  rw [hmul] at hb
  have haLo : -91 ≤ z.1 := by
    by_cases hx : -91 ≤ z.1
    · exact hx
    · have hsmall : z.1 ≤ -92 := by omega
      have hs := square_le_abs 92 (-z.1) (by omega) (by omega) (by omega)
      have heq : (-z.1)*(-z.1) = z.1*z.1 := by grind
      omega
  have haHi : z.1 ≤ 91 := by
    by_cases hx : z.1 ≤ 91
    · exact hx
    · have hlarge : 92 ≤ z.1 := by omega
      have hs := square_le_abs 92 z.1 (by omega) (by omega) hlarge
      omega
  have hbLo : -53 ≤ z.2 := by
    by_cases hx : -53 ≤ z.2
    · exact hx
    · have hsmall : z.2 ≤ -54 := by omega
      have hs := square_le_abs 54 (-z.2) (by omega) (by omega) (by omega)
      have heq : (-z.2)*(-z.2) = z.2*z.2 := by grind
      omega
  have hbHi : z.2 ≤ 53 := by
    by_cases hx : z.2 ≤ 53
    · exact hx
    · have hlarge : 54 ≤ z.2 := by omega
      have hs := square_le_abs 54 z.2 (by omega) (by omega) hlarge
      omega
  exact ⟨haLo, haHi, hbLo, hbHi⟩

theorem canonical_scheme_terminal_coordinates (scalar : Int) :
    -91 ≤ (stateAt (selectedCandidate scalar) 21).1 ∧
    (stateAt (selectedCandidate scalar) 21).1 ≤ 91 ∧
    -53 ≤ (stateAt (selectedCandidate scalar) 21).2 ∧
    (stateAt (selectedCandidate scalar) 21).2 ≤ 53 := by
  exact terminal_ball_coordinate_bounds _
    (canonical_scheme_terminal_bound scalar)

#print axioms terminal_omega_square
#print axioms terminal_omega_cube
#print axioms terminal_omega_fixed_only_zero
#print axioms terminal_omega_neg_fixed_only_zero
#print axioms terminal_orbit_norm
#print axioms terminal_ball_square_bounds
#print axioms terminal_ball_coordinate_bounds
#print axioms canonical_scheme_terminal_coordinates
