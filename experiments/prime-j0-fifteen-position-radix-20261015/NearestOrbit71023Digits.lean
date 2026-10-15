import NearestOrbit71023Selector

namespace NearestOrbit71023Digits
open NearestOrbit71023Selector SplitPrime12211Nearest

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
theorem all_residues_have_small_candidate :
    (List.range 35512).all boundCheck = true := by decide

theorem selected_digit_valid (r : Nat) (hr : r < 35512) :
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤ 23497 ∧
    ((selectedDigit r).1 + 268*(selectedDigit r).2 - (r : Int)) % 71023 = 0 := by
  have hc := (List.all_eq_true.mp all_residues_have_small_candidate) r
    (List.mem_range.mpr hr)
  obtain ⟨q, hq, hsmall⟩ := List.any_eq_true.mp hc
  have hs : nrm q.1 q.2 ≤ 23497 := of_decide_eq_true hsmall
  constructor
  · calc
      nrm (selectedDigit r).1 (selectedDigit r).2 ≤ nrm q.1 q.2 := selected_le_candidate r q hq
      _ ≤ 23497 := hs
  · exact selected_congruent r

#print axioms all_residues_have_small_candidate
#print axioms selected_digit_valid
end NearestOrbit71023Digits
