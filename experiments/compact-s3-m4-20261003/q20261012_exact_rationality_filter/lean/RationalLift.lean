import Mathlib

/-!
Q1495 structural rational-lift lemmas. The finite-field Artin-Schreier
image/kernel equivalence and normal-basis parity bridge are separate proof
obligations, documented in FORMALIZATION.md.
-/

namespace Q1495

variable {F : Type*} [Field F]

theorem curve_lift_iff_artin_schreier (x : F) (hx : x ≠ 0) :
    (∃ y : F, y ^ 2 + x * y = x ^ 3 + 1) ↔
    (∃ z : F, z ^ 2 + z = x + (x⁻¹) ^ 2) := by
  constructor
  · rintro ⟨y, hy⟩
    refine ⟨y / x, ?_⟩
    have hleft : x ^ 2 * ((y / x) ^ 2 + y / x) = y ^ 2 + x * y := by
      field_simp
    have hright : x ^ 2 * (x + (x⁻¹) ^ 2) = x ^ 3 + 1 := by
      field_simp
    apply (mul_left_cancel₀ (pow_ne_zero 2 hx))
    calc
      x ^ 2 * ((y / x) ^ 2 + y / x) = y ^ 2 + x * y := hleft
      _ = x ^ 3 + 1 := hy
      _ = x ^ 2 * (x + (x⁻¹) ^ 2) := hright.symm
  · rintro ⟨z, hz⟩
    refine ⟨x * z, ?_⟩
    calc
      (x * z) ^ 2 + x * (x * z) = x ^ 2 * (z ^ 2 + z) := by ring
      _ = x ^ 2 * (x + (x⁻¹) ^ 2) := by rw [hz]
      _ = x ^ 3 + 1 := by field_simp

theorem trace_rhs_eq_xor (tr : F → Bool)
    (hadd : ∀ a b : F, tr (a + b) = xor (tr a) (tr b))
    (hsquare : ∀ a : F, tr (a ^ 2) = tr a) (x : F) :
    tr (x + (x⁻¹) ^ 2) = xor (tr x) (tr x⁻¹) := by
  rw [hadd, hsquare]

theorem trace_rhs_zero_iff_inverse_parity (tr : F → Bool)
    (hadd : ∀ a b : F, tr (a + b) = xor (tr a) (tr b))
    (hsquare : ∀ a : F, tr (a ^ 2) = tr a)
    (x : F) (weightParity : Bool) (hweight : tr x = weightParity) :
    tr (x + (x⁻¹) ^ 2) = false ↔ tr x⁻¹ = weightParity := by
  rw [trace_rhs_eq_xor tr hadd hsquare x, hweight]
  cases weightParity <;> cases tr x⁻¹ <;> decide

#print axioms curve_lift_iff_artin_schreier
#print axioms trace_rhs_eq_xor
#print axioms trace_rhs_zero_iff_inverse_parity

end Q1495
