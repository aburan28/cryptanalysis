//! **BIKE** — Bit-Flipping Key Encapsulation.  Aragon, Barreto,
//! Bettaieb, Bidoux, Blazy, Deneuville, Gaborit, Gueron, Güneysu,
//! Aguilar Melchor, Misoczki, Persichetti, Sendrier, Tillich, Zémor
//! 2017–2024.  **NIST PQC Round 4 candidate**.
//!
//! ## Why BIKE
//!
//! BIKE is a **code-based** KEM using **Quasi-Cyclic Moderate-
//! Density Parity-Check (QC-MDPC)** codes (Misoczki-Tillich-Sendrier
//! 2013).  It sits between Classic McEliece (heavy keys, fast
//! ops) and HQC (medium keys, slower ops) in the speed/size
//! trade-off.  NIST kept it as a Round-4 candidate for further
//! analysis but did not select it for standardisation in March
//! 2025 (HQC won the code-based slot).
//!
//! ## Algorithm
//!
//! Public parameters: code length `2r`, dimension `r`, weight `w`.
//! Operations in `R = F_2[x] / (x^r − 1)` (quasi-cyclic structure).
//!
//! **Key generation**:
//! 1. Sample sparse `h0, h1 ∈ R`, each of weight `w/2`.
//! 2. Public key: `h = h1 · h0^{-1} ∈ R` (so `[h0 | h1]` is a
//!    parity-check matrix in QC form).
//! 3. Private key: `(h0, h1)`.
//!
//! **Encapsulation**:
//! 1. Sample sparse error `(e0, e1) ∈ R²` of total weight `t`.
//! 2. Compute syndrome `s = e0 + e1 · h ∈ R`.
//! 3. Shared secret derived from `(e0, e1)`.
//! 4. Ciphertext: `s`.
//!
//! **Decapsulation**:
//! 1. Compute `s' = s · h0 = (e0 + e1·h) · h0 = e0·h0 + e1·h1`
//!    (using `h·h0 = h1`).
//! 2. **Bit-flipping decoder** recovers `(e0, e1)` from `s'` given
//!    knowledge of `(h0, h1)`.
//! 3. Re-derive the shared secret.
//!
//! ## Educational scope
//!
//! Parameters: `r = 31, w = 6, t = 3`.  Production BIKE-128 uses
//! `r = 12,323, w = 142, t = 134`.  Our toy demonstrates the
//! structural correctness of the QC-MDPC framework; the
//! bit-flipping decoder is a simplified hard-decision majority-vote
//! version.
//!
//! **These parameters are not uniquely decodable, and that is not a
//! bug in the decoder.**  The code is far too short for weight-`t`
//! error patterns to have distinct syndromes: on roughly **1.6%** of
//! random keys and errors a second `(e0, e1)` of weight `<= t` gives
//! the same `s'` (measured 81 collisions in 5000 draws, with 2 to 62
//! preimages on a colliding draw).  Decapsulation then recovers *a*
//! valid error, not necessarily the one encapsulation injected, and
//! the shared secrets differ.  Production parameters are chosen so
//! that this probability is cryptographically negligible; a test over
//! these parameters must state the qualifier rather than assume it
//! away — see `bike_kem_shared_secret_matches_unless_the_syndrome_is_ambiguous`.

use crate::hash::sha256::sha256;
use rand::{rngs::OsRng, Rng};

pub const R: usize = 31;
pub const W: usize = 6;
pub const T: usize = 3;

const BYTES: usize = R.div_ceil(8);

/// An element of `F_2[x] / (x^R − 1)` stored as a packed bit-vector.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct R2Poly {
    pub bits: Vec<u8>,
}

impl R2Poly {
    pub fn zero() -> Self {
        Self {
            bits: vec![0u8; BYTES],
        }
    }

    pub fn get(&self, i: usize) -> u8 {
        (self.bits[i / 8] >> (i % 8)) & 1
    }

    pub fn set(&mut self, i: usize, v: u8) {
        let byte = i / 8;
        let bit = i % 8;
        self.bits[byte] = (self.bits[byte] & !(1 << bit)) | ((v & 1) << bit);
    }

    pub fn add(&self, other: &Self) -> Self {
        let mut out = self.clone();
        for i in 0..BYTES {
            out.bits[i] ^= other.bits[i];
        }
        out
    }

    pub fn weight(&self) -> usize {
        let mut count = 0;
        for i in 0..R {
            count += self.get(i) as usize;
        }
        count
    }

    /// Cyclic-convolution multiplication in `R = F_2[x]/(x^R − 1)`.
    pub fn mul(&self, other: &Self) -> Self {
        let mut out = Self::zero();
        for i in 0..R {
            if self.get(i) == 1 {
                for j in 0..R {
                    if other.get(j) == 1 {
                        let k = (i + j) % R;
                        out.set(k, out.get(k) ^ 1);
                    }
                }
            }
        }
        out
    }

    /// Sample random sparse polynomial with `w` set bits.
    pub fn sample_sparse(w: usize) -> Self {
        let mut rng = OsRng;
        let mut p = Self::zero();
        let mut placed = 0;
        while placed < w {
            let i: usize = rng.gen_range(0..R);
            if p.get(i) == 0 {
                p.set(i, 1);
                placed += 1;
            }
        }
        p
    }

    /// Brute-force polynomial inversion in F_2x/(x^R − 1).  Only
    /// feasible for small R (here R=31 → 2^31 candidates, infeasible).
    /// We use it only via the `from_invertible_pair` helper which
    /// samples until both halves are invertible — but for our toy
    /// scale we instead use a **deterministic** invertibility check
    /// via gcd, then explicit XGCD.
    pub fn try_invert(&self) -> Option<Self> {
        // Use the Almost-Inverse algorithm adapted for F_2.
        // Operates on polynomials of degree < R+1 (treating `x^R − 1`
        // as the modulus).
        let mut a = self.bits.clone();
        a.resize(BYTES + 1, 0);
        // Modulus m = x^R - 1 = x^R + 1 in F_2.
        let mut b = vec![0u8; BYTES + 1];
        b[0] = 1;
        let bit_r = R;
        b[bit_r / 8] |= 1 << (bit_r % 8);
        let mut u = vec![0u8; BYTES + 1];
        u[0] = 1;
        let mut v = vec![0u8; BYTES + 1];

        let max_bits = R + 1;
        let get_bit = |v: &[u8], i: usize| -> u8 { (v[i / 8] >> (i % 8)) & 1 };
        let set_bit = |v: &mut Vec<u8>, i: usize, b: u8| {
            v[i / 8] = (v[i / 8] & !(1 << (i % 8))) | ((b & 1) << (i % 8));
        };
        let degree = |v: &[u8], max: usize| -> Option<usize> {
            (0..max).rev().find(|&i| get_bit(v, i) == 1)
        };

        // Iterative trial: try b /= a and update u, v.
        for _iter in 0..(R * R) {
            let deg_a = degree(&a, max_bits);
            let deg_b = degree(&b, max_bits);
            deg_a?;
            if deg_a == Some(0) {
                // gcd is x^0 = 1 (constant); u is the inverse.
                let mut out = Self::zero();
                for i in 0..R {
                    set_bit(&mut out.bits, i, get_bit(&u, i));
                }
                // Verify u is correct.
                let prod = self.mul(&out);
                let mut one = Self::zero();
                one.set(0, 1);
                if prod == one {
                    return Some(out);
                }
                return None;
            }
            let deg_a_u = deg_a.unwrap();
            let deg_b_u = deg_b?;
            if deg_a_u < deg_b_u {
                std::mem::swap(&mut a, &mut b);
                std::mem::swap(&mut u, &mut v);
                continue;
            }
            // b = a (with leading bit at deg_b_u); subtract a shifted
            // such that degrees match: a' = a + (b shifted by (deg_a - deg_b)).
            let shift = deg_a_u - deg_b_u;
            for i in 0..=deg_b_u {
                if get_bit(&b, i) == 1 {
                    let target = i + shift;
                    if target / 8 < a.len() {
                        a[target / 8] ^= 1 << (target % 8);
                    }
                }
            }
            // Same shift on v applied to u.
            for i in 0..max_bits {
                if get_bit(&v, i) == 1 {
                    let target = (i + shift) % R;
                    let cur = get_bit(&u, target);
                    set_bit(&mut u, target, cur ^ 1);
                }
            }
        }
        None
    }
}

// ── KEM ────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct BikePublicKey {
    pub h: R2Poly,
}

#[derive(Clone, Debug)]
pub struct BikePrivateKey {
    pub h0: R2Poly,
    pub h1: R2Poly,
    pub pk: BikePublicKey,
    reject_secret: [u8; 32],
}

impl Drop for BikePrivateKey {
    fn drop(&mut self) {
        self.reject_secret.fill(0);
    }
}

#[derive(Clone, Debug)]
pub struct BikeKeyPair {
    pub pk: BikePublicKey,
    pub sk: BikePrivateKey,
}

#[derive(Clone, Debug)]
pub struct BikeCiphertext {
    pub s: R2Poly,
}

pub fn bike_keygen() -> BikeKeyPair {
    for _ in 0..200 {
        let h0 = R2Poly::sample_sparse(W / 2);
        let h1 = R2Poly::sample_sparse(W / 2);
        let h0_inv = match h0.try_invert() {
            Some(x) => x,
            None => continue,
        };
        let h = h1.mul(&h0_inv);
        let mut reject_secret = [0u8; 32];
        reject_secret.copy_from_slice(&crate::utils::random::random_bytes_vec(32));
        let pk = BikePublicKey { h };
        let sk = BikePrivateKey {
            h0,
            h1,
            pk: pk.clone(),
            reject_secret,
        };
        return BikeKeyPair { pk, sk };
    }
    panic!("BIKE keygen failed: h0 not invertible after 200 trials");
}

pub fn bike_encapsulate(pk: &BikePublicKey) -> (BikeCiphertext, [u8; 32]) {
    // Sample error vector (e0, e1) of total weight T.
    let t0 = T / 2 + (T & 1);
    let t1 = T / 2;
    let e0 = R2Poly::sample_sparse(t0);
    let e1 = R2Poly::sample_sparse(t1);
    let s = e0.add(&e1.mul(&pk.h));

    let mut hash_input = Vec::with_capacity(3 * BYTES);
    hash_input.extend_from_slice(&e0.bits);
    hash_input.extend_from_slice(&e1.bits);
    hash_input.extend_from_slice(&s.bits);
    let k = sha256(&hash_input);

    (BikeCiphertext { s }, k)
}

pub fn bike_decapsulate(ct: &BikeCiphertext, sk: &BikePrivateKey) -> [u8; 32] {
    if !r2poly_is_well_formed(&ct.s) {
        return rejection_key(sk, &ct.s);
    }

    // Compute s' = s · h0 = e0·h0 + e1·h1 (the syndrome under the
    // QC-MDPC parity-check matrix [h0 | h1]).
    let s_prime = ct.s.mul(&sk.h0);

    // **Toy bit-flipping decoder**: since the error weight T is
    // tiny in our toy parameters, we use a brute-force enumeration
    // for educational clarity.  Production BIKE uses Black-Gray-
    // Flip iterative bit-flipping.
    let (e0_decoded, e1_decoded) = brute_force_decode(&s_prime, &sk.h0, &sk.h1, T);

    let mut hash_input = Vec::with_capacity(3 * BYTES);
    hash_input.extend_from_slice(&e0_decoded.bits);
    hash_input.extend_from_slice(&e1_decoded.bits);
    hash_input.extend_from_slice(&ct.s.bits);
    sha256(&hash_input)
}

fn r2poly_is_well_formed(poly: &R2Poly) -> bool {
    let padding_bits = (BYTES * 8) - R;
    let padding_mask = if padding_bits == 0 {
        0
    } else {
        u8::MAX << (8 - padding_bits)
    };

    poly.bits.len() == BYTES
        && poly
            .bits
            .last()
            .map(|last| (last & padding_mask) == 0)
            .unwrap_or(false)
}

fn rejection_key(sk: &BikePrivateKey, poly: &R2Poly) -> [u8; 32] {
    let mut hash_input = Vec::with_capacity(32 + poly.bits.len() + 16);
    hash_input.extend_from_slice(b"BIKE-REJECT");
    hash_input.extend_from_slice(&sk.reject_secret);
    hash_input.extend_from_slice(&poly.bits);
    hash_input.extend_from_slice(&(poly.bits.len() as u64).to_le_bytes());
    sha256(&hash_input)
}

/// Brute-force decoder: enumerate all `(e0, e1)` with total weight
/// `≤ t` until one matches `e0·h0 + e1·h1 = s_prime`.  Feasible for
/// our toy `R = 31, T = 3` (search space ≈ `(2R choose T) ≈ 36k`).
fn brute_force_decode(s_prime: &R2Poly, h0: &R2Poly, h1: &R2Poly, t: usize) -> (R2Poly, R2Poly) {
    // Enumerate all positions choosing `t` bits across the 2R-bit
    // concatenated error vector.
    let total_positions = 2 * R;
    // Recursive enumeration up to weight t.
    fn enumerate(
        pos_start: usize,
        remaining: usize,
        total: usize,
        chosen: &mut Vec<usize>,
        target: &R2Poly,
        h0: &R2Poly,
        h1: &R2Poly,
    ) -> Option<(R2Poly, R2Poly)> {
        if remaining == 0 {
            // Build (e0, e1).
            let mut e0 = R2Poly::zero();
            let mut e1 = R2Poly::zero();
            for &p in chosen.iter() {
                if p < R {
                    e0.set(p, 1);
                } else {
                    e1.set(p - R, 1);
                }
            }
            let candidate = e0.mul(h0).add(&e1.mul(h1));
            if candidate == *target {
                return Some((e0, e1));
            }
            return None;
        }
        for p in pos_start..(total - remaining + 1) {
            chosen.push(p);
            if let Some(found) = enumerate(p + 1, remaining - 1, total, chosen, target, h0, h1) {
                return Some(found);
            }
            chosen.pop();
        }
        None
    }

    for weight in 0..=t {
        let mut chosen = Vec::new();
        if let Some(found) = enumerate(0, weight, total_positions, &mut chosen, s_prime, h0, h1) {
            return found;
        }
    }
    // Decode failure — return zeros (shared secret will differ).
    (R2Poly::zero(), R2Poly::zero())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Sparse sampling gives the requested weight.
    #[test]
    fn sparse_sample_weight() {
        let p = R2Poly::sample_sparse(W / 2);
        assert_eq!(p.weight(), W / 2);
    }

    /// XOR addition in F_2.
    #[test]
    fn r2poly_add_is_xor() {
        let mut a = R2Poly::zero();
        a.set(0, 1);
        a.set(3, 1);
        let mut b = R2Poly::zero();
        b.set(3, 1);
        b.set(5, 1);
        let c = a.add(&b);
        assert_eq!(c.get(0), 1);
        assert_eq!(c.get(3), 0);
        assert_eq!(c.get(5), 1);
    }

    /// Every `(e0, e1)` of total weight `<= T` whose syndrome is `target`.
    ///
    /// Deliberately a second implementation rather than a call into
    /// [`brute_force_decode`]: the point is to check that decoder's answer
    /// against an independent count, so sharing its enumeration would make the
    /// check vacuous.
    fn weight_t_preimages(target: &R2Poly, h0: &R2Poly, h1: &R2Poly) -> usize {
        fn walk(
            start: usize,
            remaining: usize,
            chosen: &mut Vec<usize>,
            target: &R2Poly,
            h0: &R2Poly,
            h1: &R2Poly,
            found: &mut usize,
        ) {
            if remaining == 0 {
                let (mut e0, mut e1) = (R2Poly::zero(), R2Poly::zero());
                for &p in chosen.iter() {
                    if p < R {
                        e0.set(p, 1);
                    } else {
                        e1.set(p - R, 1);
                    }
                }
                if e0.mul(h0).add(&e1.mul(h1)) == *target {
                    *found += 1;
                }
                return;
            }
            for p in start..(2 * R - remaining + 1) {
                chosen.push(p);
                walk(p + 1, remaining - 1, chosen, target, h0, h1, found);
                chosen.pop();
            }
        }
        let mut found = 0;
        for weight in 0..=T {
            walk(0, weight, &mut Vec::new(), target, h0, h1, &mut found);
        }
        found
    }

    /// **BIKE end-to-end**: encap → decap → same shared secret, *whenever the
    /// syndrome determines the error*.
    ///
    /// The qualifier is not a hedge, it is the contract these parameters
    /// actually support. At `R = 31`, `W = 6`, `T = 3` the code's minimum
    /// distance is too small to decode uniquely: on about 1.6% of draws the
    /// syndrome has a second weight-`<= T` preimage — measured 81 collisions in
    /// 5000 draws, with 2 to 62 preimages on a colliding draw — and
    /// [`brute_force_decode`] returns the lexicographically first, which need
    /// not be the error encapsulation injected. The shared secrets then differ
    /// for a reason that is a property of the toy parameters, not a fault in
    /// the decoder.
    ///
    /// Asserting `k_enc == k_dec` on a single draw therefore asserts something
    /// false 1.6% of the time, which is exactly how often this test used to
    /// fail in CI while passing locally. What is true, and what is asserted
    /// here, is the conjunction: the secrets agree unless the syndrome is
    /// genuinely ambiguous, and ambiguity stays near its measured rate. A
    /// decoder that returned the wrong answer on a *uniquely* decodable
    /// syndrome fails the first assertion; one that started failing to decode
    /// at all fails the second.
    ///
    /// `preimages >= 2` is exactly "ambiguous", with no slack: the error
    /// encapsulation injected has weight `<= T` and maps to this syndrome, so
    /// it is itself a preimage and the count is never below 1. That also means
    /// a well-formed ciphertext can never reach the decoder's decode-failure
    /// path, so an outright decoding failure is not among the causes this test
    /// has to distinguish.
    #[test]
    fn bike_kem_shared_secret_matches_unless_the_syndrome_is_ambiguous() {
        let trials = 200;
        let mut ambiguous = 0;
        for _ in 0..trials {
            let kp = bike_keygen();
            let (ct, k_enc) = bike_encapsulate(&kp.pk);
            let k_dec = bike_decapsulate(&ct, &kp.sk);
            if k_enc == k_dec {
                continue;
            }
            let s_prime = ct.s.mul(&kp.sk.h0);
            let preimages = weight_t_preimages(&s_prime, &kp.sk.h0, &kp.sk.h1);
            assert!(
                preimages >= 2,
                "decapsulation disagreed on a syndrome with {preimages} \
                 weight-<=T preimage(s); with a unique preimage the decoder \
                 must return it"
            );
            ambiguous += 1;
        }
        // ~1.6% measured; 15% leaves room for the sampler without letting a
        // real collapse in decoding pass unnoticed.
        assert!(
            ambiguous * 100 < trials * 15,
            "{ambiguous}/{trials} draws had an ambiguous syndrome, far above \
             the ~1.6% these parameters give"
        );
    }

    #[test]
    fn bike_decapsulate_rejects_truncated_storage_without_panicking() {
        let kp = bike_keygen();
        let malformed = BikeCiphertext {
            s: R2Poly {
                bits: vec![0u8; BYTES - 1],
            },
        };

        assert_eq!(
            bike_decapsulate(&malformed, &kp.sk),
            rejection_key(&kp.sk, &malformed.s)
        );
    }

    #[test]
    fn bike_decapsulate_rejects_noncanonical_padding_bits_without_panicking() {
        let kp = bike_keygen();
        let mut bits = vec![0u8; BYTES];
        bits[BYTES - 1] = 0x80;
        let malformed = BikeCiphertext { s: R2Poly { bits } };

        assert_eq!(
            bike_decapsulate(&malformed, &kp.sk),
            rejection_key(&kp.sk, &malformed.s)
        );
    }
}
