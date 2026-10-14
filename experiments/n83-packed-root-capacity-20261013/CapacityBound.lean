/- Numeric capacity boundary for the N83 packed root table. The Rust loop
   pushes at most 83*K*K states and the table requests four slots per state
   before rounding to a power of two. Theorems below establish the arithmetic
   under that source bound; they do not model the Rust code or state yield. -/

namespace N83PackedRootCapacity

theorem k1271_requested_slots_fit (states : Nat)
    (hStates : states ≤ 83 * 1271 ^ 2) :
    4 * states ≤ 2 ^ 29 := by
  calc
    4 * states ≤ 4 * (83 * 1271 ^ 2) := Nat.mul_le_mul_left 4 hStates
    _ ≤ 2 ^ 29 := by decide

theorem k1272_maximum_crosses_boundary :
    2 ^ 29 < 4 * (83 * 1272 ^ 2) := by decide

theorem packed_table_bytes_at_boundary : 16 * 2 ^ 29 = 8589934592 := by decide

#print axioms k1271_requested_slots_fit
#print axioms k1272_maximum_crosses_boundary
#print axioms packed_table_bytes_at_boundary

end N83PackedRootCapacity
