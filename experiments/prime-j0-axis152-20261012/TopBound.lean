import TerminalUnit

namespace PrimeJ0Axis152TopBound

open PrimeJ0Radix919TerminalUnit

def decode152 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 152 (decode152 tail))

def radius152 : Nat → Int
  | 0 => 0
  | n + 1 => 152 + 152 * radius152 n

theorem radius152_nonneg (n : Nat) : 0 ≤ radius152 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 152) ih
      simp only [radius152]
      omega

theorem decode152_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (152 : Int)^2) →
    3 * norm (decode152 digits) ≤ (radius152 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (152 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (152 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 152 (decode152 tail) (radius152 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 152 * radius152 tail.length :=
        Int.mul_nonneg (by decide) (radius152_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 152 (decode152 tail))
        152 (152 * radius152 tail.length) (by decide) hR hd hScaled
      simpa only [decode152, List.length_cons, radius152] using hSum

inductive Recodes152 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes152 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 152 quotient))
      (rest : Recodes152 quotient tail terminal) :
      Recodes152 state (digit :: tail) terminal

theorem recodes152_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes152 start digits terminal) :
    start = add (decode152 digits) (scale ((152 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode152, add, scale]
  | next digit equation rest ih =>
      simp only [decode152, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode152 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 17574891

theorem top_cap_certificate :
    (initialRadius + radius152 16)^2 <
      (topCap + 1) * ((152 : Int)^16)^2 := by decide

theorem sixteen_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 16)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (152 : Int)^2)
    (hSteps : Recodes152 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode152_bound digits hDigits
  have hResidual := norm_sub_bound start (decode152 digits)
    initialRadius (radius152 digits.length) (by decide)
    (radius152_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes152_reconstruct start top digits hSteps
  have hSub : sub start (decode152 digits) =
      scale ((152 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((152 : Int)^16) * ((152 : Int)^16)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius152 16)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius152 16)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

#print axioms radius152_nonneg
#print axioms decode152_bound
#print axioms recodes152_reconstruct
#print axioms top_cap_certificate
#print axioms sixteen_steps_top_bound

end PrimeJ0Axis152TopBound
