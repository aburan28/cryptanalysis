//! **Binary field `F_{2^m} ≅ F_2[z]/m(z)`** with polynomial basis.
//!
//! An element is a polynomial of degree `< m` over `F_2`, stored
//! as a bit-vector packed into a `Vec<u64>` (LSB-first: bit 0 of
//! word 0 is the constant term, bit 1 is `z¹`, etc.).
//!
//! ## Operations
//!
//! - **Addition** = XOR (since `1 + 1 = 0` in `F_2`).
//! - **Multiplication** = polynomial multiplication then reduction
//!   mod `m(z)`.  We use the **improved Karatsuba** scheme from
//!   Putranto et al. §3.1: divide-and-conquer with three half-size
//!   multiplications, then combine via two MODSHIFT operations.
//! - **Squaring** = bit-spread (each bit `b_i` of input goes to
//!   bit `2i` of output, others = 0) followed by reduction.  Much
//!   cheaper than general multiplication for binary fields.
//! - **Inversion** = Fermat little theorem: `a^{-1} = a^{2^m − 2}`,
//!   computed via Itoh-Tsujii's addition-chain decomposition
//!   (Larasati et al. 2023, also discussed in Putranto et al. §3.2).
//!
//! ## The reduction step
//!
//! After multiplication, the result has degree up to `2m − 2` and
//! must be reduced modulo `m(z)`.  We use the standard left-shift /
//! XOR fold algorithm: while the highest set bit is `≥ m`, XOR
//! `m(z)` shifted to that position into the value.  For sparse
//! `m(z)` (trinomials or pentanomials, which are all NIST curves),
//! this is `O(m)` time and very fast in practice.

use num_bigint::BigUint;

/// An irreducible polynomial of `F_2[z]` defining a binary field
/// `F_{2^m}`.  Stored as the bit-positions of the polynomial's
/// non-zero coefficients (in addition to the implicit `z^m` term).
///
/// E.g., `x⁸ + x⁴ + x³ + x + 1` is stored as `{8, 4, 3, 1, 0}`,
/// with `degree = 8` and `low_terms = [0, 1, 3, 4]`.
#[derive(Clone, Debug)]
pub struct IrreduciblePoly {
    /// Degree of the polynomial = `m`.
    pub degree: u32,
    /// Bit-positions of non-zero coefficients below `z^m`.
    /// The leading `z^m` term is implicit.
    pub low_terms: Vec<u32>,
}

impl IrreduciblePoly {
    /// `x⁸ + x⁴ + x³ + x + 1` (NIST/FIPS 186-4 toy).
    pub fn deg_8() -> Self {
        Self {
            degree: 8,
            low_terms: vec![0, 1, 3, 4],
        }
    }
    /// `x¹⁶ + x⁵ + x³ + x + 1`.
    pub fn deg_16() -> Self {
        Self {
            degree: 16,
            low_terms: vec![0, 1, 3, 5],
        }
    }
    /// `z¹²⁷ + z + 1` (Mersenne-like, used by Banegas et al.).
    pub fn deg_127() -> Self {
        Self {
            degree: 127,
            low_terms: vec![0, 1],
        }
    }
    /// `z¹¹³ + z⁹ + 1` — SECG sect113r1/r2.
    pub fn deg_113() -> Self {
        Self {
            degree: 113,
            low_terms: vec![0, 9],
        }
    }
    /// `z¹³¹ + z⁸ + z³ + z² + 1` — SECG sect131r1/r2.
    pub fn deg_131() -> Self {
        Self {
            degree: 131,
            low_terms: vec![0, 2, 3, 8],
        }
    }
    /// `z¹⁵⁵ + z⁶² + 1` — RFC 2409 Oakley Group 3 EC2N.
    pub fn deg_155_oakley_group3() -> Self {
        Self {
            degree: 155,
            low_terms: vec![0, 62],
        }
    }
    /// `z¹⁶³ + z⁷ + z⁶ + z³ + 1` — NIST B-163.
    pub fn deg_163() -> Self {
        Self {
            degree: 163,
            low_terms: vec![0, 3, 6, 7],
        }
    }
    /// `z²³³ + z⁷⁴ + 1` — NIST B-233.
    pub fn deg_233() -> Self {
        Self {
            degree: 233,
            low_terms: vec![0, 74],
        }
    }
}

/// Words stored inline before an element falls back to the heap:
/// `m ≤ 576`, which covers every NIST and SECG binary field up to
/// B-571.
const INLINE_WORDS: usize = 9;

/// The limbs of an [`F2mElement`]: inline up to [`INLINE_WORDS`] words,
/// a `Vec` beyond that.
///
/// Every field operation returns a fresh element, so with a `Vec` each
/// one paid a heap allocation, and so did every `clone` — after the
/// word-level arithmetic that allocation was most of a multiply.  Inline
/// storage makes creating and cloning an element a copy of at most 72
/// bytes.  It derefs to `[u64]` of exactly the element's word count, so
/// the arithmetic sees the same slice either way; the heap arm only
/// keeps fields wider than 576 bits working.
#[derive(Clone)]
enum Words {
    Inline { len: u8, w: [u64; INLINE_WORDS] },
    Heap(Vec<u64>),
}

impl Words {
    fn zeroed(n: usize) -> Self {
        if n <= INLINE_WORDS {
            Words::Inline {
                len: n as u8,
                w: [0; INLINE_WORDS],
            }
        } else {
            Words::Heap(vec![0; n])
        }
    }
}

impl std::ops::Deref for Words {
    type Target = [u64];
    #[inline(always)]
    fn deref(&self) -> &[u64] {
        match self {
            Words::Inline { len, w } => &w[..*len as usize],
            Words::Heap(v) => v,
        }
    }
}

impl std::ops::DerefMut for Words {
    #[inline(always)]
    fn deref_mut(&mut self) -> &mut [u64] {
        match self {
            Words::Inline { len, w } => &mut w[..*len as usize],
            Words::Heap(v) => v,
        }
    }
}

/// Equality and `Debug` look at the words only, so they behave exactly
/// as the old `Vec<u64>` field's derived impls did.
impl PartialEq for Words {
    fn eq(&self, other: &Self) -> bool {
        **self == **other
    }
}

impl Eq for Words {}

impl std::fmt::Debug for Words {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        (**self).fmt(f)
    }
}

/// An element of `F_{2^m}`: a polynomial of degree `< m` over `F_2`.
/// Stored as a packed bit-vector; bit `i` represents the coefficient
/// of `z^i`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct F2mElement {
    /// `bits[w] >> b` represents the coefficient of `z^(64·w + b)`.
    bits: Words,
    /// Number of bits considered (≥ irreducible's degree; we keep
    /// the result reduced so high bits are always 0).
    m: u32,
}

impl F2mElement {
    /// Zero element.
    pub fn zero(m: u32) -> Self {
        let n_words = m.div_ceil(64) as usize;
        Self {
            bits: Words::zeroed(n_words.max(1)),
            m,
        }
    }

    /// One element (the constant polynomial `1`).
    pub fn one(m: u32) -> Self {
        let mut z = Self::zero(m);
        z.bits[0] = 1;
        z
    }

    /// The polynomial `z` itself.
    pub fn z(m: u32) -> Self {
        let mut zero = Self::zero(m);
        zero.bits[0] = 2;
        zero
    }

    /// Construct from a list of set-bit positions (e.g., `[0, 3, 5]`
    /// gives `1 + z³ + z⁵`).
    pub fn from_bit_positions(positions: &[u32], m: u32) -> Self {
        let mut e = Self::zero(m);
        for &i in positions {
            assert!(i < m, "bit position must be < m");
            let w = (i / 64) as usize;
            let b = (i % 64) as u64;
            e.bits[w] |= 1u64 << b;
        }
        e
    }

    /// Construct from a hex string (most-significant-coefficient
    /// first, big-endian byte order).  Useful for ingesting NIST
    /// curve constants.
    pub fn from_hex(hex: &str, m: u32) -> Self {
        let cleaned: String = hex.chars().filter(|c| !c.is_whitespace()).collect();
        let big = BigUint::parse_bytes(cleaned.as_bytes(), 16).expect("invalid hex");
        Self::from_biguint(&big, m)
    }

    pub fn from_biguint(v: &BigUint, m: u32) -> Self {
        let mut e = Self::zero(m);
        let words = v.to_u64_digits();
        for (i, w) in words.iter().enumerate() {
            if i < e.bits.len() {
                e.bits[i] = *w;
            }
        }
        // Clear any high bits above `m - 1`.
        e.mask_in_place();
        e
    }

    pub fn to_biguint(&self) -> BigUint {
        BigUint::from_slice(
            &self
                .bits
                .iter()
                .flat_map(|w| [(*w & 0xFFFF_FFFF) as u32, (*w >> 32) as u32])
                .collect::<Vec<u32>>(),
        )
    }

    pub fn is_zero(&self) -> bool {
        self.bits.iter().all(|w| *w == 0)
    }

    /// Field width parameter `m` (i.e. `self ∈ F_{2^m}`).
    pub fn m_value(&self) -> u32 {
        self.m
    }

    /// Raw bit-vector view (LSB-first, packed into `u64`s).  Mostly
    /// used by cryptanalysis code that wants to do `F_2`-vector
    /// arithmetic across many elements (e.g. computing the rank of
    /// a set of elements as an `F_2`-subspace of `F_{2^m}`).
    pub fn raw_bits(&self) -> &[u64] {
        &self.bits
    }

    pub fn degree(&self) -> Option<u32> {
        for (i, w) in self.bits.iter().enumerate().rev() {
            if *w != 0 {
                let high_bit = 63 - w.leading_zeros();
                return Some((i as u32) * 64 + high_bit);
            }
        }
        None
    }

    /// Clear any bits above position `m - 1`.  Called after
    /// operations that could leave stray high bits.
    fn mask_in_place(&mut self) {
        let m = self.m;
        if m == 0 {
            return;
        }
        let last_word = ((m - 1) / 64) as usize;
        let last_bit_in_word = (m - 1) % 64;
        if last_word < self.bits.len() {
            let mask = if last_bit_in_word == 63 {
                u64::MAX
            } else {
                (1u64 << (last_bit_in_word + 1)) - 1
            };
            self.bits[last_word] &= mask;
            for i in (last_word + 1)..self.bits.len() {
                self.bits[i] = 0;
            }
        }
    }

    /// `self + other` = bitwise XOR.
    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.m, other.m);
        let mut out = self.clone();
        for (a, b) in out.bits.iter_mut().zip(other.bits.iter()) {
            *a ^= *b;
        }
        out
    }

    /// `self += other` in place (XOR), without allocating.
    pub fn add_assign(&mut self, other: &Self) {
        debug_assert_eq!(self.m, other.m);
        for (a, b) in self.bits.iter_mut().zip(other.bits.iter()) {
            *a ^= *b;
        }
    }

    /// Subtraction in `F_2` is the same as addition.
    pub fn sub(&self, other: &Self) -> Self {
        self.add(other)
    }

    /// `self · other (mod m(z))` using schoolbook multiplication.
    /// Used as the base case in Karatsuba.
    pub fn schoolbook_mul(&self, other: &Self, irreducible: &IrreduciblePoly) -> Self {
        let m = self.m;
        // Unreduced product has up to 2m bits.
        let n_words = (2 * m).div_ceil(64) as usize;
        let mut prod = vec![0u64; n_words.max(2)];
        // For each set bit of self, XOR a shifted copy of `other`.
        for i in 0..self.m {
            let w_i = (i / 64) as usize;
            let b_i = i % 64;
            if w_i >= self.bits.len() {
                break;
            }
            if (self.bits[w_i] >> b_i) & 1 == 1 {
                add_shifted(&mut prod, &other.bits, i);
            }
        }
        reduce_bitwise(&mut prod, irreducible);
        let mut out = Self::zero(m);
        for (i, w) in prod.iter().enumerate().take(out.bits.len()) {
            out.bits[i] = *w;
        }
        out.mask_in_place();
        out
    }

    /// **Improved Karatsuba multiplication** (Putranto et al. §3.1).
    ///
    /// Split each operand into low/high halves of `k = m/2` bits:
    /// `A = A_L + z^k · A_H`, `B = B_L + z^k · B_H`.
    /// Compute three products: `P_L = A_L · B_L`, `P_H = A_H · B_H`,
    /// `P_M = (A_L + A_H) · (B_L + B_H)`.
    /// Combine: `A · B = P_L + z^k · (P_M − P_L − P_H) + z^{2k} · P_H`.
    ///
    /// For binary fields, subtraction is XOR, so the "middle" term
    /// simplifies to `P_M ⊕ P_L ⊕ P_H`.  Reduction happens once at
    /// the end via `reduce_words`.
    pub fn karatsuba_mul(&self, other: &Self, irreducible: &IrreduciblePoly) -> Self {
        let m = self.m;
        // Threshold below which schoolbook is faster.
        if m <= 64 {
            return self.schoolbook_mul(other, irreducible);
        }
        let k = m / 2;
        let (a_lo, a_hi) = split_at(&self.bits, k);
        let (b_lo, b_hi) = split_at(&other.bits, k);

        let a_l = F2mElement::from_words(&a_lo, k);
        let a_h = F2mElement::from_words(&a_hi, m - k);
        let b_l = F2mElement::from_words(&b_lo, k);
        let b_h = F2mElement::from_words(&b_hi, m - k);

        // Recursive products (without reduction yet — work in 2m-bit space).
        let p_lo_bits = unreduced_mul(&a_l.bits, &b_l.bits);
        let p_hi_bits = unreduced_mul(&a_h.bits, &b_h.bits);
        let a_sum_bits = xor_bits(&a_l.bits, &a_h.bits);
        let b_sum_bits = xor_bits(&b_l.bits, &b_h.bits);
        let p_mid_bits = unreduced_mul(&a_sum_bits, &b_sum_bits);

        // Middle = p_mid ⊕ p_lo ⊕ p_hi
        let mid = xor_bits(&xor_bits(&p_mid_bits, &p_lo_bits), &p_hi_bits);

        // Combined product: p_lo ⊕ (mid << k) ⊕ (p_hi << 2k).
        let mut combined = vec![0u64; (2 * m).div_ceil(64) as usize + 2];
        for (i, w) in p_lo_bits.iter().enumerate() {
            if i < combined.len() {
                combined[i] ^= *w;
            }
        }
        add_shifted(&mut combined, &mid, k);
        add_shifted(&mut combined, &p_hi_bits, 2 * k);

        reduce_words(&mut combined, irreducible);
        let mut out = Self::zero(m);
        for (i, w) in combined.iter().enumerate().take(out.bits.len()) {
            out.bits[i] = *w;
        }
        out.mask_in_place();
        out
    }

    /// `self · other (mod m(z))`.
    ///
    /// Word-level schoolbook over 64-bit limbs, each limb product one
    /// carry-less multiply (`pclmulqdq` where the CPU has it, a 4-bit
    /// windowed comb otherwise), then the word-level sparse reduction
    /// `reduce_words`.  At `m ≤ 576` the whole product lives on the
    /// stack; the only allocation is the returned element.
    ///
    /// Bit-for-bit equal to [`Self::schoolbook_mul`] and
    /// [`Self::karatsuba_mul`], which are kept as independent references.
    pub fn mul(&self, other: &Self, irreducible: &IrreduciblePoly) -> Self {
        debug_assert_eq!(self.m, other.m);
        let m = self.m;
        let nw = self.bits.len().max(other.bits.len());
        let mut out = Self::zero(m);
        with_scratch(2 * nw + 1, |prod| {
            mul_words_into(&self.bits, &other.bits, prod);
            reduce_words(prod, irreducible);
            let k = out.bits.len();
            out.bits.copy_from_slice(&prod[..k]);
        });
        out.mask_in_place();
        out
    }

    /// `self²`.  In `F_{2^m}` squaring is linear: bit `i` of `self`
    /// goes to bit `2i` of the result, other bits zero.  Then
    /// reduce mod `m(z)`.
    pub fn square(&self, irreducible: &IrreduciblePoly) -> Self {
        let m = self.m;
        let nw = self.bits.len();
        let mut out = Self::zero(m);
        with_scratch(2 * nw + 1, |sq| {
            for (i, &w) in self.bits.iter().enumerate() {
                sq[2 * i] = spread32(w);
                sq[2 * i + 1] = spread32(w >> 32);
            }
            reduce_words(sq, irreducible);
            let k = out.bits.len();
            out.bits.copy_from_slice(&sq[..k]);
        });
        out.mask_in_place();
        out
    }

    /// `self^(2^k)` — `k` repeated squarings.
    pub fn square_k_times(&self, k: u32, irreducible: &IrreduciblePoly) -> Self {
        let mut acc = self.clone();
        if k == 0 {
            return acc;
        }
        let nw = acc.bits.len();
        with_scratch(2 * nw + 1, |sq| {
            for _ in 0..k {
                sq.iter_mut().for_each(|w| *w = 0);
                for (i, &w) in acc.bits.iter().enumerate() {
                    sq[2 * i] = spread32(w);
                    sq[2 * i + 1] = spread32(w >> 32);
                }
                reduce_words(sq, irreducible);
                acc.bits.copy_from_slice(&sq[..nw]);
            }
        });
        acc.mask_in_place();
        acc
    }

    /// **Fermat-little-theorem inversion** via Itoh-Tsujii.
    ///
    /// `a^(2^m − 2) = a^(-1)` in `F_{2^m}` (since `|F_{2^m}^*| =
    /// 2^m − 1`).  Itoh-Tsujii decomposes `2^m − 2 = 2 · (2^(m−1)
    /// − 1)` and exploits the binary structure of `m − 1` so that
    /// only `O(log m)` multiplications and `O(m)` squarings are
    /// needed (rather than `m − 1` multiplications via naïve
    /// square-and-multiply).
    ///
    /// Concretely:
    ///   1. Compute `b_k = a^{2^{2^k} − 1}` for increasing `k`,
    ///      using `b_{k+1} = b_k · (b_k)^{2^{2^k}}`.
    ///   2. Combine `b_k`'s per the binary expansion of `m − 1`.
    ///   3. Final squaring: result = `(combined)²`.
    pub fn flt_inverse(&self, irreducible: &IrreduciblePoly) -> Option<Self> {
        if self.is_zero() {
            return None;
        }
        let m = self.m;
        // We want a^(2^m − 2) = a^(2 · (2^(m−1) − 1)).
        // Let n = m − 1.
        let n = m - 1;
        // Compute a^(2^n − 1) using Itoh-Tsujii (binary-of-n decomposition).
        let mut bits: Vec<u32> = Vec::new();
        let mut nn = n;
        while nn > 0 {
            bits.push(nn & 1);
            nn >>= 1;
        }
        bits.reverse(); // MSB first

        // β_0 = a.  After processing bit `b`:
        //   β ← β^(2^len) · β   where len = current accumulator length.
        // Plus an extra squaring per `b = 1` bit, multiplying by `a`.
        // We follow the standard Itoh-Tsujii reduction.
        let mut beta = self.clone();
        let mut beta_len: u32 = 1; // β = a^(2^1 − 1) = a initially.
        for &bit in bits.iter().skip(1) {
            // β ← β^(2^beta_len) · β  ⇒ length doubles.
            let shifted = beta.square_k_times(beta_len, irreducible);
            beta = beta.mul(&shifted, irreducible);
            beta_len *= 2;
            if bit == 1 {
                // β ← (β^2) · a ⇒ length += 1.
                let sq = beta.square(irreducible);
                beta = sq.mul(self, irreducible);
                beta_len += 1;
            }
        }
        // Now β = a^(2^n − 1) where n = m − 1.  Final squaring
        // gives a^(2^m − 2) = a^(-1).
        Some(beta.square(irreducible))
    }

    /// Internal: construct from a `&[u64]` raw word slice.
    fn from_words(words: &[u64], m: u32) -> Self {
        let mut e = Self::zero(m);
        for (b, w) in e.bits.iter_mut().zip(words) {
            *b = *w;
        }
        e.mask_in_place();
        e
    }
}

// ── Internal helpers (unreduced bit-vector arithmetic) ────────────

/// XOR two bit-vectors (different lengths allowed; result is
/// length = max).
fn xor_bits(a: &[u64], b: &[u64]) -> Vec<u64> {
    let n = a.len().max(b.len());
    let mut out = vec![0u64; n];
    for (i, w) in a.iter().enumerate() {
        out[i] ^= *w;
    }
    for (i, w) in b.iter().enumerate() {
        out[i] ^= *w;
    }
    out
}

/// Unreduced schoolbook multiplication of two bit-vectors.  Returns
/// a bit-vector of length `len(a) + len(b)` words.
fn unreduced_mul(a: &[u64], b: &[u64]) -> Vec<u64> {
    let mut out = vec![0u64; a.len() + b.len()];
    mul_words_into(a, b, &mut out);
    out
}

/// `out ^= b << shift`  (treating both as bit-vectors of unspecified
/// length, packing word-major).
fn add_shifted(out: &mut Vec<u64>, b: &[u64], shift: u32) {
    let word_shift = (shift / 64) as usize;
    let bit_shift = shift % 64;
    if bit_shift == 0 {
        for (i, w) in b.iter().enumerate() {
            let target = i + word_shift;
            if target < out.len() {
                out[target] ^= *w;
            } else {
                // Auto-grow if needed.
                while out.len() <= target {
                    out.push(0);
                }
                out[target] ^= *w;
            }
        }
    } else {
        for (i, w) in b.iter().enumerate() {
            let target = i + word_shift;
            if target < out.len() {
                out[target] ^= *w << bit_shift;
            } else {
                while out.len() <= target {
                    out.push(0);
                }
                out[target] ^= *w << bit_shift;
            }
            if target + 1 < out.len() {
                out[target + 1] ^= *w >> (64 - bit_shift);
            } else {
                while out.len() <= target + 1 {
                    out.push(0);
                }
                out[target + 1] ^= *w >> (64 - bit_shift);
            }
        }
    }
}

/// Split a bit-vector at bit position `at`, returning `(low, high)`.
/// `low` has bits 0..at, `high` has bits at..bit_length.
fn split_at(bits: &[u64], at: u32) -> (Vec<u64>, Vec<u64>) {
    let n_words = bits.len();
    let word_at = (at / 64) as usize;
    let bit_at = at % 64;
    let mut low = Vec::with_capacity(word_at + 1);
    let mut high = Vec::new();
    for i in 0..n_words {
        if i < word_at {
            low.push(bits[i]);
        } else if i == word_at {
            if bit_at == 0 {
                high.push(bits[i]);
            } else {
                let mask = (1u64 << bit_at) - 1;
                low.push(bits[i] & mask);
                high.push(bits[i] >> bit_at);
            }
        } else {
            if bit_at == 0 {
                high.push(bits[i]);
            } else {
                // bits[i] contributes to high at offset (i - word_at).
                if let Some(last) = high.last_mut() {
                    *last ^= bits[i] << (64 - bit_at);
                }
                high.push(bits[i] >> bit_at);
            }
        }
    }
    if low.is_empty() {
        low.push(0);
    }
    if high.is_empty() {
        high.push(0);
    }
    (low, high)
}

/// Reduce a polynomial (bit-vector) modulo the irreducible
/// polynomial `m(z)`.  In place: high bits get folded down into
/// positions `< m`.
///
/// One bit at a time.  Kept only as the independent reference behind
/// [`F2mElement::schoolbook_mul`]; everything else uses
/// `reduce_words`.
fn reduce_bitwise(value: &mut [u64], irreducible: &IrreduciblePoly) {
    let m = irreducible.degree;
    // Total bit length of `value`.
    let total_bits = (value.len() as u32) * 64;
    // For each bit position from highest down to `m`, if it's set,
    // XOR `m(z)` shifted to that position into `value` and clear
    // the bit.
    for pos in (m..total_bits).rev() {
        let w = (pos / 64) as usize;
        let b = pos % 64;
        if w >= value.len() {
            continue;
        }
        if (value[w] >> b) & 1 == 1 {
            // Clear bit (pos).
            value[w] ^= 1u64 << b;
            // XOR `z^k · low_terms` for k = pos − m.
            let shift = pos - m;
            for &t in &irreducible.low_terms {
                let target_pos = t + shift;
                let tw = (target_pos / 64) as usize;
                let tb = target_pos % 64;
                if tw < value.len() {
                    value[tw] ^= 1u64 << tb;
                }
            }
        }
    }
}

// ── Word-level kernels ────────────────────────────────────────────

/// Spread the low 32 bits of `x` so that bit `i` lands at bit `2i`:
/// squaring in characteristic 2 before reduction.
#[inline(always)]
fn spread32(x: u64) -> u64 {
    let mut x = x & 0xFFFF_FFFF;
    x = (x | (x << 16)) & 0x0000_FFFF_0000_FFFF;
    x = (x | (x << 8)) & 0x00FF_00FF_00FF_00FF;
    x = (x | (x << 4)) & 0x0F0F_0F0F_0F0F_0F0F;
    x = (x | (x << 2)) & 0x3333_3333_3333_3333;
    x = (x | (x << 1)) & 0x5555_5555_5555_5555;
    x
}

/// Run `f` on a zeroed scratch buffer of `len` words: on the stack up
/// to 20 words (a product of two `m ≤ 576`-bit operands), on the heap
/// beyond that.
#[inline(always)]
fn with_scratch<R>(len: usize, f: impl FnOnce(&mut [u64]) -> R) -> R {
    const STACK: usize = 20;
    if len <= STACK {
        let mut buf = [0u64; STACK];
        f(&mut buf[..len])
    } else {
        let mut buf = vec![0u64; len];
        f(&mut buf)
    }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn clmul64_hw(a: u64, b: u64) -> (u64, u64) {
    use std::arch::x86_64::*;
    let z = _mm_clmulepi64_si128::<0x00>(_mm_set_epi64x(0, a as i64), _mm_set_epi64x(0, b as i64));
    (
        _mm_cvtsi128_si64(z) as u64,
        _mm_cvtsi128_si64(_mm_srli_si128::<8>(z)) as u64,
    )
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn clmul64_hw(a: u64, b: u64) -> (u64, u64) {
    let p = std::arch::aarch64::vmull_p64(a, b);
    (p as u64, (p >> 64) as u64)
}

/// Carry-less `64 × 64 → 128` without hardware support: a 4-bit
/// window over `a`, sixteen table lookups instead of sixty-four
/// data-dependent branches.
#[inline]
fn clmul64_soft(a: u64, b: u64) -> (u64, u64) {
    let mut tab = [0u128; 16];
    let b128 = b as u128;
    for i in 1..16usize {
        tab[i] = if i & 1 == 1 {
            tab[i - 1] ^ b128
        } else {
            tab[i >> 1] << 1
        };
    }
    let mut acc = 0u128;
    for k in (0..16).rev() {
        acc = (acc << 4) ^ tab[((a >> (4 * k)) & 0xF) as usize];
    }
    (acc as u64, (acc >> 64) as u64)
}

#[inline(always)]
fn has_hw_clmul() -> bool {
    #[cfg(target_arch = "x86_64")]
    {
        std::arch::is_x86_feature_detected!("pclmulqdq")
    }
    #[cfg(target_arch = "aarch64")]
    {
        std::arch::is_aarch64_feature_detected!("aes")
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    {
        false
    }
}

/// `out ^= a · b` over `F_2[z]`, word-level schoolbook with one
/// carry-less multiply per pair of limbs.  `out` must hold at least
/// `a.len() + b.len()` words.
fn mul_words_into(a: &[u64], b: &[u64], out: &mut [u64]) {
    debug_assert!(out.len() >= a.len() + b.len());
    #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
    if has_hw_clmul() {
        // SAFETY: the required CPU feature was detected at runtime.
        unsafe { mul_words_hw(a, b, out) };
        return;
    }
    for (i, &ai) in a.iter().enumerate() {
        if ai == 0 {
            continue;
        }
        for (j, &bj) in b.iter().enumerate() {
            let (lo, hi) = clmul64_soft(ai, bj);
            out[i + j] ^= lo;
            out[i + j + 1] ^= hi;
        }
    }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn mul_words_hw(a: &[u64], b: &[u64], out: &mut [u64]) {
    for (i, &ai) in a.iter().enumerate() {
        for (j, &bj) in b.iter().enumerate() {
            let (lo, hi) = clmul64_hw(ai, bj);
            out[i + j] ^= lo;
            out[i + j + 1] ^= hi;
        }
    }
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn mul_words_hw(a: &[u64], b: &[u64], out: &mut [u64]) {
    for (i, &ai) in a.iter().enumerate() {
        for (j, &bj) in b.iter().enumerate() {
            let (lo, hi) = clmul64_hw(ai, bj);
            out[i + j] ^= lo;
            out[i + j + 1] ^= hi;
        }
    }
}

/// Reduce `value` modulo `m(z)` in place, a whole word at a time.
///
/// Each word `w` at or above `z^m` stands for `w · z^{64i}`, and since
/// `z^m ≡ r(z) = m(z) − z^m` it folds back as `Σ_t w · z^{64i − m + t}`
/// over `r`'s few terms `t`: one two-word XOR per term.  Walking the
/// words from the top down, a fold lands strictly below the word it came
/// from as long as `m − deg r ≥ 64` (it reaches bit `64i − m + deg r +
/// 63 < 64i`), so every word is folded exactly once and the partial word
/// holding bit `m` last.  For B-163 that is three full words and one
/// partial one, five terms each; the old chunk loop spent twice the
/// instructions on the same folds through general bit-range helpers.
///
/// Every NIST and SECG field satisfies `m − deg r ≥ 64`.  The toy fields
/// (`m = 8, 16`) and dense tails do not, and take [`reduce_chunked`].
/// Both are tested against the bit-at-a-time `reduce_bitwise`.
fn reduce_words(value: &mut [u64], irreducible: &IrreduciblePoly) {
    let m = irreducible.degree as usize;
    let terms = &irreducible.low_terms;
    let t_max = terms.iter().copied().max().unwrap_or(0) as usize;
    if m < t_max + 64 || terms.len() > 8 {
        return reduce_chunked(value, irreducible);
    }
    // When r fits in one word, fold each word with a single carry-less
    // multiply `w · r` instead of one shifted XOR per term.
    #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
    if t_max < 64 && has_hw_clmul() {
        let r = terms.iter().fold(0u64, |acc, &t| acc | (1u64 << t));
        // SAFETY: the required CPU feature was detected at runtime.
        unsafe { fold_words_clmul_hw(value, m, r) };
        return;
    }
    fold_words_terms(value, m, terms);
}

/// The word-at-a-time fold of [`reduce_words`], one shifted XOR per term
/// of `r`: for `deg r ≥ 64`, or without a hardware carry-less multiply.
/// Requires `m ≥ deg r + 64`.
fn fold_words_terms(value: &mut [u64], m: usize, terms: &[u32]) {
    let wm = m / 64;
    let bm = m % 64;
    // Words wholly at or above z^m: from the top non-zero one down.
    let first_full = if bm == 0 { wm } else { wm + 1 };
    let mut top = value.len();
    while top > first_full && value[top - 1] == 0 {
        top -= 1;
    }
    for i in (first_full..top).rev() {
        let w = value[i];
        if w == 0 {
            continue;
        }
        value[i] = 0;
        let base = 64 * i - m;
        for &t in terms {
            xor_word_at(value, base + t as usize, w);
        }
    }
    // The bits of word `wm` at and above z^m.  They number fewer than
    // 64 and fold to below bit `deg r + 64 − bm ≤ m`, so one pass ends it.
    if bm != 0 {
        let w = value[wm] >> bm;
        if w != 0 {
            value[wm] &= (1u64 << bm) - 1;
            for &t in terms {
                xor_word_at(value, t as usize, w);
            }
        }
    }
}

/// The word-at-a-time fold of [`reduce_words`] with `r = m(z) − z^m`
/// packed into one word: each word `w` above `z^m` folds back as the
/// 128-bit carry-less product `w · r`, placed at bit `64i − m` with three
/// word XORs.  Same order and same bounds argument as the term loop:
/// `m − deg r ≥ 64` keeps every fold strictly below its source word, and
/// the third word can only be non-zero where it exists.
macro_rules! fold_words_clmul_body {
    ($value:ident, $m:ident, $r:ident) => {{
        let value = $value;
        let m = $m;
        let r = $r;
        #[inline(always)]
        unsafe fn place(v: &mut [u64], pos: usize, w: u64, r: u64) {
            let (lo, hi) = clmul64_hw(w, r);
            let i = pos / 64;
            let s = (pos % 64) as u32;
            v[i] ^= lo << s;
            v[i + 1] ^= ((lo >> 1) >> (63 - s)) | (hi << s);
            let third = (hi >> 1) >> (63 - s);
            if let Some(x) = v.get_mut(i + 2) {
                *x ^= third;
            }
        }
        let wm = m / 64;
        let bm = m % 64;
        let first_full = if bm == 0 { wm } else { wm + 1 };
        let mut top = value.len();
        while top > first_full && value[top - 1] == 0 {
            top -= 1;
        }
        for i in (first_full..top).rev() {
            let w = value[i];
            if w != 0 {
                value[i] = 0;
                place(value, 64 * i - m, w, r);
            }
        }
        if bm != 0 {
            let w = value[wm] >> bm;
            if w != 0 {
                value[wm] &= (1u64 << bm) - 1;
                place(value, 0, w, r);
            }
        }
    }};
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn fold_words_clmul_hw(value: &mut [u64], m: usize, r: u64) {
    fold_words_clmul_body!(value, m, r)
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn fold_words_clmul_hw(value: &mut [u64], m: usize, r: u64) {
    fold_words_clmul_body!(value, m, r)
}

/// `v ^= w << pos` for a whole word `w`, branch-free.
///
/// The spill into the next word is `(w >> 1) >> (63 − s)`, which is `w >>
/// (64 − s)` for `s > 0` and zero for `s = 0`, so both words are always
/// written.  Callers guarantee `v[pos / 64 + 1]` exists: in the top-down
/// fold it is at most the (already cleared) source word, and in the
/// partial-word fold it is at most word `m / 64`.
#[inline(always)]
fn xor_word_at(v: &mut [u64], pos: usize, w: u64) {
    let i = pos / 64;
    let s = (pos % 64) as u32;
    v[i] ^= w << s;
    v[i + 1] ^= (w >> 1) >> (63 - s);
}

/// Bits `[pos, pos + len)` of `v` as an integer, `len ≤ 64`.
#[inline(always)]
fn get_bits(v: &[u64], pos: u32, len: u32) -> u64 {
    let w = (pos / 64) as usize;
    let b = pos % 64;
    let mut x = v[w] >> b;
    if b != 0 && b + len > 64 && w + 1 < v.len() {
        x |= v[w + 1] << (64 - b);
    }
    if len < 64 {
        x &= (1u64 << len) - 1;
    }
    x
}

/// `v ^= x << pos`, dropping anything past the end of `v`.
#[inline(always)]
fn xor_bits_at(v: &mut [u64], pos: u32, x: u64) {
    let w = (pos / 64) as usize;
    let b = pos % 64;
    if w < v.len() {
        v[w] ^= x << b;
    }
    if b != 0 && w + 1 < v.len() {
        v[w + 1] ^= x >> (64 - b);
    }
}

/// Reduce `value` modulo `m(z)` in place, a chunk of up to 64 bits at
/// a time rather than one bit at a time.
///
/// The general path behind [`reduce_words`], for polynomials whose tail
/// reaches within 64 bits of `z^m` (the toy fields `m = 8, 16`, and
/// dense tails); every NIST and SECG field takes the word-at-a-time
/// path instead.
///
/// Walking down from the top, the chunk `[lo, hi)` above `z^m` is
/// cleared and folded back as `Σ_t x · z^{lo − m + t}` over the
/// irreducible's low terms `t`.  The chunk width is capped at
/// `m − t_max`, so a fold always lands strictly below `lo` and never
/// re-dirties the chunk it came from; the bits it lands in `[m, lo)`
/// are picked up by later chunks.  For a trinomial or pentanomial
/// that is a handful of shift-XORs per word of excess, independent of
/// how many bits are set.
fn reduce_chunked(value: &mut [u64], irreducible: &IrreduciblePoly) {
    let m = irreducible.degree;
    let t_max = irreducible.low_terms.iter().copied().max().unwrap_or(0);
    debug_assert!(t_max < m);
    let width = (m - t_max).min(64);
    // One past the highest set bit, so the first chunk starts at the
    // product's real degree rather than at the top of its last word.
    let mut top_word = value.len();
    while top_word > 0 && value[top_word - 1] == 0 {
        top_word -= 1;
    }
    let mut hi = match top_word {
        0 => 0,
        w => (w as u32) * 64 - value[w - 1].leading_zeros(),
    };
    while hi > m {
        let lo = hi.saturating_sub(width).max(m);
        let len = hi - lo;
        let x = get_bits(value, lo, len);
        if x != 0 {
            xor_bits_at(value, lo, x); // clear
            let base = lo - m;
            for &t in &irreducible.low_terms {
                xor_bits_at(value, base + t, x);
            }
        }
        hi = lo;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Addition in `F_2^m` is XOR; verify on a small concrete case.
    #[test]
    fn add_is_xor() {
        let m = 8;
        let a = F2mElement::from_bit_positions(&[0, 3, 7], m); // 1 + z³ + z⁷
        let b = F2mElement::from_bit_positions(&[3, 5], m); // z³ + z⁵
        let c = a.add(&b);
        // Result: 1 + z⁵ + z⁷
        let expected = F2mElement::from_bit_positions(&[0, 5, 7], m);
        assert_eq!(c, expected);
    }

    /// Schoolbook and Karatsuba agree.
    #[test]
    fn schoolbook_and_karatsuba_agree() {
        let irr = IrreduciblePoly::deg_127();
        let a = F2mElement::from_hex("5A3F1E7CABCDEF0123456789ABCDEF01", 127);
        let b = F2mElement::from_hex("12345678DEADBEEFC0FFEE0011223344", 127);
        let p1 = a.schoolbook_mul(&b, &irr);
        let p2 = a.karatsuba_mul(&b, &irr);
        assert_eq!(p1, p2);
    }

    /// Multiplication by 1 is identity.
    #[test]
    fn mul_by_one_is_identity() {
        let irr = IrreduciblePoly::deg_163();
        let a = F2mElement::from_hex("abcdef0123456789abcdef0123456789abcdef01ff", 163);
        let one = F2mElement::one(163);
        assert_eq!(a.mul(&one, &irr), a);
    }

    /// Multiplication is commutative.
    #[test]
    fn mul_commutes() {
        let irr = IrreduciblePoly::deg_127();
        let a = F2mElement::from_hex("1234567890abcdef", 127);
        let b = F2mElement::from_hex("fedcba0987654321", 127);
        assert_eq!(a.mul(&b, &irr), b.mul(&a, &irr));
    }

    /// `(a + b)² = a² + b²` in characteristic-2 fields.
    #[test]
    fn frobenius_endomorphism() {
        let irr = IrreduciblePoly::deg_127();
        let a = F2mElement::from_hex("deadbeefcafebabe", 127);
        let b = F2mElement::from_hex("0123456789abcdef", 127);
        let sum_sq = a.add(&b).square(&irr);
        let sq_sum = a.square(&irr).add(&b.square(&irr));
        assert_eq!(sum_sq, sq_sum);
    }

    /// `a · a⁻¹ = 1` for non-zero `a`.
    #[test]
    fn flt_inverse_roundtrip() {
        let irr = IrreduciblePoly::deg_127();
        let a = F2mElement::from_hex("17ce1024deadbeefcafebabe01234567", 127);
        let inv = a.flt_inverse(&irr).expect("non-zero invertible");
        let prod = a.mul(&inv, &irr);
        assert_eq!(prod, F2mElement::one(127));
    }

    /// Inverse of zero is None.
    #[test]
    fn flt_inverse_of_zero_is_none() {
        let irr = IrreduciblePoly::deg_127();
        let zero = F2mElement::zero(127);
        assert!(zero.flt_inverse(&irr).is_none());
    }

    /// Inverse at smaller field (deg 16) — exhaustive smoke test
    /// over a few sample inputs.
    #[test]
    fn flt_inverse_deg16_sanity() {
        let irr = IrreduciblePoly::deg_16();
        for v in [1u64, 2, 3, 0xDEAD, 0xCAFE, 0xBEEF, 0xFFFF] {
            let a = F2mElement::from_biguint(&BigUint::from(v), 16);
            if a.is_zero() {
                continue;
            }
            let inv = a.flt_inverse(&irr).unwrap();
            let prod = a.mul(&inv, &irr);
            assert_eq!(prod, F2mElement::one(16), "a·a⁻¹ ≠ 1 for a = {}", v);
        }
    }

    fn xorshift(s: &mut u64) -> u64 {
        *s ^= *s << 13;
        *s ^= *s >> 7;
        *s ^= *s << 17;
        *s
    }

    fn random_elem(s: &mut u64, m: u32) -> F2mElement {
        let n_words = m.div_ceil(64) as usize;
        let words: Vec<u64> = (0..n_words).map(|_| xorshift(s)).collect();
        F2mElement::from_words(&words, m)
    }

    fn all_fields() -> Vec<IrreduciblePoly> {
        vec![
            IrreduciblePoly::deg_8(),
            IrreduciblePoly::deg_16(),
            IrreduciblePoly::deg_113(),
            IrreduciblePoly::deg_127(),
            IrreduciblePoly::deg_131(),
            IrreduciblePoly::deg_155_oakley_group3(),
            IrreduciblePoly::deg_163(),
            IrreduciblePoly::deg_233(),
            // z^64 + z^4 + z^3 + z + 1: exactly one word.
            IrreduciblePoly {
                degree: 64,
                low_terms: vec![0, 1, 3, 4],
            },
            // z^571 + z^10 + z^5 + z^2 + 1 (NIST B-571): beyond the
            // stack scratch, exercises the heap path.
            IrreduciblePoly {
                degree: 571,
                low_terms: vec![0, 2, 5, 10],
            },
        ]
    }

    /// The word-level carry-less `mul` agrees bit for bit with the
    /// bit-at-a-time schoolbook reference and with Karatsuba, at every
    /// field size including ones whose reduction chunk is narrower than
    /// a word (`m − t_max < 64`).
    #[test]
    fn word_mul_matches_bitwise_reference() {
        let mut s = 0x0123_4567_89AB_CDEFu64;
        for irr in all_fields() {
            let m = irr.degree;
            for _ in 0..40 {
                let a = random_elem(&mut s, m);
                let b = random_elem(&mut s, m);
                let r = a.schoolbook_mul(&b, &irr);
                assert_eq!(a.mul(&b, &irr), r, "mul, m = {m}");
                assert_eq!(a.karatsuba_mul(&b, &irr), r, "karatsuba, m = {m}");
            }
            // Extremes: all-ones operands carry the most reduction work.
            let ones: Vec<u32> = (0..m).collect();
            let a = F2mElement::from_bit_positions(&ones, m);
            assert_eq!(
                a.mul(&a, &irr),
                a.schoolbook_mul(&a, &irr),
                "all-ones, m = {m}"
            );
        }
    }

    /// Spread-and-reduce squaring equals self-multiplication, and
    /// `square_k_times` equals repeated squaring.
    #[test]
    fn word_square_matches_mul() {
        let mut s = 0xFEED_FACE_CAFE_BEEFu64;
        for irr in all_fields() {
            let m = irr.degree;
            for _ in 0..40 {
                let a = random_elem(&mut s, m);
                let sq = a.square(&irr);
                assert_eq!(sq, a.schoolbook_mul(&a, &irr), "square, m = {m}");
                let mut rep = a.clone();
                for _ in 0..5 {
                    rep = rep.square(&irr);
                }
                assert_eq!(a.square_k_times(5, &irr), rep, "square_k, m = {m}");
            }
            assert_eq!(
                F2mElement::one(m).square_k_times(0, &irr),
                F2mElement::one(m)
            );
        }
    }

    /// Inversion round-trips at every field size.
    #[test]
    fn inverse_roundtrip_all_fields() {
        let mut s = 0xDEAD_BEEF_0BAD_F00Du64;
        for irr in all_fields() {
            let m = irr.degree;
            for _ in 0..5 {
                let a = random_elem(&mut s, m);
                if a.is_zero() {
                    continue;
                }
                let inv = a.flt_inverse(&irr).unwrap();
                assert_eq!(a.mul(&inv, &irr), F2mElement::one(m), "m = {m}");
            }
        }
    }

    /// Elements up to `INLINE_WORDS` words live inline and wider ones
    /// on the heap; arithmetic, equality and cloning must not care
    /// which.  Reduction is defined modulo any polynomial, irreducible
    /// or not, so the wide fields here need not be fields.
    #[test]
    fn inline_and_heap_storage_agree_across_the_boundary() {
        let mut s = 0xA5A5_5A5A_0F0F_F0F0u64;
        // 576 = 9 words (last inline), 577 = 10 words (first heap), 640.
        for m in [575u32, 576, 577, 640, 1031] {
            let irr = IrreduciblePoly {
                degree: m,
                low_terms: vec![0, 1, 3, 4],
            };
            let words = m.div_ceil(64) as usize;
            let heap = words > INLINE_WORDS;
            let e = F2mElement::zero(m);
            assert_eq!(matches!(e.bits, Words::Heap(_)), heap, "m = {m}");
            assert_eq!(e.raw_bits().len(), words, "m = {m}");
            for _ in 0..10 {
                let a = random_elem(&mut s, m);
                let b = random_elem(&mut s, m);
                assert_eq!(a.mul(&b, &irr), a.schoolbook_mul(&b, &irr), "mul, m = {m}");
                assert_eq!(
                    a.square(&irr),
                    a.schoolbook_mul(&a, &irr),
                    "square, m = {m}"
                );
                let c = a.clone();
                assert_eq!(c, a);
                assert_eq!(c.raw_bits(), a.raw_bits());
                let mut d = a.clone();
                d.add_assign(&b);
                assert_eq!(d, a.add(&b));
                assert_ne!(d, a, "b is non-zero with overwhelming probability");
            }
        }
    }

    /// The word-level fold against the bit-at-a-time reference, on raw
    /// vectors wider than any product, for the real field polynomials
    /// and for random dense tails with `deg r` up to `m − 1`, which take
    /// the most rounds.  Reduction modulo a polynomial is defined whether
    /// or not it is irreducible, so the random tails need not be.
    #[test]
    fn reduce_words_matches_bitwise_reduction() {
        let mut s = 0x0F1E_2D3C_4B5A_6978u64;
        let mut polys: Vec<IrreduciblePoly> = all_fields();
        // Sparse low tails that take the word-at-a-time path, including
        // m a multiple of 64 (no partial word) and one past it.
        for m in [65u32, 128, 129, 192, 200, 320] {
            polys.push(IrreduciblePoly {
                degree: m,
                low_terms: vec![0, 1, 2, 7],
            });
        }
        // deg r ≥ 64: word path, but r no longer fits one word.
        for m in [200u32, 256, 320] {
            polys.push(IrreduciblePoly {
                degree: m,
                low_terms: vec![0, 5, 70, m - 64],
            });
        }
        for m in [2u32, 7, 63, 64, 65, 127, 128, 129, 163, 200, 577] {
            for dense in [false, true] {
                let mut terms = vec![0u32];
                if dense {
                    // About half of all positions, always including m − 1.
                    terms.extend((1..m).filter(|&t| t == m - 1 || xorshift(&mut s) & 1 == 1));
                } else {
                    terms.push(1 + (xorshift(&mut s) % u64::from(m - 1)) as u32);
                }
                polys.push(IrreduciblePoly {
                    degree: m,
                    low_terms: terms,
                });
            }
        }
        for irr in &polys {
            let m = irr.degree;
            let words = (2 * m).div_ceil(64) as usize + 1;
            for rep in 0..30 {
                let mut v: Vec<u64> = (0..words).map(|_| xorshift(&mut s)).collect();
                if rep == 0 {
                    v.iter_mut().for_each(|w| *w = u64::MAX);
                }
                let mut want = v.clone();
                reduce_bitwise(&mut want, irr);
                // Each path on its own, wherever it applies, so the one a
                // given CPU dispatches to is not the only one tested.
                let mut chunked = v.clone();
                reduce_chunked(&mut chunked, irr);
                assert_eq!(
                    chunked, want,
                    "chunked, m = {m}, terms = {:?}",
                    irr.low_terms
                );
                let t_max = irr.low_terms.iter().copied().max().unwrap_or(0);
                if m >= t_max + 64 {
                    let mut terms = v.clone();
                    fold_words_terms(&mut terms, m as usize, &irr.low_terms);
                    assert_eq!(
                        terms, want,
                        "term fold, m = {m}, terms = {:?}",
                        irr.low_terms
                    );
                    #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
                    if t_max < 64 && has_hw_clmul() {
                        let r = irr.low_terms.iter().fold(0u64, |a, &t| a | (1u64 << t));
                        let mut folded = v.clone();
                        unsafe { fold_words_clmul_hw(&mut folded, m as usize, r) };
                        assert_eq!(
                            folded, want,
                            "clmul fold, m = {m}, terms = {:?}",
                            irr.low_terms
                        );
                    }
                }
                reduce_words(&mut v, irr);
                assert_eq!(v, want, "m = {m}, terms = {:?}", irr.low_terms);
            }
        }
    }

    /// `Debug` prints the same shape the old `Vec<u64>` field produced,
    /// so logged and snapshotted output does not change.
    #[test]
    fn debug_output_is_unchanged() {
        let e = F2mElement::from_bit_positions(&[0, 3], 8);
        assert_eq!(format!("{e:?}"), "F2mElement { bits: [9], m: 8 }");
    }

    /// The software carry-less multiply (the fallback on CPUs without
    /// `pclmulqdq`) is a correct `64 × 64 → 128` product.
    #[test]
    fn soft_clmul_matches_shift_xor() {
        let mut s = 0x1357_9BDF_2468_ACE0u64;
        for _ in 0..2000 {
            let a = xorshift(&mut s);
            let b = xorshift(&mut s);
            let mut want = 0u128;
            for i in 0..64 {
                if (a >> i) & 1 == 1 {
                    want ^= (b as u128) << i;
                }
            }
            let (lo, hi) = clmul64_soft(a, b);
            assert_eq!(((hi as u128) << 64) | lo as u128, want);
        }
    }

    /// Bits are correctly reduced: a degree-2m polynomial gets
    /// folded down to degree < m.
    #[test]
    fn reduction_works_at_boundary() {
        let irr = IrreduciblePoly::deg_8(); // x⁸ + x⁴ + x³ + x + 1
                                            // a = z⁵, b = z⁵.  a·b = z¹⁰ = z² · z⁸ = z² · (z⁴ + z³ + z + 1)
                                            //                       = z⁶ + z⁵ + z³ + z².
        let a = F2mElement::from_bit_positions(&[5], 8);
        let b = a.clone();
        let p = a.schoolbook_mul(&b, &irr);
        let expected = F2mElement::from_bit_positions(&[2, 3, 5, 6], 8);
        assert_eq!(p, expected);
    }
}
