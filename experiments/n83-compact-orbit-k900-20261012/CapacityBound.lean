/- Numeric capacity boundary for the current compact-orbit root index.
   The Rust bridge is build_index128: at most K*K*83 pair states are pushed,
   and RootTable128::with_capacity(states*2) requests 4*states slots before
   next_power_of_two. This module checks the arithmetic at K=899 and K=900;
   it does not formalize the Rust implementation or assert every state exists. -/

namespace N83CompactOrbitCapacity

theorem k899_requested_slots_fit (states : Nat)
    (hStates : states ≤ 83 * 899 ^ 2) :
    4 * states ≤ 2 ^ 28 := by
  calc
    4 * states ≤ 4 * (83 * 899 ^ 2) := Nat.mul_le_mul_left 4 hStates
    _ ≤ 2 ^ 28 := by decide

theorem k900_maximum_crosses_boundary :
    2 ^ 28 < 4 * (83 * 900 ^ 2) := by decide

theorem table_slot_bytes_at_boundary : 32 * 2 ^ 28 = 8589934592 := by decide

#print axioms k899_requested_slots_fit
#print axioms k900_maximum_crosses_boundary
#print axioms table_slot_bytes_at_boundary

end N83CompactOrbitCapacity
