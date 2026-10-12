import TerminalUnit

namespace PrimeJ0SplitTop

open PrimeJ0Radix919TerminalUnit

def decode671 : List Pair → Pair
  | [] => (0, 0)
  | digit :: tail => add digit (scale 671 (decode671 tail))

def radius671 : Nat → Int
  | 0 => 0
  | n + 1 => 671 + 671 * radius671 n

theorem radius671_nonneg (n : Nat) : 0 ≤ radius671 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      have hmul := Int.mul_nonneg (by decide : (0 : Int) ≤ 671) ih
      simp only [radius671]
      omega

theorem decode671_bound (digits : List Pair) :
    (∀ digit ∈ digits, 3 * norm digit ≤ (671 : Int)^2) →
    3 * norm (decode671 digits) ≤ (radius671 digits.length)^2 := by
  induction digits with
  | nil =>
      intro _
      decide
  | cons digit tail ih =>
      intro hDigits
      have hd : 3 * norm digit ≤ (671 : Int)^2 :=
        hDigits digit (by simp)
      have hTail : ∀ x ∈ tail, 3 * norm x ≤ (671 : Int)^2 := by
        intro x hx
        exact hDigits x (by simp [hx])
      have hScaled := norm_scale_bound 671 (decode671 tail) (radius671 tail.length)
        (by decide) (ih hTail)
      have hR : 0 ≤ 671 * radius671 tail.length :=
        Int.mul_nonneg (by decide) (radius671_nonneg tail.length)
      have hSum := norm_add_bound digit (scale 671 (decode671 tail))
        671 (671 * radius671 tail.length) (by decide) hR hd hScaled
      simpa only [decode671, List.length_cons, radius671] using hSum

inductive Recodes671 : Pair → List Pair → Pair → Prop where
  | done (terminal : Pair) : Recodes671 terminal [] terminal
  | next {state quotient terminal : Pair} {tail : List Pair}
      (digit : Pair) (equation : state = add digit (scale 671 quotient))
      (rest : Recodes671 quotient tail terminal) :
      Recodes671 state (digit :: tail) terminal

theorem recodes671_reconstruct (start terminal : Pair) (digits : List Pair)
    (h : Recodes671 start digits terminal) :
    start = add (decode671 digits) (scale ((671 : Int)^digits.length) terminal) := by
  induction h with
  | done terminal => simp [decode671, add, scale]
  | next digit equation rest ih =>
      simp only [decode671, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      rcases digit with ⟨da, db⟩
      rcases decode671 _ with ⟨xa, xb⟩
      rcases terminal with ⟨ta, tb⟩
      simp [add, scale]
      constructor <;> grind +ring

def topCap : Int := 1668628670

theorem top_cap_certificate :
    (initialRadius + radius671 12)^2 <
      (topCap + 1) * ((671 : Int)^12)^2 := by decide

theorem twelve_steps_top_bound (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 12)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (671 : Int)^2)
    (hSteps : Recodes671 start digits top) :
    3 * norm top ≤ topCap := by
  have hStart : 3 * norm start ≤ initialRadius^2 :=
    Int.le_trans hInitial (Int.le_of_lt initial_radius_certificate)
  have hDecode := decode671_bound digits hDigits
  have hResidual := norm_sub_bound start (decode671 digits)
    initialRadius (radius671 digits.length) (by decide)
    (radius671_nonneg digits.length) hStart hDecode
  have hReconstruct := recodes671_reconstruct start top digits hSteps
  have hSub : sub start (decode671 digits) =
      scale ((671 : Int)^digits.length) top := by
    apply Prod.ext
    · have heq := congrArg Prod.fst hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
    · have heq := congrArg Prod.snd hReconstruct
      dsimp [add, sub, scale] at heq ⊢
      omega
  rw [hSub, norm_scale, hlen] at hResidual
  let F : Int := ((671 : Int)^12) * ((671 : Int)^12)
  have hFpos : 0 < F := by decide
  have hMass : F * (3 * norm top) ≤ (initialRadius + radius671 12)^2 := by
    dsimp [F]
    grind +ring
  have hCert : (initialRadius + radius671 12)^2 < (topCap + 1) * F := by
    simpa [F, Int.pow_succ] using top_cap_certificate
  have hUpper : F * (3 * norm top) < (topCap + 1) * F := by omega
  by_cases hgood : 3 * norm top ≤ topCap
  · exact hgood
  · have hge : topCap + 1 ≤ 3 * norm top := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hge (Int.le_of_lt hFpos)
    have hcomm : (3 * norm top) * F = F * (3 * norm top) := by grind +ring
    omega

def low (x : Int) : Int := (x + 128) % 256 - 128
def high (x : Int) : Int := (x + 128) / 256

theorem split_coordinate (x : Int) : low x + 256 * high x = x := by
  dsimp [low, high]
  omega

theorem low_interval (x : Int) : -128 ≤ low x ∧ low x ≤ 127 := by
  dsimp [low]
  omega

def splitLow (z : Pair) : Pair := (low z.1, low z.2)
def splitHigh (z : Pair) : Pair := (high z.1, high z.2)

theorem split_pair (z : Pair) :
    z = add (splitLow z) (scale 256 (splitHigh z)) := by
  rcases z with ⟨a, b⟩
  have ha := split_coordinate a
  have hb := split_coordinate b
  simp only [splitLow, splitHigh, add, scale]
  exact Prod.ext ha.symm hb.symm

theorem top_coordinate_box (a b : Int)
    (h : 3 * norm (a, b) ≤ topCap) :
    -47168 ≤ a ∧ a ≤ 47168 ∧ -27232 ≤ b ∧ b ≤ 27232 := by
  have hAId : 4 * norm (a, b) = a^2 + 3 * (a + 2*b)^2 := by
    simp only [norm]
    grind +ring
  have hBId := norm_four_square (a, b)
  have hAsq : 3*a^2 ≤ 4*topCap := by
    have hs := Int.sq_nonneg (a + 2*b)
    omega
  have hBsq : 9*b^2 ≤ 4*topCap := by
    have hs := Int.sq_nonneg (2*a + 3*b)
    simp only [Prod.fst, Prod.snd] at hBId
    omega
  have hAthreshold : 4*topCap < 3*(47169 : Int)^2 := by decide
  have hBthreshold : 4*topCap < 9*(27233 : Int)^2 := by decide
  have hApos : a ≤ 47168 := by
    by_cases hc : a ≤ 47168
    · exact hc
    have hge : 47169 ≤ a := by omega
    have hs := Int.mul_self_le_mul_self (by decide : (0 : Int) ≤ 47169) hge
    have hs' : (47169 : Int)^2 ≤ a^2 := by simpa [Int.pow_succ] using hs
    omega
  have hAneg : -47168 ≤ a := by
    by_cases hc : -47168 ≤ a
    · exact hc
    have hge : 47169 ≤ -a := by omega
    have hs := Int.mul_self_le_mul_self (by decide : (0 : Int) ≤ 47169) hge
    have hs' : (47169 : Int)^2 ≤ a^2 := by
      have hx : (47169 : Int)^2 ≤ (-a)^2 := by simpa [Int.pow_succ] using hs
      have heq : (-a)^2 = a^2 := by grind +ring
      rwa [heq] at hx
    omega
  have hBpos : b ≤ 27232 := by
    by_cases hc : b ≤ 27232
    · exact hc
    have hge : 27233 ≤ b := by omega
    have hs := Int.mul_self_le_mul_self (by decide : (0 : Int) ≤ 27233) hge
    have hs' : (27233 : Int)^2 ≤ b^2 := by simpa [Int.pow_succ] using hs
    omega
  have hBneg : -27232 ≤ b := by
    by_cases hc : -27232 ≤ b
    · exact hc
    have hge : 27233 ≤ -b := by omega
    have hs := Int.mul_self_le_mul_self (by decide : (0 : Int) ≤ 27233) hge
    have hs' : (27233 : Int)^2 ≤ b^2 := by
      have hx : (27233 : Int)^2 ≤ (-b)^2 := by simpa [Int.pow_succ] using hs
      have heq : (-b)^2 = b^2 := by grind +ring
      rwa [heq] at hx
    omega
  exact ⟨hAneg, hApos, hBneg, hBpos⟩

theorem split_top_box (top : Pair) (h : 3 * norm top ≤ topCap) :
    -128 ≤ (splitLow top).1 ∧ (splitLow top).1 ≤ 127 ∧
    -128 ≤ (splitLow top).2 ∧ (splitLow top).2 ≤ 127 ∧
    -184 ≤ (splitHigh top).1 ∧ (splitHigh top).1 ≤ 184 ∧
    -106 ≤ (splitHigh top).2 ∧ (splitHigh top).2 ≤ 106 := by
  rcases top with ⟨a, b⟩
  obtain ⟨ha0, ha1, hb0, hb1⟩ := top_coordinate_box a b h
  have hla := low_interval a
  have hlb := low_interval b
  have hha : -184 ≤ high a ∧ high a ≤ 184 := by
    dsimp [high]
    omega
  have hhb : -106 ≤ high b ∧ high b ≤ 106 := by
    dsimp [high]
    omega
  simpa [splitLow, splitHigh] using
    (show -128 ≤ low a ∧ low a ≤ 127 ∧ -128 ≤ low b ∧
          low b ≤ 127 ∧ -184 ≤ high a ∧ high a ≤ 184 ∧
          -106 ≤ high b ∧ high b ≤ 106 from
      ⟨hla.1, hla.2, hlb.1, hlb.2, hha.1, hha.2, hhb.1, hhb.2⟩)

theorem twelve_steps_split (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 12)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (671 : Int)^2)
    (hSteps : Recodes671 start digits top) :
    start = add (decode671 digits)
      (scale ((671 : Int)^12) (add (splitLow top) (scale 256 (splitHigh top)))) ∧
    3 * norm top ≤ topCap := by
  have hrec := recodes671_reconstruct start top digits hSteps
  have hbound := twelve_steps_top_bound start top digits hlen hInitial hDigits hSteps
  rw [hlen] at hrec
  constructor
  · rw [← split_pair top]
    exact hrec
  · exact hbound

#print axioms radius671_nonneg
#print axioms decode671_bound
#print axioms recodes671_reconstruct
#print axioms top_cap_certificate
#print axioms twelve_steps_top_bound
#print axioms split_coordinate
#print axioms low_interval
#print axioms split_pair
#print axioms top_coordinate_box
#print axioms split_top_box
#print axioms twelve_steps_split

end PrimeJ0SplitTop
