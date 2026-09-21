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

/// An element of `F_{2^m}`: a polynomial of degree `< m` over `F_2`.
/// Stored as a packed bit-vector; bit `i` represents the coefficient
/// of `z^i`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct F2mElement {
    /// `bits[w] >> b` represents the coefficient of `z^(64·w + b)`.
    bits: Vec<u64>,
    /// Number of bits considered (≥ irreducible's degree; we keep
    /// the result reduced so high bits are always 0).
    m: u32,
}

impl F2mElement {
    /// Zero element.
    pub fn zero(m: u32) -> Self {
        let n_words = m.div_ceil(64) as usize;
        Self {
            bits: vec![0u64; n_words.max(1)],
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
        for (a, b) in out.bits.iter_mut().zip(&other.bits) {
            *a ^= *b;
        }
        out
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
        reduce(&mut prod, irreducible);
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
    /// the end via `reduce`.
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

        reduce(&mut combined, irreducible);
        let mut out = Self::zero(m);
        for (i, w) in combined.iter().enumerate().take(out.bits.len()) {
            out.bits[i] = *w;
        }
        out.mask_in_place();
        out
    }

    /// Convenience wrapper picking schoolbook or Karatsuba based on `m`.
    pub fn mul(&self, other: &Self, irreducible: &IrreduciblePoly) -> Self {
        self.karatsuba_mul(other, irreducible)
    }

    /// `self²`.  In `F_{2^m}` squaring is linear: bit `i` of `self`
    /// goes to bit `2i` of the result, other bits zero.  Then
    /// reduce mod `m(z)`.
    pub fn square(&self, irreducible: &IrreduciblePoly) -> Self {
        let m = self.m;
        let n_words = (2 * m).div_ceil(64) as usize + 1;
        let mut sq = vec![0u64; n_words];
        for i in 0..m {
            let w_i = (i / 64) as usize;
            let b_i = i % 64;
            if w_i < self.bits.len() && (self.bits[w_i] >> b_i) & 1 == 1 {
                let pos = 2 * i;
                let w_o = (pos / 64) as usize;
                let b_o = pos % 64;
                if w_o < sq.len() {
                    sq[w_o] ^= 1u64 << b_o;
                }
            }
        }
        reduce(&mut sq, irreducible);
        let mut out = Self::zero(m);
        for (i, w) in sq.iter().enumerate().take(out.bits.len()) {
            out.bits[i] = *w;
        }
        out.mask_in_place();
        out
    }

    /// `self^(2^k)` — `k` repeated squarings.
    pub fn square_k_times(&self, k: u32, irreducible: &IrreduciblePoly) -> Self {
        let mut acc = self.clone();
        for _ in 0..k {
            acc = acc.square(irreducible);
        }
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
        let n_words = m.div_ceil(64) as usize;
        let mut bits = vec![0u64; n_words.max(1)];
        for (i, w) in words.iter().enumerate().take(bits.len()) {
            bits[i] = *w;
        }
        let mut e = Self { bits, m };
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
    let n = a.len() + b.len();
    let mut out = vec![0u64; n];
    for (i, a_w) in a.iter().enumerate() {
        for bit in 0..64u32 {
            if (a_w >> bit) & 1 == 1 {
                add_shifted(&mut out, b, (i as u32) * 64 + bit);
            }
        }
    }
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
fn reduce(value: &mut [u64], irreducible: &IrreduciblePoly) {
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
