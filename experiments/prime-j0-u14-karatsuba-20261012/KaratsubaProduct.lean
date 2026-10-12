import Lean

namespace PrimeJ0Karatsuba

-- The same identity is used at radix 2^64 and then at radix 2^128.
theorem two_limb_product (base a0 a1 b0 b1 : Int) :
    (a0 + base * a1) * (b0 + base * b1) =
      a0 * b0 +
      base * (a0 * b0 + a1 * b1 + (a1 - a0) * (b0 - b1)) +
      base * base * (a1 * b1) := by
  simp [Int.mul_add, Int.mul_sub, Int.mul_comm, Int.mul_left_comm,
        Int.add_assoc, Int.add_comm, Int.add_left_comm]
  all_goals omega

-- The signed difference branch in the implementation computes this exact
-- middle coefficient; the sign is carried by a mask in the limb code.
theorem middle_coefficient (a0 a1 b0 b1 : Int) :
    a0 * b0 + a1 * b1 + (a1 - a0) * (b0 - b1) =
      a0 * b1 + a1 * b0 := by
  simp [Int.mul_sub, Int.mul_comm, Int.add_assoc]
  all_goals omega

theorem four_limb_product
    (base : Int) (a0 a1 a2 a3 b0 b1 b2 b3 : Int) :
    ((a0 + base * a1) + (base * base) * (a2 + base * a3)) *
      ((b0 + base * b1) + (base * base) * (b2 + base * b3)) =
    (a0 + base * a1) * (b0 + base * b1) +
      (base * base) *
        ((a0 + base * a1) * (b0 + base * b1) +
         (a2 + base * a3) * (b2 + base * b3) +
         ((a2 + base * a3) - (a0 + base * a1)) *
           ((b0 + base * b1) - (b2 + base * b3))) +
      (base * base) * (base * base) *
        ((a2 + base * a3) * (b2 + base * b3)) := by
  exact two_limb_product (base * base)
    (a0 + base * a1) (a2 + base * a3)
    (b0 + base * b1) (b2 + base * b3)

#print axioms two_limb_product
#print axioms middle_coefficient
#print axioms four_limb_product

end PrimeJ0Karatsuba
