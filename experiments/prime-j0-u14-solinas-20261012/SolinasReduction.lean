import Lean

namespace PrimeJ0Solinas

def radix : Nat := 2 ^ 256
def foldConstant : Nat := 2 ^ 32 + 977
def prime : Nat := radix - foldConstant

theorem radix_eq_prime_add_foldConstant :
    radix = prime + foldConstant := by
  decide

theorem product_fold_mod (low high : Nat) :
    (low + radix * high) % prime =
      (low + foldConstant * high) % prime := by
  rw [radix_eq_prime_add_foldConstant]
  simp [Nat.add_mul, Nat.add_mod, Nat.mul_mod, Nat.add_comm]

def fold (n : Nat) : Nat := n % radix + foldConstant * (n / radix)

theorem fold_mod (n : Nat) : fold n % prime = n % prime := by
  unfold fold
  simpa [Nat.mod_add_div] using
    (product_fold_mod (n % radix) (n / radix)).symm

def foldFour (n : Nat) : Nat := fold (fold (fold (fold n)))

theorem foldFour_mod (n : Nat) : foldFour n % prime = n % prime := by
  unfold foldFour
  rw [fold_mod, fold_mod, fold_mod, fold_mod]

private theorem fold_bound₁ (n : Nat) (h : n < radix * radix) :
    fold n < radix * (foldConstant + 1) := by
  unfold fold
  dsimp [radix, foldConstant] at *
  omega

private theorem fold_bound₂ (n : Nat)
    (h : n < radix * (foldConstant + 1)) :
    fold n < radix + foldConstant * foldConstant := by
  unfold fold
  dsimp [radix, foldConstant] at *
  omega

private theorem fold_bound₃ (n : Nat)
    (h : n < radix + foldConstant * foldConstant) :
    fold n < radix + foldConstant := by
  unfold fold
  dsimp [radix, foldConstant] at *
  omega

private theorem fold_bound₄ (n : Nat)
    (h : n < radix + foldConstant) :
    fold n < 2 * prime := by
  unfold fold
  dsimp [radix, foldConstant, prime] at *
  omega

theorem foldFour_lt_twoPrime (n : Nat) (h : n < radix * radix) :
    foldFour n < 2 * prime := by
  exact fold_bound₄ _ (fold_bound₃ _ (fold_bound₂ _ (fold_bound₁ n h)))

def subtractIfNeeded (n : Nat) : Nat :=
  if prime ≤ n then n - prime else n

theorem subtractIfNeeded_mod (n : Nat) (h : n < 2 * prime) :
    subtractIfNeeded n = n % prime := by
  unfold subtractIfNeeded
  by_cases hge : prime ≤ n
  · simp only [ite_eq_left hge]
    rw [Nat.mod_eq_sub_mod hge, Nat.mod_eq_of_lt (by omega)]
  · have hlt : n < prime := by omega
    rw [ite_eq_right hge, Nat.mod_eq_of_lt hlt]

theorem fourFoldReduction_correct (n : Nat)
    (h : foldFour n < 2 * prime) :
    subtractIfNeeded (foldFour n) = n % prime := by
  rw [subtractIfNeeded_mod _ h, foldFour_mod]

theorem canonical_product_reduction (a b : Nat)
    (ha : a < prime) (hb : b < prime) :
    subtractIfNeeded (foldFour (a * b)) = (a * b) % prime := by
  have hpr : prime < radix := by decide
  have haRadix : a ≤ radix := by omega
  have hbRadix : b < radix := by omega
  have hproduct : a * b < radix * radix := by
    calc
      a * b ≤ radix * b := Nat.mul_le_mul_right b haRadix
      _ < radix * radix := Nat.mul_lt_mul_of_pos_left hbRadix (by decide)
  exact fourFoldReduction_correct _ (foldFour_lt_twoPrime _ hproduct)

theorem canonical_product_result_lt_prime (a b : Nat)
    (ha : a < prime) (hb : b < prime) :
    subtractIfNeeded (foldFour (a * b)) < prime := by
  rw [canonical_product_reduction a b ha hb]
  exact Nat.mod_lt _ (by decide)

#print axioms radix_eq_prime_add_foldConstant
#print axioms product_fold_mod
#print axioms fold_mod
#print axioms foldFour_mod
#print axioms foldFour_lt_twoPrime
#print axioms subtractIfNeeded_mod
#print axioms fourFoldReduction_correct
#print axioms canonical_product_reduction
#print axioms canonical_product_result_lt_prime

end PrimeJ0Solinas
