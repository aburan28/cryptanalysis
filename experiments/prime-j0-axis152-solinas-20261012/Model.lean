import Lean

namespace PrimeJ0Axis152Solinas

-- The exact ordinary-path source count for a noninitial XYZZ addition
-- is eight field products and two squares in either representation.
-- One reference rotation has 23 source 64-bit products; one candidate
-- rotation has 16. The identity applies to any nonnegative counts.
theorem ordinary_path_product_saving (additions rotations : Nat) :
    36 * 10 * additions + 23 * rotations =
      (16 * 10 * additions + 16 * rotations) +
      (200 * additions + 7 * rotations) := by
  omega

#print axioms ordinary_path_product_saving

end PrimeJ0Axis152Solinas
