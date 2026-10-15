import SplitPrime12211NearestComplete

namespace SplitPrime12211GlobalMin
open SplitPrime12211NearestDigits

def cosetNorm (x b : Int) : Int := nrm (x-112*b) b

def center (x : Int) : Int := (2*x+110)/221

def offset (x : Int) : Int := 2*x-221*center x

theorem center_bounds (x : Int) (hx0 : -12211 ≤ x) (hx1 : x ≤ 6105) :
    -111 ≤ center x ∧ center x ≤ 56 ∧
    -110 ≤ offset x ∧ offset x ≤ 110 ∧
    2*x = 221*center x + offset x := by
  have hrem0 : 0 ≤ (2*x+110)%221 := Int.emod_nonneg _ (by decide)
  have hrem1 : (2*x+110)%221 < 221 := Int.emod_lt _ (by decide)
  have hdiv : 2*x+110 = 221*((2*x+110)/221)+(2*x+110)%221 := by
    omega
  unfold offset center
  omega

theorem quadratic_form (x b : Int) :
    cosetNorm x b = x*x - 221*x*b + 12211*b*b := by
  unfold cosetNorm nrm
  grind

theorem upper_tail (x c e b : Int)
    (he : 2*x = 221*c+e)
    (hc0 : -111 ≤ c) (hc1 : c ≤ 56)
    (he0 : -110 ≤ e) (he1 : e ≤ 110)
    (hb : c+2 ≤ b) :
    cosetNorm x (c+1) < cosetNorm x b := by
  let d := b-(c+1)
  have hd : 1 ≤ d := by dsimp [d]; omega
  have hfactor : 0 < 24422*d+3*c+48844-221*e := by omega
  have hprod : 0 < d*(24422*d+3*c+48844-221*e) := by
    apply Int.mul_pos
    · omega
    · exact hfactor
  have hidentity :
      2*(cosetNorm x b-cosetNorm x (c+1)) =
      d*(24422*d+3*c+48844-221*e) := by
    dsimp [d, cosetNorm, nrm]
    grind
  omega

theorem lower_tail (x c e b : Int)
    (he : 2*x = 221*c+e)
    (hc0 : -111 ≤ c) (hc1 : c ≤ 56)
    (he0 : -110 ≤ e) (he1 : e ≤ 110)
    (hb : b ≤ c-2) :
    cosetNorm x (c-1) < cosetNorm x b := by
  let d := (c-1)-b
  have hd : 1 ≤ d := by dsimp [d]; omega
  have hfactor : 0 < 24422*d-3*c+48844+221*e := by omega
  have hprod : 0 < d*(24422*d-3*c+48844+221*e) := by
    apply Int.mul_pos
    · omega
    · exact hfactor
  have hidentity :
      2*(cosetNorm x b-cosetNorm x (c-1)) =
      d*(24422*d-3*c+48844+221*e) := by
    dsimp [d, cosetNorm, nrm]
    grind
  omega

theorem local_min (x b : Int) (hx0 : -12211 ≤ x) (hx1 : x ≤ 6105) :
    ∃ choice : Int,
      (choice = center x-1 ∨ choice = center x ∨ choice = center x+1) ∧
      cosetNorm x choice ≤ cosetNorm x b := by
  rcases center_bounds x hx0 hx1 with ⟨hc0, hc1, he0, he1, he⟩
  by_cases hlow : b ≤ center x-2
  · refine ⟨center x-1, Or.inl rfl, ?_⟩
    have ht := lower_tail x (center x) (offset x) b he hc0 hc1 he0 he1 hlow
    omega
  by_cases hhigh : center x+2 ≤ b
  · refine ⟨center x+1, Or.inr (Or.inr rfl), ?_⟩
    have ht := upper_tail x (center x) (offset x) b he hc0 hc1 he0 he1 hhigh
    omega
  have hcases : b = center x-1 ∨ b = center x ∨ b = center x+1 := by omega
  rcases hcases with h | h | h
  · exact ⟨b, Or.inl h, by omega⟩
  · exact ⟨b, Or.inr (Or.inl h), by omega⟩
  · exact ⟨b, Or.inr (Or.inr h), by omega⟩

private theorem square_ge_of_ge (x c : Int) (hc : 0 ≤ c) (h : c ≤ x) :
    c*c ≤ x*x := by
  have hx : 0 ≤ x := by omega
  have h1 : c*c ≤ c*x := Int.mul_le_mul_of_nonneg_left h hc
  have h2 : c*x ≤ x*x := Int.mul_le_mul_of_nonneg_right h hx
  omega

theorem small_coordinates (a b : Int) (hn : nrm a b < 3997) :
    -126 ≤ a ∧ a ≤ 126 ∧ -73 ≤ b ∧ b ≤ 73 := by
  have haid : 4*nrm a b = a*a+3*((a+2*b)*(a+2*b)) := by
    unfold nrm
    grind
  have hbid : 4*nrm a b = (2*a+3*b)*(2*a+3*b)+3*(b*b) := by
    unfold nrm
    grind
  have hsa := sq_nonneg (a+2*b)
  have hsb := sq_nonneg (2*a+3*b)
  have ha2 : a*a < 15988 := by omega
  have hb2 : b*b < 5330 := by omega
  have ha0 : -126 ≤ a := by
    by_cases h : -126 ≤ a
    · exact h
    have hge : 127 ≤ -a := by omega
    have hs := square_ge_of_ge (-a) 127 (by decide) hge
    have heq : (-a)*(-a) = a*a := by grind
    omega
  have ha1 : a ≤ 126 := by
    by_cases h : a ≤ 126
    · exact h
    have hge : 127 ≤ a := by omega
    have hs := square_ge_of_ge a 127 (by decide) hge
    omega
  have hb0 : -73 ≤ b := by
    by_cases h : -73 ≤ b
    · exact h
    have hge : 74 ≤ -b := by omega
    have hs := square_ge_of_ge (-b) 74 (by decide) hge
    have heq : (-b)*(-b) = b*b := by grind
    omega
  have hb1 : b ≤ 73 := by
    by_cases h : b ≤ 73
    · exact h
    have hge : 74 ≤ b := by omega
    have hs := square_ge_of_ge b 74 (by decide) hge
    omega
  exact ⟨ha0, ha1, hb0, hb1⟩

theorem small_lift (a b : Int) (r : Nat) (hr : r < 6106)
    (hcong : (a+112*b-(r : Int))%12211 = 0)
    (hn : nrm a b < 3997) :
    a+112*b = (r : Int) ∨ a+112*b = (r : Int)-12211 := by
  rcases small_coordinates a b hn with ⟨ha0, ha1, hb0, hb1⟩
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hcong
  have hq : 12211*k = a+112*b-(r : Int) := by omega
  have hcases : k = 0 ∨ k = -1 := by omega
  rcases hcases with h | h
  · left
    omega
  · right
    omega

theorem local_choice_mem (r : Nat) (x choice : Int)
    (hx : x = (r : Int) ∨ x = (r : Int)-12211)
    (hc : choice = center x-1 ∨ choice = center x ∨
      choice = center x+1) :
    SplitPrime12211NearestDigits.candidate x choice ∈ candidates r := by
  rcases hx with hx | hx
  · subst x
    rcases hc with hc | hc | hc <;> subst choice <;>
      simp [candidates, center]
  · subst x
    rcases hc with hc | hc | hc <;> subst choice <;>
      simp [candidates, center]

theorem selected_is_global_minimum (r : Nat) (hr : r < 6106)
    (a b : Int) (hcong : (a+112*b-(r : Int))%12211 = 0) :
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤ nrm a b := by
  have hs := (selected_digit_valid r hr).1
  by_cases hbig : 3997 ≤ nrm a b
  · omega
  have hsmall : nrm a b < 3997 := by omega
  let x : Int := a+112*b
  have hxcase : x = (r : Int) ∨ x = (r : Int)-12211 :=
    small_lift a b r hr hcong hsmall
  have hx0 : -12211 ≤ x := by rcases hxcase with h | h <;> omega
  have hx1 : x ≤ 6105 := by rcases hxcase with h | h <;> omega
  obtain ⟨choice, hc, hcost⟩ := local_min x b hx0 hx1
  have hmem : SplitPrime12211NearestDigits.candidate x choice ∈ candidates r :=
    local_choice_mem r x choice hxcase hc
  have hselect := selected_le_candidate r
    (SplitPrime12211NearestDigits.candidate x choice) hmem
  have hpoint : cosetNorm x b = nrm a b := by
    dsimp [cosetNorm, x]
    congr 1 <;> omega
  calc
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤
        nrm (SplitPrime12211NearestDigits.candidate x choice).1
            (SplitPrime12211NearestDigits.candidate x choice).2 := hselect
    _ = cosetNorm x choice := rfl
    _ ≤ cosetNorm x b := hcost
    _ = nrm a b := hpoint

theorem runtime_digit_is_global_minimum (r : Nat) (hr : r < 12211)
    (a b : Int) (hcong : (a+112*b-(r : Int))%12211 = 0) :
    nrm (SplitPrime12211NearestStep.nearestDigit r).1
        (SplitPrime12211NearestStep.nearestDigit r).2 ≤ nrm a b := by
  by_cases h : r ≤ 6105
  · simpa [SplitPrime12211NearestStep.nearestDigit, h] using
      selected_is_global_minimum r (by omega) a b hcong
  · have hc : 12211-r < 6106 := by omega
    have hneg : (-a+112*(-b)-((12211-r : Nat) : Int))%12211 = 0 := by
      omega
    have hs := selected_is_global_minimum (12211-r) hc (-a) (-b) hneg
    simpa [SplitPrime12211NearestStep.nearestDigit, h,
      SplitPrime12211NearestStep.neg_norm] using hs

#print axioms quadratic_form
#print axioms center_bounds
#print axioms upper_tail
#print axioms lower_tail
#print axioms local_min
#print axioms small_coordinates
#print axioms small_lift
#print axioms local_choice_mem
#print axioms selected_is_global_minimum
#print axioms runtime_digit_is_global_minimum
end SplitPrime12211GlobalMin
