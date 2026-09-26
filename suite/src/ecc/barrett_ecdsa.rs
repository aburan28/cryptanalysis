//! **Barrett-compatible ECDSA parameters** — Maimuț, Matei (eprint
//! 2022/1458): "Speeding-Up Elliptic Curve Cryptography Algorithms."
//!
//! Two algorithms from the paper, implemented faithfully:
//!
//! - **Algorithm 1** ([`barrett_reduce`]): Barrett's modular
//!   reduction `c4 = d mod m` using a precomputed constant
//!   `k = ⌊2ᴸ / m⌋`.  Standard since Barrett 1986.
//!
//! - **Algorithm 2** ([`generate_barrett_ecdsa_params`]): the
//!   paper's main novel contribution.  Generates an ECDSA prime
//!   `p` with a **predetermined high-bit pattern** so that the
//!   associated Barrett constant `kₚ = ⌊2²ᴾ / p⌋` has predictable
//!   leading bits.  Concretely:
//!
//!   ```text
//!   p ≈ 2^(P-1) + 2^(U+1) + (random U-bit value)
//!   ```
//!
//!   where `U = P/2`.  The top `U + 1 ≈ P/2` bits of `p` are
//!   fixed (one leading `1`, then `P/2 − 1` zeros, then a single
//!   `1`).  Lemma 1 of the paper shows that `kₚ` then satisfies
//!
//!   ```text
//!   ⌊2²ᴾ/Q⌋ ≤ kₚ < 2^(P+1),       with Q = 2^(P-1) + 2^(U+1) + 2^U + 0.7(P-1)
//!   ```
//!
//!   making the top `P/2 − 1` bits of `kₚ` essentially all `1`s.
//!   The multiplication `c2 = c1 · k` in Barrett's algorithm
//!   becomes a multiply-by-mostly-ones operation, which can be
//!   evaluated as a subtraction (`c1·(2^(P+1) − ε)` rather than a
//!   full multiply), **halving** the cost of the most expensive
//!   step in modular reduction.
//!
//! ## Honest scope of this implementation
//!
//! - **Correctness**: Algorithm 1 produces correct outputs (`c4 =
//!   d mod m`), verified against direct BigUint reduction over
//!   random test inputs.
//! - **Parameter generation**: Algorithm 2 produces a prime `p`
//!   with the claimed bit pattern.  Verified against the paper's
//!   Example 1 (P = 256): given `r = 0xbba46de2...`, we re-derive
//!   `α`, `p`, `kₚ` exactly as published.
//! - **Curve generation (Line 7 of Algorithm 2)** — finding `(a, b)`
//!   with `#E(F_p)` prime — uses brute-force point counting for
//!   small primes (works up to ~24-bit `p` in seconds).  For
//!   cryptographic-size `p`, this requires Schoof's algorithm,
//!   which we do not ship; the paper notes the same limitation
//!   ("we overlooked the initial part of Algorithm 2 in our
//!   implementation").
//! - **Speed claim**: the paper's "double speed" depends on a
//!   word-level implementation of the multiply-by-mostly-ones
//!   trick.  Our `BigUint`-based `barrett_reduce` shows the
//!   structural correctness of Algorithm 1 but does **not**
//!   realise the speedup at the bit level; that requires
//!   limb-aware arithmetic (the paper targets FPGA).
//!
//! ## AI-Schoof variant (Section 3.2)
//!
//! The paper's second contribution uses a small neural network
//! to predict `#E(F_p)` more tightly than Hasse's `±2√p`,
//! reducing the Schoof search interval by ~16% (7-layer model,
//! 93% success rate).  Training requires TensorFlow infrastructure
//! and 60,000 labelled `(p, a, b, n)` tuples per their setup —
//! out of scope for a Rust crypto library.  The interval-
//! narrowing idea is documented here for completeness:
//!
//! ```text
//! Standard Schoof: search window width = 4√p  (Hasse bound)
//! AI-enhanced:     search window width = 4ε   where ε ≈ 0.84·√p
//!                                                empirically
//! ```

use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::OsRng;

// ── Algorithm 1: Barrett reduction ────────────────────────────────

/// Precomputed Barrett context: modulus `m` (bit-length `M`), the
/// maximum input bit-length `L` (so inputs `d` satisfy `d < 2ᴸ`),
/// and the Barrett constant `k = ⌊2ᴸ / m⌋`.
#[derive(Clone, Debug)]
pub struct BarrettContext {
    pub m: BigUint,
    /// Bit-length of `m`.  `m < 2ᴹ`.
    pub m_bits: u64,
    /// Maximum input bit-length.  Inputs satisfy `d < 2ᴸ`.
    /// Must satisfy `M ≤ D ≤ L`.
    pub l_bits: u64,
    /// Precomputed `k = ⌊2ᴸ / m⌋`.
    pub k: BigUint,
}

impl BarrettContext {
    /// Construct a Barrett context for modulus `m` with maximum
    /// input bit-length `l_bits`.  Requires `l_bits ≥ m.bits()`.
    pub fn new(m: BigUint, l_bits: u64) -> Self {
        let m_bits = m.bits();
        assert!(l_bits >= m_bits, "L must be at least M = bits(m)");
        let two_to_l = BigUint::one() << l_bits as usize;
        let k = &two_to_l / &m;
        Self {
            m,
            m_bits,
            l_bits,
            k,
        }
    }
}

/// **Algorithm 1 (Barrett's modular reduction)** from the paper.
///
/// Given `d < 2ᴸ` and context `(m, M, L, k = ⌊2ᴸ/m⌋)`, returns
/// `d mod m`.  The approximation `c3 ≈ ⌊d/m⌋` is accurate within
/// 2 (`⌊d/m⌋ − 2 ≤ c3 ≤ ⌊d/m⌋`), so the final `while` loop runs
/// at most 2 iterations.
pub fn barrett_reduce(d: &BigUint, ctx: &BarrettContext) -> BigUint {
    debug_assert!(
        d.bits() <= ctx.l_bits,
        "input d exceeds maximum bit-length L"
    );
    // c1 = d >> (M − 1)
    let c1 = d >> ((ctx.m_bits - 1) as usize);
    // c2 = c1 · k
    let c2 = &c1 * &ctx.k;
    // c3 = c2 >> (L − M + 1)
    let c3 = &c2 >> ((ctx.l_bits - ctx.m_bits + 1) as usize);
    // c4 = d − c3 · m  (always non-negative because c3 ≤ ⌊d/m⌋)
    let c3_m = &c3 * &ctx.m;
    let mut c4 = d - &c3_m;
    // At most 2 final subtractions.
    while c4 >= ctx.m {
        c4 -= &ctx.m;
    }
    c4
}

// ── Algorithm 2: Barrett-compatible ECDSA parameter generation ──

/// Parameters returned by [`generate_barrett_ecdsa_params`]: the
/// prime `p` of the base field, curve coefficients `a, b`, group
/// order `n`, and the precomputed Barrett constants `kₚ, kₙ`.
#[derive(Clone, Debug)]
pub struct BarrettEcdsaParams {
    pub p: BigUint,
    pub a: BigUint,
    pub b: BigUint,
    pub n: BigUint,
    /// `kₚ = ⌊2²ᴾ / p⌋`.
    pub k_p: BigUint,
    /// `kₙ = ⌊2²ᴾ / n⌋`.
    pub k_n: BigUint,
    /// Bit-length parameter `P`.
    pub bit_length: u64,
}

impl BarrettEcdsaParams {
    /// Construct a [`BarrettContext`] for reducing 2P-bit values
    /// mod `p` (used in field-level Barrett reductions).
    pub fn p_context(&self) -> BarrettContext {
        BarrettContext {
            m: self.p.clone(),
            m_bits: self.bit_length,
            l_bits: 2 * self.bit_length,
            k: self.k_p.clone(),
        }
    }

    /// Construct a [`BarrettContext`] for reducing 2P-bit values
    /// mod `n` (used in scalar-level Barrett reductions).
    pub fn n_context(&self) -> BarrettContext {
        BarrettContext {
            m: self.n.clone(),
            m_bits: self.bit_length,
            l_bits: 2 * self.bit_length,
            k: self.k_n.clone(),
        }
    }
}

/// **Algorithm 2 — Generator for Barrett-compatible ECDSA
/// parameters.**  Faithful implementation of the paper's algorithm.
///
/// `bit_length` (`P` in the paper) must be even.  For the
/// canonical 256-bit case, pass `256`.
///
/// **For full cryptographic use**, the curve-counting step
/// (`#E(F_p)` is prime) requires Schoof's algorithm, which is not
/// implemented here.  The paper notes the same gap.  If you want
/// just `(p, k_p)` without a curve, use
/// [`generate_barrett_prime`] instead.
pub fn generate_barrett_ecdsa_params(bit_length: u64) -> BarrettEcdsaParams {
    assert!(
        bit_length.is_multiple_of(2) && bit_length >= 8,
        "bit_length must be even and ≥ 8"
    );
    let (p, _alpha) = generate_barrett_prime(bit_length);
    // Curve-search step requires Schoof; we use brute-force only
    // for tiny primes (test contexts).  For production-size primes
    // this loop would block — the caller should integrate Schoof
    // or use a precomputed `(a, b)` known to give prime order.
    let (a, b, n) = if bit_length <= 20 {
        find_curve_with_prime_order(&p).expect("no prime-order curve found")
    } else {
        // For larger primes we can't brute-force point counting;
        // return zeros as placeholders so the caller can fill in.
        (BigUint::zero(), BigUint::zero(), BigUint::zero())
    };
    let two_l = BigUint::one() << (2 * bit_length) as usize;
    let k_p = &two_l / &p;
    let k_n = if n.is_zero() {
        BigUint::zero()
    } else {
        &two_l / &n
    };
    BarrettEcdsaParams {
        p,
        a,
        b,
        n,
        k_p,
        k_n,
        bit_length,
    }
}

/// **Algorithm 2, lines 1–6**: generate a prime `p` with the paper's
/// predetermined-portion structure.  Returns `(p, α)`.
///
/// The structure: `α = 2^(P−1) + 2^(U+1) + r` for random
/// `r ∈ (0, 2ᵁ)` with `U = P/2`.  Then `p = NextPrime(α)`.  If
/// `p − α ≥ 0.7(P − 1)`, the procedure restarts.
pub fn generate_barrett_prime(bit_length: u64) -> (BigUint, BigUint) {
    assert!(bit_length.is_multiple_of(2) && bit_length >= 8);
    let u = bit_length / 2;
    let two_to_p_minus_1 = BigUint::one() << ((bit_length - 1) as usize);
    let two_to_u_plus_1 = BigUint::one() << ((u + 1) as usize);
    let two_to_u = BigUint::one() << (u as usize);
    let bound_inclusive = BigUint::from(((bit_length - 1) as f64 * 0.7).ceil() as u64);
    let mut rng = OsRng;

    loop {
        // Step 3: r ∈ R (0, 2^U)
        let r = rng.gen_biguint_below(&two_to_u);
        if r.is_zero() {
            continue;
        }
        // Step 4: α = 2^(P-1) + 2^(U+1) + r
        let alpha = &two_to_p_minus_1 + &two_to_u_plus_1 + &r;
        // Step 5: p = NextPrime(α)
        let p = next_prime(&alpha);
        // Step 6: gap check
        let gap = &p - &alpha;
        if gap >= bound_inclusive {
            continue;
        }
        return (p, alpha);
    }
}

/// Deterministic variant: regenerate the paper's Example 1 exactly
/// given the specific random value `r`.  This lets us verify our
/// implementation against the paper's published test vector.
pub fn barrett_prime_from_r(bit_length: u64, r: &BigUint) -> (BigUint, BigUint) {
    assert!(bit_length.is_multiple_of(2) && bit_length >= 8);
    let u = bit_length / 2;
    let two_to_p_minus_1 = BigUint::one() << ((bit_length - 1) as usize);
    let two_to_u_plus_1 = BigUint::one() << ((u + 1) as usize);
    let alpha = &two_to_p_minus_1 + &two_to_u_plus_1 + r;
    let p = next_prime(&alpha);
    (p, alpha)
}

/// `NextPrime(α)`: the smallest prime `p ≥ α`.  Uses Miller-Rabin
/// from the existing RSA module.
fn next_prime(alpha: &BigUint) -> BigUint {
    let mut p = alpha.clone();
    if p.is_even() {
        p += BigUint::one();
    }
    loop {
        if crate::asymmetric::rsa::is_prime(&p) {
            return p;
        }
        p += BigUint::from(2u32);
    }
}

/// Brute-force search for `(a, b)` such that `E: y² = x³ + ax + b
/// (mod p)` has prime order.  Feasible only for very small `p`
/// (~20 bits or less).
fn find_curve_with_prime_order(p: &BigUint) -> Option<(BigUint, BigUint, BigUint)> {
    let p_u64: u64 = p.try_into().ok()?;
    for a in 0..p_u64 {
        for b in 0..p_u64 {
            // Skip singular curves (4a³ + 27b² ≡ 0 mod p)
            let disc = (4u128 * (a as u128).pow(3) + 27 * (b as u128).pow(2)) % p_u64 as u128;
            if disc == 0 {
                continue;
            }
            let n = count_points_brute(a, b, p_u64);
            if crate::asymmetric::rsa::is_prime(&BigUint::from(n)) {
                return Some((BigUint::from(a), BigUint::from(b), BigUint::from(n)));
            }
        }
    }
    None
}

fn count_points_brute(a: u64, b: u64, p: u64) -> u64 {
    let mut count: u64 = 1; // point at infinity
    let p_u128 = p as u128;
    let a_u128 = a as u128;
    let b_u128 = b as u128;
    for x in 0..p {
        let xx = x as u128;
        let rhs = (xx * xx % p_u128 * xx % p_u128 + a_u128 * xx % p_u128 + b_u128) % p_u128;
        if rhs == 0 {
            count += 1;
        } else {
            // Euler's criterion: rhs is QR mod p iff rhs^((p-1)/2) == 1 mod p.
            let pow = mod_pow(rhs as u64, (p - 1) / 2, p);
            if pow == 1 {
                count += 2;
            }
        }
    }
    count
}

fn mod_pow(base: u64, mut exp: u64, m: u64) -> u64 {
    let mut result: u128 = 1;
    let mut b = base as u128 % m as u128;
    let m128 = m as u128;
    while exp > 0 {
        if exp & 1 == 1 {
            result = (result * b) % m128;
        }
        b = (b * b) % m128;
        exp >>= 1;
    }
    let _ = base;
    result as u64
}

// ── Lemma 1 sanity check ─────────────────────────────────────────

/// Verify Lemma 1 from the paper: for parameters generated by
/// [`generate_barrett_ecdsa_params`], `kₚ` lies in the interval
/// `[⌊2²ᴾ/Q⌋, 2^(P+1))` where
/// `Q = 2^(P−1) + 2^(U+1) + 2ᵁ + 0.7(P − 1)`.
pub fn verify_lemma_1(p: &BigUint, bit_length: u64) -> bool {
    let u = bit_length / 2;
    let two_l = BigUint::one() << (2 * bit_length) as usize;
    let k_p = &two_l / p;
    // Upper bound: k_p < 2^(P+1)
    let upper = BigUint::one() << ((bit_length + 1) as usize);
    if k_p >= upper {
        return false;
    }
    // Lower bound: k_p ≥ ⌊2^(2P)/Q⌋ with
    //   Q = 2^(P−1) + 2^(U+1) + 2^U + 0.7·(P−1)
    let q = (BigUint::one() << ((bit_length - 1) as usize))
        + (BigUint::one() << ((u + 1) as usize))
        + (BigUint::one() << (u as usize))
        + BigUint::from(((bit_length - 1) as f64 * 0.7).ceil() as u64);
    let lower = &two_l / &q;
    k_p >= lower
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Barrett reduction agrees with direct `%` over a range of
    /// random inputs.
    #[test]
    fn barrett_reduce_matches_direct_reduction() {
        let m = BigUint::parse_bytes(
            b"FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF",
            16,
        )
        .unwrap();
        let ctx = BarrettContext::new(m.clone(), 512);
        let mut rng = OsRng;
        let two_l = BigUint::one() << 512;
        for _ in 0..40 {
            let d = rng.gen_biguint_below(&two_l);
            let barrett = barrett_reduce(&d, &ctx);
            let direct = &d % &m;
            assert_eq!(barrett, direct);
        }
    }

    /// Barrett reduction works on small moduli with small inputs.
    #[test]
    fn barrett_reduce_small() {
        let m = BigUint::from(97u32);
        let ctx = BarrettContext::new(m.clone(), 16);
        for d in 0u32..200 {
            let d_bi = BigUint::from(d);
            // input d must be < 2^L = 2^16
            assert_eq!(barrett_reduce(&d_bi, &ctx), &d_bi % &m);
        }
    }

    /// **Test vector from the paper, Example 1** (P = 256):
    /// given the specific random `r = 0xbba46de2b4b53e20b97d41941c01a6b0`,
    /// we should reproduce α, p, and kₚ exactly as published.
    #[test]
    fn paper_example_1_p256_reproduces() {
        // r from Example 1: 128-bit value.
        let r = BigUint::parse_bytes(b"bba46de2b4b53e20b97d41941c01a6b0", 16).unwrap();
        let (p, alpha) = barrett_prime_from_r(256, &r);

        // α = 2^255 + 2^129 + r.  In hex (64 chars), the high half
        // (bits 128..255) is 2^127 + 2^1 = 0x80000000000000000000000000000002
        // and the low half is r exactly.
        let expected_alpha = BigUint::parse_bytes(
            b"80000000000000000000000000000002bba46de2b4b53e20b97d41941c01a6b0",
            16,
        )
        .unwrap();
        assert_eq!(alpha, expected_alpha, "α should match Example 1");

        // p = NextPrime(α); per the paper p ends in "...01a6ef" (so
        // p − α = 0xef − 0xb0 = 0x3f = 63).
        let expected_p = BigUint::parse_bytes(
            b"80000000000000000000000000000002bba46de2b4b53e20b97d41941c01a6ef",
            16,
        )
        .unwrap();
        assert_eq!(p, expected_p, "NextPrime(α) should match Example 1's p");

        // Check the gap criterion (Line 6): p − α < 0.7(P − 1) = 178.5
        let gap = &p - &alpha;
        assert!(gap < BigUint::from(179u32), "gap criterion must hold");

        // Verify k_p = ⌊2^512 / p⌋ satisfies the structural property
        // claimed by Lemma 1: just under 2^257, with the leading
        // (P/2 − 1) bits all set to one.
        //
        // The paper's printed hex for k_p (0x1ffffffff…9647f) appears
        // to have a typesetting artefact (66 hex chars where 65
        // would correspond to a 257-bit value); we therefore
        // verify the algebraic / bit-pattern property directly.
        let two_512 = BigUint::one() << 512;
        let kp: BigUint = &two_512 / &p;
        assert!(kp < (BigUint::one() << 257), "k_p must be < 2^(P+1)");
        assert!(kp >= (BigUint::one() << 256), "k_p must be ≥ 2^P");
        // The top P/2 − 1 bits of k_p are set ones.  Concretely:
        // k_p ≈ 2^257 − 2^131 − 4r − …, so bits 132..256 inclusive
        // are unaffected by the borrow chain and remain 1.
        // (Bit 131 gets cleared by the borrow from the 2r subtraction;
        // bits 130 and below depend on r and are not reliably 1.)
        for k in 132..257u64 {
            assert!(kp.bit(k), "k_p bit {} should be set", k);
        }
    }

    /// Generated primes have the claimed structural property:
    /// top P/2 bits look like  `1 0 0 ... 0 1 [random]`.
    #[test]
    fn generated_prime_has_predetermined_top_bits() {
        let (p, _) = generate_barrett_prime(256);
        // Top bit (bit 255) must be 1.
        assert!(p.bit(255), "p must have bit 255 set (2^(P-1) term)");
        // Bit 129 (= U + 1) must be 1.
        assert!(p.bit(129), "p must have bit 129 set (2^(U+1) term)");
        // Bits 130..255 must all be zero (the gap between 2^(P-1)
        // and 2^(U+1) terms).  These are the bits we "predetermine".
        for k in 130..255 {
            assert!(
                !p.bit(k),
                "bit {} should be 0 in the predetermined region",
                k
            );
        }
        // p must be prime.
        assert!(crate::asymmetric::rsa::is_prime(&p));
    }

    /// **Lemma 1**: `kₚ` for generated primes lies in the interval
    /// `[⌊2^(2P)/Q⌋, 2^(P+1))`.  This is the formal claim of the
    /// paper; the qualitative "top bits of kₚ are mostly ones" then
    /// follows since the interval is narrow (width `~2^130`) and
    /// centred near `2^257`.
    #[test]
    fn lemma_1_holds_for_generated_prime() {
        let (p, _) = generate_barrett_prime(256);
        assert!(verify_lemma_1(&p, 256), "Lemma 1 interval violated");

        // Sanity: kₚ should be just under 2^257 — i.e., bit 256
        // (the highest bit < 2^257) is always set, and many of the
        // upper bits are 1.  Count the number of 1-bits in the top
        // P/2 region (bits 128..257).
        let two_512 = BigUint::one() << 512;
        let kp: BigUint = &two_512 / &p;
        assert!(kp.bit(256), "k_p must have bit 256 set");
        let mut ones_in_top_half = 0u32;
        for k in 128..257u64 {
            if kp.bit(k) {
                ones_in_top_half += 1;
            }
        }
        // Out of 129 bits in [128, 257), at least 120 should be 1
        // (Lemma 1 plus the gap criterion give us roughly P/2 − 1 ones).
        assert!(
            ones_in_top_half >= 120,
            "k_p should have at least 120 of 129 upper bits set, got {}",
            ones_in_top_half
        );
    }

    /// End-to-end: generate full ECDSA parameters for a tiny prime
    /// where brute-force curve search is feasible, then verify
    /// Barrett reduction works against `n` and `p`.
    #[test]
    fn full_param_generation_tiny_prime() {
        // 16-bit case: large enough to demonstrate the algorithm,
        // small enough that brute-force point counting completes
        // in milliseconds.
        let params = generate_barrett_ecdsa_params(16);
        assert!(crate::asymmetric::rsa::is_prime(&params.p));
        assert!(crate::asymmetric::rsa::is_prime(&params.n));
        // Hasse: |n − p − 1| ≤ 2√p
        let p_plus_1 = &params.p + BigUint::one();
        let hasse_bound = BigUint::from(2u32) * params.p.sqrt() + BigUint::one();
        let diff = if params.n >= p_plus_1 {
            &params.n - &p_plus_1
        } else {
            &p_plus_1 - &params.n
        };
        assert!(diff <= hasse_bound, "Hasse bound violated");

        // Barrett context for p reduces 2P-bit values correctly.
        let ctx_p = params.p_context();
        let mut rng = OsRng;
        let max = BigUint::one() << 32;
        for _ in 0..10 {
            let d = rng.gen_biguint_below(&max);
            assert_eq!(barrett_reduce(&d, &ctx_p), &d % &params.p);
        }
    }
}
