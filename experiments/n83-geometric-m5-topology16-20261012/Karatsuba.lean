import Init.Grind.Ring.Basic

namespace N83Karatsuba

open Lean.Grind

variable {R : Type} [Ring R]

-- The recursive multiplier uses this identity at each coefficient split.
theorem cross_term_char_two
    (hself : ∀ x : R, x + x = 0)
    (a b c d : R) :
    (a + b) * (c + d) + a * c + b * d = a * d + b * c := by
  letI : Std.Associative (fun x y : R => x + y) :=
    ⟨Semiring.add_assoc⟩
  letI : Std.Commutative (fun x y : R => x + y) :=
    ⟨Semiring.add_comm⟩
  calc
    (a + b) * (c + d) + a * c + b * d =
        (a * c + a * c) + (a * d + b * c) + (b * d + b * d) := by
          rw [Semiring.right_distrib, Semiring.left_distrib,
              Semiring.left_distrib]
          ac_rfl
    _ = a * d + b * c := by
          rw [hself (a * c), hself (b * d), Semiring.add_zero,
              Semiring.add_comm 0, Semiring.add_zero]

#print axioms cross_term_char_two

end N83Karatsuba
