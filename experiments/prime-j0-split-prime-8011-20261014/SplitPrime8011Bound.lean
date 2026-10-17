import Lean
import SplitPrimeLatticeCell
import SplitPrimeNormBound

namespace SplitPrime8011

-- tau^2 = 3*tau - 3 and pi = 91 - tau.
theorem norm_trial_division :
    (List.range 88).all (fun i => 8011 % (i+2) != 0) = true := by decide

theorem norm_sqrt_cap : 89*89 < 8011 ∧ 8011 < 90*90 := by decide

theorem quotient_identity (k b : Int) :
    91*(88*k-b)+3*k = 8011*k-91*b ∧
    91*k-(88*k-b)-3*k = b := by
  constructor <;> grind

theorem recoding_step_identity (a b da db k : Int)
    (hk : 8011*k = (a-da)+91*(b-db)) :
    a = da + 91*(88*k-(b-db)) + 3*k ∧
    b = db - (88*k-(b-db)) + 88*k := by
  constructor <;> omega

theorem pi_norm_identity (x y : Int) :
    nrm (91*x+3*y) (-x+88*y) = 8011*nrm x y := by
  unfold nrm
  grind

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 91*x + 3*y)
    (hb : b = db - x + 88*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 8011*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (91*x+3*y) (-x+88*y) := by
    congr 1 <;> omega
  rw [heq, pi_norm_identity] at htri
  have hpos : 0 < (8011 : Int) := by decide
  have hprod : 8011*nrm x y < 8011*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius (i : Nat) : Int :=
  ([196462116142286827589391637123844718211, 2195004686151344771069511112064924582, 24524043957344504754636329687160774, 273998837367537732002185883418446, 3061296212376046031036865520834, 34202825785487171639269240252, 382136588737491702788274343, 4269482684494716220106040, 47701484051615491547687, 532952525838811162196, 5954498071603481687, 66527590293198278, 743290234877509, 8304530057851, 92783701800, 1036640906, 11582068, 129433, 1476, 46] : List Int).getD i 0

theorem radius_checks :
    ∀ i ∈ List.range 19,
      0 ≤ radius i ∧
      (radius i + 2640) * (radius i + 2640) <
        8011 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 19 = 46 := by decide

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
    (hstep : ∀ i < 19,
      (state i).1 = (digit i).1 + 91*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 88*(state (i+1)).2)
    (hdigit : ∀ i < 19, nrm (digit i).1 (digit i).2 ≤ 2640*2640) :
    nrm (state 19).1 (state 19).2 < 46*46 := by
  have hbound : ∀ i ≤ 19,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 19 := by omega
        have hjle : j ≤ 19 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 2640 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 18 < 19 := by decide
  have hc := radius_checks 18 (List.mem_range.mpr hj)
  have hs := hstep 18 hj
  have hd := hdigit 18 hj
  have hn := step_bound
    (state 18).1 (state 18).2 (digit 18).1 (digit 18).2
    (state 19).1 (state 19).2
    (radius 18) 2640 (radius 19)
    hs.1 hs.2 (hbound 18 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 19,
      (state i).1 = (digit i).1 + 91*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 88*(state (i+1)).2)
    (hdigit : ∀ i < 19, nrm (digit i).1 (digit i).2 ≤ 2640*2640) :
    nrm (state 19).1 (state 19).2 < 46*46 := by
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
#print axioms norm_sqrt_cap
#print axioms recoding_step_identity
#print axioms step_bound
#print axioms radius_checks
#print axioms selected_terminal_bound

end SplitPrime8011
