import AlternateRadix
import Triple81Radix
import Triple243Radix

set_option maxRecDepth 4096
set_option maxHeartbeats 2000000
set_option exponentiation.threshold 300

namespace TripleMixedRadix

open AlternateRadix

private def w0 : Int := cornerW0
private def w1 : Int := -cornerW1Abs
private def v0 : Int := -cornerV0Abs
private def v1 : Int := cornerV1

/-- The two basis vectors and their sum have the exact scalar-lattice norm. -/
theorem equilateral_basis :
    pairNorm w0 w1 = scalarOrder ∧
    pairNorm v0 v1 = scalarOrder ∧
    pairNorm (w0+v0) (w1+v1) = scalarOrder := by
  decide

/-- The floor corner of each scalar-lattice cell has norm at most the
subgroup order. This is a uniform bound over every cell, independent of a
sampled scalar. -/
theorem floor_corner_norm_bound (x y a b : Int)
    (hx : 0 ≤ x ∧ x < scalarOrder)
    (hy : 0 ≤ y ∧ y < scalarOrder)
    (ha : scalarOrder*a = x*w0+y*v0)
    (hb : scalarOrder*b = x*w1+y*v1) :
    pairNorm a b ≤ scalarOrder := by
  have hn : 0 < scalarOrder := by decide
  have hbasis := equilateral_basis
  have hlinear (u v s t : Int) :
      pairNorm (x*u+y*s) (x*v+y*t) =
        x*x*pairNorm u v + y*y*pairNorm s t +
        x*y*(pairNorm (u+s) (v+t)-pairNorm u v-pairNorm s t) := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_sub,
          Int.sub_mul, Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    omega
  have hcell :
      scalarOrder*scalarOrder*pairNorm a b =
        scalarOrder*(x*x+y*y-x*y) := by
    calc
      scalarOrder*scalarOrder*pairNorm a b =
          pairNorm (scalarOrder*a) (scalarOrder*b) := by
            simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
                  Int.mul_comm, Int.mul_left_comm]
      _ = pairNorm (x*w0+y*v0) (x*w1+y*v1) := by rw [ha, hb]
      _ = scalarOrder*(x*x+y*y-x*y) := by
            rw [hlinear w0 w1 v0 v1, hbasis.1, hbasis.2.1, hbasis.2.2]
            simp [Int.mul_add, Int.mul_sub, Int.mul_neg, Int.mul_assoc,
                  Int.mul_comm, Int.mul_left_comm]
            omega
  have hcellbound : x*x+y*y-x*y ≤ scalarOrder*scalarOrder := by
    by_cases hxy : x ≤ y
    · have hprod : 0 ≤ x*(y-x) :=
        Int.mul_nonneg hx.1 (by omega)
      have hsq1 : y*y ≤ scalarOrder*y :=
        Int.mul_le_mul_of_nonneg_right (by omega : y ≤ scalarOrder) hy.1
      have hsq2 : scalarOrder*y ≤ scalarOrder*scalarOrder :=
        Int.mul_le_mul_of_nonneg_left (by omega : y ≤ scalarOrder) (by omega)
      have hform : x*x+y*y-x*y = y*y-x*(y-x) := by
        simp [Int.mul_sub, Int.mul_comm, Int.mul_left_comm]
        omega
      rw [hform]
      omega
    · have hprod : 0 ≤ y*(x-y) :=
        Int.mul_nonneg hy.1 (by omega)
      have hsq1 : x*x ≤ scalarOrder*x :=
        Int.mul_le_mul_of_nonneg_right (by omega : x ≤ scalarOrder) hx.1
      have hsq2 : scalarOrder*x ≤ scalarOrder*scalarOrder :=
        Int.mul_le_mul_of_nonneg_left (by omega : x ≤ scalarOrder) (by omega)
      have hform : x*x+y*y-x*y = x*x-y*(x-y) := by
        simp [Int.mul_sub, Int.mul_comm, Int.mul_left_comm]
        omega
      rw [hform]
      omega
  have hscaled := Int.mul_le_mul_of_nonneg_left hcellbound (by omega : 0 ≤ scalarOrder)
  have hresult : (scalarOrder*scalarOrder)*pairNorm a b ≤
      (scalarOrder*scalarOrder)*scalarOrder := by
    calc
      (scalarOrder*scalarOrder)*pairNorm a b =
          scalarOrder*(x*x+y*y-x*y) := by
            simpa only [Int.mul_assoc] using hcell
      _ ≤ scalarOrder*(scalarOrder*scalarOrder) := hscaled
      _ = (scalarOrder*scalarOrder)*scalarOrder := by
        simp [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
  exact Int.le_of_mul_le_mul_left hresult (Int.mul_pos hn hn)

/-- The selected four-corner representative inherits the floor-corner
bound when its norm is no larger than that corner's norm. -/
theorem selected_initial_norm_bound (x y floorA floorB selectedA selectedB : Int)
    (hx : 0 ≤ x ∧ x < scalarOrder)
    (hy : 0 ≤ y ∧ y < scalarOrder)
    (ha : scalarOrder*floorA = x*w0+y*v0)
    (hb : scalarOrder*floorB = x*w1+y*v1)
    (hselect : pairNorm selectedA selectedB ≤ pairNorm floorA floorB) :
    pairNorm selectedA selectedB ≤ scalarOrder := by
  exact Int.le_trans hselect (floor_corner_norm_bound x y floorA floorB hx hy ha hb)

/-- Two norm-6481 steps followed by fourteen norm-58807 steps reach the
existing terminal table with 78 triplings in the point recurrence. -/
theorem mixed_sixteen_step_terminal_bound (q : Nat → Nat)
    (hzero : q 0 ≤ scalarOrder)
    (hfirst : ∀ i : Nat, i < 2 →
      100*6481*q (i+1) ≤ 101*q i + 10100*6481)
    (hlast : ∀ i : Nat, 2 ≤ i → i < 16 →
      100*58807*q (i+1) ≤ 101*q i + 10100*58807) :
    q 16 ≤ 647 := by
  have h0 : q 0 ≤ 115792089237316195423570985008687907852837564279074904382605163141518161494337 := by
    unfold scalarOrder at hzero
    omega
  have h1 : q 1 ≤ 18045056338480073658047630745066314909946912501445093878480360248871060602 := by
    have hs : 100*6481*q 1 ≤ 101*q 0 + 10100*6481 := by
      simpa using hfirst 0 (by decide)
    omega
  have h2 : q 2 ≤ 2812144252717925381056643581625825961895753992664642002355371678963188 := by
    have hs : 100*6481*q 2 ≤ 101*q 1 + 10100*6481 := by
      simpa using hfirst 1 (by decide)
    omega
  have h3 : q 3 ≤ 48298088582058337185491693462378360084933962497513704531415059460 := by
    have hs : 100*58807*q 3 ≤ 101*q 2 + 10100*58807 := by
      simpa using hlast 2 (by decide) (by decide)
    omega
  have h4 : q 4 ≤ 829511273621829383531664774550685185195356031127057009824258 := by
    have hs : 100*58807*q 4 ≤ 101*q 3 + 10100*58807 := by
      simpa using hlast 3 (by decide) (by decide)
    omega
  have h5 : q 5 ≤ 14246711894129060781318234602958696023386834755017728941 := by
    have hs : 100*58807*q 5 ≤ 101*q 4 + 10100*58807 := by
      simpa using hlast 4 (by decide) (by decide)
    omega
  have h6 : q 6 ≤ 244684799650897875918367149301754603765209976747221 := by
    have hs : 100*58807*q 6 ≤ 101*q 5 + 10100*58807 := by
      simpa using hlast 5 (by decide) (by decide)
    omega
  have h7 : q 7 ≤ 4202418889713926142764480772608229459126669995 := by
    have hs : 100*58807*q 7 ≤ 101*q 6 + 10100*58807 := by
      simpa using hlast 6 (by decide) (by decide)
    omega
  have h8 : q 8 ≤ 72175813740049065658716234127473119759958 := by
    have hs : 100*58807*q 8 ≤ 101*q 7 + 10100*58807 := by
      simpa using hlast 7 (by decide) (by decide)
    omega
  have h9 : q 9 ≤ 1239607051498113427233210272055161067 := by
    have hs : 100*58807*q 9 ≤ 101*q 8 + 10100*58807 := by
      simpa using hlast 8 (by decide) (by decide)
    omega
  have h10 : q 10 ≤ 21290035574218963074218075650545 := by
    have hs : 100*58807*q 10 ≤ 101*q 9 + 10100*58807 := by
      simpa using hlast 9 (by decide) (by decide)
    omega
  have h11 : q 11 ≤ 365652659206576644021294443 := by
    have hs : 100*58807*q 11 ≤ 101*q 10 + 10100*58807 := by
      simpa using hlast 10 (by decide) (by decide)
    omega
  have h12 : q 12 ≤ 6280020844434206990110 := by
    have hs : 100*58807*q 12 ≤ 101*q 11 + 10100*58807 := by
      simpa using hlast 11 (by decide) (by decide)
    omega
  have h13 : q 13 ≤ 107858266071701583 := by
    have hs : 100*58807*q 13 ≤ 101*q 12 + 10100*58807 := by
      simpa using hlast 12 (by decide) (by decide)
    omega
  have h14 : q 14 ≤ 1852446966149 := by
    have hs : 100*58807*q 14 ≤ 101*q 13 + 10100*58807 := by
      simpa using hlast 13 (by decide) (by decide)
    omega
  have h15 : q 15 ≤ 31815555 := by
    have hs : 100*58807*q 15 ≤ 101*q 14 + 10100*58807 := by
      simpa using hlast 14 (by decide) (by decide)
    omega
  have h16 : q 16 ≤ 647 := by
    have hs : 100*58807*q 16 ≤ 101*q 15 + 10100*58807 := by
      simpa using hlast 15 (by decide) (by decide)
    omega
  exact h16

theorem mixed_sixteen_step_terminal_below_table (q : Nat → Nat)
    (hzero : q 0 ≤ scalarOrder)
    (hfirst : ∀ i : Nat, i < 2 →
      100*6481*q (i+1) ≤ 101*q i + 10100*6481)
    (hlast : ∀ i : Nat, 2 ≤ i → i < 16 →
      100*58807*q (i+1) ≤ 101*q i + 10100*58807) :
    q 16 < 5000 := by
  have h := mixed_sixteen_step_terminal_bound q hzero hfirst hlast
  omega

/-- The numeric terminal certificate applies to the actual mixed quotient
sequence once each digit and exact division equation is supplied. -/
theorem mixed_quotients_terminal
    (state digit : Nat → HornerRadix.Pair)
    (hinitial : pairNorm (state 0).1 (state 0).2 ≤ scalarOrder)
    (hquot81 : ∀ i : Nat, i < 2 →
      Triple81Radix.primePair81 (state (i+1)) =
        HornerRadix.pairAdd (state i) (-(digit i).1,-(digit i).2))
    (hdigit81 : ∀ i : Nat, i < 2 →
      pairNorm (digit i).1 (digit i).2 ≤ 6481)
    (hquot243 : ∀ i : Nat, 2 ≤ i → i < 16 →
      Triple243Radix.primePair243 (state (i+1)) =
        HornerRadix.pairAdd (state i) (-(digit i).1,-(digit i).2))
    (hdigit243 : ∀ i : Nat, 2 ≤ i → i < 16 →
      pairNorm (digit i).1 (digit i).2 ≤ 58807) :
    pairNorm (state 16).1 (state 16).2 ≤ 647 := by
  let norms : Nat → Nat := fun i => (pairNorm (state i).1 (state i).2).toNat
  have hnorm (i : Nat) : (norms i : Int) = pairNorm (state i).1 (state i).2 := by
    have hn := pair_norm_nonnegative (state i).1 (state i).2
    simp [norms, Int.toNat_of_nonneg hn]
  have hzero : norms 0 ≤ scalarOrder := by
    have heq := hnorm 0
    omega
  have hfirst : ∀ i : Nat, i < 2 →
      100*6481*norms (i+1) ≤ 101*norms i + 10100*6481 := by
    intro i hi
    have hs := Triple81Radix.quotient_norm_step (state i) (digit i) (state (i+1))
      (hquot81 i hi) (hdigit81 i hi)
    have hnow := hnorm i
    have hnext := hnorm (i+1)
    omega
  have hlast : ∀ i : Nat, 2 ≤ i → i < 16 →
      100*58807*norms (i+1) ≤ 101*norms i + 10100*58807 := by
    intro i hlo hhi
    have hs := Triple243Radix.quotient_norm_step (state i) (digit i) (state (i+1))
      (hquot243 i hlo hhi) (hdigit243 i hlo hhi)
    have hnow := hnorm i
    have hnext := hnorm (i+1)
    omega
  have hterminal := mixed_sixteen_step_terminal_bound norms hzero hfirst hlast
  have heq := hnorm 16
  omega

private theorem square_below_100 (x : Int) (h : x*x ≤ 2588) :
    -100 < x ∧ x < 100 := by
  have hupper : x < 100 := by
    by_cases hc : x < 100
    · exact hc
    have hx : 100 ≤ x := by omega
    have hfirst : 100*x ≤ x*x :=
      Int.mul_le_mul_of_nonneg_right hx (by omega)
    have hsecond : 10000 ≤ 100*x :=
      Int.mul_le_mul_of_nonneg_left hx (by decide)
    omega
  have hlower : -100 < x := by
    by_cases hc : -100 < x
    · exact hc
    have hx : 100 ≤ -x := by omega
    have hfirst : 100*(-x) ≤ (-x)*(-x) :=
      Int.mul_le_mul_of_nonneg_right hx (by omega)
    have hsecond : 10000 ≤ 100*(-x) :=
      Int.mul_le_mul_of_nonneg_left hx (by decide)
    have heq : (-x)*(-x) = x*x := by simp [Int.neg_mul, Int.mul_neg]
    rw [heq] at hfirst
    omega
  exact ⟨hlower,hupper⟩

/-- The terminal norm certificate also covers both native signed
coordinate lookups, which require magnitudes below 100. -/
theorem terminal_coordinates_in_table (a b : Int)
    (hnorm : pairNorm a b ≤ 647) :
    -100 < a ∧ a < 100 ∧ -100 < b ∧ b < 100 := by
  have square_nonneg (x : Int) : 0 ≤ x*x := by
    by_cases hx : 0 ≤ x
    · exact Int.mul_nonneg hx hx
    · have h := Int.mul_nonneg (by omega : 0 ≤ -x) (by omega : 0 ≤ -x)
      simpa [Int.neg_mul, Int.mul_neg] using h
  have hsq : 0 ≤ (a+2*b)*(a+2*b) := square_nonneg _
  have hsq2 : 0 ≤ (2*a+3*b)*(2*a+3*b) := square_nonneg _
  have haidentity : 4*pairNorm a b =
      a*a + 3*((a+2*b)*(a+2*b)) := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
          Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  have hbidentity : 4*pairNorm a b =
      (2*a+3*b)*(2*a+3*b) + 3*(b*b) := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
          Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  have ha : a*a ≤ 2588 := by omega
  have hb : b*b ≤ 2588 := by omega
  have haa := square_below_100 a ha
  have hbb := square_below_100 b hb
  exact ⟨haa.1,haa.2,hbb.1,hbb.2⟩

/-- The two radix-81 steps wrap the fourteen radix-243 steps in the
shared two-scalar point recurrence. -/
theorem two_scalar_mixed_horner {Point : Type}
    (add : Point → Point → Point) (prime81 prime243 : Point → Point)
    (g q : HornerRadix.Pair → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime81_add : ∀ x y, prime81 (add x y) = add (prime81 x) (prime81 y))
    (prime243_add : ∀ x y, prime243 (add x y) = add (prime243 x) (prime243 y))
    (g_add : ∀ x y, g (HornerRadix.pairAdd x y) = add (g x) (g y))
    (q_add : ∀ x y, q (HornerRadix.pairAdd x y) = add (q x) (q y))
    (g_prime81 : ∀ x, g (Triple81Radix.primePair81 x) = prime81 (g x))
    (q_prime81 : ∀ x, q (Triple81Radix.primePair81 x) = prime81 (q x))
    (g_prime243 : ∀ x, g (Triple243Radix.primePair243 x) = prime243 (g x))
    (q_prime243 : ∀ x, q (Triple243Radix.primePair243 x) = prime243 (q x))
    (scalarG scalarQ middleG middleQ terminalG terminalQ : HornerRadix.Pair)
    (digits81 digits243 : List (HornerRadix.Pair × HornerRadix.Pair))
    (_hlen81 : digits81.length = 2) (_hlen243 : digits243.length = 14)
    (trace81G : Triple81Radix.ValidTrace81 scalarG (digits81.map Prod.fst) middleG)
    (trace81Q : Triple81Radix.ValidTrace81 scalarQ (digits81.map Prod.snd) middleQ)
    (trace243G : Triple243Radix.ValidTrace243 middleG (digits243.map Prod.fst) terminalG)
    (trace243Q : Triple243Radix.ValidTrace243 middleQ (digits243.map Prod.snd) terminalQ) :
    add (g scalarG) (q scalarQ) =
      HornerRadix.evaluatePoints add prime81
        (digits81.map (fun d => add (g d.1) (q d.2)))
        (HornerRadix.evaluatePoints add prime243
          (digits243.map (fun d => add (g d.1) (q d.2)))
          (add (g terminalG) (q terminalQ))) := by
  have houter := Triple81Radix.two_scalar_horner81 add prime81 g q
    assoc comm prime81_add g_add q_add g_prime81 q_prime81
    scalarG scalarQ middleG middleQ digits81 trace81G trace81Q
  have hinner := Triple243Radix.two_scalar_horner243 add prime243 g q
    assoc comm prime243_add g_add q_add g_prime243 q_prime243
    middleG middleQ terminalG terminalQ digits243 trace243G trace243Q
  rw [houter, hinner]

theorem mixed_horner_tripling_count : 2*4+14*5 = 78 := by decide

#print axioms equilateral_basis
#print axioms floor_corner_norm_bound
#print axioms selected_initial_norm_bound
#print axioms mixed_sixteen_step_terminal_bound
#print axioms mixed_sixteen_step_terminal_below_table
#print axioms mixed_quotients_terminal
#print axioms terminal_coordinates_in_table
#print axioms two_scalar_mixed_horner
#print axioms mixed_horner_tripling_count

end TripleMixedRadix
