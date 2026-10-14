import SplitPrimeDigitChoice

open SplitPrimeRadix SplitPrimeDigitChoice

-- Combining low and high points before the mixed addition is valid for all
-- six unit actions. The native batch inversion changes how the sum is
-- computed, while this equation fixes the coefficient and endomorphism law.
theorem split_unit_digit_add (low high : Int) (u : UnitCode) :
    digit (low + 32*high) u =
      add (digit low u) (digit (32*high) u) := by
  cases u <;>
    simp only [digit, omegaMul, add] <;>
    apply Prod.ext <;> dsimp <;> omega

theorem split_unit_digit_nat (m : Nat) (hm_bound : m ≤ 1064)
    (u : UnitCode) :
    digit (m : Int) u =
      add (digit ((m % 32 : Nat) : Int) u)
          (digit (32 * ((m / 32 : Nat) : Int)) u) := by
  have h := split_seed_reconstruct m hm_bound
  have hm : (m : Int) = ((m % 32 : Nat) : Int) +
      32 * ((m / 32 : Nat) : Int) := by
    omega
  rw [hm]
  exact split_unit_digit_add _ _ u

#print axioms split_unit_digit_add
#print axioms split_unit_digit_nat
