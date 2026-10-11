//! **UOV** — Unbalanced Oil and Vinegar multivariate signatures
//! (Kipnis–Patarin–Goubin 1999; NIST additional-signatures round 3).
//!
//! UOV is the oldest unbroken multivariate scheme (25+ years) and the
//! foundation of the entire multivariate branch of the NIST on-ramp
//! (MAYO, QR-UOV and SNOVA are all UOV variants).  Its appeal: tiny
//! signatures (~100 bytes) and very fast verification; its drawback:
//! large public keys (tens of kilobytes at real parameters).
//!
//! # The trapdoor
//! Work over `F_q` with `n = v + m` variables: `v` **vinegar** and `m`
//! **oil** variables.  The secret *central map* `F: F_q^n → F_q^m` is a
//! tuple of quadratic forms with **no oil×oil monomials**: writing a
//! form as `x^T Q x`, the oil-oil block of `Q` is zero.  Fixing the
//! vinegar variables therefore makes every equation *linear* in the
//! oils — the signer just solves an `m×m` linear system.  The public
//! key `P = F ∘ T` composes with a secret invertible linear map `T`,
//! which scrambles the special structure: to a verifier, `P` looks
//! like a random quadratic map, and inverting a random quadratic map
//! (the MQ problem) is NP-hard.
//!
//! # Sign / verify
//! - Sign: `t = H(msg)`; pick random vinegars, solve the linear system
//!   for the oils (retry if singular), obtaining `x` with `F(x) = t`;
//!   output `s = T⁻¹(x)`.
//! - Verify: check `P(s) = H(msg)` — just evaluating public quadratics.
//!
//! # This implementation
//! Toy parameters `q = 256, v = 24, m = 12` (real UOV-Ip uses
//! `q = 256, v = 68, m = 44`).  Structure is faithful — including the
//! v > m "unbalanced" choice that defeats the Kipnis–Shamir attack on
//! balanced OV — but the parameter sizes are far below any security
//! level.  Educational implementation: no constant-time guarantees.

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Vinegar variables.
pub const V: usize = 24;
/// Oil variables = number of equations.
pub const M: usize = 12;
/// Total variables.
pub const N: usize = V + M;

// ── GF(256) arithmetic (AES polynomial x⁸+x⁴+x³+x+1) ─────────────────────────

fn gf_mul(a: u8, b: u8) -> u8 {
    let (mut a, mut b, mut r) = (a as u16, b as u16, 0u16);
    while b != 0 {
        if b & 1 == 1 {
            r ^= a;
        }
        a <<= 1;
        if a & 0x100 != 0 {
            a ^= 0x11b;
        }
        b >>= 1;
    }
    r as u8
}

fn gf_inv(a: u8) -> u8 {
    // a^254 by square-and-multiply (a^255 = 1 for a ≠ 0).
    let mut result = 1u8;
    let mut base = a;
    let mut e = 254u32;
    while e > 0 {
        if e & 1 == 1 {
            result = gf_mul(result, base);
        }
        base = gf_mul(base, base);
        e >>= 1;
    }
    result
}

// ── Linear algebra over GF(256) ───────────────────────────────────────────────

type Matrix = Vec<Vec<u8>>;

fn zero_matrix(rows: usize, cols: usize) -> Matrix {
    vec![vec![0u8; cols]; rows]
}

fn mat_mul(a: &Matrix, b: &Matrix) -> Matrix {
    let (r, k, c) = (a.len(), b.len(), b[0].len());
    let mut out = zero_matrix(r, c);
    for i in 0..r {
        for l in 0..k {
            if a[i][l] == 0 {
                continue;
            }
            for j in 0..c {
                out[i][j] ^= gf_mul(a[i][l], b[l][j]);
            }
        }
    }
    out
}

fn transpose(a: &Matrix) -> Matrix {
    let mut out = zero_matrix(a[0].len(), a.len());
    for (i, row) in a.iter().enumerate() {
        for (j, &x) in row.iter().enumerate() {
            out[j][i] = x;
        }
    }
    out
}

/// Solve `A·x = b` over GF(256) by Gaussian elimination.
/// Returns `None` if `A` is singular.
fn solve(a: &Matrix, b: &[u8]) -> Option<Vec<u8>> {
    let n = a.len();
    let mut m: Matrix = a.to_vec();
    let mut rhs = b.to_vec();
    for col in 0..n {
        let pivot = (col..n).find(|&r| m[r][col] != 0)?;
        m.swap(col, pivot);
        rhs.swap(col, pivot);
        let inv = gf_inv(m[col][col]);
        for j in 0..n {
            m[col][j] = gf_mul(m[col][j], inv);
        }
        rhs[col] = gf_mul(rhs[col], inv);
        for r in 0..n {
            if r != col && m[r][col] != 0 {
                let f = m[r][col];
                for j in 0..n {
                    m[r][j] ^= gf_mul(f, m[col][j]);
                }
                rhs[r] ^= gf_mul(f, rhs[col]);
            }
        }
    }
    Some(rhs)
}

/// Random invertible n×n matrix together with its inverse.
fn random_invertible(n: usize) -> (Matrix, Matrix) {
    loop {
        let mut m = zero_matrix(n, n);
        for row in m.iter_mut() {
            let mut buf = vec![0u8; n];
            random_bytes(&mut buf);
            row.copy_from_slice(&buf);
        }
        if let Some(inv) = invert(&m) {
            return (m, inv);
        }
    }
}

fn invert(a: &Matrix) -> Option<Matrix> {
    let n = a.len();
    let mut m: Matrix = a.to_vec();
    let mut inv = zero_matrix(n, n);
    for (i, row) in inv.iter_mut().enumerate() {
        row[i] = 1;
    }
    for col in 0..n {
        let pivot = (col..n).find(|&r| m[r][col] != 0)?;
        m.swap(col, pivot);
        inv.swap(col, pivot);
        let piv_inv = gf_inv(m[col][col]);
        for j in 0..n {
            m[col][j] = gf_mul(m[col][j], piv_inv);
            inv[col][j] = gf_mul(inv[col][j], piv_inv);
        }
        for r in 0..n {
            if r != col && m[r][col] != 0 {
                let f = m[r][col];
                for j in 0..n {
                    m[r][j] ^= gf_mul(f, m[col][j]);
                    inv[r][j] ^= gf_mul(f, inv[col][j]);
                }
            }
        }
    }
    Some(inv)
}

/// Evaluate the quadratic form `x^T Q x`.
fn eval_form(q: &Matrix, x: &[u8]) -> u8 {
    let mut acc = 0u8;
    for (i, row) in q.iter().enumerate() {
        if x[i] == 0 {
            continue;
        }
        let mut inner = 0u8;
        for (j, &qij) in row.iter().enumerate() {
            if qij != 0 {
                inner ^= gf_mul(qij, x[j]);
            }
        }
        acc ^= gf_mul(x[i], inner);
    }
    acc
}

// ── Keys ──────────────────────────────────────────────────────────────────────

/// Public key: `m` quadratic forms `P_k(s) = s^T Q_k s` over GF(256).
#[derive(Clone)]
pub struct UovPublicKey {
    pub forms: Vec<Matrix>,
}

/// Secret key: the central map's forms (oil×oil block zero) and `T⁻¹`.
/// (Signing needs only `T⁻¹`; `T` itself is consumed at keygen to build
/// the public forms, so it is not retained.)
#[derive(Clone)]
pub struct UovSecretKey {
    central: Vec<Matrix>,
    t_inv: Matrix,
}

/// Hash a message to the target vector in `F_q^m`.
fn hash_to_target(msg: &[u8]) -> Vec<u8> {
    let mut input = b"UOV-toy".to_vec();
    input.extend_from_slice(msg);
    shake256(&input, M)
}

pub fn uov_keygen() -> (UovPublicKey, UovSecretKey) {
    // Central map: m random quadratic forms with zero oil×oil block
    // (variables 0..V are vinegar, V..N oil).
    let mut central = Vec::with_capacity(M);
    for _ in 0..M {
        let mut q = zero_matrix(N, N);
        for i in 0..N {
            for j in i..N {
                if i >= V && j >= V {
                    continue; // no oil×oil monomials — the trapdoor
                }
                let mut b = [0u8; 1];
                random_bytes(&mut b);
                q[i][j] = b[0];
            }
        }
        central.push(q);
    }
    let (t, t_inv) = random_invertible(N);
    // Public forms: P_k(y) = F_k(T·y), i.e. Q'_k = Tᵀ Q_k T.
    let t_t = transpose(&t);
    let forms = central
        .iter()
        .map(|q| mat_mul(&t_t, &mat_mul(q, &t)))
        .collect();
    (UovPublicKey { forms }, UovSecretKey { central, t_inv })
}

pub fn uov_sign(sk: &UovSecretKey, msg: &[u8]) -> Vec<u8> {
    let target = hash_to_target(msg);
    loop {
        // Random vinegar assignment.
        let mut vinegar = vec![0u8; V];
        random_bytes(&mut vinegar);

        // With vinegars fixed, each F_k(x) = const_k + Σ_o coeff_{k,o}·x_o
        // is linear in the M oil variables.
        let mut a = zero_matrix(M, M);
        let mut b = vec![0u8; M];
        for (k, q) in sk.central.iter().enumerate() {
            // Constant part: vinegar×vinegar terms.
            let mut c = 0u8;
            for i in 0..V {
                for j in i..V {
                    if q[i][j] != 0 {
                        c ^= gf_mul(q[i][j], gf_mul(vinegar[i], vinegar[j]));
                    }
                }
            }
            // Linear part: vinegar×oil terms (upper triangle only, so
            // both (i, V+o) with i < V contribute; oil×vinegar entries
            // are zero by construction of the upper-triangular form).
            for o in 0..M {
                let mut coeff = 0u8;
                for i in 0..V {
                    if q[i][V + o] != 0 {
                        coeff ^= gf_mul(q[i][V + o], vinegar[i]);
                    }
                }
                a[k][o] = coeff;
            }
            b[k] = target[k] ^ c;
        }
        let Some(oil) = solve(&a, &b) else { continue };

        let mut x = vinegar;
        x.extend_from_slice(&oil);
        // s = T⁻¹ x.
        let mut s = vec![0u8; N];
        for (i, row) in sk.t_inv.iter().enumerate() {
            for (j, &tij) in row.iter().enumerate() {
                if tij != 0 {
                    s[i] ^= gf_mul(tij, x[j]);
                }
            }
        }
        return s;
    }
}

pub fn uov_verify(pk: &UovPublicKey, msg: &[u8], sig: &[u8]) -> bool {
    if sig.len() != N {
        return false;
    }
    let target = hash_to_target(msg);
    pk.forms
        .iter()
        .zip(target.iter())
        .all(|(q, &t)| eval_form(q, sig) == t)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gf256_field_axioms() {
        assert_eq!(gf_mul(0x53, 0xca), 0x01); // known AES inverse pair
        for a in 1..=255u8 {
            assert_eq!(gf_mul(a, gf_inv(a)), 1);
        }
    }

    #[test]
    fn central_map_is_linear_in_oils() {
        // The defining trapdoor property: with vinegars fixed, F is
        // affine in the oil variables.  Check via the oil×oil block.
        let (_, sk) = uov_keygen();
        for q in &sk.central {
            for i in V..N {
                for j in V..N {
                    assert_eq!(q[i][j], 0, "oil×oil term at ({i},{j})");
                }
            }
        }
    }

    #[test]
    fn public_key_hides_oil_structure() {
        // After composing with T, the oil×oil block is (overwhelmingly)
        // nonzero — the public map looks like random MQ.
        let (pk, _) = uov_keygen();
        let nonzero = pk
            .forms
            .iter()
            .any(|q| (V..N).any(|i| (V..N).any(|j| q[i][j] != 0)));
        assert!(nonzero);
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = uov_keygen();
        let msg = b"unbalanced oil and vinegar";
        let sig = uov_sign(&sk, msg);
        assert_eq!(sig.len(), N);
        assert!(uov_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = uov_keygen();
        let sig = uov_sign(&sk, b"message one");
        assert!(!uov_verify(&pk, b"message two", &sig));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = uov_keygen();
        let msg = b"tamper test";
        let mut sig = uov_sign(&sk, msg);
        sig[0] ^= 1;
        assert!(!uov_verify(&pk, msg, &sig));
        assert!(!uov_verify(&pk, msg, &sig[..N - 1]));
    }

    #[test]
    fn signatures_are_randomized() {
        // Fresh vinegars each call: two signatures on the same message
        // differ (overwhelmingly) but both verify.
        let (pk, sk) = uov_keygen();
        let msg = b"same message";
        let s1 = uov_sign(&sk, msg);
        let s2 = uov_sign(&sk, msg);
        assert!(uov_verify(&pk, msg, &s1));
        assert!(uov_verify(&pk, msg, &s2));
        assert_ne!(s1, s2);
    }
}
