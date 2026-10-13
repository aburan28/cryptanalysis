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

-- In an equilateral W,V cell, the four scores are norm differences
-- divided by the common positive cell scale. The minimum corner lies
-- between all three pairs of Voronoi support lines.
def cornerScore (x y d : Int) : Nat → Int
  | 0 => 0
  | 1 => d - 2*x + y
  | 2 => d + x - 2*y
  | 3 => d - x - y
  | _ => 0

def cornerResidual (x y d : Int) : Nat → Pair
  | 0 => (x, y)
  | 1 => (x-d, y)
  | 2 => (x, y-d)
  | 3 => (x-d, y-d)
  | _ => (x, y)

def cellNorm (x y d : Int) (corner : Nat) : Int :=
  let z := cornerResidual x y d corner
  z.1*z.1 + z.2*z.2 - z.1*z.2

theorem corner_score_norm_identity (x y d : Int) (corner : Nat)
    (hc : corner < 4) :
    cellNorm x y d corner =
      cellNorm x y d 0 + d * cornerScore x y d corner := by
  have hcases : corner = 0 ∨ corner = 1 ∨ corner = 2 ∨ corner = 3 := by omega
  rcases hcases with h | h | h | h
  all_goals
    subst corner
    simp only [cellNorm, cornerResidual, cornerScore]
    grind +ring

theorem four_corner_minimum_has_hex_strips (x y d : Int) (corner : Nat)
    (hx0 : 0 ≤ x) (hxd : x ≤ d)
    (hy0 : 0 ≤ y) (hyd : y ≤ d) (hc : corner < 4)
    (hmin : ∀ j < 4, cornerScore x y d corner ≤ cornerScore x y d j) :
    let z := cornerResidual x y d corner;
    -d ≤ 2*z.1-z.2 ∧ 2*z.1-z.2 ≤ d ∧
    -d ≤ 2*z.2-z.1 ∧ 2*z.2-z.1 ≤ d ∧
    -d ≤ z.1+z.2 ∧ z.1+z.2 ≤ d := by
  have h0 := hmin 0 (by decide)
  have h1 := hmin 1 (by decide)
  have h2 := hmin 2 (by decide)
  have h3 := hmin 3 (by decide)
  have hcases : corner = 0 ∨ corner = 1 ∨ corner = 2 ∨ corner = 3 := by omega
  rcases hcases with h | h | h | h
  all_goals
    subst corner
    simp only [cornerScore, cornerResidual] at h0 h1 h2 h3 ⊢
    omega

def fractionBase : Int := 18446744073709551616
def fractionTail : Int := (2 : Int)^448

theorem fraction_base_width :
    0 < fractionBase ∧ fractionBase*fractionBase = (2 : Int)^128 := by
  decide

-- Little-endian words copied from RECIP_V1 and RECIP_MINUS_W1 in
-- eisenstein_fixed.rs. Keeping the words in the statement makes changes to
-- either production constant visible to this certificate.
def nativeRecipV1 : Int :=
  0x44180e526536385c + fractionBase*0x46683369b37d7630 +
  fractionBase^2*0x1571b4ae8ac47f71 +
  fractionBase^3*0x221208ac9df506c6 +
  fractionBase^4*0x6f547fa90abfe4c4 +
  fractionBase^5*0xe4437ed6010e8828 + fractionBase^6*0x0

def nativeRecipMinusW1 : Int :=
  0x06dfcbca80313b00 + fractionBase*0x30e98f407e1a0fa2 +
  fractionBase^2*0xfe04d548d0a02fa2 +
  fractionBase^3*0x5fbc92c10fddd145 +
  fractionBase^4*0x57c1108d9d44cfd9 +
  fractionBase^5*0x14ca50f7a8e2f3f6 + fractionBase^6*0x1

theorem native_reciprocals_floor :
    subgroupOrder*nativeRecipV1 ≤ (fractionBase*fractionTail)*basisV.2 ∧
      (fractionBase*fractionTail)*basisV.2 <
        subgroupOrder*(nativeRecipV1+1) ∧
    subgroupOrder*nativeRecipMinusW1 ≤
      (fractionBase*fractionTail)*(-basisW.2) ∧
      (fractionBase*fractionTail)*(-basisW.2) <
        subgroupOrder*(nativeRecipMinusW1+1) := by decide

theorem reduced_scalar_below_fraction_tail (k : Int)
    (hk : k < subgroupOrder) : k < fractionTail := by
  have hbound : subgroupOrder < fractionTail := by decide
  omega

-- Extract the high quotient, high fractional word, and seven lower words
-- from an exact product. The native routine returns the corresponding array
-- entries; proving that its loop computes this exact P is a separate bridge.
theorem exact_product_high_fraction_decomposition (P B L : Int)
    (hB : 0 < B) (hL : 0 < L) :
    let q := (P / L) / B
    let h := (P / L) % B
    let low := P % L
    P = (B*L)*q + L*h + low ∧
      0 ≤ low ∧ low < L ∧ 0 ≤ h ∧ h < B := by
  have h1 := Int.emod_add_ediv_mul P L
  have h2 := Int.emod_add_ediv_mul (P / L) B
  dsimp
  constructor
  · grind +ring
  constructor
  · exact Int.emod_nonneg _ (by omega)
  constructor
  · exact Int.emod_lt_of_pos _ hL
  constructor
  · exact Int.emod_nonneg _ (by omega)
  · exact Int.emod_lt_of_pos _ hB

theorem product_quotient_remainder_from_words
    (P B L Q H low : Int)
    (hB : 0 < B) (hL : 0 < L)
    (hP : P = L*(B*Q+H)+low)
    (hH0 : 0 ≤ H) (hHB : H < B)
    (hlow0 : 0 ≤ low) (hlowL : low < L) :
    (P/L)/B = Q ∧ (P/L)%B = H ∧ P%L = low := by
  have hquot : P/L = B*Q+H := by
    rw [Int.ediv_eq_iff_of_pos hL]
    rw [hP]
    grind +ring
  have hhigh : (P/L)/B = Q := by
    rw [hquot, Int.ediv_eq_iff_of_pos hB]
    grind +ring
  have hfrac : (P/L)%B = H := by
    have hdiv := Int.emod_add_ediv_mul (B*Q+H) B
    rw [hquot]
    have hhigh' : (B*Q+H)/B = Q := by simpa [hquot] using hhigh
    rw [hhigh'] at hdiv
    grind +ring
  have hlow : P%L = low := by
    have hdiv := Int.emod_add_ediv_mul P L
    rw [hquot] at hdiv
    rw [hP] at hdiv ⊢
    grind +ring
  exact ⟨hhigh, hfrac, hlow⟩

-- One native inner-loop multiply-add fits in u128: its four inputs are
-- 64-bit words, and the incoming carry is also a 64-bit word.
theorem schoolbook_muladd_fits_double_word
    (B a b word carry : Int)
    (hB : 0 < B)
    (ha0 : 0 ≤ a) (haB : a < B)
    (hb0 : 0 ≤ b) (hbB : b < B)
    (hw0 : 0 ≤ word) (hwB : word < B)
    (hc0 : 0 ≤ carry) (hcB : carry < B) :
    0 ≤ a*b + word + carry ∧
      a*b + word + carry < B*B := by
  have hmul0 := Int.mul_nonneg ha0 hb0
  have h1 := Int.mul_le_mul_of_nonneg_right
    (by omega : a ≤ B-1) hb0
  have h2 := Int.mul_le_mul_of_nonneg_left
    (by omega : b ≤ B-1) (by omega : 0 ≤ B-1)
  have hpoly : (B-1)*(B-1)+2*(B-1) = B*B-1 := by
    grind +ring
  constructor
  · omega
  · omega

-- Replacing one product-array word by the low 64 bits of the multiply-add
-- preserves its weighted integer value when the high bits are carried into
-- the next position. The bounds supply the next inner-loop carry premise.
theorem schoolbook_word_step
    (B a b word carry : Int) (position : Nat)
    (hB : 0 < B)
    (ha0 : 0 ≤ a) (haB : a < B)
    (hb0 : 0 ≤ b) (hbB : b < B)
    (hw0 : 0 ≤ word) (hwB : word < B)
    (hc0 : 0 ≤ carry) (hcB : carry < B) :
    let sum := a*b + word + carry
    0 ≤ sum % B ∧ sum % B < B ∧
    0 ≤ sum / B ∧ sum / B < B ∧
    (word+a*b+carry)*B^position =
      (sum%B)*B^position + (sum/B)*B^(position+1) := by
  have hfit := schoolbook_muladd_fits_double_word B a b word carry
    hB ha0 haB hb0 hbB hw0 hwB hc0 hcB
  have hdiv := Int.emod_add_ediv_mul (a*b+word+carry) B
  dsimp
  constructor
  · exact Int.emod_nonneg _ (by omega)
  constructor
  · exact Int.emod_lt_of_pos _ hB
  constructor
  · exact Int.ediv_nonneg hfit.1 (by omega)
  constructor
  · exact Int.ediv_lt_of_lt_mul hB hfit.2
  · grind +ring [Int.pow_succ]

def wordValue (B : Int) : List Int → Int
  | [] => 0
  | word::rest => word + B*wordValue B rest

def pairFirstValue (B : Int) : List (Int × Int) → Int
  | [] => 0
  | (word, _)::rest => word + B*pairFirstValue B rest

def pairSecondValue (B : Int) : List (Int × Int) → Int
  | [] => 0
  | (_, coeff)::rest => coeff + B*pairSecondValue B rest

-- This list pass has the same multiply-add, low-word store, and carry update
-- as one inner pass of reciprocal_cell_limbs_from_words_512.
def schoolbookPass (B a : Int) : List (Int × Int) → Int → List Int × Int
  | [], carry => ([], carry)
  | (word, coeff)::rest, carry =>
      let sum := a*coeff + word + carry
      let tail := schoolbookPass B a rest (sum / B)
      ((sum % B)::tail.1, tail.2)

theorem schoolbook_pass_value (B a carry : Int) (xs : List (Int × Int))
    (hB : 0 < B) :
    let out := schoolbookPass B a xs carry
    wordValue B out.1 + out.2*B^xs.length =
      pairFirstValue B xs + a*pairSecondValue B xs + carry := by
  induction xs generalizing carry with
  | nil =>
      simp [schoolbookPass, wordValue, pairFirstValue, pairSecondValue]
  | cons head rest ih =>
      rcases head with ⟨word, coeff⟩
      let sum := a*coeff + word + carry
      have hdiv := Int.emod_add_ediv_mul sum B
      have htail := ih (carry := sum / B)
      dsimp [schoolbookPass, wordValue, pairFirstValue,
        pairSecondValue, sum] at htail ⊢
      grind +ring [Int.pow_succ]

theorem schoolbook_pass_length (B a carry : Int)
    (xs : List (Int × Int)) :
    (schoolbookPass B a xs carry).1.length = xs.length := by
  induction xs generalizing carry with
  | nil => simp [schoolbookPass]
  | cons head rest ih =>
      rcases head with ⟨word, coeff⟩
      simp [schoolbookPass, ih]

def boundedWord (B word : Int) : Prop := 0 ≤ word ∧ word < B

theorem word_value_bounds (B : Int) (xs : List Int)
    (hB : 0 < B)
    (hxs : ∀ word ∈ xs, boundedWord B word) :
    0 ≤ wordValue B xs ∧ wordValue B xs < B^xs.length := by
  induction xs with
  | nil =>
      simp [wordValue]
  | cons word rest ih =>
      have hw := hxs word (by simp)
      have hrest : ∀ w ∈ rest, boundedWord B w := by
        intro w hmem
        exact hxs w (by simp [hmem])
      have ht := ih hrest
      have hmul0 := Int.mul_nonneg (by omega : 0 ≤ B) ht.1
      have hmulLe := Int.mul_le_mul_of_nonneg_left
        (show wordValue B rest ≤ B^rest.length - 1 by omega)
        (by omega : 0 ≤ B)
      have hw0 := hw.1
      have hwB := hw.2
      have hwLe : word ≤ B-1 := by omega
      constructor
      · simpa [wordValue] using (show 0 ≤ word + B*wordValue B rest by omega)
      · simp only [List.length_cons, wordValue]
        have hpoly : (B-1) + B*(B^rest.length-1) =
            B^(rest.length+1)-1 := by
          grind +ring [Int.pow_succ]
        omega

theorem word_values_product_fits (B : Int) (xs ys : List Int)
    (hB : 0 < B)
    (hxs : ∀ word ∈ xs, boundedWord B word)
    (hys : ∀ word ∈ ys, boundedWord B word) :
    0 ≤ wordValue B xs * wordValue B ys ∧
      wordValue B xs * wordValue B ys < B^(xs.length+ys.length) := by
  have hx := word_value_bounds B xs hB hxs
  have hy := word_value_bounds B ys hB hys
  have hp : 0 < B^ys.length := Int.pow_pos hB
  have hupper1 := Int.mul_le_mul_of_nonneg_left
    (show wordValue B ys ≤ B^ys.length by omega) hx.1
  have hupper2 := Int.mul_lt_mul_of_pos_right hx.2 hp
  constructor
  · exact Int.mul_nonneg hx.1 hy.1
  · rw [Int.pow_add]
    omega

theorem four_word_prefix_product_fits (B : Int)
    (scalarWords reciprocal : List Int) (offset : Nat)
    (hB : 1 < B)
    (hscalarLen : scalarWords.length = 4)
    (hrecLen : reciprocal.length = 7)
    (hscalar : ∀ word ∈ scalarWords, boundedWord B word)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word) :
    wordValue B (scalarWords.take offset) * wordValue B reciprocal <
      B^11 := by
  let preWords := scalarWords.take offset
  have hpre : ∀ word ∈ preWords, boundedWord B word := by
    intro word hw
    exact hscalar word (List.mem_of_mem_take hw)
  have hpreLen : preWords.length ≤ 4 := by
    simp [preWords, List.length_take]
    omega
  have hp := word_values_product_fits B preWords reciprocal
    (by omega) hpre hrec
  have hsum : preWords.length + reciprocal.length ≤ 11 := by omega
  change wordValue B preWords * wordValue B reciprocal < B^11
  by_cases heq : preWords.length + reciprocal.length = 11
  · have hpLt := hp.2
    rw [heq] at hpLt
    exact hpLt
  · have hlt : preWords.length + reciprocal.length < 11 := by omega
    have hpow := Int.pow_lt_pow_of_lt hB hlt
    omega

theorem four_scalar_prefix_values (B a0 a1 a2 a3 : Int) :
    let digits := [a0, a1, a2, a3]
    wordValue B (digits.take 1) = a0 ∧
    wordValue B (digits.take 2) = a0 + B*a1 ∧
    wordValue B (digits.take 3) = a0 + B*a1 + B^2*a2 ∧
    wordValue B (digits.take 4) =
      a0 + B*a1 + B^2*a2 + B^3*a3 := by
  dsimp
  simp [wordValue]
  grind +ring

theorem four_scalar_prefix_capacity (B a0 a1 a2 a3 : Int)
    (reciprocal : List Int) (hB : 1 < B)
    (hrecLen : reciprocal.length = 7)
    (ha0 : boundedWord B a0) (ha1 : boundedWord B a1)
    (ha2 : boundedWord B a2) (ha3 : boundedWord B a3)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word) :
    let R := wordValue B reciprocal
    a0*R < B^11 ∧
    (a0+B*a1)*R < B^11 ∧
    (a0+B*a1+B^2*a2)*R < B^11 ∧
    (a0+B*a1+B^2*a2+B^3*a3)*R < B^11 := by
  let digits := [a0, a1, a2, a3]
  have hdigits : ∀ word ∈ digits, boundedWord B word := by
    intro word hw
    simp [digits] at hw
    rcases hw with h | h | h | h
    · subst word; exact ha0
    · subst word; exact ha1
    · subst word; exact ha2
    · subst word; exact ha3
  have hp1 := four_word_prefix_product_fits B digits reciprocal 1 hB
    (by simp [digits]) hrecLen hdigits hrec
  have hp2 := four_word_prefix_product_fits B digits reciprocal 2 hB
    (by simp [digits]) hrecLen hdigits hrec
  have hp3 := four_word_prefix_product_fits B digits reciprocal 3 hB
    (by simp [digits]) hrecLen hdigits hrec
  have hp4 := four_word_prefix_product_fits B digits reciprocal 4 hB
    (by simp [digits]) hrecLen hdigits hrec
  have hv := four_scalar_prefix_values B a0 a1 a2 a3
  dsimp [digits] at hp1 hp2 hp3 hp4
  dsimp at hv ⊢
  grind

theorem schoolbook_pass_bounds (B a carry : Int)
    (xs : List (Int × Int))
    (hB : 0 < B) (ha : boundedWord B a)
    (hc : boundedWord B carry)
    (hxs : ∀ pair ∈ xs,
      boundedWord B pair.1 ∧ boundedWord B pair.2) :
    let out := schoolbookPass B a xs carry
    (∀ word ∈ out.1, boundedWord B word) ∧
      boundedWord B out.2 := by
  induction xs generalizing carry with
  | nil =>
      simp [schoolbookPass, hc]
  | cons head rest ih =>
      rcases head with ⟨word, coeff⟩
      have hhead := hxs (word, coeff) (by simp)
      have hrest : ∀ pair ∈ rest,
          boundedWord B pair.1 ∧ boundedWord B pair.2 := by
        intro pair hp
        exact hxs pair (by simp [hp])
      let sum := a*coeff + word + carry
      have hstep := schoolbook_word_step B a coeff word carry 0
        hB ha.1 ha.2 hhead.2.1 hhead.2.2 hhead.1.1 hhead.1.2
        hc.1 hc.2
      have htail := ih (carry := sum / B)
        ⟨hstep.2.2.1, hstep.2.2.2.1⟩ hrest
      dsimp [schoolbookPass, boundedWord, sum] at hstep htail ⊢
      constructor
      · intro w hw
        rcases List.mem_cons.mp hw with heq | hmem
        · subst w
          exact ⟨hstep.1, hstep.2.1⟩
        · exact htail.1 w hmem
      · exact htail.2

-- Propagate a completed inner pass's carry through the remaining array
-- words. Processing all trailing words is equivalent to the native loop's
-- early stop once the carry reaches zero, proved below.
def carryPass (B : Int) : List Int → Int → List Int × Int
  | [], carry => ([], carry)
  | word::rest, carry =>
      let sum := word + carry
      let tail := carryPass B rest (sum / B)
      ((sum % B)::tail.1, tail.2)

theorem carry_pass_value (B carry : Int) (xs : List Int)
    (hB : 0 < B) :
    let out := carryPass B xs carry
    wordValue B out.1 + out.2*B^xs.length =
      wordValue B xs + carry := by
  induction xs generalizing carry with
  | nil => simp [carryPass, wordValue]
  | cons word rest ih =>
      let sum := word + carry
      have hdiv := Int.emod_add_ediv_mul sum B
      have htail := ih (carry := sum / B)
      dsimp [carryPass, wordValue, sum] at htail ⊢
      grind +ring [Int.pow_succ]

theorem carry_pass_length (B carry : Int) (xs : List Int) :
    (carryPass B xs carry).1.length = xs.length := by
  induction xs generalizing carry with
  | nil => simp [carryPass]
  | cons word rest ih => simp [carryPass, ih]

theorem carry_pass_zero (B : Int) (xs : List Int)
    (hxs : ∀ word ∈ xs, boundedWord B word) :
    carryPass B xs 0 = (xs, 0) := by
  induction xs with
  | nil => simp [carryPass]
  | cons word rest ih =>
      have hw := hxs word (by simp)
      have hrest : ∀ w ∈ rest, boundedWord B w := by
        intro w hmem
        exact hxs w (by simp [hmem])
      have hmod : word % B = word := Int.emod_eq_of_lt hw.1 hw.2
      have hdiv : word / B = 0 := Int.ediv_eq_zero_of_lt hw.1 hw.2
      simp [carryPass, hmod, hdiv, ih hrest]

theorem carry_pass_bounds (B carry : Int) (xs : List Int)
    (hB : 0 < B) (hc : boundedWord B carry)
    (hxs : ∀ word ∈ xs, boundedWord B word) :
    let out := carryPass B xs carry
    (∀ word ∈ out.1, boundedWord B word) ∧
      boundedWord B out.2 := by
  induction xs generalizing carry with
  | nil => simp [carryPass, hc]
  | cons word rest ih =>
      have hw := hxs word (by simp)
      have hrest : ∀ w ∈ rest, boundedWord B w := by
        intro w hmem
        exact hxs w (by simp [hmem])
      let sum := word + carry
      have hstep := schoolbook_word_step B 0 0 word carry 0
        hB (by omega) hB (by omega) hB hw.1 hw.2 hc.1 hc.2
      simp at hstep
      have htail := ih (carry := sum / B)
        ⟨hstep.2.2.1, hstep.2.2.2.1⟩ hrest
      dsimp [carryPass, boundedWord, sum] at hstep htail ⊢
      constructor
      · intro w hmem
        rcases List.mem_cons.mp hmem with heq | hin
        · subst w
          exact ⟨hstep.1, hstep.2.1⟩
        · exact htail.1 w hin
      · exact htail.2

theorem word_value_append (B : Int) (xs ys : List Int) :
    wordValue B (xs ++ ys) =
      wordValue B xs + B^xs.length * wordValue B ys := by
  induction xs with
  | nil => simp [wordValue]
  | cons word rest ih =>
      simp only [List.cons_append, List.length_cons, wordValue]
      rw [ih]
      grind +ring [Int.pow_succ]

theorem eleven_word_product_output (B fraction : Int)
    (low high : List Int)
    (hB : 0 < B) (hLowLen : low.length = 7)
    (hHighLen : high.length = 3)
    (hlow : ∀ word ∈ low, boundedWord B word)
    (hfrac : boundedWord B fraction) :
    let words := low ++ fraction::high
    let P := wordValue B words
    let L := B^7
    words.length = 11 ∧
    (P/L)/B = wordValue B high ∧
    (P/L)%B = fraction ∧ P%L = wordValue B low := by
  have hlowValue := word_value_bounds B low hB hlow
  have hL : 0 < B^7 := Int.pow_pos hB
  have hP : wordValue B (low ++ fraction::high) =
      B^7*(B*wordValue B high+fraction)+wordValue B low := by
    rw [word_value_append, hLowLen]
    simp only [wordValue]
    grind +ring
  have hparts := product_quotient_remainder_from_words
    (wordValue B (low ++ fraction::high)) B (B^7)
    (wordValue B high) fraction (wordValue B low)
    hB hL hP hfrac.1 hfrac.2 hlowValue.1
    (by simpa [hLowLen] using hlowValue.2)
  dsimp
  constructor
  · simp [List.length_append, hLowLen, hHighLen]
  · exact hparts

theorem eleven_word_split (words : List Int)
    (hlen : words.length = 11) :
    ∃ fraction high, high.length = 3 ∧
      words = words.take 7 ++ fraction::high := by
  have htail : (words.drop 7).length = 4 := by
    simp [List.length_drop]
    omega
  cases hdrop : words.drop 7 with
  | nil =>
      simp [hdrop] at htail
  | cons fraction high =>
      have hhigh : high.length = 3 := by
        simp [hdrop] at htail
        omega
      refine ⟨fraction, high, hhigh, ?_⟩
      have hsplit := (List.take_append_drop 7 words).symm
      rw [hdrop] at hsplit
      exact hsplit

theorem eleven_word_output_from_bounded (B : Int) (words : List Int)
    (hB : 0 < B) (hlen : words.length = 11)
    (hwords : ∀ word ∈ words, boundedWord B word) :
    ∃ fraction high, high.length = 3 ∧
      words = words.take 7 ++ fraction::high ∧
      ((wordValue B words / B^7) / B = wordValue B high) ∧
      ((wordValue B words / B^7) % B = fraction) ∧
      wordValue B words % B^7 = wordValue B (words.take 7) := by
  rcases eleven_word_split words hlen with ⟨fraction, high, hhigh, hsplit⟩
  have hlowLen : (words.take 7).length = 7 := by
    simp [List.length_take, hlen]
  have hlow : ∀ word ∈ words.take 7, boundedWord B word := by
    intro word hw
    exact hwords word (List.mem_of_mem_take hw)
  have hfrac : boundedWord B fraction := by
    apply hwords fraction
    rw [hsplit]
    simp
  have hparts := eleven_word_product_output B fraction (words.take 7)
    high hB hlowLen hhigh hlow hfrac
  dsimp at hparts
  rw [← hsplit] at hparts
  exact ⟨fraction, high, hhigh, hsplit, hparts.2.1,
    hparts.2.2.1, hparts.2.2.2⟩

def schoolbookWholePass (B a : Int)
    (xs : List (Int × Int)) (suffix : List Int) : List Int × Int :=
  let inner := schoolbookPass B a xs 0
  let finish := carryPass B suffix inner.2
  (inner.1 ++ finish.1, finish.2)

theorem schoolbook_whole_pass_value (B a : Int)
    (xs : List (Int × Int)) (suffix : List Int)
    (hB : 0 < B) :
    let out := schoolbookWholePass B a xs suffix
    wordValue B out.1 + out.2*B^(xs.length+suffix.length) =
      pairFirstValue B xs + B^xs.length*wordValue B suffix +
        a*pairSecondValue B xs := by
  have hinner := schoolbook_pass_value B a 0 xs hB
  cases hI : schoolbookPass B a xs 0 with
  | mk innerWords innerCarry =>
    have hfinish := carry_pass_value B innerCarry suffix hB
    have hlen := schoolbook_pass_length B a 0 xs
    cases hF : carryPass B suffix innerCarry with
    | mk tailWords finalCarry =>
      simp only [hI, Prod.fst, Prod.snd] at hinner hlen
      simp only [hF, Prod.fst, Prod.snd] at hfinish
      dsimp [schoolbookWholePass]
      simp only [hI, hF, Prod.fst, Prod.snd]
      rw [word_value_append, hlen, Int.pow_add]
      grind +ring

theorem schoolbook_whole_pass_length (B a : Int)
    (xs : List (Int × Int)) (suffix : List Int) :
    (schoolbookWholePass B a xs suffix).1.length =
      xs.length + suffix.length := by
  cases hI : schoolbookPass B a xs 0 with
  | mk innerWords innerCarry =>
    cases hF : carryPass B suffix innerCarry with
    | mk tailWords finalCarry =>
      have hlenInner := schoolbook_pass_length B a 0 xs
      have hlenTail := carry_pass_length B innerCarry suffix
      simp only [hI, Prod.fst] at hlenInner
      simp only [hF, Prod.fst] at hlenTail
      simp [schoolbookWholePass, hI, hF, List.length_append,
        hlenInner, hlenTail]

theorem schoolbook_whole_pass_bounds (B a : Int)
    (xs : List (Int × Int)) (suffix : List Int)
    (hB : 0 < B) (ha : boundedWord B a)
    (hxs : ∀ pair ∈ xs,
      boundedWord B pair.1 ∧ boundedWord B pair.2)
    (hsuffix : ∀ word ∈ suffix, boundedWord B word) :
    let out := schoolbookWholePass B a xs suffix
    (∀ word ∈ out.1, boundedWord B word) ∧
      boundedWord B out.2 := by
  have hinner := schoolbook_pass_bounds B a 0 xs hB ha
    ⟨by omega, hB⟩ hxs
  cases hI : schoolbookPass B a xs 0 with
  | mk innerWords innerCarry =>
    simp only [hI, Prod.fst, Prod.snd] at hinner
    have hfinish := carry_pass_bounds B innerCarry suffix hB
      hinner.2 hsuffix
    cases hF : carryPass B suffix innerCarry with
    | mk tailWords finalCarry =>
      simp only [hF, Prod.fst, Prod.snd] at hfinish
      dsimp [schoolbookWholePass]
      simp only [hI, hF, Prod.fst, Prod.snd]
      constructor
      · intro word hmem
        rcases List.mem_append.mp hmem with hin | htail
        · exact hinner.1 word hin
        · exact hfinish.1 word htail
      · exact hfinish.2

theorem pair_first_value_map (B : Int) (xs : List (Int × Int)) :
    wordValue B (xs.map Prod.fst) = pairFirstValue B xs := by
  induction xs with
  | nil => simp [wordValue, pairFirstValue]
  | cons head rest ih =>
      rcases head with ⟨word, coeff⟩
      simp [wordValue, pairFirstValue, ih]

-- One outer iteration starts at a shifted array offset. Its prefix is
-- unchanged; the inner pass and carry propagation update the suffix.
theorem shifted_schoolbook_pass_value (B a : Int)
    (preWords : List Int) (xs : List (Int × Int))
    (suffix : List Int) (hB : 0 < B) :
    let out := schoolbookWholePass B a xs suffix
    wordValue B (preWords ++ out.1) +
        out.2*B^(preWords.length+xs.length+suffix.length) =
      wordValue B (preWords ++ xs.map Prod.fst ++ suffix) +
        a*B^preWords.length*pairSecondValue B xs := by
  have hwhole := schoolbook_whole_pass_value B a xs suffix hB
  have hlen := schoolbook_whole_pass_length B a xs suffix
  cases hOut : schoolbookWholePass B a xs suffix with
  | mk outWords outCarry =>
    simp only [hOut, Prod.fst, Prod.snd] at hwhole hlen
    dsimp
    rw [word_value_append B preWords outWords]
    rw [List.append_assoc]
    rw [word_value_append B preWords (xs.map Prod.fst ++ suffix)]
    rw [word_value_append B (xs.map Prod.fst) suffix]
    rw [pair_first_value_map]
    simp only [List.length_map]
    grind +ring [Int.pow_add]

-- The native eleven-word array is split at the scalar-word offset.  Zip
-- pairs the next reciprocal-sized segment with the seven fixed reciprocal
-- words; the rest of the array receives the propagated carry.
def schoolbookOuterAt (B a : Int) (words reciprocal : List Int)
    (offset : Nat) : List Int × Int :=
  let preWords := words.take offset
  let segment := (words.drop offset).take reciprocal.length
  let suffix := words.drop (offset + reciprocal.length)
  let out := schoolbookWholePass B a (List.zip segment reciprocal) suffix
  (preWords ++ out.1, out.2)

theorem schoolbook_outer_at_value (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hB : 0 < B)
    (hlen : offset + reciprocal.length ≤ words.length) :
    let out := schoolbookOuterAt B a words reciprocal offset
    wordValue B out.1 + out.2 * B^words.length =
      wordValue B words + a * B^offset * wordValue B reciprocal := by
  let preWords := words.take offset
  let segment := (words.drop offset).take reciprocal.length
  let suffix := words.drop (offset + reciprocal.length)
  let xs := List.zip segment reciprocal
  have hoff : offset ≤ words.length := by omega
  have hseg : segment.length = reciprocal.length := by
    simp [segment, List.length_take, List.length_drop]
    omega
  have hfst : xs.map Prod.fst = segment := by
    simp [xs, List.map_fst_zip, hseg]
  have hsnd : xs.map Prod.snd = reciprocal := by
    simp [xs, List.map_snd_zip, hseg]
  have hxlen : xs.length = reciprocal.length := by
    simp [xs, hseg]
  have hprelen : preWords.length = offset := by
    simp [preWords, List.length_take, Nat.min_eq_left hoff]
  have htail : words.drop offset = segment ++ suffix := by
    calc
      words.drop offset =
          (words.drop offset).take reciprocal.length ++
            (words.drop offset).drop reciprocal.length :=
        (List.take_append_drop reciprocal.length (words.drop offset)).symm
      _ = segment ++ suffix := by
        simp [segment, suffix, List.drop_drop, Nat.add_comm]
  have hsplit : words = preWords ++ segment ++ suffix := by
    calc
      words = words.take offset ++ words.drop offset :=
        (List.take_append_drop offset words).symm
      _ = preWords ++ segment ++ suffix := by
        rw [htail]
        simp [preWords, List.append_assoc]
  have hlen : words.length = preWords.length + xs.length + suffix.length := by
    rw [hsplit]
    simp [hxlen, hseg]
    omega
  have hcoeff : pairSecondValue B xs = wordValue B reciprocal := by
    rw [← hsnd]
    induction xs with
    | nil => simp [pairSecondValue, wordValue]
    | cons head rest ih =>
        rcases head with ⟨word, coeff⟩
        simp [pairSecondValue, wordValue, ih]
  have hstep := shifted_schoolbook_pass_value B a preWords xs suffix hB
  dsimp [schoolbookOuterAt, preWords, segment, suffix, xs]
  rw [← hlen, hfst, ← hsplit, hprelen, hcoeff] at hstep
  exact hstep

theorem schoolbook_outer_at_length (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hlen : offset + reciprocal.length ≤ words.length) :
    (schoolbookOuterAt B a words reciprocal offset).1.length =
      words.length := by
  let preWords := words.take offset
  let segment := (words.drop offset).take reciprocal.length
  let suffix := words.drop (offset + reciprocal.length)
  let xs := List.zip segment reciprocal
  have hseg : segment.length = reciprocal.length := by
    simp [segment, List.length_take, List.length_drop]
    omega
  have hpass := schoolbook_whole_pass_length B a xs suffix
  dsimp [schoolbookOuterAt]
  simp [preWords, segment, suffix, xs, hpass, hseg,
    List.length_take, List.length_drop]
  omega

theorem schoolbook_outer_at_bounds (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hB : 0 < B) (ha : boundedWord B a)
    (hwords : ∀ word ∈ words, boundedWord B word)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word) :
    let out := schoolbookOuterAt B a words reciprocal offset
    (∀ word ∈ out.1, boundedWord B word) ∧ boundedWord B out.2 := by
  let preWords := words.take offset
  let segment := (words.drop offset).take reciprocal.length
  let suffix := words.drop (offset + reciprocal.length)
  let xs := List.zip segment reciprocal
  have hpre : ∀ w ∈ preWords, boundedWord B w := by
    intro w hw
    exact hwords w (List.mem_of_mem_take hw)
  have hsegment : ∀ w ∈ segment, boundedWord B w := by
    intro w hw
    exact hwords w (List.mem_of_mem_drop (List.mem_of_mem_take hw))
  have hsuffix : ∀ w ∈ suffix, boundedWord B w := by
    intro w hw
    exact hwords w (List.mem_of_mem_drop hw)
  have hxs : ∀ pair ∈ xs,
      boundedWord B pair.1 ∧ boundedWord B pair.2 := by
    intro pair hp
    rcases pair with ⟨w, c⟩
    have hmem := List.of_mem_zip hp
    exact ⟨hsegment w hmem.1, hrec c hmem.2⟩
  have hpass := schoolbook_whole_pass_bounds B a xs suffix hB ha hxs hsuffix
  dsimp [schoolbookOuterAt, preWords, segment, suffix, xs]
  constructor
  · intro w hw
    rcases List.mem_append.mp hw with hp | ho
    · exact hpre w hp
    · exact hpass.1 w ho
  · exact hpass.2

theorem schoolbook_outer_at_no_carry (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hB : 0 < B)
    (hlen : offset + reciprocal.length ≤ words.length)
    (hcarry : (schoolbookOuterAt B a words reciprocal offset).2 = 0) :
    wordValue B (schoolbookOuterAt B a words reciprocal offset).1 =
      wordValue B words + a * B^offset * wordValue B reciprocal := by
  have h := schoolbook_outer_at_value B a words reciprocal offset hB hlen
  dsimp at h
  rw [hcarry] at h
  simpa using h

theorem schoolbook_outer_at_zero_carry_of_capacity (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hB : 0 < B)
    (hlen : offset + reciprocal.length ≤ words.length)
    (hword : 0 ≤ wordValue B
      (schoolbookOuterAt B a words reciprocal offset).1)
    (hcarry : 0 ≤ (schoolbookOuterAt B a words reciprocal offset).2)
    (hcapacity : wordValue B words +
      a * B^offset * wordValue B reciprocal < B^words.length) :
    (schoolbookOuterAt B a words reciprocal offset).2 = 0 := by
  have hpow : 0 < B^words.length := Int.pow_pos hB
  have hvalue := schoolbook_outer_at_value B a words reciprocal offset hB hlen
  dsimp at hvalue
  by_cases hzero : (schoolbookOuterAt B a words reciprocal offset).2 = 0
  · exact hzero
  · have hpositive : 1 ≤
        (schoolbookOuterAt B a words reciprocal offset).2 := by omega
    have hmul := Int.mul_le_mul_of_nonneg_right hpositive
      (by omega : 0 ≤ B^words.length)
    omega

theorem schoolbook_outer_at_no_overflow (B a : Int)
    (words reciprocal : List Int) (offset : Nat)
    (hB : 0 < B) (ha : boundedWord B a)
    (hwords : ∀ word ∈ words, boundedWord B word)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word)
    (hlen : offset + reciprocal.length ≤ words.length)
    (hcapacity : wordValue B words +
      a * B^offset * wordValue B reciprocal < B^words.length) :
    (schoolbookOuterAt B a words reciprocal offset).2 = 0 := by
  have hb := schoolbook_outer_at_bounds B a words reciprocal offset
    hB ha hwords hrec
  have hv := word_value_bounds B
    (schoolbookOuterAt B a words reciprocal offset).1 hB hb.1
  exact schoolbook_outer_at_zero_carry_of_capacity B a words reciprocal
    offset hB hlen hv.1 hb.2.1 hcapacity

theorem word_value_replicate_zero (B : Int) (n : Nat) :
    wordValue B (List.replicate n 0) = 0 := by
  induction n with
  | zero => simp [wordValue]
  | succ n ih => simp [List.replicate, wordValue, ih]

-- Four native scalar words, at offsets 0, 1, 2, and 3, compose into the
-- exact product as soon as each pass is shown to stay within eleven words.
theorem four_scalar_word_product (B a0 a1 a2 a3 : Int)
    (reciprocal : List Int) (hB : 0 < B)
    (hrec : reciprocal.length = 7) :
    let z := List.replicate 11 (0 : Int)
    let p0 := schoolbookOuterAt B a0 z reciprocal 0
    let p1 := schoolbookOuterAt B a1 p0.1 reciprocal 1
    let p2 := schoolbookOuterAt B a2 p1.1 reciprocal 2
    let p3 := schoolbookOuterAt B a3 p2.1 reciprocal 3
    p0.2 = 0 → p1.2 = 0 → p2.2 = 0 → p3.2 = 0 →
    wordValue B p3.1 =
      (a0 + B*a1 + B^2*a2 + B^3*a3) * wordValue B reciprocal := by
  intro z p0 p1 p2 p3 hc0 hc1 hc2 hc3
  have hz : z.length = 11 := by simp [z]
  have hp0 : p0.1.length = 11 := by
    rw [show p0 = schoolbookOuterAt B a0 z reciprocal 0 from rfl]
    rw [schoolbook_outer_at_length B a0 z reciprocal 0 (by omega)]
    exact hz
  have hp1 : p1.1.length = 11 := by
    rw [show p1 = schoolbookOuterAt B a1 p0.1 reciprocal 1 from rfl]
    rw [schoolbook_outer_at_length B a1 p0.1 reciprocal 1 (by omega)]
    exact hp0
  have hp2 : p2.1.length = 11 := by
    rw [show p2 = schoolbookOuterAt B a2 p1.1 reciprocal 2 from rfl]
    rw [schoolbook_outer_at_length B a2 p1.1 reciprocal 2 (by omega)]
    exact hp1
  have he0 := schoolbook_outer_at_no_carry B a0 z reciprocal 0 hB
    (by omega) hc0
  have he1 := schoolbook_outer_at_no_carry B a1 p0.1 reciprocal 1 hB
    (by omega) hc1
  have he2 := schoolbook_outer_at_no_carry B a2 p1.1 reciprocal 2 hB
    (by omega) hc2
  have he3 := schoolbook_outer_at_no_carry B a3 p2.1 reciprocal 3 hB
    (by omega) hc3
  change wordValue B p0.1 = _ at he0
  change wordValue B p1.1 = _ at he1
  change wordValue B p2.1 = _ at he2
  change wordValue B p3.1 = _ at he3
  rw [he3, he2, he1, he0]
  simp [z, wordValue] <;> grind +ring

theorem four_scalar_word_product_bounded (B a0 a1 a2 a3 : Int)
    (reciprocal : List Int) (hB : 1 < B)
    (hrecLen : reciprocal.length = 7)
    (ha0 : boundedWord B a0) (ha1 : boundedWord B a1)
    (ha2 : boundedWord B a2) (ha3 : boundedWord B a3)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word) :
    let z := List.replicate 11 (0 : Int)
    let p0 := schoolbookOuterAt B a0 z reciprocal 0
    let p1 := schoolbookOuterAt B a1 p0.1 reciprocal 1
    let p2 := schoolbookOuterAt B a2 p1.1 reciprocal 2
    let p3 := schoolbookOuterAt B a3 p2.1 reciprocal 3
    p0.2 = 0 ∧ p1.2 = 0 ∧ p2.2 = 0 ∧ p3.2 = 0 ∧
    wordValue B p3.1 =
      (a0+B*a1+B^2*a2+B^3*a3)*wordValue B reciprocal := by
  intro z p0 p1 p2 p3
  have hB0 : 0 < B := by omega
  have hzlen : z.length = 11 := by simp [z]
  have hzval : wordValue B z = 0 := word_value_replicate_zero B 11
  have hzwords : ∀ word ∈ z, boundedWord B word := by
    intro word hw
    have hzero : word = 0 := by simpa [z] using hw
    subst word
    exact ⟨by omega, hB0⟩
  have hcaps := four_scalar_prefix_capacity B a0 a1 a2 a3 reciprocal
    hB hrecLen ha0 ha1 ha2 ha3 hrec
  rcases hcaps with ⟨hcap0, hcap1, hcap2, hcap3⟩
  have hc0 : p0.2 = 0 := by
    apply schoolbook_outer_at_no_overflow B a0 z reciprocal 0
      hB0 ha0 hzwords hrec (by omega)
    rw [hzval, hzlen]
    simpa using hcap0
  have hb0 := schoolbook_outer_at_bounds B a0 z reciprocal 0
    hB0 ha0 hzwords hrec
  have hp0len : p0.1.length = 11 := by
    rw [show p0 = schoolbookOuterAt B a0 z reciprocal 0 from rfl]
    rw [schoolbook_outer_at_length B a0 z reciprocal 0 (by omega)]
    exact hzlen
  have he0 := schoolbook_outer_at_no_carry B a0 z reciprocal 0
    hB0 (by omega) hc0
  have hp0val : wordValue B p0.1 = a0*wordValue B reciprocal := by
    change wordValue B p0.1 = _ at he0
    rw [hzval] at he0
    simpa using he0
  have hc1 : p1.2 = 0 := by
    apply schoolbook_outer_at_no_overflow B a1 p0.1 reciprocal 1
      hB0 ha1 hb0.1 hrec (by omega)
    rw [hp0val, hp0len]
    grind +ring
  have hb1 := schoolbook_outer_at_bounds B a1 p0.1 reciprocal 1
    hB0 ha1 hb0.1 hrec
  have hp1len : p1.1.length = 11 := by
    rw [show p1 = schoolbookOuterAt B a1 p0.1 reciprocal 1 from rfl]
    rw [schoolbook_outer_at_length B a1 p0.1 reciprocal 1 (by omega)]
    exact hp0len
  have he1 := schoolbook_outer_at_no_carry B a1 p0.1 reciprocal 1
    hB0 (by omega) hc1
  have hp1val : wordValue B p1.1 =
      (a0+B*a1)*wordValue B reciprocal := by
    change wordValue B p1.1 = _ at he1
    rw [hp0val] at he1
    grind +ring
  have hc2 : p2.2 = 0 := by
    apply schoolbook_outer_at_no_overflow B a2 p1.1 reciprocal 2
      hB0 ha2 hb1.1 hrec (by omega)
    rw [hp1val, hp1len]
    grind +ring
  have hb2 := schoolbook_outer_at_bounds B a2 p1.1 reciprocal 2
    hB0 ha2 hb1.1 hrec
  have hp2len : p2.1.length = 11 := by
    rw [show p2 = schoolbookOuterAt B a2 p1.1 reciprocal 2 from rfl]
    rw [schoolbook_outer_at_length B a2 p1.1 reciprocal 2 (by omega)]
    exact hp1len
  have he2 := schoolbook_outer_at_no_carry B a2 p1.1 reciprocal 2
    hB0 (by omega) hc2
  have hp2val : wordValue B p2.1 =
      (a0+B*a1+B^2*a2)*wordValue B reciprocal := by
    change wordValue B p2.1 = _ at he2
    rw [hp1val] at he2
    grind +ring
  have hc3 : p3.2 = 0 := by
    apply schoolbook_outer_at_no_overflow B a3 p2.1 reciprocal 3
      hB0 ha3 hb2.1 hrec (by omega)
    rw [hp2val, hp2len]
    grind +ring
  have hproduct := four_scalar_word_product B a0 a1 a2 a3
    reciprocal hB0 hrecLen hc0 hc1 hc2 hc3
  exact ⟨hc0, hc1, hc2, hc3, hproduct⟩

theorem four_scalar_word_output_bounded (B a0 a1 a2 a3 : Int)
    (reciprocal : List Int) (hB : 1 < B)
    (hrecLen : reciprocal.length = 7)
    (ha0 : boundedWord B a0) (ha1 : boundedWord B a1)
    (ha2 : boundedWord B a2) (ha3 : boundedWord B a3)
    (hrec : ∀ word ∈ reciprocal, boundedWord B word) :
    let z := List.replicate 11 (0 : Int)
    let p0 := schoolbookOuterAt B a0 z reciprocal 0
    let p1 := schoolbookOuterAt B a1 p0.1 reciprocal 1
    let p2 := schoolbookOuterAt B a2 p1.1 reciprocal 2
    let p3 := schoolbookOuterAt B a3 p2.1 reciprocal 3
    let P := (a0+B*a1+B^2*a2+B^3*a3)*wordValue B reciprocal
    ∃ fraction high, high.length = 3 ∧
      p3.2 = 0 ∧ p3.1 = p3.1.take 7 ++ fraction::high ∧
      (P / B^7) / B = wordValue B high ∧
      (P / B^7) % B = fraction ∧
      P % B^7 = wordValue B (p3.1.take 7) := by
  intro z p0 p1 p2 p3 P
  have hB0 : 0 < B := by omega
  have hzlen : z.length = 11 := by simp [z]
  have hzwords : ∀ word ∈ z, boundedWord B word := by
    intro word hw
    have hzero : word = 0 := by simpa [z] using hw
    subst word
    exact ⟨by omega, hB0⟩
  have hb0 := schoolbook_outer_at_bounds B a0 z reciprocal 0
    hB0 ha0 hzwords hrec
  have hp0len : p0.1.length = 11 := by
    rw [show p0 = schoolbookOuterAt B a0 z reciprocal 0 from rfl]
    rw [schoolbook_outer_at_length B a0 z reciprocal 0 (by omega)]
    exact hzlen
  have hb1 := schoolbook_outer_at_bounds B a1 p0.1 reciprocal 1
    hB0 ha1 hb0.1 hrec
  have hp1len : p1.1.length = 11 := by
    rw [show p1 = schoolbookOuterAt B a1 p0.1 reciprocal 1 from rfl]
    rw [schoolbook_outer_at_length B a1 p0.1 reciprocal 1 (by omega)]
    exact hp0len
  have hb2 := schoolbook_outer_at_bounds B a2 p1.1 reciprocal 2
    hB0 ha2 hb1.1 hrec
  have hp2len : p2.1.length = 11 := by
    rw [show p2 = schoolbookOuterAt B a2 p1.1 reciprocal 2 from rfl]
    rw [schoolbook_outer_at_length B a2 p1.1 reciprocal 2 (by omega)]
    exact hp1len
  have hb3 := schoolbook_outer_at_bounds B a3 p2.1 reciprocal 3
    hB0 ha3 hb2.1 hrec
  have hp3len : p3.1.length = 11 := by
    rw [show p3 = schoolbookOuterAt B a3 p2.1 reciprocal 3 from rfl]
    rw [schoolbook_outer_at_length B a3 p2.1 reciprocal 3 (by omega)]
    exact hp2len
  have hproduct := four_scalar_word_product_bounded B a0 a1 a2 a3
    reciprocal hB hrecLen ha0 ha1 ha2 ha3 hrec
  have hparts := eleven_word_output_from_bounded B p3.1 hB0 hp3len hb3.1
  rcases hparts with ⟨fraction, high, hhigh, hsplit, hq, hf, hlow⟩
  have hval : wordValue B p3.1 = P := hproduct.2.2.2.2
  rw [hval] at hq hf hlow
  exact ⟨fraction, high, hhigh, hproduct.2.2.2.1,
    hsplit, hq, hf, hlow⟩

-- A floor reciprocal R, its exact product limbs, and k smaller than one
-- fractional limb imply a two-unit enclosure of the true scaled coordinate.
-- Here B = 2^64 and L = 2^448 in the native 512-bit product.
theorem reciprocal_high_fraction_interval
    (n k c R q h low B L : Int)
    (hn : 0 < n) (hk : 0 ≤ k) (hkL : k < L)
    (hB : 0 < B) (hL : 0 < L)
    (hrecLo : n*R ≤ (B*L)*c)
    (hrecHi : (B*L)*c < n*(R+1))
    (hproduct : k*R = (B*L)*q + L*h + low)
    (hlow : 0 ≤ low) (hlowL : low < L) :
    n*(B*q+h) ≤ B*k*c ∧ B*k*c < n*(B*q+h+2) := by
  have hrecHiLe : (B*L)*c ≤ n*(R+1) := by omega
  have hpLo := Int.mul_le_mul_of_nonneg_left hrecLo hk
  have hpHi := Int.mul_le_mul_of_nonneg_left hrecHiLe hk
  have hpLo' : n*(k*R) ≤ (B*L)*(k*c) := by
    calc
      n*(k*R) = k*(n*R) := by grind +ring
      _ ≤ k*((B*L)*c) := hpLo
      _ = (B*L)*(k*c) := by grind +ring
  have hpHi' : (B*L)*(k*c) ≤ n*(k*R+k) := by
    calc
      (B*L)*(k*c) = k*((B*L)*c) := by grind +ring
      _ ≤ k*(n*(R+1)) := hpHi
      _ = n*(k*R+k) := by grind +ring
  have hscaledLo : L*(n*(B*q+h)) ≤ L*(B*k*c) := by
    have hlowExtra : n*((B*L)*q+L*h) ≤
        n*((B*L)*q+L*h+low) := by
      exact Int.mul_le_mul_of_nonneg_left (by omega) (by omega)
    calc
      L*(n*(B*q+h)) = n*((B*L)*q+L*h) := by grind +ring
      _ ≤ n*((B*L)*q+L*h+low) := hlowExtra
      _ = n*(k*R) := by rw [hproduct]
      _ ≤ (B*L)*(k*c) := hpLo'
      _ = L*(B*k*c) := by grind +ring
  have hsum : low+k < 2*L := by omega
  have hscaledHi : L*(B*k*c) < L*(n*(B*q+h+2)) := by
    have hhiExtra : n*((B*L)*q+L*h+low+k) <
        n*((B*L)*q+L*h+2*L) := by
      exact Int.mul_lt_mul_of_pos_left (by omega) hn
    calc
      L*(B*k*c) = (B*L)*(k*c) := by grind +ring
      _ ≤ n*(k*R+k) := hpHi'
      _ = n*((B*L)*q+L*h+low+k) := by rw [hproduct]
      _ < n*((B*L)*q+L*h+2*L) := hhiExtra
      _ = L*(n*(B*q+h+2)) := by grind +ring
  constructor
  · exact Int.le_of_mul_le_mul_left hscaledLo hL
  · exact Int.lt_of_mul_lt_mul_left hscaledHi (by omega)

-- The native classifier uses the high 64-bit fraction limbs. These are
-- exactly its score intervals after allowing two units of coordinate error.
theorem fraction_limb_score_intervals (n hw hv x y : Int)
    (hx0 : hw*n ≤ x) (hx2 : x ≤ (hw+2)*n)
    (hy0 : hv*n ≤ y) (hy2 : y ≤ (hv+2)*n) :
    let a10 := fractionBase - 2*hw + hv
    let a01 := fractionBase + hw - 2*hv
    let a11 := fractionBase - hw - hv
    n*(a10-4) ≤ fractionBase*n - 2*x + y ∧
      fractionBase*n - 2*x + y ≤ n*(a10+2) ∧
    n*(a01-4) ≤ fractionBase*n + x - 2*y ∧
      fractionBase*n + x - 2*y ≤ n*(a01+2) ∧
    n*(a11-4) ≤ fractionBase*n - x - y ∧
      fractionBase*n - x - y ≤ n*a11 := by
  have hx2' : x ≤ hw*n + 2*n := by
    have h : (hw+2)*n = hw*n+2*n := by grind +ring
    rw [h] at hx2
    exact hx2
  have hy2' : y ≤ hv*n + 2*n := by
    have h : (hv+2)*n = hv*n+2*n := by grind +ring
    rw [h] at hy2
    exact hy2
  dsimp
  constructor
  · have h : n*(fractionBase-2*hw+hv-4) =
        fractionBase*n - 2*(hw*n) + hv*n - 4*n := by grind +ring
    rw [h]
    omega
  constructor
  · have h : n*(fractionBase-2*hw+hv+2) =
        fractionBase*n - 2*(hw*n) + hv*n + 2*n := by grind +ring
    rw [h]
    omega
  constructor
  · have h : n*(fractionBase+hw-2*hv-4) =
        fractionBase*n + hw*n - 2*(hv*n) - 4*n := by grind +ring
    rw [h]
    omega
  constructor
  · have h : n*(fractionBase+hw-2*hv+2) =
        fractionBase*n + hw*n - 2*(hv*n) + 2*n := by grind +ring
    rw [h]
    omega
  constructor
  · have h : n*(fractionBase-hw-hv-4) =
        fractionBase*n - hw*n - hv*n - 4*n := by grind +ring
    rw [h]
    omega
  · have h : n*(fractionBase-hw-hv) =
        fractionBase*n - hw*n - hv*n := by grind +ring
    rw [h]
    omega

theorem strictly_separated_interval_certifies_minimum
    (n : Int) (score lo hi : Fin 4 → Int) (winner : Fin 4)
    (hn : 0 < n)
    (hlo : ∀ i, n*lo i ≤ score i)
    (hhi : ∀ i, score i ≤ n*hi i)
    (hsep : ∀ j, j ≠ winner → hi winner < lo j) :
    ∀ j, score winner ≤ score j := by
  intro j
  by_cases heq : j = winner
  · subst j
    omega
  · have hlt := Int.mul_lt_mul_of_pos_left (hsep j heq) hn
    have hw := hhi winner
    have hj := hlo j
    omega

-- These are the four exact intervals tested by the native fractional-limb
-- classifier, including its asymmetric upper bound for the (1,1) corner.
def fractionCornerLower (hw hv : Int) (corner : Fin 4) : Int :=
  match corner.val with
  | 0 => 0
  | 1 => fractionBase - 2*hw + hv - 4
  | 2 => fractionBase + hw - 2*hv - 4
  | _ => fractionBase - hw - hv - 4

def fractionCornerUpper (hw hv : Int) (corner : Fin 4) : Int :=
  match corner.val with
  | 0 => 0
  | 1 => fractionBase - 2*hw + hv + 2
  | 2 => fractionBase + hw - 2*hv + 2
  | _ => fractionBase - hw - hv

-- A native strict-separation success identifies an actual minimum of the
-- four exact norm scores; the rejected/tie path has a separate exact fallback.
theorem fraction_corner_certificate (n hw hv x y : Int) (winner : Fin 4)
    (hn : 0 < n)
    (hx0 : hw*n ≤ x) (hx2 : x ≤ (hw+2)*n)
    (hy0 : hv*n ≤ y) (hy2 : y ≤ (hv+2)*n)
    (hsep : ∀ j : Fin 4, j ≠ winner →
      fractionCornerUpper hw hv winner < fractionCornerLower hw hv j) :
    ∀ j : Fin 4, cornerScore x y (fractionBase*n) winner.val ≤
      cornerScore x y (fractionBase*n) j.val := by
  have h := fraction_limb_score_intervals n hw hv x y hx0 hx2 hy0 hy2
  dsimp at h
  rcases h with ⟨h10lo, h10hi, h01lo, h01hi, h11lo, h11hi⟩
  have hlo : ∀ i : Fin 4,
      n * fractionCornerLower hw hv i ≤ cornerScore x y (fractionBase*n) i.val := by
    intro ⟨i, hi⟩
    have hcases : i = 0 ∨ i = 1 ∨ i = 2 ∨ i = 3 := by omega
    rcases hcases with h0 | h1 | h2 | h3
    · subst i; simp [fractionCornerLower, cornerScore]
    · subst i; simpa [fractionCornerLower, cornerScore] using h10lo
    · subst i; simpa [fractionCornerLower, cornerScore] using h01lo
    · subst i; simpa [fractionCornerLower, cornerScore] using h11lo
  have hhi : ∀ i : Fin 4,
      cornerScore x y (fractionBase*n) i.val ≤ n * fractionCornerUpper hw hv i := by
    intro ⟨i, hi⟩
    have hcases : i = 0 ∨ i = 1 ∨ i = 2 ∨ i = 3 := by omega
    rcases hcases with h0 | h1 | h2 | h3
    · subst i; simp [fractionCornerUpper, cornerScore]
    · subst i; simpa [fractionCornerUpper, cornerScore] using h10hi
    · subst i; simpa [fractionCornerUpper, cornerScore] using h01hi
    · subst i; simpa [fractionCornerUpper, cornerScore] using h11hi
  exact strictly_separated_interval_certifies_minimum n
    (fun i => cornerScore x y (fractionBase*n) i.val)
    (fractionCornerLower hw hv) (fractionCornerUpper hw hv)
    winner hn hlo hhi hsep

-- The certified branch therefore lands in the six Voronoi support strips
-- required by the terminal digit bound, for the complete normalized cell.
theorem fraction_corner_certified_hex_strips
    (n hw hv x y : Int) (winner : Fin 4)
    (hn : 0 < n)
    (hx : 0 ≤ x ∧ x ≤ fractionBase*n)
    (hy : 0 ≤ y ∧ y ≤ fractionBase*n)
    (hx0 : hw*n ≤ x) (hx2 : x ≤ (hw+2)*n)
    (hy0 : hv*n ≤ y) (hy2 : y ≤ (hv+2)*n)
    (hsep : ∀ j : Fin 4, j ≠ winner →
      fractionCornerUpper hw hv winner < fractionCornerLower hw hv j) :
    let d := fractionBase*n;
    let z := cornerResidual x y d winner.val;
    -d ≤ 2*z.1-z.2 ∧ 2*z.1-z.2 ≤ d ∧
    -d ≤ 2*z.2-z.1 ∧ 2*z.2-z.1 ≤ d ∧
    -d ≤ z.1+z.2 ∧ z.1+z.2 ≤ d := by
  have hmin := fraction_corner_certificate n hw hv x y winner
    hn hx0 hx2 hy0 hy2 hsep
  have hmin' : ∀ j < 4,
      cornerScore x y (fractionBase*n) winner.val ≤
        cornerScore x y (fractionBase*n) j := by
    intro j hj
    exact hmin ⟨j, hj⟩
  exact four_corner_minimum_has_hex_strips x y (fractionBase*n) winner.val
    hx.1 hx.2 hy.1 hy.2 winner.isLt hmin'

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

theorem equilateral_basis_determinant :
    basisW.1*basisV.2 - basisW.2*basisV.1 = subgroupOrder := by decide

-- Cramer's rule for the two floor quotients, stated independently of any
-- particular reciprocal implementation or scalar-range assumption.
theorem floor_cell_scaled_generic (w v : Pair) (n k qw qv : Int)
    (hdet : w.1*v.2 - w.2*v.1 = n) :
    scale n (k-qw*w.1-qv*v.1, -qw*w.2-qv*v.2) =
      add (scale (k*v.2-qw*n) w) (scale (-k*w.2-qv*n) v) := by
  rcases w with ⟨w0,w1⟩
  rcases v with ⟨v0,v1⟩
  simp [scale, add] at *
  constructor <;> grind +ring

def floorCellCoordinates (k qw qv : Int) : Pair :=
  (k*basisV.2 - qw*subgroupOrder,
   -k*basisW.2 - qv*subgroupOrder)

def floorRepresentative (k qw qv : Int) : Pair :=
  (k-qw*basisW.1-qv*basisV.1,
   -qw*basisW.2-qv*basisV.2)

theorem floor_representative_scaled_coordinates (k qw qv : Int) :
    scale subgroupOrder (floorRepresentative k qw qv) =
      add (scale (floorCellCoordinates k qw qv).1 basisW)
          (scale (floorCellCoordinates k qw qv).2 basisV) := by
  exact floor_cell_scaled_generic basisW basisV subgroupOrder k qw qv
    equilateral_basis_determinant

def exactFloorW (k : Int) : Int := k*basisV.2 / subgroupOrder
def exactFloorV (k : Int) : Int := -k*basisW.2 / subgroupOrder

theorem exact_floor_remainder_bounds (n a : Int) (hn : 0 < n) :
    0 ≤ a - (a/n)*n ∧ a - (a/n)*n < n := by
  have hrem : a - (a/n)*n = a % n := by
    rw [Int.emod_def]
    grind +ring
  rw [hrem]
  exact ⟨Int.emod_nonneg a (by omega), Int.emod_lt_of_pos a hn⟩

theorem exact_floor_cell_bounds (k : Int) :
    0 ≤ (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1 ∧
      (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1 < subgroupOrder ∧
    0 ≤ (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2 ∧
      (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2 < subgroupOrder := by
  have hn : 0 < subgroupOrder := by decide
  have hw := exact_floor_remainder_bounds subgroupOrder (k*basisV.2) hn
  have hv := exact_floor_remainder_bounds subgroupOrder (-k*basisW.2) hn
  dsimp [floorCellCoordinates, exactFloorW, exactFloorV] at *
  omega

def cornerOffsetW : Nat → Int
  | 1 | 3 => 1
  | _ => 0

def cornerOffsetV : Nat → Int
  | 2 | 3 => 1
  | _ => 0

def cornerRepresentative (k qw qv : Int) (corner : Nat) : Pair :=
  floorRepresentative k (qw + cornerOffsetW corner) (qv + cornerOffsetV corner)

theorem corner_residual_floor_coordinates (k qw qv : Int) (corner : Nat)
    (hc : corner < 4) :
    cornerResidual (floorCellCoordinates k qw qv).1
        (floorCellCoordinates k qw qv).2 subgroupOrder corner =
      floorCellCoordinates k (qw + cornerOffsetW corner)
        (qv + cornerOffsetV corner) := by
  have hcases : corner = 0 ∨ corner = 1 ∨ corner = 2 ∨ corner = 3 := by omega
  rcases hcases with h | h | h | h
  all_goals
    subst corner
    simp [cornerResidual, floorCellCoordinates, cornerOffsetW, cornerOffsetV]
  all_goals grind +ring

theorem corner_representative_scaled_coordinates (k qw qv : Int) (corner : Nat)
    (hc : corner < 4) :
    scale subgroupOrder (cornerRepresentative k qw qv corner) =
      add (scale (cornerResidual (floorCellCoordinates k qw qv).1
          (floorCellCoordinates k qw qv).2 subgroupOrder corner).1 basisW)
          (scale (cornerResidual (floorCellCoordinates k qw qv).1
          (floorCellCoordinates k qw qv).2 subgroupOrder corner).2 basisV) := by
  have h := floor_representative_scaled_coordinates k
    (qw + cornerOffsetW corner) (qv + cornerOffsetV corner)
  rw [← corner_residual_floor_coordinates k qw qv corner hc] at h
  exact h

theorem equilateral_basis_inner_values :
    twiceInner basisW basisW = 2*subgroupOrder ∧
    twiceInner basisV basisW = -subgroupOrder ∧
    twiceInner basisW basisV = -subgroupOrder ∧
    twiceInner basisV basisV = 2*subgroupOrder := by decide

theorem inner_second_add (z w v : Pair) :
    twiceInner z (add w v) = twiceInner z w + twiceInner z v := by
  rcases z with ⟨a,b⟩
  rcases w with ⟨c,d⟩
  rcases v with ⟨e,f⟩
  simp [twiceInner, add]
  grind +ring

-- The four-corner norm minimum becomes the actual six-neighbor condition
-- once the native floor quotients establish the scaled lattice coordinates.
theorem four_corner_minimum_six_neighbors
    (start : Pair) (x y : Int) (corner : Nat)
    (hx : 0 ≤ x ∧ x ≤ subgroupOrder)
    (hy : 0 ≤ y ∧ y ≤ subgroupOrder)
    (hc : corner < 4)
    (hmin : ∀ j < 4,
      cornerScore x y subgroupOrder corner ≤ cornerScore x y subgroupOrder j)
    (hscaled :
      scale subgroupOrder start =
        add (scale (cornerResidual x y subgroupOrder corner).1 basisW)
            (scale (cornerResidual x y subgroupOrder corner).2 basisV)) :
    sixNeighborsClosest start := by
  let z := cornerResidual x y subgroupOrder corner
  have hz := four_corner_minimum_has_hex_strips x y subgroupOrder corner
    hx.1 hx.2 hy.1 hy.2 hc hmin
  dsimp at hz
  have hb := equilateral_basis_inner_values
  have hW := congrArg (fun p : Pair => twiceInner p basisW) hscaled
  have hV := congrArg (fun p : Pair => twiceInner p basisV) hscaled
  simp only [inner_scale, inner_add, hb.1, hb.2.1] at hW
  simp only [inner_scale, inner_add, hb.2.2.1, hb.2.2.2] at hV
  have hW' : twiceInner start basisW = 2*z.1-z.2 := by
    have heq : subgroupOrder * twiceInner start basisW =
        subgroupOrder * (2*z.1-z.2) := by
      calc
        _ = (cornerResidual x y subgroupOrder corner).1 * (2*subgroupOrder) +
              (cornerResidual x y subgroupOrder corner).2 * -subgroupOrder := hW
        _ = subgroupOrder * (2*z.1-z.2) := by dsimp [z]; grind +ring
    dsimp [subgroupOrder] at heq ⊢
    omega
  have hV' : twiceInner start basisV = 2*z.2-z.1 := by
    have heq : subgroupOrder * twiceInner start basisV =
        subgroupOrder * (2*z.2-z.1) := by
      calc
        _ = (cornerResidual x y subgroupOrder corner).1 * -subgroupOrder +
              (cornerResidual x y subgroupOrder corner).2 * (2*subgroupOrder) := hV
        _ = subgroupOrder * (2*z.2-z.1) := by dsimp [z]; grind +ring
    dsimp [subgroupOrder] at heq ⊢
    omega
  have hS' : twiceInner start basisSum = z.1+z.2 := by
    rw [show basisSum = add basisW basisV from rfl, inner_second_add,
        hW', hV']
    omega
  dsimp [z] at hW' hV' hS'
  have hn := neighbor_norms
  dsimp [sixNeighborsClosest]
  rw [norm_add_inner, norm_sub_inner, norm_add_inner, norm_sub_inner,
      norm_add_inner, norm_sub_inner, hn.1, hn.2.1, hn.2.2,
      hW', hV', hS']
  omega

theorem corner_score_scaled (x y d t : Int) (corner : Nat)
    (hc : corner < 4) :
    cornerScore (t*x) (t*y) (t*d) corner =
      t * cornerScore x y d corner := by
  have hcases : corner = 0 ∨ corner = 1 ∨ corner = 2 ∨ corner = 3 := by omega
  rcases hcases with h | h | h | h
  all_goals
    subst corner
    simp only [cornerScore]
    grind +ring

-- This is the certified chooser branch at the actual subgroup lattice:
-- once its reciprocal words establish the high-fraction intervals and the
-- floor quotients establish the exact scaled-coordinate identity, the
-- selected representative is no farther than all six lattice neighbors.
theorem fraction_corner_certified_six_neighbors
    (start : Pair) (x y hw hv : Int) (winner : Fin 4)
    (hx : 0 ≤ x ∧ x ≤ subgroupOrder)
    (hy : 0 ≤ y ∧ y ≤ subgroupOrder)
    (hx0 : hw*subgroupOrder ≤ fractionBase*x)
    (hx2 : fractionBase*x ≤ (hw+2)*subgroupOrder)
    (hy0 : hv*subgroupOrder ≤ fractionBase*y)
    (hy2 : fractionBase*y ≤ (hv+2)*subgroupOrder)
    (hsep : ∀ j : Fin 4, j ≠ winner →
      fractionCornerUpper hw hv winner < fractionCornerLower hw hv j)
    (hscaled :
      scale subgroupOrder start =
        add (scale (cornerResidual x y subgroupOrder winner.val).1 basisW)
            (scale (cornerResidual x y subgroupOrder winner.val).2 basisV)) :
    sixNeighborsClosest start := by
  have hn : 0 < subgroupOrder := by decide
  have hcert := fraction_corner_certificate subgroupOrder hw hv
    (fractionBase*x) (fractionBase*y) winner hn hx0 hx2 hy0 hy2 hsep
  have hmin : ∀ j < 4,
      cornerScore x y subgroupOrder winner.val ≤ cornerScore x y subgroupOrder j := by
    intro j hj
    have h := hcert ⟨j,hj⟩
    rw [corner_score_scaled x y subgroupOrder fractionBase winner.val winner.isLt,
        corner_score_scaled x y subgroupOrder fractionBase j hj] at h
    dsimp [fractionBase] at h
    omega
  exact four_corner_minimum_six_neighbors start x y winner.val
    hx hy winner.isLt hmin hscaled

-- The floor-quotient-to-representative coordinate identity is discharged
-- here for every four-corner offset; only the native word-loop/output link
-- and its stated high-fraction interval hypotheses remain external.
theorem certified_corner_representative_six_neighbors
    (k qw qv hw hv : Int) (winner : Fin 4)
    (hx : 0 ≤ (floorCellCoordinates k qw qv).1 ∧
      (floorCellCoordinates k qw qv).1 ≤ subgroupOrder)
    (hy : 0 ≤ (floorCellCoordinates k qw qv).2 ∧
      (floorCellCoordinates k qw qv).2 ≤ subgroupOrder)
    (hx0 : hw*subgroupOrder ≤
      fractionBase*(floorCellCoordinates k qw qv).1)
    (hx2 : fractionBase*(floorCellCoordinates k qw qv).1 ≤
      (hw+2)*subgroupOrder)
    (hy0 : hv*subgroupOrder ≤
      fractionBase*(floorCellCoordinates k qw qv).2)
    (hy2 : fractionBase*(floorCellCoordinates k qw qv).2 ≤
      (hv+2)*subgroupOrder)
    (hsep : ∀ j : Fin 4, j ≠ winner →
      fractionCornerUpper hw hv winner < fractionCornerLower hw hv j) :
    sixNeighborsClosest (cornerRepresentative k qw qv winner.val) := by
  exact fraction_corner_certified_six_neighbors
    (cornerRepresentative k qw qv winner.val)
    (floorCellCoordinates k qw qv).1 (floorCellCoordinates k qw qv).2
    hw hv winner hx hy hx0 hx2 hy0 hy2 hsep
    (corner_representative_scaled_coordinates k qw qv winner.val winner.isLt)

-- For mathematical floor quotients, Euclidean remainder bounds also supply
-- the normalized-cell hypotheses. The native reciprocal output must still
-- be proved equal to these quotients and to the reported high limbs.
theorem exact_floor_certified_six_neighbors
    (k hw hv : Int) (winner : Fin 4)
    (hx0 : hw*subgroupOrder ≤
      fractionBase*(floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1)
    (hx2 : fractionBase*(floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1 ≤
      (hw+2)*subgroupOrder)
    (hy0 : hv*subgroupOrder ≤
      fractionBase*(floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2)
    (hy2 : fractionBase*(floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2 ≤
      (hv+2)*subgroupOrder)
    (hsep : ∀ j : Fin 4, j ≠ winner →
      fractionCornerUpper hw hv winner < fractionCornerLower hw hv j) :
    sixNeighborsClosest
      (cornerRepresentative k (exactFloorW k) (exactFloorV k) winner.val) := by
  have hb := exact_floor_cell_bounds k
  have hx : 0 ≤ (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1 ∧
      (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).1 ≤ subgroupOrder := by
    omega
  have hy : 0 ≤ (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2 ∧
      (floorCellCoordinates k (exactFloorW k) (exactFloorV k)).2 ≤ subgroupOrder := by
    omega
  exact certified_corner_representative_six_neighbors k
    (exactFloorW k) (exactFloorV k) hw hv winner
    hx hy hx0 hx2 hy0 hy2 hsep

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
#print axioms corner_score_norm_identity
#print axioms four_corner_minimum_has_hex_strips
#print axioms native_reciprocals_floor
#print axioms fraction_base_width
#print axioms reduced_scalar_below_fraction_tail
#print axioms exact_product_high_fraction_decomposition
#print axioms product_quotient_remainder_from_words
#print axioms schoolbook_muladd_fits_double_word
#print axioms schoolbook_word_step
#print axioms schoolbook_pass_value
#print axioms schoolbook_pass_length
#print axioms word_value_bounds
#print axioms word_values_product_fits
#print axioms four_word_prefix_product_fits
#print axioms four_scalar_prefix_values
#print axioms four_scalar_prefix_capacity
#print axioms schoolbook_pass_bounds
#print axioms carry_pass_value
#print axioms carry_pass_length
#print axioms carry_pass_zero
#print axioms carry_pass_bounds
#print axioms word_value_append
#print axioms eleven_word_product_output
#print axioms eleven_word_split
#print axioms eleven_word_output_from_bounded
#print axioms schoolbook_whole_pass_value
#print axioms schoolbook_whole_pass_length
#print axioms schoolbook_whole_pass_bounds
#print axioms pair_first_value_map
#print axioms shifted_schoolbook_pass_value
#print axioms schoolbook_outer_at_value
#print axioms schoolbook_outer_at_length
#print axioms schoolbook_outer_at_bounds
#print axioms schoolbook_outer_at_no_carry
#print axioms schoolbook_outer_at_zero_carry_of_capacity
#print axioms schoolbook_outer_at_no_overflow
#print axioms word_value_replicate_zero
#print axioms four_scalar_word_product
#print axioms four_scalar_word_product_bounded
#print axioms four_scalar_word_output_bounded
#print axioms reciprocal_high_fraction_interval
#print axioms fraction_limb_score_intervals
#print axioms strictly_separated_interval_certifies_minimum
#print axioms fraction_corner_certificate
#print axioms fraction_corner_certified_hex_strips
#print axioms equilateral_basis_determinant
#print axioms floor_cell_scaled_generic
#print axioms floor_representative_scaled_coordinates
#print axioms exact_floor_remainder_bounds
#print axioms exact_floor_cell_bounds
#print axioms corner_residual_floor_coordinates
#print axioms corner_representative_scaled_coordinates
#print axioms equilateral_basis_inner_values
#print axioms inner_second_add
#print axioms four_corner_minimum_six_neighbors
#print axioms corner_score_scaled
#print axioms fraction_corner_certified_six_neighbors
#print axioms certified_corner_representative_six_neighbors
#print axioms exact_floor_certified_six_neighbors
#print axioms digit_inner_bound
#print axioms decode_inner_bound
#print axioms terminal_inner_bound
#print axioms recoded_terminal_in_domain

end PrimeJ0HexTerminal
