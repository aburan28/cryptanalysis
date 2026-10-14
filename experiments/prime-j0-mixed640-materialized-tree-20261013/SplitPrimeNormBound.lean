import Lean

def nrm (a b : Int) : Int := a*a+3*a*b+3*b*b

theorem sq_nonneg (x : Int) : 0 ≤ x*x := by
  by_cases h : 0 ≤ x
  · exact Int.mul_nonneg h h
  · have h' : x ≤ 0 := by omega
    exact Int.mul_nonneg_of_nonpos_of_nonpos h' h'

theorem cs_identity (a b c d : Int) :
    4*nrm a b*nrm c d - (2*a*c+3*a*d+3*b*c+6*b*d)^2 =
    3*(a*d-b*c)^2 := by
  unfold nrm
  grind

theorem triangle_bound (a b c d B D : Int)
    (hB : nrm a b ≤ B*B) (hD : nrm c d ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D) :
    nrm (a+c) (b+d) ≤ (B+D)*(B+D) := by
  have hn1 : 0 ≤ nrm a b := by
    have h := sq_nonneg (2*a+3*b)
    have h2 := sq_nonneg b
    unfold nrm
    grind
  have hn2 : 0 ≤ nrm c d := by
    have h := sq_nonneg (2*c+3*d)
    have h2 := sq_nonneg d
    unfold nrm
    grind
  have hcs := cs_identity a b c d
  have hs := sq_nonneg (a*d-b*c)
  let N1 := nrm a b
  let N2 := nrm c d
  let C := 2*a*c+3*a*d+3*b*c+6*b*d
  have hN1 : N1 ≤ B*B := hB
  have hN2 : N2 ≤ D*D := hD
  have hNN : N1*N2 ≤ (B*B)*(D*D) := by
    have h1 := Int.mul_le_mul_of_nonneg_right hN1 hn2
    have h2 := Int.mul_le_mul_of_nonneg_left hN2 (sq_nonneg B)
    dsimp [N1,N2] at *
    grind
  have hcs' : C*C ≤ (2*B*D)*(2*B*D) := by
    have hsq : 0 ≤ 3*(a*d-b*c)^2 := by
      apply Int.mul_nonneg (by decide)
      have hpow : (a*d-b*c)^2 = (a*d-b*c)*(a*d-b*c) := by grind
      rw [hpow]
      exact hs
    dsimp [C,N1,N2] at *
    grind
  have hC : C ≤ 2*B*D := by
    have hy : 0 ≤ 2*B*D := by
      apply Int.mul_nonneg
      · omega
      · exact hD0
    by_cases hc : C ≤ 2*B*D
    · exact hc
    · have hx : 2*B*D < C := by omega
      have hx0 : 0 < C := by omega
      have hmul1 := Int.mul_lt_mul_of_pos_right hx hx0
      have hxle : 2*B*D ≤ C := by omega
      have hmul2 := Int.mul_le_mul_of_nonneg_left hxle hy
      grind
  have hexpand : nrm (a+c) (b+d) = N1+N2+C := by
    dsimp [nrm,N1,N2,C]
    grind
  have hresult : N1+N2+C ≤ B*B+D*D+2*B*D := by omega
  have htarget : B*B+D*D+2*B*D = (B+D)*(B+D) := by grind
  omega

-- A unit digit (da,db) is subtracted before exact division by pi.
-- This is the structural contraction used by the radix evaluator.
theorem split_step_bound (a b da db x y B D R : Int)
    (ha : a = da + 86*x + 63*y)
    (hb : b = db - 21*x + 23*y)
    (hB : nrm a b ≤ B*B)
    (hD : nrm da db ≤ D*D)
    (hB0 : 0 ≤ B) (hD0 : 0 ≤ D)
    (hR : (B+D)*(B+D) < 3301*(R*R)) :
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
  have hpi : nrm (86*x+63*y) (-21*x+23*y) = 3301*nrm x y := by
    unfold nrm
    grind
  have heq : nrm (a-da) (b-db) = nrm (86*x+63*y) (-21*x+23*y) := by
    congr 1 <;> omega
  have hpos : 0 < (3301 : Int) := by decide
  have hprod : 3301*nrm x y < 3301*(R*R) := by omega
  exact (Int.mul_lt_mul_left hpos).mp hprod

def radius : Nat → Int
  | 0 => 27 * 57 ^ 21
  | i + 1 => (radius i + 1064 + 56) / 57

theorem radius_checks :
    ∀ i ∈ List.range 21,
      0 ≤ radius i ∧
      (radius i + 1064) * (radius i + 1064) <
        3301 * (radius (i+1) * radius (i+1)) := by
  decide

theorem radius_last : radius 21 = 46 := by decide

theorem terminal_bound (state digit : Nat → Int × Int)
    (hinitial : nrm (state 0).1 (state 0).2 ≤ radius 0 * radius 0)
    (hstep : ∀ i < 21,
      (state i).1 = (digit i).1 + 86*(state (i+1)).1 + 63*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - 21*(state (i+1)).1 + 23*(state (i+1)).2)
    (hdigit : ∀ i < 21, nrm (digit i).1 (digit i).2 ≤ 1064*1064) :
    nrm (state 21).1 (state 21).2 < 46*46 := by
  have hbound : ∀ i ≤ 21,
      nrm (state i).1 (state i).2 ≤ radius i * radius i := by
    intro i hi
    induction i with
    | zero => exact hinitial
    | succ j ih =>
        have hj : j < 21 := by omega
        have hjle : j ≤ 21 := by omega
        have hc := radius_checks j (List.mem_range.mpr hj)
        have hs := hstep j hj
        have hd := hdigit j hj
        have hn := split_step_bound
          (state j).1 (state j).2 (digit j).1 (digit j).2
          (state (j+1)).1 (state (j+1)).2
          (radius j) 1064 (radius (j+1))
          hs.1 hs.2 (ih hjle) hd hc.1 (by decide) hc.2
        omega
  have hj : 20 < 21 := by decide
  have hc := radius_checks 20 (List.mem_range.mpr hj)
  have hs := hstep 20 hj
  have hd := hdigit 20 hj
  have hn := split_step_bound
    (state 20).1 (state 20).2 (digit 20).1 (digit 20).2
    (state 21).1 (state 21).2
    (radius 20) 1064 (radius 21)
    hs.1 hs.2 (hbound 20 (by decide)) hd hc.1 (by decide) hc.2
  rw [radius_last] at hn
  exact hn

theorem initial_radius_from_cell (a b : Int)
    (hcell : 3 * nrm a b ≤
      115792089237316195423570985008687907852837564279074904382605163141518161494337) :
    nrm a b ≤ radius 0 * radius 0 := by
  have hn :
      115792089237316195423570985008687907852837564279074904382605163141518161494337
      < 3 * (radius 0 * radius 0) := by decide
  omega

theorem terminal_bound_from_cell (state digit : Nat → Int × Int)
    (hcell : 3 * nrm (state 0).1 (state 0).2 ≤
      115792089237316195423570985008687907852837564279074904382605163141518161494337)
    (hstep : ∀ i < 21,
      (state i).1 = (digit i).1 + 86*(state (i+1)).1 + 63*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - 21*(state (i+1)).1 + 23*(state (i+1)).2)
    (hdigit : ∀ i < 21, nrm (digit i).1 (digit i).2 ≤ 1064*1064) :
    nrm (state 21).1 (state 21).2 < 46*46 := by
  exact terminal_bound state digit
    (initial_radius_from_cell _ _ hcell) hstep hdigit

#print axioms cs_identity
#print axioms triangle_bound
#print axioms split_step_bound
#print axioms radius_checks
#print axioms terminal_bound
#print axioms initial_radius_from_cell
#print axioms terminal_bound_from_cell
