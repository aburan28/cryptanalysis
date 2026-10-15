import SplitPrime12211NearestBound

namespace NearestOrbit53593
open SplitPrime12211Nearest

theorem norm_trial_division :
    (List.range 230).all (fun i => 53593 % (i+2) != 0) = true := by decide

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 233*x + 3*y)
    (hb : b = db - x + 230*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 53593*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (233*x+3*y) (-x+230*y) := by
    congr 1 <;> omega
  rw [heq] at htri
  have hnorm : nrm (233*x+3*y) (-x+230*y) = 53593*nrm x y := by
    unfold nrm
    grind
  rw [hnorm] at htri
  have hpos : 0 < (53593 : Int) := by decide
  have hprod : 53593*nrm x y < 53593*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius (i : Nat) : Int :=
  ([196462116142286827589391637123844718211,
    848642511689860374392781372877572866,
    3665816732451753542242300993111876,
    15834950678071023723112745561503,
    68401036188527485720939320306,
    295466771370720499377022104,
    1276305416538120383649719,
    5513159766587436780495,
    23814778357959442161,
    102870892963398892,
    444363598939404,
    1919483756525,
    8291448491,
    35815943,
    154712,
    669,
    4] : List Int).getD i 0

theorem radius_checks :
    ∀ i ∈ List.range 16,
      0 ≤ radius i ∧
      (radius i + 134) * (radius i + 134) <
        53593 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 16 = 4 := by decide

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
    (hstep : ∀ i < 16,
      (state i).1 = (digit i).1 + 233*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 230*(state (i+1)).2)
    (hdigit : ∀ i < 16, nrm (digit i).1 (digit i).2 ≤ 134*134) :
    nrm (state 16).1 (state 16).2 < 4*4 := by
  have hbound : ∀ i ≤ 16,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 16 := by omega
        have hjle : j ≤ 16 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 134 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 15 < 16 := by decide
  have hc := radius_checks 15 (List.mem_range.mpr hj)
  have hs := hstep 15 hj
  have hd := hdigit 15 hj
  have hn := step_bound
    (state 15).1 (state 15).2 (digit 15).1 (digit 15).2
    (state 16).1 (state 16).2
    (radius 15) 134 (radius 16)
    hs.1 hs.2 (hbound 15 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 16,
      (state i).1 = (digit i).1 + 233*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 230*(state (i+1)).2)
    (hdigit : ∀ i < 16, nrm (digit i).1 (digit i).2 ≤ 134*134) :
    nrm (state 16).1 (state 16).2 < 4*4 := by
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
#print axioms step_bound
#print axioms radius_checks
#print axioms selected_terminal_bound
end NearestOrbit53593
