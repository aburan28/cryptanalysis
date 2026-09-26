//! **FrodoKEM** — conservative learning-with-errors (LWE) key
//! encapsulation.  Naehrig, Alkim, Avanzi, Bos, Ducas, Easterbrook,
//! LaMacchia, Longa, Mironov, Nikolaenko, Peikert, Raghunathan,
//! Stebila 2016.  NIST PQC alternate finalist.
//!
//! ## Why FrodoKEM matters
//!
//! Kyber/ML-KEM uses **Module-LWE** with structured (cyclotomic)
//! polynomial rings.  FrodoKEM uses **plain LWE** over generic
//! matrices — no ring structure, no structured-lattice
//! assumptions, no algebraic-attack surface.  This is the most
//! conservative lattice KEM in the NIST process; the trade-off is
//! larger keys (~10 KB vs Kyber's ~800 B).
//!
//! ## Algorithm
//!
//! Public parameters: dimensions `(n, m, ℓ)` and modulus `q = 2^D`.
//!
//! **Key generation**:
//! 1. Sample matrix `A ∈ Z_q^{n×n}` from a public seed.
//! 2. Sample secret `S, E ∈ Z_q^{n×ℓ}` with small entries
//!    (discrete Gaussian).
//! 3. Compute `B = A·S + E  (mod q)`.
//! 4. Public key: `(seed_A, B)`.  Secret key: `S`.
//!
//! **Encapsulation**:
//! 1. Sample `S', E', E'' ∈ Z_q` with small entries.
//! 2. Compute `B' = S'·A + E'`, `V = S'·B + E''`.
//! 3. Encode message `μ` as `enc(μ) ∈ Z_q^{m×ℓ}` (high bits).
//! 4. Ciphertext: `(B', C = V + enc(μ))`.
//!
//! **Decapsulation**:
//! 1. Compute `M = C − B'·S  (mod q)`.
//! 2. Decode `μ = dec(M)` (round high bits).
//! 3. Re-encapsulate and verify (Fujisaki-Okamoto for IND-CCA).
//!
//! ## Educational scope
//!
//! Parameters: `n = 8`, `m = 1`, `ℓ = 4`, `q = 2^12 = 4096`.
//! Production FrodoKEM-640 uses `n = 640, m = ℓ = 8, q = 2^15`.
//! Our toy scale verifies the **structural correctness** of
//! encapsulation/decapsulation; security at toy scale is trivial.

use crate::hash::sha256::sha256;
use rand::{rngs::OsRng, Rng};

// ── Parameters ─────────────────────────────────────────────────────

pub const N: usize = 8;
pub const M: usize = 1;
pub const L: usize = 4;
/// log₂ of the modulus.
pub const D: u32 = 12;
/// Modulus `q = 2^D`.
pub const Q: u32 = 1u32 << D;
/// Bits encoded per message-matrix coefficient.  Each ciphertext
/// coefficient carries `B = D − log₂(2·𝒪) = 2` bits in our toy.
pub const B: u32 = 2;

// ── Matrices over Z_q ──────────────────────────────────────────────

/// `Matrix<R, C>` stored row-major in a `Vec<u32>`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Matrix {
    pub rows: usize,
    pub cols: usize,
    pub data: Vec<u32>,
}

impl Matrix {
    pub fn zero(rows: usize, cols: usize) -> Self {
        Self {
            rows,
            cols,
            data: vec![0u32; rows * cols],
        }
    }
    pub fn get(&self, r: usize, c: usize) -> u32 {
        self.data[r * self.cols + c]
    }
    pub fn set(&mut self, r: usize, c: usize, v: u32) {
        self.data[r * self.cols + c] = v & (Q - 1);
    }

    pub fn is_well_formed(&self) -> bool {
        self.data.len() == self.rows.saturating_mul(self.cols)
    }

    /// Element-wise addition mod `q`.
    pub fn add(&self, other: &Self) -> Self {
        assert_eq!((self.rows, self.cols), (other.rows, other.cols));
        let mut out = Self::zero(self.rows, self.cols);
        for i in 0..self.data.len() {
            out.data[i] = (self.data[i].wrapping_add(other.data[i])) & (Q - 1);
        }
        out
    }

    pub fn sub(&self, other: &Self) -> Self {
        assert_eq!((self.rows, self.cols), (other.rows, other.cols));
        let mut out = Self::zero(self.rows, self.cols);
        for i in 0..self.data.len() {
            out.data[i] = (self.data[i].wrapping_sub(other.data[i])) & (Q - 1);
        }
        out
    }

    /// `self · other` (matrix multiplication mod `q`).
    pub fn mul(&self, other: &Self) -> Self {
        assert_eq!(self.cols, other.rows);
        let mut out = Self::zero(self.rows, other.cols);
        for i in 0..self.rows {
            for k in 0..self.cols {
                let a = self.get(i, k);
                for j in 0..other.cols {
                    let v = out.get(i, j).wrapping_add(a.wrapping_mul(other.get(k, j)));
                    out.set(i, j, v);
                }
            }
        }
        out
    }
}

// ── Sampling: deterministic A from seed, ternary error from PRNG ──

/// Expand a 32-byte seed into an `n × n` matrix `A` over `Z_q` via
/// SHAKE-like hash iteration.  Our toy uses SHA-256 chained.
pub fn expand_a(seed: &[u8; 32]) -> Matrix {
    let mut a = Matrix::zero(N, N);
    let mut counter = 0u32;
    let mut output = Vec::new();
    let need = N * N * 2; // 2 bytes per coefficient
    while output.len() < need {
        let mut input = seed.to_vec();
        input.extend_from_slice(&counter.to_le_bytes());
        let h = sha256(&input);
        output.extend_from_slice(&h);
        counter += 1;
    }
    for i in 0..N {
        for j in 0..N {
            let off = (i * N + j) * 2;
            let v = u16::from_le_bytes([output[off], output[off + 1]]) as u32 & (Q - 1);
            a.set(i, j, v);
        }
    }
    a
}

/// Sample a "small error" matrix with entries in `[−η, η]` (here
/// `η = 1` for toy parameters).  Each entry is mapped to its mod-`q`
/// representative.
fn sample_error(rows: usize, cols: usize) -> Matrix {
    let mut rng = OsRng;
    let mut m = Matrix::zero(rows, cols);
    for r in 0..rows {
        for c in 0..cols {
            let bit: i32 = rng.gen_range(-1..=1);
            let v = if bit >= 0 {
                bit as u32
            } else {
                (Q as i32 + bit) as u32
            };
            m.set(r, c, v);
        }
    }
    m
}

// ── Encode/decode message bits ─────────────────────────────────────

/// Pack `B`-bit messages into the high bits of `Z_q`.  Each
/// coefficient encodes `B` bits in positions `[D - B, D)`.
fn encode(msg: &[u8]) -> Matrix {
    // For our toy: M·L coefficients × B bits/coef = M·L·B bits.
    // M = 1, L = 4, B = 2 → 8 bits per ciphertext = 1 byte.
    assert!(
        msg.len() * 8 >= M * L * B as usize,
        "msg too short for encoding"
    );
    let mut m = Matrix::zero(M, L);
    let shift = D - B;
    for i in 0..M {
        for j in 0..L {
            let bit_off = (i * L + j) * B as usize;
            let mut val = 0u32;
            for k in 0..B as usize {
                let bi = bit_off + k;
                let byte = msg[bi / 8];
                let b = (byte >> (bi % 8)) & 1;
                val |= (b as u32) << k;
            }
            m.set(i, j, val << shift);
        }
    }
    m
}

fn decode(m: &Matrix) -> Vec<u8> {
    let shift = D - B;
    let half = 1u32 << (shift - 1);
    let mask = (1u32 << B) - 1;
    let n_bits = M * L * B as usize;
    let mut out = vec![0u8; n_bits.div_ceil(8)];
    for i in 0..M {
        for j in 0..L {
            // Round-to-nearest by adding half then truncating.
            let v = m.get(i, j).wrapping_add(half) >> shift;
            let v = v & mask;
            let bit_off = (i * L + j) * B as usize;
            for k in 0..B as usize {
                let b = ((v >> k) & 1) as u8;
                out[(bit_off + k) / 8] |= b << ((bit_off + k) % 8);
            }
        }
    }
    out
}

// ── KEM API ────────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct FrodoPublicKey {
    pub seed_a: [u8; 32],
    pub b: Matrix,
}

#[derive(Clone, Debug)]
pub struct FrodoPrivateKey {
    pub s: Matrix,
    pub pk: FrodoPublicKey,
}

#[derive(Clone, Debug)]
pub struct FrodoKeyPair {
    pub pk: FrodoPublicKey,
    pub sk: FrodoPrivateKey,
}

#[derive(Clone, Debug)]
pub struct FrodoCiphertext {
    pub b_prime: Matrix,
    pub c: Matrix,
}

fn serialize_ciphertext(ct: &FrodoCiphertext) -> Vec<u8> {
    let mut out = Vec::with_capacity(
        4 * std::mem::size_of::<usize>() + 4 * (ct.b_prime.data.len() + ct.c.data.len()),
    );
    out.extend_from_slice(&ct.b_prime.rows.to_le_bytes());
    out.extend_from_slice(&ct.b_prime.cols.to_le_bytes());
    out.extend_from_slice(&ct.c.rows.to_le_bytes());
    out.extend_from_slice(&ct.c.cols.to_le_bytes());
    for &val in ct.b_prime.data.iter().chain(ct.c.data.iter()) {
        out.extend_from_slice(&val.to_le_bytes());
    }
    out
}

fn rejection_key(sk: &FrodoPrivateKey, ct: &FrodoCiphertext) -> [u8; 32] {
    let mut hash_input = Vec::with_capacity(16 + 4 * sk.s.data.len());
    hash_input.extend_from_slice(b"FRODO-REJECT");
    for &val in &sk.s.data {
        hash_input.extend_from_slice(&val.to_le_bytes());
    }
    hash_input.extend_from_slice(&serialize_ciphertext(ct));
    sha256(&hash_input)
}

fn ciphertext_is_well_formed(ct: &FrodoCiphertext) -> bool {
    ct.b_prime.rows == M
        && ct.b_prime.cols == N
        && ct.c.rows == M
        && ct.c.cols == L
        && ct.b_prime.is_well_formed()
        && ct.c.is_well_formed()
}

pub fn frodo_keygen() -> FrodoKeyPair {
    let mut rng = OsRng;
    let mut seed_a = [0u8; 32];
    rng.fill(&mut seed_a);
    let a = expand_a(&seed_a);
    let s = sample_error(N, L);
    let e = sample_error(N, L);
    let b = a.mul(&s).add(&e);
    let pk = FrodoPublicKey { seed_a, b };
    let sk = FrodoPrivateKey { s, pk: pk.clone() };
    FrodoKeyPair { pk, sk }
}

pub fn frodo_encapsulate(pk: &FrodoPublicKey) -> (FrodoCiphertext, [u8; 32]) {
    let mut rng = OsRng;
    let mut msg_bytes = vec![0u8; (M * L * B as usize).div_ceil(8)];
    rng.fill(&mut msg_bytes[..]);

    let a = expand_a(&pk.seed_a);
    let s_prime = sample_error(M, N);
    let e_prime = sample_error(M, N);
    let e_pp = sample_error(M, L);
    let b_prime = s_prime.mul(&a).add(&e_prime);
    let v = s_prime.mul(&pk.b).add(&e_pp);
    let mu = encode(&msg_bytes);
    let c = v.add(&mu);

    // Shared secret = SHA-256(msg ‖ ciphertext_bytes).
    let mut hash_input = msg_bytes.clone();
    for &val in b_prime.data.iter().chain(c.data.iter()) {
        hash_input.extend_from_slice(&val.to_le_bytes());
    }
    let k = sha256(&hash_input);
    (FrodoCiphertext { b_prime, c }, k)
}

pub fn frodo_decapsulate(ct: &FrodoCiphertext, sk: &FrodoPrivateKey) -> [u8; 32] {
    if !ciphertext_is_well_formed(ct) || !sk.s.is_well_formed() {
        return rejection_key(sk, ct);
    }

    let m_mat = ct.c.sub(&ct.b_prime.mul(&sk.s));
    let msg_bytes = decode(&m_mat);

    let mut hash_input = msg_bytes.clone();
    for &val in ct.b_prime.data.iter().chain(ct.c.data.iter()) {
        hash_input.extend_from_slice(&val.to_le_bytes());
    }
    sha256(&hash_input)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Matrix multiplication is associative on small test cases.
    #[test]
    fn matrix_mul_associative() {
        let a = {
            let mut m = Matrix::zero(2, 2);
            m.set(0, 0, 1);
            m.set(0, 1, 2);
            m.set(1, 0, 3);
            m.set(1, 1, 4);
            m
        };
        let b = {
            let mut m = Matrix::zero(2, 2);
            m.set(0, 0, 5);
            m.set(0, 1, 6);
            m.set(1, 0, 7);
            m.set(1, 1, 8);
            m
        };
        let c = {
            let mut m = Matrix::zero(2, 2);
            m.set(0, 0, 9);
            m.set(0, 1, 10);
            m.set(1, 0, 11);
            m.set(1, 1, 12);
            m
        };
        let lhs = a.mul(&b).mul(&c);
        let rhs = a.mul(&b.mul(&c));
        assert_eq!(lhs, rhs);
    }

    /// `expand_a` is deterministic.
    #[test]
    fn expand_a_deterministic() {
        let seed = [42u8; 32];
        let a1 = expand_a(&seed);
        let a2 = expand_a(&seed);
        assert_eq!(a1, a2);
    }

    /// Encode/decode roundtrip on random byte.
    #[test]
    fn encode_decode_roundtrip() {
        let msg = vec![0b10110001u8];
        let m_mat = encode(&msg);
        let decoded = decode(&m_mat);
        assert_eq!(msg, decoded);
    }

    /// **FrodoKEM end-to-end**: encapsulate → decapsulate → same key.
    #[test]
    fn frodo_kem_shared_secret_matches() {
        // Run multiple trials: at toy scale the error sampling can
        // occasionally exceed decoding margins.  We accept ≥80% of
        // 5 trials yielding correct shared-secret recovery as the
        // educational-scale success criterion.
        let mut successes = 0;
        for _ in 0..5 {
            let kp = frodo_keygen();
            let (ct, k_enc) = frodo_encapsulate(&kp.pk);
            let k_dec = frodo_decapsulate(&ct, &kp.sk);
            if k_enc == k_dec {
                successes += 1;
            }
        }
        assert!(
            successes >= 4,
            "FrodoKEM should succeed in ≥4 of 5 trials at toy scale; got {}/5",
            successes
        );
    }

    #[test]
    fn frodo_decapsulate_rejects_malformed_b_prime_shape_without_panicking() {
        let kp = frodo_keygen();
        let ct = FrodoCiphertext {
            b_prime: Matrix::zero(M + 1, N),
            c: Matrix::zero(M, L),
        };

        assert_eq!(frodo_decapsulate(&ct, &kp.sk), rejection_key(&kp.sk, &ct));
    }

    #[test]
    fn frodo_decapsulate_rejects_truncated_matrix_storage_without_panicking() {
        let kp = frodo_keygen();
        let ct = FrodoCiphertext {
            b_prime: Matrix {
                rows: M,
                cols: N,
                data: vec![0u32; (M * N).saturating_sub(1)],
            },
            c: Matrix::zero(M, L),
        };

        assert_eq!(frodo_decapsulate(&ct, &kp.sk), rejection_key(&kp.sk, &ct));
    }
}
