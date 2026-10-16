import Radix4033

set_option exponentiation.threshold 300

namespace Radix4033Bounds

open Radix4033 AlternateRadix

private theorem nonnegative_square_bound (x limit : Int)
    (hx : 0 ≤ x) (hlimit : 0 ≤ limit) (h : x ≤ limit) :
    x*x ≤ limit*limit := by
  have h1 := Int.mul_le_mul_of_nonneg_right h hx
  have h2 := Int.mul_le_mul_of_nonneg_left h hlimit
  exact Int.le_trans h1 h2

private theorem signed_square_bound (x limit : Int)
    (hlimit : 0 ≤ limit) (h : -limit ≤ x ∧ x ≤ limit) :
    x*x ≤ limit*limit := by
  by_cases hx : 0 ≤ x
  · exact nonnegative_square_bound x limit hx hlimit h.2
  · have hy : 0 ≤ -x := by omega
    have hybound : -x ≤ limit := by omega
    have hs := nonnegative_square_bound (-x) limit hy hlimit hybound
    simpa [Int.neg_mul, Int.mul_neg] using hs

/-- A rounded candidate in the residue class a+65b=r. -/
def nearestB (r : Int) : Int := (127*r+4033) / 8066

theorem nearest_rounding_error (r : Int) :
    -4033 ≤ 8066*nearestB r-127*r ∧
      8066*nearestB r-127*r ≤ 4033 := by
  dsimp [nearestB]
  omega

theorem digit_norm_identity (r b : Int) :
    4*4033*pairNorm (r-65*b) b =
      (8066*b-127*r)*(8066*b-127*r)+3*r*r := by
  simp [pairNorm, Int.mul_sub, Int.add_mul,
        Int.sub_mul, Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
  simp only [← Int.mul_assoc]
  omega

theorem rounded_digit_norm_below_radix (r : Int)
    (hr : 0 ≤ r ∧ r ≤ 2016) :
    pairNorm (r-65*nearestB r) (nearestB r) < 4033 := by
  let b := nearestB r
  let e := 8066*b-127*r
  have herr : -4033 ≤ e ∧ e ≤ 4033 := by
    simpa [e,b] using nearest_rounding_error r
  have he2 := signed_square_bound e 4033 (by decide) herr
  have hr2 := nonnegative_square_bound r 2016 hr.1 (by decide) hr.2
  have hident := digit_norm_identity r b
  dsimp [e,b] at he2 hident
  simp only [Int.mul_assoc] at hident
  omega

/-- A minimum-norm selector that includes the rounded candidate inherits its
uniform digit norm bound. The source-level candidate inclusion is separate. -/
theorem selected_digit_norm_below_radix (r da db : Int)
    (hr : 0 ≤ r ∧ r ≤ 2016)
    (hselect : pairNorm da db ≤
      pairNorm (r-65*nearestB r) (nearestB r)) :
    pairNorm da db < 4033 := by
  have hc := rounded_digit_norm_below_radix r hr
  omega

/-- A selected digit and an exact quotient imply a uniform norm recurrence. -/
theorem quotient_norm_step (a b da db nextA nextB : Int)
    (hquot : mulRadix (nextA,nextB) = (a-da,b-db))
    (hdigit : pairNorm da db ≤ 4033) :
    100*4033*pairNorm nextA nextB ≤
      101*pairNorm a b + 10100*4033 := by
  have hscale := multiply_prime_norm 65 nextA nextB
  have hnorm : AlternateRadix.norm 65 = 4033 := by decide
  have hrewrite : multiplyPrime 65 nextA nextB = mulRadix (nextA,nextB) := by
    apply Prod.ext
    · simp [multiplyPrime, mulRadix]
    · simp [multiplyPrime, mulRadix]
      omega
  rw [hrewrite, hquot, hnorm] at hscale
  have hweight := pair_norm_weighted a b da db
  rw [hscale] at hweight
  omega

/-- Conservative integral recurrence for the 22 quotient steps. -/
def boundStep (q : Nat) : Nat :=
  (101*q + 10100*4033) / (100*4033)

def bound : Nat → Nat
  | 0 => 7*2^260
  | i+1 => boundStep (bound i)

theorem twenty_two_step_numeric_bound : bound 22 = 101 := by decide

theorem terminal_from_recurrence (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 22 →
      100*4033*q (i+1) ≤ 101*q i + 10100*4033) :
    q 22 ≤ 101 := by
  have hall : ∀ i : Nat, i ≤ 22 → q i ≤ bound i := by
    intro i hi
    induction i with
    | zero => simpa [bound] using hzero
    | succ i ih =>
      have hq := hstep i (by omega)
      have hb := ih (by omega)
      simp only [bound, boundStep]
      omega
  have hfinal := hall 22 (by decide)
  simpa only [twenty_two_step_numeric_bound] using hfinal

private theorem square_nonnegative (x : Int) : 0 ≤ x*x := by
  by_cases hx : 0 ≤ x
  · exact Int.mul_nonneg hx hx
  · have hn : 0 ≤ -x := by omega
    have h := Int.mul_nonneg hn hn
    simpa [Int.neg_mul, Int.mul_neg] using h

private theorem square_lower (x limit : Int)
    (hlimit : 0 ≤ limit) (h : limit ≤ x) :
    limit*limit ≤ x*x := by
  have hx : 0 ≤ x := by omega
  calc
    limit*limit ≤ x*limit := Int.mul_le_mul_of_nonneg_right h hlimit
    _ ≤ x*x := Int.mul_le_mul_of_nonneg_left h hx

/-- Norm at most 101 fits the native terminal coordinate table of radius 100. -/
theorem terminal_coordinates (a b : Int)
    (h : pairNorm a b ≤ 101) :
    -100 < a ∧ a < 100 ∧ -100 < b ∧ b < 100 := by
  have hs1 := square_nonnegative (a+2*b)
  have hs2 := square_nonnegative (2*a+3*b)
  have hsa : 4*pairNorm a b = a*a+3*(a+2*b)*(a+2*b) := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
          Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  have hsb : 4*pairNorm a b =
      (2*a+3*b)*(2*a+3*b)+3*b*b := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
          Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  have hs1three : 0 ≤ 3*((a+2*b)*(a+2*b)) :=
    Int.mul_nonneg (by decide) hs1
  simp only [Int.mul_assoc] at hsa hsb
  have ha2 : a*a ≤ 404 := by omega
  have hb3 : 3*(b*b) ≤ 404 := by omega
  have hb2 : b*b ≤ 404 := by omega
  have hal : -100 < a := by
    by_cases hlow : -100 < a
    · exact hlow
    · have hs := square_lower (-a) 100 (by decide) (by omega)
      have hs' : 100*100 ≤ a*a := by
        simpa [Int.neg_mul, Int.mul_neg] using hs
      omega
  have hau : a < 100 := by
    by_cases hu : a < 100
    · exact hu
    · have hs := square_lower a 100 (by decide) (by omega)
      omega
  have hbl : -100 < b := by
    by_cases hlow : -100 < b
    · exact hlow
    · have hs := square_lower (-b) 100 (by decide) (by omega)
      have hs' : 100*100 ≤ b*b := by
        simpa [Int.neg_mul, Int.mul_neg] using hs
      omega
  have hbu : b < 100 := by
    by_cases hu : b < 100
    · exact hu
    · have hs := square_lower b 100 (by decide) (by omega)
      omega
  exact ⟨hal,hau,hbl,hbu⟩

/-- Twenty-two exact selected quotient steps from the secp256k1 four-corner
initial lattice land in the native terminal coordinate table. The hypotheses
expose the selector and executed quotient obligations. -/
theorem terminal_from_verified_digit_steps
    (rw rv dw dv : Int)
    (a b da db r : Nat → Int) (q : Nat → Nat)
    (hrw : 0 ≤ rw ∧ rw < scalarOrder)
    (hrv : 0 ≤ rv ∧ rv < scalarOrder)
    (hdw : 0 ≤ dw ∧ dw ≤ 1) (hdv : 0 ≤ dv ∧ dv ≤ 1)
    (ha : scalarOrder*(a 0) =
      (rw-scalarOrder*dw)*cornerW0 - (rv-scalarOrder*dv)*cornerV0Abs)
    (hb : scalarOrder*(b 0) =
      (rv-scalarOrder*dv)*cornerV1 - (rw-scalarOrder*dw)*cornerW1Abs)
    (hq : ∀ i : Nat, i ≤ 22 → (q i : Int) = pairNorm (a i) (b i))
    (hresidue : ∀ i : Nat, i < 22 → 0 ≤ r i ∧ r i ≤ 2016)
    (hselect : ∀ i : Nat, i < 22 → pairNorm (da i) (db i) ≤
      pairNorm (r i-65*nearestB (r i)) (nearestB (r i)))
    (hquot : ∀ i : Nat, i < 22 →
      mulRadix (a (i+1),b (i+1)) =
        (a i-da i,b i-db i)) :
    -100 < a 22 ∧ a 22 < 100 ∧ -100 < b 22 ∧ b 22 < 100 := by
  obtain ⟨hal, hau, hbl, hbu⟩ :=
    selector_corner_coordinate_bound rw rv dw dv (a 0) (b 0)
      hrw hrv hdw hdv ha hb
  have hnorm := selector_initial_norm_bound (a 0) (b 0)
    ⟨hal,hau⟩ ⟨hbl,hbu⟩
  have hzero : q 0 ≤ 7*2^260 := by
    have hqzero := hq 0 (by decide)
    omega
  have hstep : ∀ i : Nat, i < 22 →
      100*4033*q (i+1) ≤ 101*q i + 10100*4033 := by
    intro i hi
    have hdigit := selected_digit_norm_below_radix
      (r i) (da i) (db i) (hresidue i hi) (hselect i hi)
    have hbound := quotient_norm_step
      (a i) (b i) (da i) (db i) (a (i+1)) (b (i+1))
      (hquot i hi) (Int.le_of_lt hdigit)
    have hcurrent := hq i (by omega)
    have hnext := hq (i+1) (by omega)
    omega
  have hfinal := terminal_from_recurrence q hzero hstep
  have hqfinal := hq 22 (by decide)
  have hnormfinal : pairNorm (a 22) (b 22) ≤ 101 := by omega
  exact terminal_coordinates (a 22) (b 22) hnormfinal

#print axioms nearest_rounding_error
#print axioms digit_norm_identity
#print axioms rounded_digit_norm_below_radix
#print axioms selected_digit_norm_below_radix
#print axioms quotient_norm_step
#print axioms twenty_two_step_numeric_bound
#print axioms terminal_from_recurrence
#print axioms terminal_coordinates
#print axioms terminal_from_verified_digit_steps

end Radix4033Bounds
