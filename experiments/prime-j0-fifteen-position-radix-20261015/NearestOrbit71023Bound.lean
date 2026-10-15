import SplitPrime12211NearestBound

namespace NearestOrbit71023
open SplitPrime12211Nearest

set_option maxRecDepth 100000 in
theorem norm_trial_division :
    (List.range 265).all (fun i => 71023 % (i+2) != 0) = true := by decide

theorem radix_norm_identity (x y : Int) :
    nrm (268*x+3*y) (-x+265*y) = 71023*nrm x y := by
  unfold nrm
  grind

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 268*x + 3*y)
    (hb : b = db - x + 265*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 71023*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (268*x+3*y) (-x+265*y) := by
    congr 1 <;> omega
  rw [heq, radix_norm_identity] at htri
  have hpos : 0 < (71023 : Int) := by decide
  have hprod : 71023*nrm x y < 71023*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius (i : Nat) : Int :=
  ([
    196462116142286827589391637123844718211,
    737189789206598017108375911713710776,
    2766175973167661568638210679974724,
    10379592374394182407225489091052,
    38947608143385404286473546317,
    146144099438128245881270703,
    548380216878833677632227,
    2057701018516934596981,
    7721163804384969344,
    28972319087013146,
    108713568905637,
    407928686300,
    1530681173,
    5743615,
    21553,
    82] : List Int).getD i 0

theorem radius_checks :
    ∀ i ∈ List.range 15,
      0 ≤ radius i ∧
      (radius i + 154) * (radius i + 154) <
        71023 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 15 = 82 := by decide

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
    (hstep : ∀ i < 15,
      (state i).1 = (digit i).1 + 268*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 265*(state (i+1)).2)
    (hdigit : ∀ i < 15, nrm (digit i).1 (digit i).2 ≤ 154*154) :
    nrm (state 15).1 (state 15).2 < 82*82 := by
  have hbound : ∀ i ≤ 15,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 15 := by omega
        have hjle : j ≤ 15 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 154 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 14 < 15 := by decide
  have hc := radius_checks 14 (List.mem_range.mpr hj)
  have hs := hstep 14 hj
  have hd := hdigit 14 hj
  have hn := step_bound
    (state 14).1 (state 14).2 (digit 14).1 (digit 14).2
    (state 15).1 (state 15).2
    (radius 14) 154 (radius 15)
    hs.1 hs.2 (hbound 14 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 15,
      (state i).1 = (digit i).1 + 268*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 265*(state (i+1)).2)
    (hdigit : ∀ i < 15, nrm (digit i).1 (digit i).2 ≤ 154*154) :
    nrm (state 15).1 (state 15).2 < 82*82 := by
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
end NearestOrbit71023
