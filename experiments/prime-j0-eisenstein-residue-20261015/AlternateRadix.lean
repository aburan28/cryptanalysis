import Lean

set_option maxRecDepth 4096
set_option maxHeartbeats 2000000
set_option exponentiation.threshold 300

namespace AlternateRadix

/-- Norm of the digit prime `t - τ` when `τ² = 3τ - 3`. -/
def norm (t : Int) : Int := t*t - 3*t + 3

/-- Multiplication by `t - τ` in the basis `(1, τ)`. -/
def multiplyPrime (t : Int) (u v : Int) : Int × Int :=
  (t*u + 3*v, (t-3)*v-u)

/-- Norm in the basis `(1, τ)`, with `τ² = 3τ - 3`. -/
def pairNorm (a b : Int) : Int := a*a + 3*a*b + 3*b*b

private theorem int_square_nonnegative (x : Int) : 0 ≤ x*x := by
  by_cases hx : 0 ≤ x
  · exact Int.mul_nonneg hx hx
  · have hn : 0 ≤ -x := by omega
    have h := Int.mul_nonneg hn hn
    have heq : (-x)*(-x) = x*x := by simp [Int.neg_mul, Int.mul_neg]
    rw [heq] at h
    exact h

theorem pair_norm_nonnegative (a b : Int) : 0 ≤ pairNorm a b := by
  have h₁ : 0 ≤ (2*a+3*b)*(2*a+3*b) := int_square_nonnegative _
  have h₂ : 0 ≤ b*b := int_square_nonnegative _
  have h₃ : 0 ≤ 3*(b*b) := Int.mul_nonneg (by decide) h₂
  have heq : 4*pairNorm a b = (2*a+3*b)*(2*a+3*b)+3*(b*b) := by
    simp [pairNorm, Int.mul_add, Int.add_mul, Int.mul_assoc,
          Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  omega

/-- An exact weighted Cauchy bound, with integer coefficients. -/
theorem pair_norm_weighted (a b da db : Int) :
    100*pairNorm (a-da) (b-db) ≤
      101*pairNorm a b + 10100*pairNorm da db := by
  have hn := pair_norm_nonnegative (a+100*da) (b+100*db)
  have heq : 101*pairNorm a b + 10100*pairNorm da db -
      100*pairNorm (a-da) (b-db) =
      pairNorm (a+100*da) (b+100*db) := by
    simp [pairNorm, Int.mul_add, Int.mul_sub, Int.add_mul,
          Int.sub_mul, Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    simp only [← Int.mul_assoc]
    omega
  omega

/-- Multiplication by the digit prime scales the pair norm by its norm. -/
theorem multiply_prime_norm (t a b : Int) :
    pairNorm (multiplyPrime t a b).1 (multiplyPrime t a b).2 =
      norm t * pairNorm a b := by
  simp only [multiplyPrime, pairNorm, norm, Int.mul_add, Int.mul_sub,
             Int.mul_assoc, Int.mul_comm,
             Int.mul_left_comm]
  omega

/-- The exact quotient step used by the alternate digit recoder. -/
theorem quotient_step (t a b da db k : Int)
    (h : (a-da) + t*(b-db) = norm t*k) :
    multiplyPrime t ((t-3)*k-(b-db)) k = (a-da,b-db) := by
  apply Prod.ext
  · simp only [multiplyPrime, norm] at h ⊢
    simp only [Int.mul_add, Int.mul_sub, Int.mul_comm,
               Int.mul_left_comm] at h ⊢
    omega
  · simp only [multiplyPrime]
    omega

/-- The chosen parameter gives a prime norm of 110557. -/
theorem norm_334 : norm 334 = 110557 := by decide

private theorem linear_corner_bound (n w v limit x y a : Int)
    (hn : 0 < n) (hw : 0 < w) (hv : 0 < v)
    (hm : w + v < limit)
    (hx : -n ≤ x ∧ x < n) (hy : -n ≤ y ∧ y < n)
    (ha : n*a = x*w - y*v) :
    -limit < a ∧ a < limit := by
  have hxu : x*w < n*w := Int.mul_lt_mul_of_pos_right hx.2 hw
  have hxl : -n*w ≤ x*w := Int.mul_le_mul_of_nonneg_right hx.1 (Int.le_of_lt hw)
  have hyu : y*v < n*v := Int.mul_lt_mul_of_pos_right hy.2 hv
  have hyl : -n*v ≤ y*v := Int.mul_le_mul_of_nonneg_right hy.1 (Int.le_of_lt hv)
  have hup : x*w - y*v < n*(w+v) := by
    have hyneg := Int.neg_le_neg hyl
    have hsum := Int.add_lt_add_of_lt_of_le hxu hyneg
    have hcalc : x*w - y*v < n*w + n*v := by
      simpa [Int.sub_eq_add_neg, Int.neg_mul, Int.mul_add] using hsum
    simpa [Int.mul_add] using hcalc
  have hlo : -(n*(w+v)) < x*w - y*v := by
    have hyneg := Int.neg_lt_neg hyu
    have hsum := Int.add_lt_add_of_le_of_lt hxl hyneg
    have hcalc : (-n)*w - n*v < x*w - y*v := by
      simpa [Int.sub_eq_add_neg, Int.neg_mul] using hsum
    simpa [Int.mul_add, Int.neg_mul, Int.neg_add, Int.sub_eq_add_neg] using hcalc
  have hmargin : n*(w+v) < n*limit := Int.mul_lt_mul_of_pos_left hm hn
  have hpos : n*a < n*limit := by rw [ha]; exact Int.lt_trans hup hmargin
  have hneg : n*(-limit) < n*a := by
    have hmarginneg := Int.neg_lt_neg hmargin
    have hsmall : n*(-limit) < -(n*(w+v)) := by
      simpa [Int.mul_neg] using hmarginneg
    rw [ha]
    exact Int.lt_trans hsmall hlo
  exact ⟨Int.lt_of_mul_lt_mul_left hneg (Int.le_of_lt hn),
         Int.lt_of_mul_lt_mul_left hpos (Int.le_of_lt hn)⟩

private theorem corner_remainder_bound (n r d : Int)
    (hn : 0 < n) (hr : 0 ≤ r ∧ r < n) (hd : 0 ≤ d ∧ d ≤ 1) :
    -n ≤ r - n*d ∧ r - n*d < n := by
  have hd01 : d = 0 ∨ d = 1 := by omega
  rcases hd01 with hz | ho
  · simp [hz]
    omega
  · simp [ho]
    omega

def scalarOrder : Int := 115792089237316195423570985008687907852837564279074904382605163141518161494337
def cornerW0 : Int := 671331852483699643819086596696745227419
def cornerV0Abs : Int := 238911465918039986966665730306072050094
def cornerW1Abs : Int := 367917413016453100223835821029139468248
def cornerV1 : Int := 303414439467246543595250775667605759171
def selectorCoordinateLimit : Int := 2^130

/-- Any four-corner lattice output has both coordinates below the recoder limit.
The hypotheses expose the two exact floor remainders and the basis-coordinate equations. -/
theorem selector_corner_coordinate_bound (rw rv dw dv a b : Int)
    (hrw : 0 ≤ rw ∧ rw < scalarOrder)
    (hrv : 0 ≤ rv ∧ rv < scalarOrder)
    (hdw : 0 ≤ dw ∧ dw ≤ 1) (hdv : 0 ≤ dv ∧ dv ≤ 1)
    (ha : scalarOrder*a =
      (rw-scalarOrder*dw)*cornerW0 - (rv-scalarOrder*dv)*cornerV0Abs)
    (hb : scalarOrder*b =
      (rv-scalarOrder*dv)*cornerV1 - (rw-scalarOrder*dw)*cornerW1Abs) :
    -selectorCoordinateLimit < a ∧ a < selectorCoordinateLimit ∧
      -selectorCoordinateLimit < b ∧ b < selectorCoordinateLimit := by
  have hn : 0 < scalarOrder := by decide
  have hx := corner_remainder_bound scalarOrder rw dw hn hrw hdw
  have hy := corner_remainder_bound scalarOrder rv dv hn hrv hdv
  have hwa : 0 < cornerW0 := by decide
  have hva : 0 < cornerV0Abs := by decide
  have hwb : 0 < cornerW1Abs := by decide
  have hvb : 0 < cornerV1 := by decide
  have hma : cornerW0 + cornerV0Abs < selectorCoordinateLimit := by decide
  have hmb : cornerV1 + cornerW1Abs < selectorCoordinateLimit := by decide
  have hab := linear_corner_bound scalarOrder cornerW0 cornerV0Abs
    selectorCoordinateLimit (rw-scalarOrder*dw) (rv-scalarOrder*dv) a
    hn hwa hva hma hx hy ha
  have hbb := linear_corner_bound scalarOrder cornerV1 cornerW1Abs
    selectorCoordinateLimit (rv-scalarOrder*dv) (rw-scalarOrder*dw) b
    hn hvb hwb hmb hy hx hb
  exact ⟨hab.1, hab.2, hbb.1, hbb.2⟩

private theorem nonnegative_square_bound (x limit : Int)
    (hx : 0 ≤ x) (hlimit : 0 ≤ limit) (h : x ≤ limit) :
    x*x ≤ limit*limit := by
  have h1 := Int.mul_le_mul_of_nonneg_right h hx
  have h2 := Int.mul_le_mul_of_nonneg_left h hlimit
  exact Int.le_trans h1 h2

private theorem signed_square_bound (x limit : Int)
    (hlimit : 0 ≤ limit) (h : -limit ≤ x ∧ x ≤ limit) :
    x*x ≤ limit*limit := by
  by_cases hx : 0 ≤ x
  · exact nonnegative_square_bound x limit hx hlimit h.2
  · have hy : 0 ≤ -x := by omega
    have hybound : -x ≤ limit := by omega
    have hs := nonnegative_square_bound (-x) limit hy hlimit hybound
    simpa [Int.neg_mul, Int.mul_neg] using hs

private theorem pair_norm_coordinate_bound (a b limit : Int)
    (hlimit : 0 ≤ limit)
    (ha : -limit ≤ a ∧ a ≤ limit)
    (hb : -limit ≤ b ∧ b ≤ limit) :
    a*a + 3*(a*b) + 3*(b*b) ≤ 7*(limit*limit) := by
  have haa := signed_square_bound a limit hlimit ha
  have hbb := signed_square_bound b limit hlimit hb
  have hsq : 0 ≤ (a-b)*(a-b) := by
    by_cases hx : 0 ≤ a-b
    · exact Int.mul_nonneg hx hx
    · have hy : 0 ≤ -(a-b) := by omega
      have hn := Int.mul_nonneg hy hy
      simpa [Int.neg_mul, Int.mul_neg] using hn
  have hcross : 2*(a*b) ≤ a*a + b*b := by
    have heq : (a-b)*(a-b) = a*a + b*b - 2*(a*b) := by
      simp [Int.mul_sub, Int.mul_assoc, Int.mul_comm]
      simp only [← Int.mul_assoc]
      omega
    omega
  omega

/-- The selector coordinate envelope supplies the initial norm budget. -/
theorem selector_initial_norm_bound (a b : Int)
    (ha : -selectorCoordinateLimit < a ∧ a < selectorCoordinateLimit)
    (hb : -selectorCoordinateLimit < b ∧ b < selectorCoordinateLimit) :
    pairNorm a b ≤ 7*2^260 := by
  have hcoord := pair_norm_coordinate_bound a b selectorCoordinateLimit
    (by decide) ⟨Int.le_of_lt ha.1, Int.le_of_lt ha.2⟩
    ⟨Int.le_of_lt hb.1, Int.le_of_lt hb.2⟩
  have hnorm : pairNorm a b ≤
      7*(selectorCoordinateLimit*selectorCoordinateLimit) := by
    simpa only [pairNorm, Int.mul_assoc] using hcoord
  have hpow : 7*(selectorCoordinateLimit*selectorCoordinateLimit) =
      7*2^260 := by decide
  rw [hpow] at hnorm
  exact hnorm

/-- The nearest-lift digit has an exact centered-error norm formula. -/
theorem digit_candidate_norm_identity (r b : Int) :
    4*110557*pairNorm (r-334*b) b =
      (2*110557*b-665*r)*(2*110557*b-665*r)+3*r*r := by
  simp [pairNorm, Int.mul_sub, Int.add_mul,
        Int.sub_mul, Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
  simp only [← Int.mul_assoc]
  omega

/-- A digit norm at most the prime norm suffices for one quotient step. -/
theorem quotient_norm_step (a b da db nextA nextB : Int)
    (hquot : multiplyPrime 334 nextA nextB = (a-da,b-db))
    (hdigit : pairNorm da db ≤ 110557) :
    100*110557*pairNorm nextA nextB ≤
      101*pairNorm a b + 10100*110557 := by
  have hscale := multiply_prime_norm 334 nextA nextB
  rw [hquot, norm_334] at hscale
  have hweight := pair_norm_weighted a b da db
  rw [hscale] at hweight
  omega

theorem norm_334_no_small_divisor :
    ∀ d : Fin 331, 110557 % (d.val + 2) ≠ 0 := by decide

/-- Factor definition of primality, stated directly for the digit norm. -/
theorem norm_334_prime_factors (a b : Nat) (h : a*b = 110557) :
    a = 1 ∨ b = 1 := by
  by_cases ha : a = 1
  · exact Or.inl ha
  by_cases hb : b = 1
  · exact Or.inr hb
  have ha0 : a ≠ 0 := by
    intro hz
    simp [hz] at h
  have hb0 : b ≠ 0 := by
    intro hz
    simp [hz] at h
  have ha2 : 2 ≤ a := by omega
  have hb2 : 2 ≤ b := by omega
  by_cases hsmall : a ≤ 332
  · have hbound : a - 2 < 331 := by omega
    have htrial := norm_334_no_small_divisor ⟨a-2, hbound⟩
    have hmod : 110557 % a = 0 := by rw [← h]; simp
    simp only [Nat.sub_add_cancel ha2] at htrial
    exact False.elim (htrial hmod)
  · have hbsmall : b ≤ 332 := by
      by_cases hlarge : b ≤ 332
      · exact hlarge
      · have hmul : 333*333 ≤ a*b := Nat.mul_le_mul (by omega) (by omega)
        omega
    have hbound : b - 2 < 331 := by omega
    have htrial := norm_334_no_small_divisor ⟨b-2, hbound⟩
    have hmod : 110557 % b = 0 := by rw [← h]; simp
    simp only [Nat.sub_add_cancel hb2] at htrial
    exact False.elim (htrial hmod)

/-- Conservative integer ceiling for the weighted norm recurrence. -/
def boundStep (q : Nat) : Nat :=
  (101*q + 10100*36631 + 100*110557 - 1) / (100*110557)

def boundIter : Nat → Nat → Nat
  | 0, q => q
  | n+1, q => boundIter n (boundStep q)

theorem fifteen_step_numeric_bound :
    boundIter 15 (7*2^260) = 3375 := by decide

theorem terminal_norm_below_table_limit :
    boundIter 15 (7*2^260) < 5000 := by
  rw [fifteen_step_numeric_bound]
  decide

/-- A fifteen-step bound for every sequence obeying the weighted norm recurrence. -/
theorem terminal_from_recurrence (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 15 →
      100*110557*q (i+1) ≤ 101*q i + 10100*36631) :
    q 15 < 5000 := by
  have h1 : q 1 ≤ 118476452278238447373882701449775013218176150450692951184849823195049912974 := by
    have hs : 100*110557*q 1 ≤ 101*q 0 + 10100*36631 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 1082348623796058430019099002905946826979367312383656219838620091238042 := by
    have hs : 100*110557*q 2 ≤ 101*q 1 + 10100*36631 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 9887859746863780803741870645323283873921696369361440542317594507 := by
    have hs : 100*110557*q 3 ≤ 101*q 2 + 10100*36631 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 90331126426480626389819634684158549098301449325280669227136 := by
    have hs : 100*110557*q 4 ≤ 101*q 3 + 10100*36631 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 825225337977201196249155015340504306278973414786340799 := by
    have hs : 100*110557*q 5 ≤ 101*q 4 + 10100*36631 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 7538894790533147681391920597464740806477772994365 := by
    have hs : 100*110557*q 6 ≤ 101*q 5 + 10100*36631 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 68872018401715668462474920660287346930023015 := by
    have hs : 100*110557*q 7 ≤ 101*q 6 + 10100*36631 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 629184389823645948669913889368291654107 := by
    have hs : 100*110557*q 8 ≤ 101*q 7 + 10100*36631 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 5747951135811232288833932073608892 := by
    have hs : 100*110557*q 9 ≤ 101*q 8 + 10100*36631 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 52510746919411205185761836863 := by
    have hs : 100*110557*q 10 ≤ 101*q 9 + 10100*36631 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 479715028343798377647939 := by
    have hs : 100*110557*q 11 ≤ 101*q 10 + 10100*36631 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 4382464960402655329 := by
    have hs : 100*110557*q 12 ≤ 101*q 11 + 10100*36631 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 40036267355395 := by
    have hs : 100*110557*q 13 ≤ 101*q 12 + 10100*36631 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 365753718 := by
    have hs : 100*110557*q 14 ≤ 101*q 13 + 10100*36631 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 3375 := by
    have hs : 100*110557*q 15 ≤ 101*q 14 + 10100*36631 := by
      simpa using hstep 14 (by decide)
    omega
  omega

/-- Terminal norm bound using only the loose digit bound `Q(d) ≤ N(π)`. -/
theorem terminal_from_prime_norm_digits (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 15 →
      100*110557*q (i+1) ≤ 101*q i + 10100*110557) :
    q 15 < 5000 := by
  have h1 : q 1 ≤ 118476452278238447373882701449775013218176150450692951184849823195049913041 := by
    have hs : 100*110557*q 1 ≤ 101*q 0 + 10100*110557 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 1082348623796058430019099002905946826979367312383656219838620091238109 := by
    have hs : 100*110557*q 2 ≤ 101*q 1 + 10100*110557 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 9887859746863780803741870645323283873921696369361440542317594574 := by
    have hs : 100*110557*q 3 ≤ 101*q 2 + 10100*110557 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 90331126426480626389819634684158549098301449325280669227204 := by
    have hs : 100*110557*q 4 ≤ 101*q 3 + 10100*110557 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 825225337977201196249155015340504306278973414786340866 := by
    have hs : 100*110557*q 5 ≤ 101*q 4 + 10100*110557 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 7538894790533147681391920597464740806477772994432 := by
    have hs : 100*110557*q 6 ≤ 101*q 5 + 10100*110557 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 68872018401715668462474920660287346930023083 := by
    have hs : 100*110557*q 7 ≤ 101*q 6 + 10100*110557 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 629184389823645948669913889368291654174 := by
    have hs : 100*110557*q 8 ≤ 101*q 7 + 10100*110557 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 5747951135811232288833932073608960 := by
    have hs : 100*110557*q 9 ≤ 101*q 8 + 10100*110557 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 52510746919411205185761836931 := by
    have hs : 100*110557*q 10 ≤ 101*q 9 + 10100*110557 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 479715028343798377648007 := by
    have hs : 100*110557*q 11 ≤ 101*q 10 + 10100*110557 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 4382464960402655396 := by
    have hs : 100*110557*q 12 ≤ 101*q 11 + 10100*110557 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 40036267355463 := by
    have hs : 100*110557*q 13 ≤ 101*q 12 + 10100*110557 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 365753785 := by
    have hs : 100*110557*q 14 ≤ 101*q 13 + 10100*110557 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 3443 := by
    have hs : 100*110557*q 15 ≤ 101*q 14 + 10100*110557 := by
      simpa using hstep 14 (by decide)
    omega
  omega

/-- The corner envelope and per-digit recurrence compose to terminal coverage. -/
theorem terminal_for_selector_corner (rw rv dw dv a b : Int) (q : Nat → Nat)
    (hrw : 0 ≤ rw ∧ rw < scalarOrder)
    (hrv : 0 ≤ rv ∧ rv < scalarOrder)
    (hdw : 0 ≤ dw ∧ dw ≤ 1) (hdv : 0 ≤ dv ∧ dv ≤ 1)
    (ha : scalarOrder*a =
      (rw-scalarOrder*dw)*cornerW0 - (rv-scalarOrder*dv)*cornerV0Abs)
    (hb : scalarOrder*b =
      (rv-scalarOrder*dv)*cornerV1 - (rw-scalarOrder*dw)*cornerW1Abs)
    (hqzero : (q 0 : Int) = pairNorm a b)
    (hstep : ∀ i : Nat, i < 15 →
      100*110557*q (i+1) ≤ 101*q i + 10100*110557) :
    q 15 < 5000 := by
  obtain ⟨hal, hau, hbl, hbu⟩ :=
    selector_corner_coordinate_bound rw rv dw dv a b hrw hrv hdw hdv ha hb
  have hnorm := selector_initial_norm_bound a b ⟨hal, hau⟩ ⟨hbl, hbu⟩
  have hzero : q 0 ≤ 7*2^260 := by omega
  exact terminal_from_prime_norm_digits q hzero hstep

#print axioms quotient_step
#print axioms pair_norm_nonnegative
#print axioms pair_norm_weighted
#print axioms multiply_prime_norm
#print axioms norm_334
#print axioms selector_corner_coordinate_bound
#print axioms selector_initial_norm_bound
#print axioms digit_candidate_norm_identity
#print axioms quotient_norm_step
#print axioms norm_334_no_small_divisor
#print axioms norm_334_prime_factors
#print axioms fifteen_step_numeric_bound
#print axioms terminal_norm_below_table_limit
#print axioms terminal_from_recurrence
#print axioms terminal_from_prime_norm_digits
#print axioms terminal_for_selector_corner

end AlternateRadix
