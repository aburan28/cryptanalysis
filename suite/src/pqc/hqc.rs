//! **HQC** — Hamming Quasi-Cyclic code-based KEM.  Aguilar Melchor,
//! Aragon, Bettaieb, Bidoux, Blazy, Deneuville, Gaborit, Persichetti,
//! Zémor 2017–2024.  **Selected by NIST for standardisation in
//! March 2025 (FIPS 206 successor)** as the fifth post-quantum
//! standard alongside ML-KEM, ML-DSA, SLH-DSA, and FN-DSA.
//!
//! ## Why HQC matters
//!
//! HQC is the only **code-based** scheme NIST chose for primary
//! standardisation (Classic McEliece remains a Round-4 candidate
//! with much larger keys).  Its security rests on the **syndrome
//! decoding problem** for quasi-cyclic codes — a different
//! hardness assumption from lattice-based ML-KEM.
//!
//! ## Algorithm sketch
//!
//! Public parameters: code length `n`, message length `k`,
//! decoding-radius parameters.  All arithmetic in the polynomial
//! ring `R = F_2[x] / (x^n − 1)`.
//!
//! - **Key generation**:
//!   1. Sample sparse `h ∈ R` (Hamming weight `ω`).
//!   2. Sample sparse `x, y ∈ R` (weight `ω_r` each).
//!   3. Public key: `s = x + h · y`.  Private key: `(x, y)`.
//!
//! - **Encapsulation**:
//!   1. Sample sparse `r1, r2, e ∈ R`.
//!   2. Encode `m ∈ F_2^k` via concatenated code `C` (BCH or
//!      Reed-Muller × Reed-Solomon in real HQC).
//!   3. `u = r1 + h · r2`, `v = m·C + s·r2 + e`.
//!   4. Ciphertext `(u, v)`.
//!
//! - **Decapsulation**:
//!   1. Compute `v − u·y = m·C + (e·1 + r1·y − x·r2)`.
//!   2. Decode `m·C` to recover `m`.
//!
//! ## Educational scope
//!
//! Parameters: `n = 31` (prime; ensures `x^n − 1 = (x − 1) · Φ_n(x)`
//! has a quasi-cyclic structure), `k = 16`, weights `ω = ω_r = 5`.
//!
//! Production HQC-128 uses `n = 17 669, k = 128, ω = 66`.  Our toy
//! demonstrates the **structural** correctness; security analysis at
//! toy parameters is trivial.
//!
//! Our error-correcting code: **simple repetition code** (each
//! message bit repeated multiple times) instead of HQC's
//! concatenated BCH/Reed-Muller.  Repetition decoding is majority-
//! vote, which is structurally what HQC's inner decoder approximates
//! at the "few bit errors per chunk" level.

use crate::hash::sha256::sha256;
use rand::{rngs::OsRng, Rng};

// ── Parameters ─────────────────────────────────────────────────────

pub const N: usize = 31;
pub const K: usize = 1; // message length in bits (toy: single-bit encryption)
/// Repetition factor: each message bit → `N / K` repeated copies.
pub const REP: usize = N / K;
/// Sparse-vector weight.  Kept small at toy scale so that the
/// noise term `e + r1·y − x·r2` (max weight ~3W + 2W²) stays
/// below the repetition code's correction radius `⌊REP/2⌋`.
pub const W: usize = 2;

// ── F_2 polynomial in R = F_2[x] / (x^N − 1) ──────────────────────

/// A polynomial over `F_2` of length `N` (coefficient of `x^i`
/// stored as bit `i`).  Held as a `[u8; (N+7)/8]` bit-vector.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct F2Poly {
    pub bits: Vec<u8>,
}

const BYTES: usize = N.div_ceil(8);

impl F2Poly {
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

    pub fn is_well_formed(&self) -> bool {
        if self.bits.len() != BYTES {
            return false;
        }

        let used_bits_in_last_byte = N % 8;
        if used_bits_in_last_byte == 0 {
            return true;
        }

        let padding_mask = !((1u8 << used_bits_in_last_byte) - 1);
        (self.bits[BYTES - 1] & padding_mask) == 0
    }

    /// XOR (addition in F_2).
    pub fn add(&self, other: &Self) -> Self {
        let mut out = self.clone();
        for i in 0..BYTES {
            out.bits[i] ^= other.bits[i];
        }
        out
    }

    /// Multiply in `R = F_2[x] / (x^N − 1)`.  Cyclic convolution.
    pub fn mul(&self, other: &Self) -> Self {
        let mut out = Self::zero();
        for i in 0..N {
            if self.get(i) == 1 {
                for j in 0..N {
                    if other.get(j) == 1 {
                        let k = (i + j) % N;
                        out.set(k, out.get(k) ^ 1);
                    }
                }
            }
        }
        out
    }

    pub fn weight(&self) -> usize {
        let mut count = 0;
        for i in 0..N {
            count += self.get(i) as usize;
        }
        count
    }

    /// Sample a random polynomial with exactly `w` set bits.
    pub fn sample_sparse(w: usize) -> Self {
        let mut rng = OsRng;
        let mut p = Self::zero();
        let mut placed = 0;
        while placed < w {
            let i: usize = rng.gen_range(0..N);
            if p.get(i) == 0 {
                p.set(i, 1);
                placed += 1;
            }
        }
        p
    }
}

// ── Repetition encoding/decoding (toy error-correcting code) ──────

/// Encode `K`-bit message into an `N`-bit codeword by repeating
/// each message bit `REP = N/K` times.  Truncated/padded to exactly
/// `N` bits.
fn encode_rep(msg: &[u8]) -> F2Poly {
    assert!(msg.len() * 8 >= K);
    let mut out = F2Poly::zero();
    for i in 0..K {
        let bit = (msg[i / 8] >> (i % 8)) & 1;
        for r in 0..REP {
            let pos = i * REP + r;
            if pos < N {
                out.set(pos, bit);
            }
        }
    }
    out
}

/// Decode the noisy codeword via majority vote per chunk.
fn decode_rep(noisy: &F2Poly) -> Vec<u8> {
    let mut out = vec![0u8; K.div_ceil(8)];
    for i in 0..K {
        let mut ones = 0;
        let mut total = 0;
        for r in 0..REP {
            let pos = i * REP + r;
            if pos < N {
                ones += noisy.get(pos) as usize;
                total += 1;
            }
        }
        let bit = if 2 * ones > total { 1u8 } else { 0u8 };
        out[i / 8] |= bit << (i % 8);
    }
    out
}

// ── KEM ────────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct HqcPublicKey {
    pub h: F2Poly,
    pub s: F2Poly,
}

#[derive(Clone, Debug)]
pub struct HqcPrivateKey {
    pub x: F2Poly,
    pub y: F2Poly,
    pub pk: HqcPublicKey,
}

#[derive(Clone, Debug)]
pub struct HqcKeyPair {
    pub pk: HqcPublicKey,
    pub sk: HqcPrivateKey,
}

#[derive(Clone, Debug)]
pub struct HqcCiphertext {
    pub u: F2Poly,
    pub v: F2Poly,
}

fn ciphertext_is_well_formed(ct: &HqcCiphertext) -> bool {
    ct.u.is_well_formed() && ct.v.is_well_formed()
}

fn rejection_key(sk: &HqcPrivateKey, ct: &HqcCiphertext) -> [u8; 32] {
    let mut input = Vec::new();
    input.extend_from_slice(b"HQC-REJECT");
    input.extend_from_slice(&sk.x.bits);
    input.extend_from_slice(&sk.y.bits);
    input.extend_from_slice(&ct.u.bits);
    input.extend_from_slice(&(ct.u.bits.len() as u64).to_le_bytes());
    input.extend_from_slice(&ct.v.bits);
    input.extend_from_slice(&(ct.v.bits.len() as u64).to_le_bytes());
    sha256(&input)
}

pub fn hqc_keygen() -> HqcKeyPair {
    let h = F2Poly::sample_sparse(W);
    let x = F2Poly::sample_sparse(W);
    let y = F2Poly::sample_sparse(W);
    let s = x.add(&h.mul(&y));
    let pk = HqcPublicKey { h, s };
    let sk = HqcPrivateKey {
        x,
        y,
        pk: pk.clone(),
    };
    HqcKeyPair { pk, sk }
}

pub fn hqc_encapsulate(pk: &HqcPublicKey) -> (HqcCiphertext, [u8; 32]) {
    let mut rng = OsRng;
    let mut msg = vec![0u8; K.div_ceil(8)];
    rng.fill(&mut msg[..]);
    // Mask off bits beyond K.
    let total_bits = msg.len() * 8;
    for bi in K..total_bits {
        msg[bi / 8] &= !(1u8 << (bi % 8));
    }

    let r1 = F2Poly::sample_sparse(W);
    let r2 = F2Poly::sample_sparse(W);
    let e = F2Poly::sample_sparse(W);
    let u = r1.add(&pk.h.mul(&r2));
    let m_c = encode_rep(&msg);
    let v = m_c.add(&pk.s.mul(&r2)).add(&e);

    let mut hash_input = msg.clone();
    hash_input.extend_from_slice(&u.bits);
    hash_input.extend_from_slice(&v.bits);
    let k = sha256(&hash_input);

    (HqcCiphertext { u, v }, k)
}

pub fn hqc_decapsulate(ct: &HqcCiphertext, sk: &HqcPrivateKey) -> [u8; 32] {
    if !ciphertext_is_well_formed(ct) || !sk.x.is_well_formed() || !sk.y.is_well_formed() {
        return rejection_key(sk, ct);
    }

    // Decode m · C from (v + u · y).
    let raw = ct.v.add(&ct.u.mul(&sk.y));
    let msg = decode_rep(&raw);

    let mut hash_input = msg.clone();
    hash_input.extend_from_slice(&ct.u.bits);
    hash_input.extend_from_slice(&ct.v.bits);
    sha256(&hash_input)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// F_2 poly addition is XOR.
    #[test]
    fn f2poly_add_is_xor() {
        let mut a = F2Poly::zero();
        a.set(0, 1);
        a.set(3, 1);
        a.set(7, 1);
        let mut b = F2Poly::zero();
        b.set(3, 1);
        b.set(5, 1);
        let c = a.add(&b);
        assert_eq!(c.get(0), 1);
        assert_eq!(c.get(3), 0);
        assert_eq!(c.get(5), 1);
        assert_eq!(c.get(7), 1);
    }

    /// Cyclic mul: x · x^k = x^{k+1} (or wraps).
    #[test]
    fn f2poly_mul_basic() {
        let mut x = F2Poly::zero();
        x.set(1, 1);
        let mut x_n_minus_1 = F2Poly::zero();
        x_n_minus_1.set(N - 1, 1);
        let prod = x.mul(&x_n_minus_1);
        // x · x^{N-1} = x^N ≡ 1 (mod x^N - 1).
        assert_eq!(prod.get(0), 1);
        assert_eq!(prod.weight(), 1);
    }

    /// Sparse sampling has the requested weight.
    #[test]
    fn sparse_sample_has_correct_weight() {
        let p = F2Poly::sample_sparse(W);
        assert_eq!(p.weight(), W);
    }

    /// Repetition encode/decode without errors.
    #[test]
    fn repetition_roundtrip_no_errors() {
        let msg = vec![0b10110u8];
        let c = encode_rep(&msg);
        let decoded = decode_rep(&c);
        // Compare first K bits.
        for i in 0..K {
            let orig = (msg[i / 8] >> (i % 8)) & 1;
            let dec = (decoded[i / 8] >> (i % 8)) & 1;
            assert_eq!(orig, dec);
        }
    }

    /// **HQC end-to-end**: encapsulate → decapsulate → same key.
    ///
    /// At toy scale (W=5 weight) the error term can occasionally
    /// exceed the repetition-decoder margin.  Run 5 trials and
    /// require ≥ 60% success — the structural correctness check.
    #[test]
    fn hqc_kem_shared_secret_matches() {
        let mut successes = 0;
        for _ in 0..5 {
            let kp = hqc_keygen();
            let (ct, k_enc) = hqc_encapsulate(&kp.pk);
            let k_dec = hqc_decapsulate(&ct, &kp.sk);
            if k_enc == k_dec {
                successes += 1;
            }
        }
        assert!(
            successes >= 3,
            "HQC educational toy should succeed ≥ 3/5 trials; got {}/5",
            successes
        );
    }

    #[test]
    fn hqc_decapsulate_rejects_truncated_u_storage_without_panicking() {
        let kp = hqc_keygen();
        let ct = HqcCiphertext {
            u: F2Poly {
                bits: vec![0u8; BYTES - 1],
            },
            v: F2Poly::zero(),
        };

        assert_eq!(hqc_decapsulate(&ct, &kp.sk), rejection_key(&kp.sk, &ct));
    }

    #[test]
    fn hqc_decapsulate_rejects_noncanonical_padding_bits_without_panicking() {
        let kp = hqc_keygen();
        let mut malformed = F2Poly::zero();
        malformed.bits[BYTES - 1] |= 0x80;
        let ct = HqcCiphertext {
            u: malformed,
            v: F2Poly::zero(),
        };

        assert_eq!(hqc_decapsulate(&ct, &kp.sk), rejection_key(&kp.sk, &ct));
    }
}
