import Triple81Radix

namespace Triple81Digit

def nearestB (r : Int) : Int := (161*r+6481) / 12962

theorem rounding_error (r : Int) :
    -6481 ≤ 12962*nearestB r-161*r ∧
    12962*nearestB r-161*r ≤ 6481 := by
  dsimp [nearestB]
  omega

/-- The zero-lift rounded coefficient lies in the native selector's
floor-center neighborhood. -/
theorem rounded_in_native_window (r : Int) :
    161*r / 12962 ≤ nearestB r ∧
    nearestB r ≤ 161*r / 12962 + 1 := by
  dsimp [nearestB]
  omega

theorem norm_identity (r b : Int) :
    4*6481*AlternateRadix.pairNorm (r-82*b) b =
      (12962*b-161*r)*(12962*b-161*r)+3*r*r := by
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
    (hr : 0 ≤ r ∧ r ≤ 3240) :
    AlternateRadix.pairNorm (r-82*nearestB r) (nearestB r) < 6481 := by
  let b := nearestB r
  let e := 12962*b-161*r
  have herr : -6481 ≤ e ∧ e ≤ 6481 := by
    simpa [e,b] using rounding_error r
  have he2 := square_bound e 6481 (by decide) herr
  have hr2 := square_bound r 3240 (by decide) (by omega)
  have hident := norm_identity r b
  dsimp [e,b] at he2 hident
  simp only [Int.mul_assoc] at hident
  omega

/-- A selector that keeps a digit no longer than the rounded candidate
inherits the bound for every centered nonnegative residue. -/
theorem selected_digit_norm_below_radix (r da db : Int)
    (hr : 0 ≤ r ∧ r ≤ 3240)
    (hselect : AlternateRadix.pairNorm da db ≤
      AlternateRadix.pairNorm (r-82*nearestB r) (nearestB r)) :
    AlternateRadix.pairNorm da db < 6481 := by
  have hc := rounded_digit_norm_below_radix r hr
  omega

/-- Matching the residue modulo 6481 gives explicit integral coordinates
for the next radix state. -/
theorem exact_quotient (a b da db k : Int)
    (hresidue : (a-da)+82*(b-db) = 6481*k) :
    Triple81Radix.primePair81 (79*k-(b-db), k) =
      (a-da,b-db) := by
  simp only [Triple81Radix.primePair81, Prod.mk.injEq]
  constructor <;> omega

#print axioms rounding_error
#print axioms rounded_in_native_window
#print axioms norm_identity
#print axioms rounded_digit_norm_below_radix
#print axioms selected_digit_norm_below_radix
#print axioms exact_quotient
end Triple81Digit
