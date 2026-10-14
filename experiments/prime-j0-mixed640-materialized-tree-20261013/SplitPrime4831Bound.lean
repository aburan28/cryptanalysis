import Lean
import SplitPrimeLatticeCell
import SplitPrimeNormBound

namespace SplitPrime4831

-- tau^2 = 3*tau - 3 and pi = 71 - tau.
theorem norm_trial_division :
    (List.range 68).all (fun i => 4831 % (i+2) != 0) = true := by decide

theorem norm_sqrt_cap : 69*69 < 4831 ∧ 4831 < 70*70 := by decide

theorem quotient_identity (k b : Int) :
    71*(68*k-b)+3*k = 4831*k-71*b ∧
    71*k-(68*k-b)-3*k = b := by
  constructor <;> grind

theorem recoding_step_identity (a b da db k : Int)
    (hk : 4831*k = (a-da)+71*(b-db)) :
    a = da + 71*(68*k-(b-db)) + 3*k ∧
    b = db - (68*k-(b-db)) + 68*k := by
  constructor <;> omega

theorem pi_norm_identity (x y : Int) :
    nrm (71*x+3*y) (-x+68*y) = 4831*nrm x y := by
  unfold nrm
  grind

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 71*x + 3*y)
    (hb : b = db - x + 68*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 4831*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (71*x+3*y) (-x+68*y) := by
    congr 1 <;> omega
  rw [heq, pi_norm_identity] at htri
  have hpos : 0 < (4831 : Int) := by decide
  have hprod : 4831*nrm x y < 4831*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius : Nat → Int
  | 0 => 33 * 69 ^ 20
  | i + 1 => (radius i + 1564 + 68) / 69

theorem radius_checks :
    ∀ i ∈ List.range 20,
      0 ≤ radius i ∧
      (radius i + 1564) * (radius i + 1564) <
        4831 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 20 = 56 := by decide

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
    (hstep : ∀ i < 20,
      (state i).1 = (digit i).1 + 71*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 68*(state (i+1)).2)
    (hdigit : ∀ i < 20, nrm (digit i).1 (digit i).2 ≤ 1564*1564) :
    nrm (state 20).1 (state 20).2 < 56*56 := by
  have hbound : ∀ i ≤ 20,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 20 := by omega
        have hjle : j ≤ 20 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 1564 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 19 < 20 := by decide
  have hc := radius_checks 19 (List.mem_range.mpr hj)
  have hs := hstep 19 hj
  have hd := hdigit 19 hj
  have hn := step_bound
    (state 19).1 (state 19).2 (digit 19).1 (digit 19).2
    (state 20).1 (state 20).2
    (radius 19) 1564 (radius 20)
    hs.1 hs.2 (hbound 19 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 20,
      (state i).1 = (digit i).1 + 71*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 68*(state (i+1)).2)
    (hdigit : ∀ i < 20, nrm (digit i).1 (digit i).2 ≤ 1564*1564) :
    nrm (state 20).1 (state 20).2 < 56*56 := by
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

#print axioms pi_norm_identity
#print axioms norm_trial_division
#print axioms recoding_step_identity
#print axioms step_bound
#print axioms radius_checks
#print axioms selected_terminal_bound

end SplitPrime4831
