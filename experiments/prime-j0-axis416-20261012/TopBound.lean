import TerminalUnit

namespace PrimeJ0Axis416TopBound

open PrimeJ0Radix919TerminalUnit

def decode416 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 416 (decode416 tail))

def radius416 : Nat → Int
  | 0 => 0
  | n + 1 => 416 + 416 * radius416 n

theorem radius416_nonneg (n : Nat) : 0 ≤ radius416 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 416) ih
      simp only [radius416]
      omega

theorem decode416_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (416 : Int)^2) →
    3 * norm (decode416 digits) ≤ (radius416 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (416 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (416 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 416 (decode416 tail) (radius416 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 416 * radius416 tail.length :=
        Int.mul_nonneg (by decide) (radius416_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 416 (decode416 tail))
        416 (416 * radius416 tail.length) (by decide) hR hd hScaled
      simpa only [decode416, List.length_cons, radius416] using hSum

inductive Recodes416 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes416 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 416 quotient))
      (rest : Recodes416 quotient tail terminal) :
      Recodes416 state (digit :: tail) terminal

theorem recodes416_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes416 start digits terminal) :
    start = add (decode416 digits) (scale ((416 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode416, add, scale]
  | next digit equation rest ih =>
      simp only [decode416, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode416 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 927429454

theorem top_cap_certificate :
    (initialRadius + radius416 13)^2 <
      (topCap + 1) * ((416 : Int)^13)^2 := by decide

theorem thirteen_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 13)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (416 : Int)^2)
    (hSteps : Recodes416 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode416_bound digits hDigits
  have hResidual := norm_sub_bound start (decode416 digits)
    initialRadius (radius416 digits.length) (by decide)
    (radius416_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes416_reconstruct start top digits hSteps
  have hSub : sub start (decode416 digits) =
      scale ((416 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((416 : Int)^13) * ((416 : Int)^13)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius416 13)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius416 13)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

#print axioms radius416_nonneg
#print axioms decode416_bound
#print axioms recodes416_reconstruct
#print axioms top_cap_certificate
#print axioms thirteen_steps_top_bound

end PrimeJ0Axis416TopBound
