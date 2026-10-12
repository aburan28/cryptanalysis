import TerminalUnit

namespace PrimeJ0Power2DirectTerminalTopBound

open PrimeJ0Radix919TerminalUnit

def decode256 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 256 (decode256 tail))

def radius256 : Nat → Int
  | 0 => 0
  | n + 1 => 256 + 256 * radius256 n

theorem radius256_nonneg (n : Nat) : 0 ≤ radius256 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 256) ih
      simp only [radius256]
      omega

theorem decode256_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (256 : Int)^2) →
    3 * norm (decode256 digits) ≤ (radius256 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (256 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (256 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 256 (decode256 tail) (radius256 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 256 * radius256 tail.length :=
        Int.mul_nonneg (by decide) (radius256_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 256 (decode256 tail))
        256 (256 * radius256 tail.length) (by decide) hR hd hScaled
      simpa only [decode256, List.length_cons, radius256] using hSum

inductive Recodes256 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes256 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 256 quotient))
      (rest : Recodes256 quotient tail terminal) :
      Recodes256 state (digit :: tail) terminal

theorem recodes256_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes256 start digits terminal) :
    start = add (decode256 digits) (scale ((256 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode256, add, scale]
  | next digit equation rest ih =>
      simp only [decode256, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode256 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 66051

theorem top_cap_certificate :
    (initialRadius + radius256 15)^2 <
      (topCap + 1) * ((256 : Int)^15)^2 := by decide

theorem fifteen_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 15)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (256 : Int)^2)
    (hSteps : Recodes256 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode256_bound digits hDigits
  have hResidual := norm_sub_bound start (decode256 digits)
    initialRadius (radius256 digits.length) (by decide)
    (radius256_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes256_reconstruct start top digits hSteps
  have hSub : sub start (decode256 digits) =
      scale ((256 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((256 : Int)^15) * ((256 : Int)^15)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius256 15)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius256 15)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

#print axioms radius256_nonneg
#print axioms decode256_bound
#print axioms recodes256_reconstruct
#print axioms top_cap_certificate
#print axioms fifteen_steps_top_bound

end PrimeJ0Power2DirectTerminalTopBound
