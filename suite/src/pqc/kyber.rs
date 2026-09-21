//! Simplified Kyber / ML-KEM — educational post-quantum key encapsulation.
//!
//! # Background
//! Kyber (standardised as ML-KEM in NIST FIPS 203) is a lattice-based KEM
//! whose security reduces to the Module Learning With Errors (Module-LWE)
//! problem.  The core idea is:
//!
//!   - Work in the polynomial ring  Rq = Zqx / (xⁿ + 1),  q = 3329, n = 256.
//!   - Key generation: sample secret **s** and error **e** from a centred
//!     binomial distribution; public key is  **A**·**s** + **e**.
//!   - Encapsulation: sample a fresh secret **r**; ciphertext is
//!     (**A**ᵀ·**r** + **e₁**, **t**·**r** + **e₂** + encode(m)).
//!   - Decapsulation: recover the message by subtracting off the LWE term.
//!
//! # This implementation
//! This is a *didactic*, non-interoperable toy implementation inspired by
//! Kyber-512 (k=2):
//!   - Polynomial arithmetic is in Zqx / (xⁿ + 1).
//!   - The Number Theoretic Transform (NTT) is omitted; multiplication uses
//!     naive O(n²) schoolbook convolution for clarity.
//!   - Random sampling uses the OS CSPRNG instead of SHAKE-256 XOF expansion.
//!   - Compression / decompression uses the standard rounding formulas.
//!   - The resulting ciphertexts are *NOT* compatible with the NIST standard.
//!
//! For production use, see the `pqcrypto-kyber` or `kyber-kem` crates.

use crate::hash::sha256::sha256;
use crate::utils::random::random_bytes_vec;

// ── Parameters (Kyber-512) ────────────────────────────────────────────────────

const N: usize = 256; // Polynomial degree
const Q: i64 = 3329; // Modulus
const K: usize = 2; // Module rank (Kyber-512 uses k=2)
const ETA: i64 = 3; // Noise distribution parameter (centred binomial)

// Compression bit widths for ciphertext components
const DU: u32 = 10;
const DV: u32 = 4;

// ── Polynomial type ───────────────────────────────────────────────────────────

/// A polynomial in Zqx / (xⁿ + 1), stored as `N` coefficients.
#[derive(Clone, Debug, PartialEq)]
pub struct Poly([i64; N]);

impl Poly {
    pub fn zero() -> Self {
        Poly([0; N])
    }

    /// Reduce all coefficients mod Q into [0, Q)
    #[allow(dead_code)]
    fn reduce(&mut self) {
        for c in self.0.iter_mut() {
            *c = ((*c % Q) + Q) % Q;
        }
    }

    /// Polynomial addition mod q
    pub fn add(&self, rhs: &Poly) -> Poly {
        let mut out = Poly::zero();
        for i in 0..N {
            out.0[i] = (self.0[i] + rhs.0[i]).rem_euclid(Q);
        }
        out
    }

    /// Polynomial subtraction mod q
    pub fn sub(&self, rhs: &Poly) -> Poly {
        let mut out = Poly::zero();
        for i in 0..N {
            out.0[i] = (self.0[i] - rhs.0[i]).rem_euclid(Q);
        }
        out
    }

    /// Schoolbook polynomial multiplication mod (xⁿ + 1) and mod q.
    ///
    /// The reduction by (xⁿ + 1) means that xⁿ ≡ -1, so for i+j ≥ n,
    /// coefficient [i+j mod n] is negated.
    pub fn mul(&self, rhs: &Poly) -> Poly {
        let mut out = Poly::zero();
        for i in 0..N {
            for j in 0..N {
                let idx = (i + j) % N;
                let sign: i64 = if i + j >= N { -1 } else { 1 };
                out.0[idx] = (out.0[idx] + sign * self.0[i] * rhs.0[j]).rem_euclid(Q);
            }
        }
        out
    }

    /// Compress coefficient to `d` bits: round(x * 2^d / q) mod 2^d
    pub fn compress(&self, d: u32) -> Vec<u16> {
        let two_d = 1i64 << d;
        self.0
            .iter()
            .map(|&c| ((c * two_d + Q / 2) / Q).rem_euclid(two_d) as u16)
            .collect()
    }

    /// Decompress from `d`-bit representation: round(x * q / 2^d)
    pub fn decompress(data: &[u16], d: u32) -> Poly {
        let two_d = 1i64 << d;
        let mut p = Poly::zero();
        for (i, &v) in data.iter().enumerate().take(N) {
            p.0[i] = (v as i64 * Q + two_d / 2) / two_d;
        }
        p
    }
}

// ── Vector operations ─────────────────────────────────────────────────────────

type PolyVec = [Poly; K];

fn polyvec_add(a: &PolyVec, b: &PolyVec) -> PolyVec {
    [a[0].add(&b[0]), a[1].add(&b[1])]
}

/// Inner product of two poly-vectors (dot product mod q)
fn polyvec_dot(a: &PolyVec, b: &PolyVec) -> Poly {
    a[0].mul(&b[0]).add(&a[1].mul(&b[1]))
}

/// Matrix-vector product: A ∈ R^(k×k), v ∈ R^k → R^k
fn matrix_vec_mul(a: &[PolyVec; K], v: &PolyVec) -> PolyVec {
    [polyvec_dot(&a[0], v), polyvec_dot(&a[1], v)]
}

/// Transpose matrix-vector product: Aᵀ·v
fn matrix_transpose_vec_mul(a: &[PolyVec; K], v: &PolyVec) -> PolyVec {
    let at = [
        [a[0][0].clone(), a[1][0].clone()],
        [a[0][1].clone(), a[1][1].clone()],
    ];
    matrix_vec_mul(&at, v)
}

// ── Sampling ──────────────────────────────────────────────────────────────────

/// Sample a polynomial from a centred binomial distribution CBD(η):
/// each coefficient = Σ(aᵢ - bᵢ) for i=1..η where aᵢ,bᵢ are random bits.
fn sample_cbd() -> Poly {
    let bytes = random_bytes_vec((N * 2 * ETA as usize).div_ceil(8) + 8);
    let mut p = Poly::zero();
    let mut bit_idx = 0usize;

    for coeff in p.0.iter_mut() {
        let mut a = 0i64;
        let mut b = 0i64;
        for _ in 0..ETA {
            let byte_a = bytes[bit_idx / 8];
            let bit_a = (byte_a >> (bit_idx % 8)) & 1;
            a += bit_a as i64;
            bit_idx += 1;

            let byte_b = bytes[bit_idx / 8];
            let bit_b = (byte_b >> (bit_idx % 8)) & 1;
            b += bit_b as i64;
            bit_idx += 1;
        }
        *coeff = (a - b).rem_euclid(Q);
    }
    p
}

/// Sample a random public polynomial (uniform in Zq)
fn sample_uniform() -> Poly {
    let mut p = Poly::zero();
    let mut filled = 0usize;
    while filled < N {
        let bytes = random_bytes_vec(3);
        let candidates = [
            (bytes[0] as i64 | ((bytes[1] as i64) << 8)) & 0x0fff,
            (((bytes[1] as i64) >> 4) | ((bytes[2] as i64) << 4)) & 0x0fff,
        ];
        for v in candidates {
            if v < Q {
                p.0[filled] = v;
                filled += 1;
                if filled == N {
                    break;
                }
            }
        }
    }
    p
}

fn sample_uniform_matrix() -> [PolyVec; K] {
    [
        [sample_uniform(), sample_uniform()],
        [sample_uniform(), sample_uniform()],
    ]
}

fn sample_cbd_vec() -> PolyVec {
    [sample_cbd(), sample_cbd()]
}

// ── Message encoding/decoding ─────────────────────────────────────────────────

/// Encode a 32-byte message into a polynomial: bit i → coefficient 0 or q/2.
fn encode_message(msg: &[u8; 32]) -> Poly {
    let mut p = Poly::zero();
    for (byte_idx, &byte) in msg.iter().enumerate() {
        for bit in 0..8 {
            let coeff_idx = byte_idx * 8 + bit;
            if coeff_idx < N {
                p.0[coeff_idx] = if (byte >> bit) & 1 == 1 { Q / 2 } else { 0 };
            }
        }
    }
    p
}

/// Decode a polynomial back into a 32-byte message by rounding each coefficient
/// to the nearest multiple of q/2.
fn decode_message(p: &Poly) -> [u8; 32] {
    let mut msg = [0u8; 32];
    for i in 0..N.min(256) {
        let rounded = ((2 * p.0[i] + Q / 2) / Q) % 2;
        if rounded == 1 {
            msg[i / 8] |= 1 << (i % 8);
        }
    }
    msg
}

// ── Serialisation helpers ─────────────────────────────────────────────────────

fn compress_polyvec(v: &PolyVec, d: u32) -> Vec<Vec<u16>> {
    v.iter().map(|p| p.compress(d)).collect()
}

fn decompress_polyvec(data: &[Vec<u16>], d: u32) -> PolyVec {
    [Poly::decompress(&data[0], d), Poly::decompress(&data[1], d)]
}

// ── Public types ──────────────────────────────────────────────────────────────

/// Kyber public key: the matrix A and the vector t = A·s + e.
#[derive(Clone, Debug)]
pub struct KyberPublicKey {
    pub a: [PolyVec; K],
    pub t: PolyVec,
}

/// Kyber private key: the secret vector s.
#[derive(Clone, Debug)]
pub struct KyberPrivateKey {
    pub s: PolyVec,
    pub public: KyberPublicKey,
}

impl Drop for KyberPrivateKey {
    fn drop(&mut self) {
        for poly in self.s.iter_mut() {
            for c in poly.0.iter_mut() {
                *c = 0;
            }
        }
    }
}

/// An encapsulated shared secret (ciphertext).
#[derive(Clone, Debug)]
pub struct KyberCiphertext {
    pub u: Vec<Vec<u16>>, // Compressed A^T·r + e1
    pub v: Vec<u16>,      // Compressed t·r + e2 + msg
}

pub fn kyber_ciphertext_is_well_formed(ct: &KyberCiphertext) -> bool {
    let u_bound = 1u16 << DU;
    let v_bound = 1u16 << DV;
    ct.u.len() == K
        && ct
            .u
            .iter()
            .all(|poly| poly.len() == N && poly.iter().all(|&x| x < u_bound))
        && ct.v.len() == N
        && ct.v.iter().all(|&x| x < v_bound)
}

/// Canonical toy-Kyber ciphertext serialization used for transcript binding.
pub fn kyber_ciphertext_to_bytes(ct: &KyberCiphertext) -> Result<Vec<u8>, &'static str> {
    if !kyber_ciphertext_is_well_formed(ct) {
        return Err("malformed Kyber ciphertext");
    }
    let mut out = Vec::with_capacity((K + 1) * N * 2);
    for poly in &ct.u {
        for &coeff in poly {
            out.extend_from_slice(&coeff.to_le_bytes());
        }
    }
    for &coeff in &ct.v {
        out.extend_from_slice(&coeff.to_le_bytes());
    }
    Ok(out)
}

/// Key generation: sample s, e; compute t = A·s + e.
pub fn kyber_keygen() -> KyberPrivateKey {
    let a = sample_uniform_matrix();
    let s = sample_cbd_vec();
    let e = sample_cbd_vec();

    // t = A·s + e
    let as_prod = matrix_vec_mul(&a, &s);
    let t = polyvec_add(&as_prod, &e);

    KyberPrivateKey {
        s,
        public: KyberPublicKey { a, t },
    }
}

/// Encapsulation: sample r; produce ciphertext and shared secret.
/// Returns `(ciphertext, shared_secret_32_bytes)`.
pub fn kyber_encapsulate(pk: &KyberPublicKey) -> (KyberCiphertext, [u8; 32]) {
    let m: [u8; 32] = random_bytes_vec(32).try_into().unwrap();

    let r = sample_cbd_vec();
    let e1 = sample_cbd_vec();
    let e2 = sample_cbd();
    let mu = encode_message(&m);

    // u = A^T·r + e1
    let at_r = matrix_transpose_vec_mul(&pk.a, &r);
    let u_poly = polyvec_add(&at_r, &e1);

    // v = t·r + e2 + μ
    let tr = polyvec_dot(&pk.t, &r);
    let v_poly = tr.add(&e2).add(&mu);

    let u_compressed = compress_polyvec(&u_poly, DU);
    let v_compressed = v_poly.compress(DV);

    // Shared secret = SHA256(m)
    let shared_secret: [u8; 32] = sha256(&m);

    (
        KyberCiphertext {
            u: u_compressed,
            v: v_compressed,
        },
        shared_secret,
    )
}

/// Decapsulation: recover the message from the ciphertext, return shared secret.
pub fn kyber_decapsulate(sk: &KyberPrivateKey, ct: &KyberCiphertext) -> [u8; 32] {
    kyber_decapsulate_checked(sk, ct).expect("malformed Kyber ciphertext")
}

/// Checked decapsulation that rejects malformed ciphertext shapes.
pub fn kyber_decapsulate_checked(
    sk: &KyberPrivateKey,
    ct: &KyberCiphertext,
) -> Result<[u8; 32], &'static str> {
    if !kyber_ciphertext_is_well_formed(ct) {
        return Err("malformed Kyber ciphertext");
    }
    let u_poly = decompress_polyvec(&ct.u, DU);
    let v_poly = Poly::decompress(&ct.v, DV);

    // Recover μ ≈ v - s·u = (t·r + e2 + μ) - s·(A^T·r + e1)
    //           = μ + e2 + e1·s - e1·s  (with small noise)
    //           ≈ μ
    let su = polyvec_dot(&sk.s, &u_poly);
    let recovered_mu = v_poly.sub(&su);
    let m = decode_message(&recovered_mu);

    Ok(sha256(&m))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn poly_add_sub() {
        let mut a = Poly::zero();
        let mut b = Poly::zero();
        a.0[0] = 100;
        b.0[0] = 200;
        let sum = a.add(&b);
        assert_eq!(sum.0[0], 300);
        let diff = sum.sub(&b);
        assert_eq!(diff.0[0], 100);
    }

    #[test]
    fn encode_decode_roundtrip() {
        let msg: [u8; 32] = [0xab; 32];
        let poly = encode_message(&msg);
        let recovered = decode_message(&poly);
        assert_eq!(recovered, msg);
    }

    #[test]
    fn kyber_kem_roundtrip() {
        let sk = kyber_keygen();
        let (ct, ss_enc) = kyber_encapsulate(&sk.public);
        let ss_dec = kyber_decapsulate(&sk, &ct);
        assert_eq!(ss_enc, ss_dec, "shared secrets must match");
    }

    #[test]
    fn poly_mul_identity() {
        // 1 · p = p for any p
        let mut one = Poly::zero();
        one.0[0] = 1;
        let mut p = Poly::zero();
        p.0[0] = 7;
        p.0[1] = 13;
        p.0[5] = 100;
        p.0[N - 1] = 42;
        assert_eq!(one.mul(&p), p);
        assert_eq!(p.mul(&one), p);
    }

    #[test]
    fn poly_mul_anticyclic() {
        // x · x^(N-1) = x^N ≡ -1 (mod xⁿ + 1)
        let mut x = Poly::zero();
        x.0[1] = 1;
        let mut x_n_minus_1 = Poly::zero();
        x_n_minus_1.0[N - 1] = 1;
        let prod = x.mul(&x_n_minus_1);
        // Constant term should be -1 mod Q = Q - 1; all other coefficients zero.
        assert_eq!(prod.0[0], Q - 1);
        for i in 1..N {
            assert_eq!(prod.0[i], 0, "coeff {i} should be 0");
        }
    }

    #[test]
    fn poly_mul_commutative() {
        // Random-ish polynomials; mul must be commutative.
        let mut a = Poly::zero();
        let mut b = Poly::zero();
        for i in 0..16 {
            a.0[i] = (i as i64 * 17 + 3).rem_euclid(Q);
            b.0[i] = (i as i64 * 31 + 5).rem_euclid(Q);
        }
        assert_eq!(a.mul(&b), b.mul(&a));
    }

    #[test]
    fn poly_mul_distributes_over_add() {
        // a·(b+c) == a·b + a·c
        let mut a = Poly::zero();
        let mut b = Poly::zero();
        let mut c = Poly::zero();
        for i in 0..8 {
            a.0[i] = (i as i64 + 1) * 11;
            b.0[i] = (i as i64 + 2) * 13;
            c.0[i] = (i as i64 + 3) * 17;
        }
        let lhs = a.mul(&b.add(&c));
        let rhs = a.mul(&b).add(&a.mul(&c));
        assert_eq!(lhs, rhs);
    }

    #[test]
    fn poly_compress_decompress_approx_inverse() {
        // For d=10 the round-trip error per coefficient is bounded by q/2^(d+1).
        let mut p = Poly::zero();
        for i in 0..N {
            p.0[i] = (i as i64 * 13 + 7).rem_euclid(Q);
        }
        let compressed = p.compress(10);
        let recovered = Poly::decompress(&compressed, 10);
        let bound = (Q + (1 << 11) - 1) / (1 << 11) + 1; // ⌈q/2^11⌉ + 1
        for i in 0..N {
            let diff = (p.0[i] - recovered.0[i]).abs();
            let wrap = (Q - diff).abs();
            let err = diff.min(wrap);
            assert!(err <= bound, "coeff {i}: err {err} > bound {bound}");
        }
    }

    #[test]
    fn encode_decode_message_patterns() {
        let patterns: [[u8; 32]; 4] = [
            [0x00; 32],
            [0xff; 32],
            [0xaa; 32],
            *b"PaymentChannelSettlementRoot=ABC",
        ];
        for msg in &patterns {
            let p = encode_message(msg);
            // Encoded coefficients must be exactly 0 or Q/2.
            for &c in &p.0 {
                assert!(c == 0 || c == Q / 2, "encoded coeff out of set: {c}");
            }
            assert_eq!(decode_message(&p), *msg);
        }
    }

    #[test]
    fn cbd_samples_are_reduced() {
        // Centred-binomial samples should sit in [0, Q) after reduction,
        // i.e., representing values in {-η..η} (here {-3..3}) mod q.
        for _ in 0..4 {
            let p = sample_cbd();
            for &c in &p.0 {
                assert!((0..Q).contains(&c), "out-of-range coeff {c}");
                // Modulo Q, valid representatives are {0, 1, 2, 3} ∪ {Q-3, Q-2, Q-1}.
                let small = c <= ETA || c >= Q - ETA;
                assert!(small, "coeff {c} not in CBD range");
            }
        }
    }

    #[test]
    fn kyber_multiple_roundtrips_distinct_secrets() {
        // Each fresh encapsulation samples a new message, so two encaps under
        // the same public key must (with overwhelming probability) yield
        // different shared secrets — and both must decap correctly.
        let sk = kyber_keygen();
        let (ct1, ss1) = kyber_encapsulate(&sk.public);
        let (ct2, ss2) = kyber_encapsulate(&sk.public);
        assert_ne!(ss1, ss2, "two encaps must produce different secrets");
        assert_eq!(ss1, kyber_decapsulate(&sk, &ct1));
        assert_eq!(ss2, kyber_decapsulate(&sk, &ct2));
    }

    #[test]
    fn kyber_decap_with_wrong_key_differs() {
        // Encapsulate under Alice's pk; Bob's sk must not recover Alice's secret.
        let alice = kyber_keygen();
        let bob = kyber_keygen();
        let (ct, alice_ss) = kyber_encapsulate(&alice.public);
        let bob_ss = kyber_decapsulate(&bob, &ct);
        assert_ne!(alice_ss, bob_ss);
    }

    #[test]
    fn kyber_rejects_malformed_ciphertext() {
        let sk = kyber_keygen();
        let bad = KyberCiphertext {
            u: vec![vec![0u16; N]],
            v: vec![0u16; N],
        };
        assert!(kyber_decapsulate_checked(&sk, &bad).is_err());
    }

    #[test]
    fn kyber_ciphertext_serialization_is_stable() {
        let ct = KyberCiphertext {
            u: vec![vec![1u16; N], vec![2u16; N]],
            v: vec![3u16; N],
        };
        let bytes1 = kyber_ciphertext_to_bytes(&ct).unwrap();
        let bytes2 = kyber_ciphertext_to_bytes(&ct).unwrap();
        assert_eq!(bytes1, bytes2);
        assert_eq!(bytes1.len(), (K + 1) * N * 2);
    }
}
