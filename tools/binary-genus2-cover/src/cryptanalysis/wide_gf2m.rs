//! `GF(2^n)` for `n ≤ 127`, one element per `u128`: the field under the
//! wide Koblitz curves the m = 83 gate needs (AGENTS.md §8a), where the
//! one-word [`Gf2`](crate::cryptanalysis::semaev_decomp::Gf2) stops at 63.
//!
//! Polynomial basis, bit `i` the coefficient of `z^i`.  A product is the
//! 256-bit carry-less product of two `u128`s (Karatsuba over three 64-bit
//! carry-less multiplies: `PCLMULQDQ` on x86-64, `PMULL` on AArch64, a
//! bit-serial loop elsewhere), folded back through the modulus's low
//! terms.  Inversion is Itoh–Tsujii; a batch is inverted with one
//! inversion by Montgomery's trick, as the one-word field does it.
//!
//! The tests check every operation against the repository's
//! arbitrary-width [`F2mElement`](crate::binary_ecc::F2mElement) on the
//! m = 83 modulus `z^83 + z^45 + z^2 + z + 1`.

use crate::binary_ecc::IrreduciblePoly;

/// The field `GF(2)[z] / (f)` with `deg f = n ≤ 127`.
#[derive(Clone, Debug)]
pub struct WideGf2 {
    pub n: u32,
    /// The exponents of `f` below `z^n`, ascending.
    low_terms: Vec<u32>,
    mask: u128,
    has_clmul: bool,
}

/// The bit-serial 64 × 64 → 128 carry-less product.
fn clmul_portable(a: u64, b: u64) -> u128 {
    let mut acc = 0u128;
    let a = a as u128;
    let mut b = b;
    let mut i = 0;
    while b != 0 {
        if b & 1 == 1 {
            acc ^= a << i;
        }
        b >>= 1;
        i += 1;
    }
    acc
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn clmul_hw(a: u64, b: u64) -> u128 {
    use std::arch::x86_64::*;
    let x = _mm_set_epi64x(0, a as i64);
    let y = _mm_set_epi64x(0, b as i64);
    let z = _mm_clmulepi64_si128::<0x00>(x, y);
    let lo = _mm_cvtsi128_si64(z) as u64;
    let hi = _mm_cvtsi128_si64(_mm_srli_si128::<8>(z)) as u64;
    ((hi as u128) << 64) | (lo as u128)
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn clmul_hw(a: u64, b: u64) -> u128 {
    std::arch::aarch64::vmull_p64(a, b)
}

/// `(lo, hi) << s` for a 256-bit value held as two halves, `s < 128`.
#[inline(always)]
fn shl256(lo: u128, hi: u128, s: u32) -> (u128, u128) {
    if s == 0 {
        (lo, hi)
    } else {
        (lo << s, (hi << s) | (lo >> (128 - s)))
    }
}

impl WideGf2 {
    /// The field of `irr`, for `2 ≤ n ≤ 127`.
    pub fn new(irr: &IrreduciblePoly) -> Self {
        #[cfg(target_arch = "x86_64")]
        let has_clmul = std::arch::is_x86_feature_detected!("pclmulqdq");
        #[cfg(target_arch = "aarch64")]
        let has_clmul = std::arch::is_aarch64_feature_detected!("aes");
        #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
        let has_clmul = false;
        Self::with_kernel(irr, has_clmul)
    }

    /// The same field with the multiply chosen by the caller (`has_clmul`
    /// must be false unless the CPU has the instruction), so a test can
    /// compare both kernels on one machine.
    pub fn with_kernel(irr: &IrreduciblePoly, has_clmul: bool) -> Self {
        let n = irr.degree;
        assert!(
            (2..=127).contains(&n),
            "WideGf2 handles 2 ≤ n ≤ 127, not {n}"
        );
        let mut low_terms = irr.low_terms.clone();
        low_terms.sort_unstable();
        low_terms.dedup();
        assert!(
            low_terms.iter().all(|&t| t < n),
            "a low term at or above z^n"
        );
        Self {
            n,
            low_terms,
            mask: (1u128 << n) - 1,
            has_clmul,
        }
    }

    /// The modulus with its leading term, as a word.
    pub fn modulus_bits(&self) -> u128 {
        self.low_terms
            .iter()
            .fold(1u128 << self.n, |acc, &t| acc | (1u128 << t))
    }

    /// Which carry-less kernel this instance uses.
    pub fn kernel_name(&self) -> &'static str {
        if !self.has_clmul {
            "portable"
        } else if cfg!(target_arch = "x86_64") {
            "pclmulqdq"
        } else {
            "pmull"
        }
    }

    #[inline(always)]
    fn clmul64(&self, a: u64, b: u64) -> u128 {
        #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
        if self.has_clmul {
            // SAFETY: `has_clmul` is set only when the CPU reports the
            // instruction (or by a caller bound to the same rule).
            return unsafe { clmul_hw(a, b) };
        }
        clmul_portable(a, b)
    }

    /// The 256-bit carry-less product `a·b`, unreduced, as `(lo, hi)`.
    #[inline(always)]
    pub fn mul_unreduced(&self, a: u128, b: u128) -> (u128, u128) {
        let (a0, a1) = (a as u64, (a >> 64) as u64);
        let (b0, b1) = (b as u64, (b >> 64) as u64);
        let lo = self.clmul64(a0, b0);
        let hi = self.clmul64(a1, b1);
        let mid = self.clmul64(a0 ^ a1, b0 ^ b1) ^ lo ^ hi;
        (lo ^ (mid << 64), hi ^ (mid >> 64))
    }

    /// Reduce a value below `z^{2n−1}` modulo `f`.
    #[inline(always)]
    pub fn reduce(&self, mut lo: u128, mut hi: u128) -> u128 {
        let n = self.n;
        loop {
            // The part at and above z^n, shifted down: below 2^(n−1) < 2^127.
            let top = if n == 128 {
                hi
            } else {
                (lo >> n) | (hi << (128 - n))
            };
            if top == 0 {
                return lo;
            }
            lo &= self.mask;
            hi = 0;
            for &t in &self.low_terms {
                let (l, h) = shl256(top, 0, t);
                lo ^= l;
                hi ^= h;
            }
        }
    }

    #[inline(always)]
    pub fn mul(&self, a: u128, b: u128) -> u128 {
        let (lo, hi) = self.mul_unreduced(a, b);
        self.reduce(lo, hi)
    }

    #[inline(always)]
    pub fn sqr(&self, a: u128) -> u128 {
        self.mul(a, a)
    }

    /// `a^{2^k}`.
    pub fn sqr_k(&self, mut a: u128, k: u32) -> u128 {
        for _ in 0..k {
            a = self.sqr(a);
        }
        a
    }

    /// `a^{-1}` by Itoh–Tsujii: `a^{-1} = (a^{2^{n−1} − 1})^2`.  `0` maps
    /// to `0`.
    pub fn inv(&self, a: u128) -> u128 {
        if a == 0 {
            return 0;
        }
        // beta(k) = a^{2^k − 1}; build beta(n − 1) along the bits of n − 1.
        let e = self.n - 1;
        let bits = 32 - e.leading_zeros();
        let mut c = a;
        let mut k = 1u32;
        for i in (0..bits - 1).rev() {
            c = self.mul(c, self.sqr_k(c, k));
            k *= 2;
            if (e >> i) & 1 == 1 {
                c = self.mul(self.sqr(c), a);
                k += 1;
            }
        }
        debug_assert_eq!(k, e);
        self.sqr(c)
    }

    /// Invert every nonzero entry of `xs` in place with one inversion
    /// (Montgomery's trick); zeros stay zero.  `scratch` is reused.
    pub fn batch_inv(&self, xs: &mut [u128], scratch: &mut Vec<u128>) {
        scratch.clear();
        let mut acc = 1u128;
        for &x in xs.iter() {
            scratch.push(acc);
            if x != 0 {
                acc = self.mul(acc, x);
            }
        }
        let mut inv = self.inv(acc);
        for i in (0..xs.len()).rev() {
            let x = xs[i];
            if x == 0 {
                continue;
            }
            xs[i] = self.mul(inv, scratch[i]);
            inv = self.mul(inv, x);
        }
    }

    /// The absolute trace `Tr(a) = Σ a^{2^i}`, `0` or `1`.
    pub fn trace(&self, a: u128) -> u128 {
        let mut t = a;
        let mut acc = a;
        for _ in 1..self.n {
            t = self.sqr(t);
            acc ^= t;
        }
        acc
    }

    /// A root `z` of `z² + z = c` for odd `n` and `Tr(c) = 0`: the
    /// half-trace `Σ_{i ≤ (n−1)/2} c^{4^i}`.  `None` otherwise.
    pub fn solve_quadratic(&self, c: u128) -> Option<u128> {
        if self.n.is_multiple_of(2) || self.trace(c) != 0 {
            return None;
        }
        let mut t = c;
        let mut acc = c;
        for _ in 0..(self.n - 1) / 2 {
            t = self.sqr(self.sqr(t));
            acc ^= t;
        }
        debug_assert_eq!(self.sqr(acc) ^ acc, c);
        Some(acc)
    }

    pub fn mask(&self) -> u128 {
        self.mask
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::F2mElement;
    use num_bigint::BigUint;

    /// AGENTS.md §8a's m = 83 modulus.
    fn m83() -> IrreduciblePoly {
        IrreduciblePoly {
            degree: 83,
            low_terms: vec![45, 2, 1, 0],
        }
    }

    fn lib(v: u128, n: u32) -> F2mElement {
        F2mElement::from_biguint(&BigUint::from(v), n)
    }

    fn back(e: &F2mElement) -> u128 {
        let bits = e.raw_bits();
        bits.first().copied().unwrap_or(0) as u128
            | ((bits.get(1).copied().unwrap_or(0) as u128) << 64)
    }

    fn samples(n: u32) -> Vec<u128> {
        let mask = (1u128 << n) - 1;
        let mut s = 0x0123_4567_89ab_cdef_fedc_ba98_7654_3210u128;
        let mut out = vec![0, 1, 2, mask, 1u128 << (n - 1)];
        for _ in 0..200 {
            s = s
                .wrapping_mul(0x2360_ed05_1fc6_5da4_4385_df64_9fcc_f645)
                .wrapping_add(0x5851_f42d_4c95_7f2d);
            out.push((s ^ (s >> 61)) & mask);
        }
        out
    }

    #[test]
    fn mul_matches_the_library_field_on_both_kernels() {
        let irr = m83();
        let portable = WideGf2::with_kernel(&irr, false);
        let native = WideGf2::new(&irr);
        let xs = samples(83);
        for (i, &a) in xs.iter().enumerate() {
            let b = xs[(i * 7 + 3) % xs.len()];
            let want = back(&lib(a, 83).mul(&lib(b, 83), &irr));
            assert_eq!(portable.mul(a, b), want, "portable a={a:x} b={b:x}");
            assert_eq!(
                native.mul(a, b),
                want,
                "{} a={a:x} b={b:x}",
                native.kernel_name()
            );
        }
    }

    #[test]
    fn mul_matches_the_library_at_the_width_limits() {
        for irr in [
            IrreduciblePoly {
                degree: 127,
                low_terms: vec![1, 0],
            },
            IrreduciblePoly {
                degree: 67,
                low_terms: vec![5, 2, 1, 0],
            },
        ] {
            let f = WideGf2::new(&irr);
            let xs = samples(irr.degree);
            for (i, &a) in xs.iter().enumerate() {
                let b = xs[(i * 5 + 1) % xs.len()];
                assert_eq!(
                    f.mul(a, b),
                    back(&lib(a, irr.degree).mul(&lib(b, irr.degree), &irr))
                );
            }
        }
    }

    #[test]
    fn inverses_and_batches_invert() {
        let f = WideGf2::new(&m83());
        let mut xs = samples(83);
        for &x in &xs {
            if x != 0 {
                assert_eq!(f.mul(x, f.inv(x)), 1, "x={x:x}");
            }
        }
        let orig = xs.clone();
        let mut scratch = Vec::new();
        f.batch_inv(&mut xs, &mut scratch);
        for (x, y) in orig.iter().zip(&xs) {
            if *x == 0 {
                assert_eq!(*y, 0);
            } else {
                assert_eq!(f.mul(*x, *y), 1);
            }
        }
    }

    #[test]
    fn half_trace_solves_artin_schreier() {
        let f = WideGf2::new(&m83());
        let mut solved = 0;
        for c in samples(83) {
            match f.solve_quadratic(c) {
                Some(z) => {
                    assert_eq!(f.sqr(z) ^ z, c);
                    solved += 1;
                }
                None => assert_eq!(f.trace(c), 1),
            }
        }
        assert!(solved > 50, "about half of random c have trace 0: {solved}");
    }

    #[test]
    fn frobenius_has_order_n() {
        let f = WideGf2::new(&m83());
        for x in samples(83) {
            assert_eq!(f.sqr_k(x, 83), x);
        }
    }
}
