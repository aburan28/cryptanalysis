import TopBound

namespace PrimeJ0HexTerminal

open PrimeJ0Radix919TerminalUnit
open PrimeJ0Power2DirectTerminalTopBound

def basisU : Pair :=
  (193508920647619669885755136084601127231,
   238911465918039986966665730306072050094)

def basisV : Pair :=
  (-238911465918039986966665730306072050094,
   303414439467246543595250775667605759171)

def basisW : Pair := sub basisU (scale 2 basisV)
def basisSum : Pair := add basisW basisV

def twiceInner (z v : Pair) : Int :=
  z.1 * (2*v.1 + 3*v.2) + z.2 * (3*v.1 + 6*v.2)

def digitSupport : Int := 100588603464850855725768518207408495723870
def hexLimit : Int := 87506751043387112747509266240600930742795

theorem neighbor_norms :
    norm basisW = subgroupOrder ∧
    norm basisV = subgroupOrder ∧
    norm basisSum = subgroupOrder := by decide

theorem support_certificate :
    4 * (256 : Int)^2 * subgroupOrder ≤ 3 * digitSupport^2 := by decide

theorem support_minimal_certificate :
    3 * (digitSupport - 1)^2 <
      4 * (256 : Int)^2 * subgroupOrder := by decide

theorem hex_limit_certificate :
    (subgroupOrder + digitSupport * radius256 15 / 256) <
      (hexLimit + 1) * ((256 : Int)^15) := by decide

theorem inner_add (z w v : Pair) :
    twiceInner (add z w) v = twiceInner z v + twiceInner w v := by
  rcases z with ⟨a,b⟩
  rcases w with ⟨c,d⟩
  rcases v with ⟨x,y⟩
  simp [twiceInner, add]
  grind +ring

theorem inner_sub (z w v : Pair) :
    twiceInner (sub z w) v = twiceInner z v - twiceInner w v := by
  rcases z with ⟨a,b⟩
  rcases w with ⟨c,d⟩
  rcases v with ⟨x,y⟩
  simp [twiceInner, sub]
  grind +ring

theorem inner_scale (c : Int) (z v : Pair) :
    twiceInner (scale c z) v = c * twiceInner z v := by
  rcases z with ⟨a,b⟩
  rcases v with ⟨x,y⟩
  simp [twiceInner, scale]
  grind +ring

theorem norm_add_inner (z v : Pair) :
    norm (add z v) = norm z + norm v + twiceInner z v := by
  rcases z with ⟨a,b⟩
  rcases v with ⟨x,y⟩
  simp [norm, add, twiceInner]
  grind +ring

theorem norm_sub_inner (z v : Pair) :
    norm (sub z v) = norm z + norm v - twiceInner z v := by
  rcases z with ⟨a,b⟩
  rcases v with ⟨x,y⟩
  simp [norm, sub, twiceInner]
  grind +ring

theorem closest_neighbor_inner (z v : Pair)
    (hn : norm v = subgroupOrder)
    (hp : norm z ≤ norm (add z v))
    (hm : norm z ≤ norm (sub z v)) :
    -subgroupOrder ≤ twiceInner z v ∧
      twiceInner z v ≤ subgroupOrder := by
  rw [norm_add_inner, hn] at hp
  rw [norm_sub_inner, hn] at hm
  omega

theorem inner_cauchy_identity (z v : Pair) :
    4 * norm z * norm v - (twiceInner z v)^2 =
      3 * (z.1*v.2 - z.2*v.1)^2 := by
  rcases z with ⟨a,b⟩
  rcases v with ⟨x,y⟩
  simp [norm, twiceInner]
  grind +ring

theorem digit_inner_bound (digit v : Pair)
    (hv : norm v = subgroupOrder)
    (hd : 3 * norm digit ≤ (256 : Int)^2) :
    -digitSupport ≤ twiceInner digit v ∧
      twiceInner digit v ≤ digitSupport := by
  have hc : (twiceInner digit v)^2 ≤
      4 * norm digit * subgroupOrder := by
    have hid := inner_cauchy_identity digit v
    have hsq := Int.sq_nonneg (digit.1*v.2 - digit.2*v.1)
    rw [hv] at hid
    omega
  have hcert := support_certificate
  have h4n : 0 ≤ 4 * subgroupOrder := by decide
  have hDigitMul := Int.mul_le_mul_of_nonneg_right hd h4n
  have hCrossMul := Int.mul_le_mul_of_nonneg_left hc (by decide : (0 : Int) ≤ 3)
  have hScaled : 3 * (twiceInner digit v)^2 ≤
      4 * (256 : Int)^2 * subgroupOrder := by
    have hA : 3 * (twiceInner digit v)^2 ≤
        12 * norm digit * subgroupOrder := by
      calc
        3 * (twiceInner digit v)^2 ≤
            3 * (4 * norm digit * subgroupOrder) := hCrossMul
        _ = 12 * norm digit * subgroupOrder := by grind +ring
    have hB : 12 * norm digit * subgroupOrder ≤
        4 * (256 : Int)^2 * subgroupOrder := by
      calc
        12 * norm digit * subgroupOrder =
            3 * norm digit * (4 * subgroupOrder) := by grind +ring
        _ ≤ (256 : Int)^2 * (4 * subgroupOrder) := hDigitMul
        _ = 4 * (256 : Int)^2 * subgroupOrder := by grind +ring
    omega
  have hsq : (twiceInner digit v)^2 ≤ digitSupport^2 := by
    omega
  have hm : 0 ≤ digitSupport := by decide
  constructor
  · by_cases hlow : -digitSupport ≤ twiceInner digit v
    · exact hlow
    · have hlt : digitSupport < -twiceInner digit v := by omega
      have hs := Int.mul_self_lt_mul_self hm hlt
      have heq : (-twiceInner digit v) * (-twiceInner digit v) =
          (twiceInner digit v)^2 := by grind +ring
      rw [heq] at hs
      have hs' : digitSupport^2 < (twiceInner digit v)^2 := by
        calc
          digitSupport^2 = digitSupport * digitSupport := by grind +ring
          _ < (twiceInner digit v)^2 := hs
      omega
  · by_cases hupp : twiceInner digit v ≤ digitSupport
    · exact hupp
    · have hlt : digitSupport < twiceInner digit v := by omega
      have hs := Int.mul_self_lt_mul_self hm hlt
      have hs' : digitSupport^2 < (twiceInner digit v)^2 := by
        calc
          digitSupport^2 = digitSupport * digitSupport := by grind +ring
          _ < twiceInner digit v * twiceInner digit v := hs
          _ = (twiceInner digit v)^2 := by grind +ring
      omega

def digitWeight : Nat → Int
  | 0 => 0
  | n + 1 => 1 + 256 * digitWeight n

theorem digitWeight_eq_radius (n : Nat) :
    256 * digitWeight n = radius256 n := by
  induction n with
  | zero => decide
  | succ n ih =>
      simp only [digitWeight, radius256]
      omega

theorem decode_inner_bound (digits : List Pair) (v : Pair)
    (hDigits : ∀ digit ∈ digits,
      -digitSupport ≤ twiceInner digit v ∧
        twiceInner digit v ≤ digitSupport) :
    -digitSupport * digitWeight digits.length ≤
        twiceInner (decode256 digits) v ∧
      twiceInner (decode256 digits) v ≤
        digitSupport * digitWeight digits.length := by
  induction digits with
  | nil =>
      simp [decode256, digitWeight, twiceInner]
  | cons digit tail ih =>
      have hd := hDigits digit (by simp)
      have ht : ∀ item ∈ tail,
          -digitSupport ≤ twiceInner item v ∧
            twiceInner item v ≤ digitSupport := by
        intro item hmem
        exact hDigits item (by simp [hmem])
      have hr := ih ht
      simp only [decode256, List.length_cons, digitWeight,
        inner_add, inner_scale]
      constructor <;> grind +ring

theorem hex_limit_floor_certificate :
    subgroupOrder + digitSupport * digitWeight 15 <
      (hexLimit + 1) * ((256 : Int)^15) := by decide

theorem terminal_inner_bound (start top v : Pair) (digits : List Pair)
    (hlen : digits.length = 15)
    (hStart : -subgroupOrder ≤ twiceInner start v ∧
      twiceInner start v ≤ subgroupOrder)
    (hDigits : ∀ digit ∈ digits,
      -digitSupport ≤ twiceInner digit v ∧
        twiceInner digit v ≤ digitSupport)
    (hSteps : Recodes256 start digits top) :
    -hexLimit ≤ twiceInner top v ∧
      twiceInner top v ≤ hexLimit := by
  have hd := decode_inner_bound digits v hDigits
  have heq := recodes256_reconstruct start top digits hSteps
  have hlin := congrArg (fun z => twiceInner z v) heq
  rw [inner_add, inner_scale, hlen] at hlin
  rw [hlen] at hd
  have hsign : -digitSupport * digitWeight 15 =
      -(digitSupport * digitWeight 15) := by grind +ring
  rw [hsign] at hd
  have hPval : (256 : Int)^15 = 1329227995784915872903807060280344576 := by decide
  rw [hPval] at hlin
  have hcert := hex_limit_floor_certificate
  rw [hPval] at hcert
  constructor
  · omega
  · omega

def sixNeighborsClosest (start : Pair) : Prop :=
  (norm start ≤ norm (add start basisW) ∧
    norm start ≤ norm (sub start basisW)) ∧
  (norm start ≤ norm (add start basisV) ∧
    norm start ≤ norm (sub start basisV)) ∧
  (norm start ≤ norm (add start basisSum) ∧
    norm start ≤ norm (sub start basisSum))

def terminalDomain (top : Pair) : Prop :=
  3 * norm top ≤ topCap ∧
  -hexLimit ≤ twiceInner top basisW ∧
    twiceInner top basisW ≤ hexLimit ∧
  -hexLimit ≤ twiceInner top basisV ∧
    twiceInner top basisV ≤ hexLimit ∧
  -hexLimit ≤ twiceInner top basisSum ∧
    twiceInner top basisSum ≤ hexLimit

theorem recoded_terminal_in_domain (start top : Pair) (digits : List Pair)
    (hlen : digits.length = 15)
    (hInitial : 3 * norm start ≤ subgroupOrder)
    (hNearest : sixNeighborsClosest start)
    (hDigits : ∀ digit ∈ digits, 3 * norm digit ≤ (256 : Int)^2)
    (hSteps : Recodes256 start digits top) :
    terminalDomain top := by
  have hn := neighbor_norms
  rcases hNearest with ⟨hw, hv, hs⟩
  have hw0 := closest_neighbor_inner start basisW hn.1 hw.1 hw.2
  have hv0 := closest_neighbor_inner start basisV hn.2.1 hv.1 hv.2
  have hs0 := closest_neighbor_inner start basisSum hn.2.2 hs.1 hs.2
  have hBound (v : Pair) (hnorm : norm v = subgroupOrder)
      (hstart : -subgroupOrder ≤ twiceInner start v ∧
        twiceInner start v ≤ subgroupOrder) :
      -hexLimit ≤ twiceInner top v ∧
        twiceInner top v ≤ hexLimit := by
    apply terminal_inner_bound start top v digits hlen hstart
    · intro digit hmem
      exact digit_inner_bound digit v hnorm (hDigits digit hmem)
    · exact hSteps
  have htW := hBound basisW hn.1 hw0
  have htV := hBound basisV hn.2.1 hv0
  have htS := hBound basisSum hn.2.2 hs0
  exact ⟨fifteen_steps_top_bound start top digits hlen hInitial hDigits hSteps,
    htW.1, htW.2, htV.1, htV.2, htS.1, htS.2⟩

#print axioms neighbor_norms
#print axioms support_certificate
#print axioms support_minimal_certificate
#print axioms inner_cauchy_identity
#print axioms closest_neighbor_inner
#print axioms digit_inner_bound
#print axioms decode_inner_bound
#print axioms terminal_inner_bound
#print axioms recoded_terminal_in_domain

end PrimeJ0HexTerminal
