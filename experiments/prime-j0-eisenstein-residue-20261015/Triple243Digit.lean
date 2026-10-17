import Triple243Radix

namespace Triple243Digit

def nearestB (r : Int) : Int := (485*r+58807) / 117614

theorem rounding_error (r : Int) :
    -58807 ≤ 117614*nearestB r-485*r ∧
    117614*nearestB r-485*r ≤ 58807 := by
  dsimp [nearestB]
  omega

/-- The zero-lift rounded coefficient lies in the proposed selector's
floor-center neighborhood. -/
theorem rounded_in_native_window (r : Int) :
    485*r / 117614 ≤ nearestB r ∧
    nearestB r ≤ 485*r / 117614 + 1 := by
  dsimp [nearestB]
  omega

theorem norm_identity (r b : Int) :
    4*58807*AlternateRadix.pairNorm (r-244*b) b =
      (117614*b-485*r)*(117614*b-485*r)+3*r*r := by
  simp [AlternateRadix.pairNorm, Int.mul_sub,
        Int.add_mul, Int.sub_mul, Int.mul_assoc, Int.mul_comm,
        Int.mul_left_comm]
  simp only [← Int.mul_assoc]
  omega

private theorem square_bound (x limit : Int)
    (hlimit : 0 ≤ limit) (h : -limit ≤ x ∧ x ≤ limit) :
    x*x ≤ limit*limit := by
  by_cases hx : 0 ≤ x
  · have h1 := Int.mul_le_mul_of_nonneg_right h.2 hx
    have h2 := Int.mul_le_mul_of_nonneg_left h.2 hlimit
    exact Int.le_trans h1 h2
  · have hy : 0 ≤ -x := by omega
    have hybound : -x ≤ limit := by omega
    have h1 := Int.mul_le_mul_of_nonneg_right hybound hy
    have h2 := Int.mul_le_mul_of_nonneg_left hybound hlimit
    have hs := Int.le_trans h1 h2
    simpa [Int.neg_mul, Int.mul_neg] using hs

theorem rounded_digit_norm_below_radix (r : Int)
    (hr : 0 ≤ r ∧ r ≤ 29403) :
    AlternateRadix.pairNorm (r-244*nearestB r) (nearestB r) < 58807 := by
  let b := nearestB r
  let e := 117614*b-485*r
  have herr : -58807 ≤ e ∧ e ≤ 58807 := by
    simpa [e,b] using rounding_error r
  have he2 := square_bound e 58807 (by decide) herr
  have hr2 := square_bound r 29403 (by decide) (by omega)
  have hident := norm_identity r b
  dsimp [e,b] at he2 hident
  simp only [Int.mul_assoc] at hident
  omega

/-- A selector that keeps a digit no longer than the rounded candidate
inherits the bound for every centered nonnegative residue. -/
theorem selected_digit_norm_below_radix (r da db : Int)
    (hr : 0 ≤ r ∧ r ≤ 29403)
    (hselect : AlternateRadix.pairNorm da db ≤
      AlternateRadix.pairNorm (r-244*nearestB r) (nearestB r)) :
    AlternateRadix.pairNorm da db < 58807 := by
  have hc := rounded_digit_norm_below_radix r hr
  omega

/-- Matching the residue modulo 58807 gives explicit integral coordinates
for the next radix state. -/
theorem exact_quotient (a b da db k : Int)
    (hresidue : (a-da)+244*(b-db) = 58807*k) :
    Triple243Radix.primePair243 (241*k-(b-db), k) =
      (a-da,b-db) := by
  simp only [Triple243Radix.primePair243, Prod.mk.injEq]
  constructor <;> omega

#print axioms rounding_error
#print axioms rounded_in_native_window
#print axioms norm_identity
#print axioms rounded_digit_norm_below_radix
#print axioms selected_digit_norm_below_radix
#print axioms exact_quotient
end Triple243Digit
