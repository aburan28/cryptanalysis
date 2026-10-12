import Mathlib

/-!
Q1506 algebra for the independent uniform first-pair scan model.
The hypothesis `B = 2*n*K` is supplied by a complete signed-Frobenius
orbit count; this file does not prove that a given curve base has that count.
The probability union bound and independence law are separate model
assumptions, not conclusions of these identities.
-/

namespace Q1506

theorem scan_work_identity (B K r : ℚ) (hB : B ≠ 0) (hB1 : B + 1 ≠ 0) :
    K * (r - 1) * (10 * B) / (4 * (B * (B + 1) / 2)) =
      5 * K * (r - 1) / (B + 1) := by
  field_simp
  ring

theorem full_orbit_scan_work (n B K r : ℚ)
    (hn : n ≠ 0) (hB : B ≠ 0) (hB1 : B + 1 ≠ 0)
    (horbit : B = 2 * n * K) :
    K * (r - 1) * (10 * B) / (4 * (B * (B + 1) / 2)) =
      (5 * (r - 1) / (2 * n)) * (B / (B + 1)) := by
  rw [scan_work_identity B K r hB hB1]
  have hK : K = B / (2 * n) := by
    rw [horbit]
    field_simp
  rw [hK]
  field_simp

#print axioms scan_work_identity
#print axioms full_orbit_scan_work

end Q1506
