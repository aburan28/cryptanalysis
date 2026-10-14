import Lean

namespace CurveAudit

/-- Two multiples of `r` in an interval of width strictly less than `r`
    coincide. This is the arithmetic uniqueness step of the large-field
    order certificate. -/
theorem unique_multiple_in_short_interval
    (r width n m k l : Nat)
    (hwidth : width < r)
    (hn : n = k * r) (hm : m = l * r)
    (hnm : n ≤ m + width) (hmn : m ≤ n + width) : n = m := by
  by_cases hkl : k < l
  · have hmul := Nat.mul_le_mul_right r (Nat.succ_le_of_lt hkl)
    rw [Nat.succ_mul] at hmul
    omega
  by_cases hlk : l < k
  · have hmul := Nat.mul_le_mul_right r (Nat.succ_le_of_lt hlk)
    rw [Nat.succ_mul] at hmul
    omega
  · have heq : k = l := by omega
    simp [hn, hm, heq]

#print axioms unique_multiple_in_short_interval

end CurveAudit
