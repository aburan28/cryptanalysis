import NearestOrbit19183Selector

namespace NearestOrbit19183Digits
open NearestOrbit19183Selector SplitPrime12211Nearest

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem all_residues_have_small_candidate :
    (List.range 9592).all boundCheck = true := by decide

theorem selected_digit_valid (r : Nat) (hr : r < 9592) :
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤ 6348 ∧
    ((selectedDigit r).1 + 140*(selectedDigit r).2 - (r : Int)) % 19183 = 0 := by
  have hc := (List.all_eq_true.mp all_residues_have_small_candidate) r
    (List.mem_range.mpr hr)
  obtain ⟨q, hq, hsmall⟩ := List.any_eq_true.mp hc
  have hs : nrm q.1 q.2 ≤ 6348 := of_decide_eq_true hsmall
  constructor
  · calc
      nrm (selectedDigit r).1 (selectedDigit r).2 ≤ nrm q.1 q.2 := selected_le_candidate r q hq
      _ ≤ 6348 := hs
  · exact selected_congruent r

#print axioms all_residues_have_small_candidate
#print axioms selected_digit_valid
end NearestOrbit19183Digits
