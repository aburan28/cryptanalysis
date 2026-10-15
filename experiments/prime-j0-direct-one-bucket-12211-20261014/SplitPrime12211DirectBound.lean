import Lean
import SplitPrimeLatticeCell
import SplitPrimeNormBound

namespace SplitPrime12211Direct

-- tau^2 = 3*tau - 3 and pi = 112 - tau.
theorem norm_trial_division :
    (List.range 109).all (fun i => 12211 % (i+2) != 0) = true := by decide

theorem norm_sqrt_cap : 110*110 < 12211 ∧ 12211 < 111*111 := by decide

theorem quotient_identity (k b : Int) :
    112*(109*k-b)+3*k = 12211*k-112*b ∧
    112*k-(109*k-b)-3*k = b := by
  constructor <;> grind

theorem recoding_step_identity (a b da db k : Int)
    (hk : 12211*k = (a-da)+112*(b-db)) :
    a = da + 112*(109*k-(b-db)) + 3*k ∧
    b = db - (109*k-(b-db)) + 109*k := by
  constructor <;> omega

theorem pi_norm_identity (x y : Int) :
    nrm (112*x+3*y) (-x+109*y) = 12211*nrm x y := by
  unfold nrm
  grind

theorem step_bound (a b da db x y B D R : Int)
    (ha : a = da + 112*x + 3*y)
    (hb : b = db - x + 109*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 12211*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (112*x+3*y) (-x+109*y) := by
    congr 1 <;> omega
  rw [heq, pi_norm_identity] at htri
  have hpos : 0 < (12211 : Int) := by decide
  have hprod : 12211*nrm x y < 12211*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius (i : Nat) : Int :=
  ([196462116142286827589391637123844718211, 1777883101312200412943998541762414320, 16088945716344838882105612736372566, 145596847212529720165752071227836, 1317578062103418137917092190407, 11923417182256139559884700018, 107900914102319067882818187, 976448872512991528939922, 8836370002646717540210, 79964693515108633988, 723640160727763347, 6548578618877186, 59261334921665, 536285203469, 4853110770, 43918261, 397494, 3653, 89] : List Int).getD i 0

theorem radius_checks :
    ∀ i ∈ List.range 18,
      0 ≤ radius i ∧
      (radius i + 6105) * (radius i + 6105) <
        12211 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 18 = 89 := by decide

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
    (hstep : ∀ i < 18,
      (state i).1 = (digit i).1 + 112*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 109*(state (i+1)).2)
    (hdigit : ∀ i < 18, nrm (digit i).1 (digit i).2 ≤ 6105*6105) :
    nrm (state 18).1 (state 18).2 < 89*89 := by
  have hbound : ∀ i ≤ 18,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 18 := by omega
        have hjle : j ≤ 18 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 6105 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 17 < 18 := by decide
  have hc := radius_checks 17 (List.mem_range.mpr hj)
  have hs := hstep 17 hj
  have hd := hdigit 17 hj
  have hn := step_bound
    (state 17).1 (state 17).2 (digit 17).1 (digit 17).2
    (state 18).1 (state 18).2
    (radius 17) 6105 (radius 18)
    hs.1 hs.2 (hbound 17 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 18,
      (state i).1 = (digit i).1 + 112*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 + 109*(state (i+1)).2)
    (hdigit : ∀ i < 18, nrm (digit i).1 (digit i).2 ≤ 6105*6105) :
    nrm (state 18).1 (state 18).2 < 89*89 := by
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

end SplitPrime12211Direct
