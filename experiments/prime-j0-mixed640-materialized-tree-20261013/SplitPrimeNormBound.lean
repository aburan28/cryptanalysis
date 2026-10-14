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

#print axioms cs_identity
#print axioms triangle_bound
#print axioms split_step_bound
