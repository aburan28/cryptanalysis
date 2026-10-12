import TerminalUnit

namespace PrimeJ0Axis286TopBound

open PrimeJ0Radix919TerminalUnit

def decode286 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 286 (decode286 tail))

def radius286 : Nat → Int
  | 0 => 0
  | n + 1 => 286 + 286 * radius286 n

theorem radius286_nonneg (n : Nat) : 0 ≤ radius286 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 286) ih
      simp only [radius286]
      omega

theorem decode286_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (286 : Int)^2) →
    3 * norm (decode286 digits) ≤ (radius286 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (286 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (286 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 286 (decode286 tail) (radius286 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 286 * radius286 tail.length :=
        Int.mul_nonneg (by decide) (radius286_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 286 (decode286 tail))
        286 (286 * radius286 tail.length) (by decide) hR hd hScaled
      simpa only [decode286, List.length_cons, radius286] using hSum

inductive Recodes286 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes286 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 286 quotient))
      (rest : Recodes286 quotient tail terminal) :
      Recodes286 state (digit :: tail) terminal

theorem recodes286_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes286 start digits terminal) :
    start = add (decode286 digits) (scale ((286 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode286, add, scale]
  | next digit equation rest ih =>
      simp only [decode286, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode286 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 192971294

theorem top_cap_certificate :
    (initialRadius + radius286 14)^2 <
      (topCap + 1) * ((286 : Int)^14)^2 := by decide

theorem fourteen_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 14)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (286 : Int)^2)
    (hSteps : Recodes286 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode286_bound digits hDigits
  have hResidual := norm_sub_bound start (decode286 digits)
    initialRadius (radius286 digits.length) (by decide)
    (radius286_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes286_reconstruct start top digits hSteps
  have hSub : sub start (decode286 digits) =
      scale ((286 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((286 : Int)^14) * ((286 : Int)^14)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius286 14)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius286 14)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

#print axioms radius286_nonneg
#print axioms decode286_bound
#print axioms recodes286_reconstruct
#print axioms top_cap_certificate
#print axioms fourteen_steps_top_bound

end PrimeJ0Axis286TopBound
