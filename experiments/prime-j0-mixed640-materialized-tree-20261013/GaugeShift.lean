import Lean

namespace PrimeJ0GaugeShift

-- Unit powers are represented in {0,1,2}; table construction stores a
-- point in gauge g and selection uses (u-g) mod 3.
def adjusted (u g : Nat) : Nat := (u + 3 - g) % 3

theorem adjusted_compose (u g : Nat) (hu : u < 3) (hg : g < 3) :
    (adjusted u g + g) % 3 = u := by
  unfold adjusted
  omega

theorem gauge_shift {P : Type} (unit : Nat → P → P)
    (unit_compose : ∀ a b x, unit a (unit b x) = unit ((a + b) % 3) x)
    (u g : Nat) (hu : u < 3) (hg : g < 3) (x : P) :
    unit (adjusted u g) (unit g x) = unit u x := by
  rw [unit_compose, adjusted_compose u g hu hg]

#print axioms adjusted_compose
#print axioms gauge_shift

end PrimeJ0GaugeShift
