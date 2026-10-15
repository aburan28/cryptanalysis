import SplitPrime12211NearestSelector

namespace SplitPrime12211NearestDigits

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem all_residues_have_small_candidate :
    (List.range 6106).all boundCheck = true := by decide

theorem selected_digit_valid (r : Nat) (hr : r < 6106) :
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤ 3997 ∧
    ((selectedDigit r).1 + 112*(selectedDigit r).2 - (r : Int)) % 12211 = 0 := by
  have hc := (List.all_eq_true.mp all_residues_have_small_candidate) r
    (List.mem_range.mpr hr)
  obtain ⟨q, hq, hsmall⟩ := List.any_eq_true.mp hc
  have hs : nrm q.1 q.2 ≤ 3997 := of_decide_eq_true hsmall
  constructor
  · calc
      nrm (selectedDigit r).1 (selectedDigit r).2 ≤ nrm q.1 q.2 := selected_le_candidate r q hq
      _ ≤ 3997 := hs
  · exact selected_congruent r

#print axioms all_residues_have_small_candidate
#print axioms selected_digit_valid
end SplitPrime12211NearestDigits
