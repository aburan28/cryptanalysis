import TerminalUnit

namespace PrimeJ0Radix569TopBound

open PrimeJ0Radix919TerminalUnit

def decode569 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 569 (decode569 tail))

def radius569 : Nat → Int
  | 0 => 0
  | n + 1 => 569 + 569 * radius569 n

theorem radius569_nonneg (n : Nat) : 0 ≤ radius569 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 569) ih
      simp only [radius569]
      omega

theorem decode569_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (569 : Int)^2) →
    3 * norm (decode569 digits) ≤ (radius569 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (569 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (569 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 569 (decode569 tail) (radius569 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 569 * radius569 tail.length :=
        Int.mul_nonneg (by decide) (radius569_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 569 (decode569 tail))
        569 (569 * radius569 tail.length) (by decide) hR hd hScaled
      simpa only [decode569, List.length_cons, radius569] using hSum

inductive Recodes569 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes569 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 569 quotient))
      (rest : Recodes569 quotient tail terminal) :
      Recodes569 state (digit :: tail) terminal

theorem recodes569_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes569 start digits terminal) :
    start = add (decode569 digits) (scale ((569 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode569, add, scale]
  | next digit equation rest ih =>
      simp only [decode569, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode569 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 270666

theorem top_cap_certificate :
    (initialRadius + radius569 13)^2 <
      (topCap + 1) * ((569 : Int)^13)^2 := by decide

theorem thirteen_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 13)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (569 : Int)^2)
    (hSteps : Recodes569 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode569_bound digits hDigits
  have hResidual := norm_sub_bound start (decode569 digits)
    initialRadius (radius569 digits.length) (by decide)
    (radius569_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes569_reconstruct start top digits hSteps
  have hSub : sub start (decode569 digits) =
      scale ((569 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((569 : Int)^13) * ((569 : Int)^13)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius569 13)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius569 13)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

#print axioms radius569_nonneg
#print axioms decode569_bound
#print axioms recodes569_reconstruct
#print axioms top_cap_certificate
#print axioms thirteen_steps_top_bound

end PrimeJ0Radix569TopBound
