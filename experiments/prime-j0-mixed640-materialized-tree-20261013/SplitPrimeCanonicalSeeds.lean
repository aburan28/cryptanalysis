import Lean

set_option maxRecDepth 100000
set_option maxHeartbeats 0

namespace SplitPrimeCanonicalSeeds

-- Of the six unit images, the three sign-folded residues suffice to find
-- the smallest positive integer representative of an orbit.
def centered (x : Nat) : Nat := min x (3301 - x)
def orbitMinimum (m : Nat) : Nat :=
  min (centered (m % 3301))
    (min (centered ((1726 * m) % 3301))
         (centered ((1574 * m) % 3301)))

def isCanonical (m : Nat) : Bool :=
  decide (0 < m ∧ m = orbitMinimum m)

def seeds : List Nat := (List.range 1065).filter isCanonical

theorem canonical_count : seeds.length = 550 := by decide
theorem canonical_last : seeds.getLast? = some 1064 := by decide

#print axioms canonical_count
#print axioms canonical_last

end SplitPrimeCanonicalSeeds
