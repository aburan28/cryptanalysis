import NearestOrbit19183Complete

namespace UnitBasisSplit
open NearestOrbit19183Selector NearestOrbit19183Digits

-- omega = 1-tau, so (a,b) in the 1,tau basis has coordinates
-- (a+b,-b) in the 1,omega basis.
def split (a b : Int) : Int × Int := (a+b, -b)

theorem split_pair (a b : Int) :
    (split a b).1 + (split a b).2 = a ∧
    -(split a b).2 = b := by
  simp only [split, Prod.fst, Prod.snd]
  constructor <;> omega

theorem split_value (a b lambda : Int) :
    a+b*lambda = (split a b).1 + (split a b).2*(1-lambda) := by
  simp only [split, Prod.fst, Prod.snd]
  grind

private theorem square_bound_92 (x : Int) (h : x*x ≤ 8464) :
    -92 ≤ x ∧ x ≤ 92 := by
  constructor
  · by_cases hn : -92 ≤ x
    · exact hn
    have hx : 93 ≤ -x := by omega
    have hp : 0 ≤ (-x-93)*(-x+93) :=
      Int.mul_nonneg (by omega) (by omega)
    have heq : (-x-93)*(-x+93) = x*x-8649 := by grind
    omega
  · by_cases hn : x ≤ 92
    · exact hn
    have hx : 93 ≤ x := by omega
    have hp : 0 ≤ (x-93)*(x+93) :=
      Int.mul_nonneg (by omega) (by omega)
    have heq : (x-93)*(x+93) = x*x-8649 := by grind
    omega

private theorem square_bound_90 (x : Int) (h : x*x < 8112) :
    -90 ≤ x ∧ x ≤ 90 := by
  constructor
  · by_cases hn : -90 ≤ x
    · exact hn
    have hx : 91 ≤ -x := by omega
    have hp : 0 ≤ (-x-91)*(-x+91) :=
      Int.mul_nonneg (by omega) (by omega)
    have heq : (-x-91)*(-x+91) = x*x-8281 := by grind
    omega
  · by_cases hn : x ≤ 90
    · exact hn
    have hx : 91 ≤ x := by omega
    have hp : 0 ≤ (x-91)*(x+91) :=
      Int.mul_nonneg (by omega) (by omega)
    have heq : (x-91)*(x+91) = x*x-8281 := by grind
    omega

theorem norm_digit_coefficient_bounds (a b : Int)
    (h : nrm a b ≤ 6348) :
    -(92 : Int) ≤ a+b ∧ a+b ≤ 92 ∧ -92 ≤ b ∧ b ≤ 92 := by
  have hid1 : 4*nrm a b =
      3*((a+b)*(a+b))+(a+3*b)*(a+3*b) := by unfold nrm; grind
  have hid2 : 4*nrm a b =
      3*(b*b)+(2*a+3*b)*(2*a+3*b) := by unfold nrm; grind
  have h1 := sq_nonneg (a+3*b)
  have h2 := sq_nonneg (2*a+3*b)
  have hx : (a+b)*(a+b) ≤ 8464 := by omega
  have hy : b*b ≤ 8464 := by omega
  obtain ⟨hxlo,hxhi⟩ := square_bound_92 (a+b) hx
  obtain ⟨hylo,hyhi⟩ := square_bound_92 b hy
  exact ⟨hxlo,hxhi,hylo,hyhi⟩

theorem selected_digit_coefficient_bounds (r : Nat) (hr : r < 9592) :
    -(92 : Int) ≤ (split (selectedDigit r).1 (selectedDigit r).2).1 ∧
    (split (selectedDigit r).1 (selectedDigit r).2).1 ≤ 92 ∧
    -92 ≤ (split (selectedDigit r).1 (selectedDigit r).2).2 ∧
    (split (selectedDigit r).1 (selectedDigit r).2).2 ≤ 92 := by
  have h := (selected_digit_valid r hr).1
  have bounds := norm_digit_coefficient_bounds
    (selectedDigit r).1 (selectedDigit r).2 h
  simp only [split, Prod.fst, Prod.snd]
  omega

theorem norm_terminal_coefficient_bounds (a b : Int)
    (h : nrm a b < 78*78) :
    -(90 : Int) ≤ a+b ∧ a+b ≤ 90 ∧ -90 ≤ b ∧ b ≤ 90 := by
  have hid1 : 4*nrm a b =
      3*((a+b)*(a+b))+(a+3*b)*(a+3*b) := by unfold nrm; grind
  have hid2 : 4*nrm a b =
      3*(b*b)+(2*a+3*b)*(2*a+3*b) := by unfold nrm; grind
  have h1 := sq_nonneg (a+3*b)
  have h2 := sq_nonneg (2*a+3*b)
  have hx : (a+b)*(a+b) < 8112 := by omega
  have hy : b*b < 8112 := by omega
  obtain ⟨hxlo,hxhi⟩ := square_bound_90 (a+b) hx
  obtain ⟨hylo,hyhi⟩ := square_bound_90 b hy
  exact ⟨hxlo,hxhi,hylo,hyhi⟩

#print axioms split_pair
#print axioms split_value
#print axioms norm_digit_coefficient_bounds
#print axioms selected_digit_coefficient_bounds
#print axioms norm_terminal_coefficient_bounds

end UnitBasisSplit
