-- Kernel-checked on the standard foundations: expected `ok`.
theorem add_zero' (n : Nat) : n + 0 = n := rfl
theorem classical_em (p : Prop) : p ∨ ¬p := Classical.em p
