import Lean

namespace PrimeJ0Radix919TerminalUnit

abbrev Pair := Int × Int

def norm (z : Pair) : Int :=
  z.1 * z.1 + 3 * z.1 * z.2 + 3 * z.2 * z.2

def cross (x y : Pair) : Int :=
  2 * x.1 * y.1 + 3 * x.1 * y.2 + 3 * x.2 * y.1 + 6 * x.2 * y.2

def add (x y : Pair) : Pair := (x.1 + y.1, x.2 + y.2)
def sub (x y : Pair) : Pair := (x.1 - y.1, x.2 - y.2)
def scale (k : Int) (x : Pair) : Pair := (k * x.1, k * x.2)

theorem norm_four_square (z : Pair) :
    4 * norm z = (2 * z.1 + 3 * z.2)^2 + 3 * z.2^2 := by
  rcases z with ⟨a, b⟩
  simp only [norm]
  grind +ring

theorem norm_nonneg (z : Pair) : 0 ≤ norm z := by
  have h := norm_four_square z
  have h₁ := Int.sq_nonneg (2 * z.1 + 3 * z.2)
  have h₂ := Int.sq_nonneg z.2
  omega

theorem norm_zero (z : Pair) (h : norm z = 0) : z = (0, 0) := by
  rcases z with ⟨a, b⟩
  have hid := norm_four_square (a, b)
  have hsum : (2 * a + 3 * b)^2 + 3 * b^2 = 0 := by
    simpa [h] using hid.symm
  have h₁ := Int.sq_nonneg (2 * a + 3 * b)
  have h₂ := Int.sq_nonneg b
  have hbsq : b^2 = 0 := by omega
  have hbmul : b * b = 0 := by simpa [Int.pow_succ] using hbsq
  have hb : b = 0 := by
    cases (Int.mul_eq_zero.mp hbmul) with
    | inl h => exact h
    | inr h => exact h
  have hasq : (2 * a + 3 * b)^2 = 0 := by omega
  have hamul : (2 * a + 3 * b) * (2 * a + 3 * b) = 0 := by
    simpa [Int.pow_succ] using hasq
  have ha₂ : 2 * a + 3 * b = 0 := by
    cases (Int.mul_eq_zero.mp hamul) with
    | inl h => exact h
    | inr h => exact h
  have ha : a = 0 := by omega
  simp [ha, hb]

private theorem square_lt_bounds (x k : Int) (hk : 0 ≤ k)
    (h : x * x < k * k) : -k < x ∧ x < k := by
  constructor
  · by_cases hx : x ≤ -k
    · have hneg : k ≤ -x := by omega
      have hs := Int.mul_self_le_mul_self hk hneg
      have heq : (-x) * (-x) = x * x := by grind +ring
      rw [heq] at hs
      omega
    · omega
  · by_cases hx : k ≤ x
    · have hs := Int.mul_self_le_mul_self hk hx
      omega
    · omega

theorem norm_lt_three_classify (z : Pair) (h : norm z < 3) :
    z = (0, 0) ∨ z = (1, 0) ∨ z = (-1, 0) ∨
    z = (1, -1) ∨ z = (2, -1) ∨ z = (-1, 1) ∨ z = (-2, 1) := by
  rcases z with ⟨a, b⟩
  have hfour := norm_four_square (a, b)
  have hnonneg := Int.sq_nonneg (2 * a + 3 * b)
  have hbsqnonneg := Int.sq_nonneg b
  have hfourlt : 4 * norm (a, b) < 12 := by omega
  have hsum : (2 * a + 3 * b)^2 + 3 * b^2 < 12 := by
    rw [hfour.symm]
    exact hfourlt
  have hbsq : b * b < 2 * 2 := by
    have hsq : b^2 < 4 := by omega
    simpa [Int.pow_succ] using hsq
  have hxsq : (2 * a + 3 * b) * (2 * a + 3 * b) < 4 * 4 := by
    have hsq : (2 * a + 3 * b)^2 < 16 := by omega
    simpa [Int.pow_succ] using hsq
  have hb := square_lt_bounds b 2 (by decide) hbsq
  have hx := square_lt_bounds (2 * a + 3 * b) 4 (by decide) hxsq
  have hbCases : b = -1 ∨ b = 0 ∨ b = 1 := by omega
  rcases hbCases with hbm | hb0 | hbp
  · subst b
    have haCases : a = 0 ∨ a = 1 ∨ a = 2 ∨ a = 3 := by omega
    rcases haCases with ha | ha | ha | ha <;> subst a <;> simp [norm] at h ⊢
  · subst b
    have haCases : a = -1 ∨ a = 0 ∨ a = 1 := by omega
    rcases haCases with ha | ha | ha <;> subst a <;> simp [norm] at h ⊢
  · subst b
    have haCases : a = -3 ∨ a = -2 ∨ a = -1 ∨ a = 0 := by omega
    rcases haCases with ha | ha | ha | ha <;> subst a <;> simp [norm] at h ⊢

theorem norm_scale (k : Int) (z : Pair) :
    norm (scale k z) = k * k * norm z := by
  rcases z with ⟨a, b⟩
  simp only [norm, scale]
  grind +ring

theorem norm_add (x y : Pair) :
    norm (add x y) = norm x + norm y + cross x y := by
  rcases x with ⟨a, b⟩
  rcases y with ⟨c, d⟩
  simp only [norm, add, cross]
  grind +ring

theorem norm_sub (x y : Pair) :
    norm (sub x y) = norm x + norm y - cross x y := by
  rcases x with ⟨a, b⟩
  rcases y with ⟨c, d⟩
  simp only [norm, sub, cross]
  grind +ring

theorem cross_square (x y : Pair) :
    4 * norm x * norm y - (cross x y)^2 =
      3 * (x.1 * y.2 - x.2 * y.1)^2 := by
  rcases x with ⟨a, b⟩
  rcases y with ⟨c, d⟩
  simp only [norm, cross]
  grind +ring

theorem cross_bound (x y : Pair) :
    (cross x y)^2 ≤ 4 * norm x * norm y := by
  have hid := cross_square x y
  have hsq := Int.sq_nonneg (x.1 * y.2 - x.2 * y.1)
  omega

private theorem square_triangle_bound (A B T K R : Int)
    (hB0 : 0 ≤ B) (hK : 0 ≤ K) (hR : 0 ≤ R)
    (hA : A ≤ K * K) (hB : B ≤ R * R)
    (hCS : T * T ≤ 4 * A * B) :
    A + B - T ≤ (K + R)^2 := by
  have hK₂ : 0 ≤ K * K := Int.mul_nonneg hK hK
  have hAB₁ : A * B ≤ (K * K) * B :=
    Int.mul_le_mul_of_nonneg_right hA hB0
  have hAB₂ : (K * K) * B ≤ (K * K) * (R * R) :=
    Int.mul_le_mul_of_nonneg_left hB hK₂
  have hT₂ : T * T ≤ (2 * K * R) * (2 * K * R) := by
    calc
      T * T ≤ 4 * A * B := hCS
      _ ≤ 4 * ((K * K) * (R * R)) := by
        have hAB := Int.le_trans hAB₁ hAB₂
        have h4 := Int.mul_le_mul_of_nonneg_left hAB (by decide : (0 : Int) ≤ 4)
        grind +ring
      _ = (2 * K * R) * (2 * K * R) := by grind +ring
  have hC0 : 0 ≤ 2 * K * R := by
    have h2K : 0 ≤ 2 * K := Int.mul_nonneg (by decide) hK
    exact Int.mul_nonneg h2K hR
  have hTlow : -(2 * K * R) ≤ T := by
    by_cases hbad : T < -(2 * K * R)
    · have hlt : 2 * K * R < -T := by omega
      have hs := Int.mul_self_lt_mul_self hC0 hlt
      have heq : (-T) * (-T) = T * T := by grind +ring
      rw [heq] at hs
      omega
    · omega
  have hsum : A + B - T ≤ K * K + R * R + 2 * K * R := by omega
  calc
    A + B - T ≤ K * K + R * R + 2 * K * R := hsum
    _ = (K + R)^2 := by grind +ring

theorem norm_sub_bound (x y : Pair) (K R : Int)
    (hK : 0 ≤ K) (hR : 0 ≤ R)
    (hx : 3 * norm x ≤ K^2) (hy : 3 * norm y ≤ R^2) :
    3 * norm (sub x y) ≤ (K + R)^2 := by
  have hB0 : 0 ≤ 3 * norm y := by
    have h := norm_nonneg y
    omega
  have hCS := cross_bound x y
  have hCS' : (3 * cross x y) * (3 * cross x y) ≤
      4 * (3 * norm x) * (3 * norm y) := by
    have h9 := Int.mul_le_mul_of_nonneg_left hCS (by decide : (0 : Int) ≤ 9)
    grind +ring
  have hMain := square_triangle_bound
    (3 * norm x) (3 * norm y) (3 * cross x y) K R
    hB0 hK hR (by simpa [Int.pow_succ] using hx)
    (by simpa [Int.pow_succ] using hy) hCS'
  rw [norm_sub]
  grind +ring

theorem norm_add_bound (x y : Pair) (K R : Int)
    (hK : 0 ≤ K) (hR : 0 ≤ R)
    (hx : 3 * norm x ≤ K^2) (hy : 3 * norm y ≤ R^2) :
    3 * norm (add x y) ≤ (K + R)^2 := by
  have hB0 : 0 ≤ 3 * norm y := by
    have h := norm_nonneg y
    omega
  have hCS := cross_bound x y
  have hCS' : (-3 * cross x y) * (-3 * cross x y) ≤
      4 * (3 * norm x) * (3 * norm y) := by
    have h9 := Int.mul_le_mul_of_nonneg_left hCS (by decide : (0 : Int) ≤ 9)
    grind +ring
  have hMain := square_triangle_bound
    (3 * norm x) (3 * norm y) (-3 * cross x y) K R
    hB0 hK hR (by simpa [Int.pow_succ] using hx)
    (by simpa [Int.pow_succ] using hy) hCS'
  rw [norm_add]
  grind +ring

theorem norm_scale_bound (k : Int) (z : Pair) (K : Int)
    (hk : 0 ≤ k) (h : 3 * norm z ≤ K^2) :
    3 * norm (scale k z) ≤ (k * K)^2 := by
  have hk₂ : 0 ≤ k * k := Int.mul_nonneg hk hk
  have hmul := Int.mul_le_mul_of_nonneg_left h hk₂
  rw [norm_scale]
  grind +ring

def decode : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 919 (decode tail))

def radius : Nat → Int
  | 0 => 0
  | n + 1 => 919 + 919 * radius n

theorem radius_nonneg (n : Nat) : 0 ≤ radius n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 919) ih
      simp only [radius]
      omega

theorem norm_decode_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (919 : Int)^2) →
    3 * norm (decode digits) ≤ (radius digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (919 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (919 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 919 (decode tail) (radius tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 919 * radius tail.length :=
        Int.mul_nonneg (by decide) (radius_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 919 (decode tail))
        919 (919 * radius tail.length) (by decide) hR hd hScaled
      simpa only [decode, List.length_cons, radius] using hSum

inductive Recodes : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 919 quotient))
      (rest : Recodes quotient tail terminal) :
      Recodes state (digit :: tail) terminal

theorem recodes_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes start digits terminal) :
    start = add (decode digits) (scale ((919 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode, add, scale]
  | next digit equation rest ih =>
      simp only [decode, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def subgroupOrder : Int :=
  0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

def initialRadius : Int := 340282366920938463463374607431768211456

theorem initial_radius_certificate : subgroupOrder < initialRadius^2 := by decide

theorem thirteen_window_certificate :
    (initialRadius + radius 13)^2 < 6 * ((919 : Int)^13)^2 := by decide

-- The covering hypotheses are the exact secp256k1 lattice and radix-digit
-- bounds. Thirteen steps leave a pair of norm at most one; the hypotheses
-- do not assert a particular terminal state.
theorem thirteen_steps_terminal_norm_lt_two (start terminal : Pair) (digits : List Pair)
    (hlen : digits.length = 13)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (919 : Int)^2)
    (hSteps : Recodes start digits terminal) :
    norm terminal < 2 := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := norm_decode_bound digits hDigits
  have hResidual := norm_sub_bound start (decode digits)
    initialRadius (radius digits.length) (by decide)
    (radius_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes_reconstruct start terminal digits hSteps
  have hSub : sub start (decode digits) =
      scale ((919 : Int)^digits.length) terminal := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := 3 * ((919 : Int)^13) * ((919 : Int)^13)
  have hFpos : 0 < F := by decide
  have hMass : F * norm terminal ≤ (initialRadius + radius 13)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius 13)^2 < 2 * F := by
    simpa [F, Int.pow_succ] using thirteen_window_certificate
  have hUpper : F * norm terminal < 2 * F := by omega
  by_cases hgood : norm terminal < 2
  · exact hgood
  · have hge : 2 ≤ norm terminal := by omega
    have hmul := Int.mul_le_mul_of_nonneg_left hge (Int.le_of_lt hFpos)
    omega

theorem thirteen_steps_terminal_unit (start terminal : Pair) (digits : List Pair)
    (hlen : digits.length = 13)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (919 : Int)^2)
    (hSteps : Recodes start digits terminal) :
    terminal = (0, 0) ∨ terminal = (1, 0) ∨ terminal = (-1, 0) ∨
    terminal = (1, -1) ∨ terminal = (2, -1) ∨
    terminal = (-1, 1) ∨ terminal = (-2, 1) := by
  have hBound := thirteen_steps_terminal_norm_lt_two start terminal digits
    hlen hInitial hDigits hSteps
  exact norm_lt_three_classify terminal (by omega)

#print axioms norm_four_square
#print axioms norm_nonneg
#print axioms norm_zero
#print axioms norm_lt_three_classify
#print axioms norm_scale
#print axioms norm_add
#print axioms norm_sub
#print axioms cross_square
#print axioms cross_bound
#print axioms norm_sub_bound
#print axioms norm_add_bound
#print axioms norm_scale_bound
#print axioms radius_nonneg
#print axioms norm_decode_bound
#print axioms recodes_reconstruct
#print axioms initial_radius_certificate
#print axioms thirteen_window_certificate
#print axioms thirteen_steps_terminal_norm_lt_two
#print axioms thirteen_steps_terminal_unit

end PrimeJ0Radix919TerminalUnit
