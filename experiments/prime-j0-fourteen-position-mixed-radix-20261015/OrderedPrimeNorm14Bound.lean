import SplitPrime12211NearestBound

namespace OrderedPrimeNorm14
open SplitPrime12211Nearest

def radix (i : Nat) : Int :=
  ([394, 380, 380, 371, 371, 371, 371, 371, 371, 371, 371, 371, 371, 371] : List Int).getD i 0

def digitRadius (i : Nat) : Int :=
  ([227, 219, 219, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214] : List Int).getD i 0

def radius (i : Nat) : Int :=
  ([196462116142286827589391637123844718211,
    500539204893499577535820936979797876,
    1322425085069037573324748128430572,
    3493848410919075947982528196254,
    9455585425170859181347962581,
    25590147372531336824475968,
    69255959636792077853001,
    187431040368351047195,
    507254467020618599,
    1372809401296051,
    3715306172377,
    10054928195,
    27212181,
    73647,
    200] : List Int).getD i 0

theorem radix_norm_identity (t x y : Int) :
    nrm (t*x+3*y) (-x+(t-3)*y) = (t*t-3*t+3)*nrm x y := by
  unfold nrm
  grind

theorem numeric_checks :
    ∀ i ∈ List.range 14,
      0 ≤ radius i ∧ 0 ≤ digitRadius i ∧
      0 < radix i * radix i - 3 * radix i + 3 ∧
      (radius i + digitRadius i) * (radius i + digitRadius i) <
        (radix i * radix i - 3 * radix i + 3) *
          (radius (i+1) * radius (i+1)) := by
  decide

theorem step_bound (t a b da db x y B D R : Int)
    (ha : a = da + t*x + 3*y)
    (hb : b = db - x + (t-3)*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hq : 0 < t*t-3*t+3)
    (hR : (B+D)*(B+D) < (t*t-3*t+3)*(R*R)) :
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
  have heq : nrm (a-da) (b-db) = nrm (t*x+3*y) (-x+(t-3)*y) := by
    congr 1 <;> omega
  rw [heq, radix_norm_identity] at htri
  have hprod : (t*t-3*t+3)*nrm x y < (t*t-3*t+3)*(R*R) := by omega
  exact (Int.mul_lt_mul_left hq).mp hprod

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
    (hstep : ∀ i < 14,
      (state i).1 = (digit i).1 + radix i*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 +
        (radix i-3)*(state (i+1)).2)
    (hdigit : ∀ i < 14,
      nrm (digit i).1 (digit i).2 ≤ digitRadius i * digitRadius i) :
    nrm (state 14).1 (state 14).2 < 200*200 := by
  have hbound : ∀ i ≤ 14,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 14 := by omega
        have hjle : j ≤ 14 := by omega
        have hc := numeric_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := step_bound (radix j)
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) (digitRadius j) (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 hc.2.1 hc.2.2.1 hc.2.2.2
        omega
  have hj : 13 < 14 := by decide
  have hc := numeric_checks 13 (List.mem_range.mpr hj)
  have hs := hstep 13 hj
  have hd := hdigit 13 hj
  have hn := step_bound (radix 13)
    (state 13).1 (state 13).2 (digit 13).1 (digit 13).2
    (state 14).1 (state 14).2
    (radius 13) (digitRadius 13) (radius 14)
    hs.1 hs.2 (hbound 13 (by decide)) hd hc.1 hc.2.1 hc.2.2.1 hc.2.2.2
  have hlast : radius 14 = 200 := by decide
  rw [hlast] at hn
  exact hn

theorem selected_terminal_bound (scalar : Int) (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 14,
      (state i).1 = (digit i).1 + radix i*(state (i+1)).1 + 3*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - (state (i+1)).1 +
        (radix i-3)*(state (i+1)).2)
    (hdigit : ∀ i < 14,
      nrm (digit i).1 (digit i).2 ≤ digitRadius i * digitRadius i) :
    nrm (state 14).1 (state 14).2 < 200*200 := by
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

#print axioms radix_norm_identity
#print axioms numeric_checks
#print axioms selected_terminal_bound
end OrderedPrimeNorm14
