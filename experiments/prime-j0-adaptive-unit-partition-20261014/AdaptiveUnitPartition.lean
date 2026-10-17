import SplitPrimeRadix

namespace AdaptiveUnitPartition
open SplitPrimeRadix

theorem omega_add (a b : Coeff) :
    omegaMul (add a b) = add (omegaMul a) (omegaMul b) := by
  cases a; cases b
  simp [add, omegaMul]
  constructor <;> omega

theorem omega_cube (a : Coeff) :
    omegaMul (omegaMul (omegaMul a)) = a := by
  cases a
  simp [omegaMul]
  constructor <;> omega

-- Aggregate coefficients in unit classes one and two before applying omega.
theorem merge_unit_classes_1_2 (a b c : Coeff) :
    add a (omegaMul (add b (omegaMul c))) =
      add (add a (omegaMul b)) (omegaMul (omegaMul c)) := by
  cases a; cases b; cases c
  simp [add, omegaMul]
  constructor <;> omega

-- Source-loop products in the declared XYZZ and Solinas cost model.
def threeCost (n : Nat) : Nat := (n - 2) * 288 + 2 * 432 + 2 * 23
def twoUpper (n m : Nat) : Nat := (n - 1) * 288 + 432 + (m + 2) * 23

theorem small_unit_class (n0 n1 n2 : Nat)
    (h : n0 + n1 + n2 ≤ 20) :
    n0 ≤ 6 ∨ n1 ≤ 6 ∨ n2 ≤ 6 := by
  omega

theorem three_way_cost_dominated (n0 n1 n2 : Nat)
    (h0 : 0 < n0) (h1 : 0 < n1) (h2 : 0 < n2)
    (h : n0 + n1 + n2 ≤ 20) :
    ∃ m, (m = n0 ∨ m = n1 ∨ m = n2) ∧
      twoUpper (n0 + n1 + n2) m < threeCost (n0 + n1 + n2) := by
  have hn : 3 ≤ n0 + n1 + n2 := by omega
  rcases small_unit_class n0 n1 n2 h with hm | hm | hm
  · refine ⟨n0, Or.inl rfl, ?_⟩
    simp only [twoUpper, threeCost]
    omega
  · refine ⟨n1, Or.inr (Or.inl rfl), ?_⟩
    simp only [twoUpper, threeCost]
    omega
  · refine ⟨n2, Or.inr (Or.inr rfl), ?_⟩
    simp only [twoUpper, threeCost]
    omega

#print axioms merge_unit_classes_1_2
#print axioms three_way_cost_dominated
#print axioms omega_cube
end AdaptiveUnitPartition
