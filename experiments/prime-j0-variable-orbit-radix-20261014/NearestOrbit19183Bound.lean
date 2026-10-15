import SplitPrime12211NearestBound

namespace NearestOrbit19183
open SplitPrime12211Nearest

theorem norm_trial_division :
    (List.range 137).all (fun i => 19183 % (i+2) != 0) = true := by decide

theorem radix_norm_identity (x y : Int) :
    nrm (140*x+3*y) (-x+137*y) = 19183*nrm x y := by
  unfold nrm
  grind

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 140*x + 3*y)
    (hb : b = db - x + 137*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 19183*(R*R)) :
    nrm x y < R*R := by
  have hdneg : nrm (-da) (-db) ≤ D*D := by
    have heq : nrm (-da) (-db) = nrm da db := by
      unfold nrm
      grind
    omega
  have htri := triangle_bound a b (-da) (-db) B D hB hdneg hB0 hD0
  have hterms : nrm (a + -da) (b + -db) = nrm (a-da) (b-db) := by
    congr 1 <;> omega
  rw [hterms] at htri
  have heq : nrm (a-da) (b-db) = nrm (140*x+3*y) (-x+137*y) := by
    congr 1 <;> omega
  rw [heq, radix_norm_identity] at htri
  have hpos : 0 < (19183 : Int) := by decide
  have hprod : 19183*nrm x y < 19183*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius (i : Nat) : Int :=
  ([196462116142286827589391637123844718211,
    1418471303635765583620358079301134012,
    10241469850507575853067384513571638,
    73944185144959890716799149210298,
    533882596596339251059134885763,
    3854672634361668702330143837,
    27831027294809948968312303,
    200942117205946343237771,
    1450817249377571233297,
    10475010019597891011,
    75630362788801087,
    546056926424329,
    3942572214399,
    28465668897,
    205524279,
    1483902,
    10715,
    78] : List Int).getD i 0

theorem radius_checks :
    ∀ i ∈ List.range 17,
      0 ≤ radius i ∧
      (radius i + 80) * (radius i + 80) <
        19183 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 17 = 78 := by decide

theorem initial_radius_from_cell (a b : Int)
    (hcell : 3*nrm a b ≤
      115792089237316195423570985008687907852837564279074904382605163141518161494337) :
    nrm a b ≤ radius 0 * radius 0 := by
  have hn :
      115792089237316195423570985008687907852837564279074904382605163141518161494337
      < 3 * (radius 0 * radius 0) := by decide
  omega

theorem terminal_bound (state digit : Nat → Int × Int)
    (hinitial : nrm (state 0).1 (state 0).2 ≤ radius 0 * radius 0)
    (hstep : ∀ i < 17,
      (state i).1 = (digit i).1 + 140*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 137*(state (i+1)).2)
    (hdigit : ∀ i < 17, nrm (digit i).1 (digit i).2 ≤ 80*80) :
    nrm (state 17).1 (state 17).2 < 78*78 := by
  have hbound : ∀ i ≤ 17,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 17 := by omega
        have hjle : j ≤ 17 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 80 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 16 < 17 := by decide
  have hc := radius_checks 16 (List.mem_range.mpr hj)
  have hs := hstep 16 hj
  have hd := hdigit 16 hj
  have hn := step_bound
    (state 16).1 (state 16).2 (digit 16).1 (digit 16).2
    (state 17).1 (state 17).2
    (radius 16) 80 (radius 17)
    hs.1 hs.2 (hbound 16 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 17,
      (state i).1 = (digit i).1 + 140*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 137*(state (i+1)).2)
    (hdigit : ∀ i < 17, nrm (digit i).1 (digit i).2 ≤ 80*80) :
    nrm (state 17).1 (state 17).2 < 78*78 := by
  have hnorm : nrm (state 0).1 (state 0).2 = selectedNorm scalar := by
    rw [hstart]
    simpa [nrm, eNorm] using selected_candidate_norm scalar
  have hcell : 3*nrm (state 0).1 (state 0).2 ≤
      115792089237316195423570985008687907852837564279074904382605163141518161494337 := by
    rw [hnorm]
    have h := selected_norm_bound scalar
    simpa [order] using h
  exact terminal_bound state digit
    (initial_radius_from_cell _ _ hcell) hstep hdigit

#print axioms norm_trial_division
#print axioms radix_norm_identity
#print axioms radius_checks
#print axioms selected_terminal_bound
end NearestOrbit19183
