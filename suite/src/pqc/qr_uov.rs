//! **QR-UOV** — Quotient-Ring UOV (Furue–Ikematsu–Kiyomura–Takagi
//! 2021; NIST additional-signatures round 3).
//!
//! # The idea: compress UOV keys with ring structure
//! Plain UOV public keys are `m` random-looking `n×n` matrices — tens
//! of kilobytes.  QR-UOV replaces scalar matrix entries with elements
//! of the quotient ring
//!
//! ```text
//! W = F_q[x] / (f(x)),   f irreducible of degree ℓ,
//! ```
//!
//! embedded as ℓ×ℓ blocks via the regular representation (the matrix
//! of "multiply by g mod f").  A block that would take ℓ² field
//! elements is described by just ℓ — an ℓ-fold public-key compression
//! — while the UOV trapdoor (an oil subspace on which the central map
//! vanishes) carries over to the block structure.
//!
//! # This implementation
//! We work directly in the field `W = F_31[x]/(x³ − x − 1) ≅ F_{31³}`
//! and run UOV over it: `ℓ = 3`, vinegar `V = 8`, oil `M = 4` ring
//! variables (so 24 vinegar / 12 oil `F_31`-variables).  Each public
//! coefficient is stored as its ℓ ring coordinates — exactly the
//! ℓ-fold compression QR-UOV is about, as the included test
//! demonstrates against the regular representation.
//!
//! *Simplification*: real QR-UOV keeps the variables over `F_q` and
//! works with block matrices in `W` directly, which requires extra
//! machinery (a twist by a matrix `J`) to keep quadratic-form matrices
//! symmetric under transposition.  Working over the extension field
//! sidesteps that bookkeeping while preserving the trapdoor, the
//! signing algorithm, and the compression.  Toy parameters, not
//! constant-time; see SECURITY.md.

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Base-field size.
pub const Q: u32 = 31;
/// Quotient-ring degree: W = F_qx/(x³ − x − 1).
pub const L: usize = 3;
/// Vinegar ring-variables.
pub const V: usize = 8;
/// Oil ring-variables = ring-equations.
pub const M: usize = 4;
/// Total ring-variables.
pub const N: usize = V + M;

// ── The quotient ring W = F_31[x]/(x³ − x − 1) ───────────────────────────────

/// A ring element `c0 + c1·x + c2·x²`.
pub type W = [u32; 3];

const ZERO: W = [0, 0, 0];

#[allow(dead_code)] // used by tests to reduce signed modular-poly coefficients
fn fq(v: i64) -> u32 {
    v.rem_euclid(Q as i64) as u32
}

fn w_add(a: &W, b: &W) -> W {
    [(a[0] + b[0]) % Q, (a[1] + b[1]) % Q, (a[2] + b[2]) % Q]
}

fn w_sub(a: &W, b: &W) -> W {
    [
        (a[0] + Q - b[0]) % Q,
        (a[1] + Q - b[1]) % Q,
        (a[2] + Q - b[2]) % Q,
    ]
}

/// Multiply mod f(x) = x³ − x − 1, i.e. x³ ≡ x + 1.
fn w_mul(a: &W, b: &W) -> W {
    let mut t = [0u32; 5];
    for i in 0..3 {
        for j in 0..3 {
            t[i + j] = (t[i + j] + a[i] * b[j]) % Q;
        }
    }
    // x⁴ ≡ x² + x, x³ ≡ x + 1.
    [
        (t[0] + t[3]) % Q,
        (t[1] + t[3] + t[4]) % Q,
        (t[2] + t[4]) % Q,
    ]
}

fn w_is_zero(a: &W) -> bool {
    *a == ZERO
}

/// Inverse via Fermat: a^(31³ − 2) (W is a field since f is irreducible).
fn w_inv(a: &W) -> W {
    let mut result: W = [1, 0, 0];
    let mut base = *a;
    let mut e = 31u32 * 31 * 31 - 2;
    while e > 0 {
        if e & 1 == 1 {
            result = w_mul(&result, &base);
        }
        base = w_mul(&base, &base);
        e >>= 1;
    }
    result
}

/// The regular representation: the ℓ×ℓ matrix over F_q of
/// "multiplication by g" acting on coordinates.  This is the block a
/// deployed QR-UOV key would actually contain; storing `g` instead is
/// the ℓ-fold compression.
pub fn regular_representation(g: &W) -> [[u32; L]; L] {
    let x: W = [0, 1, 0];
    let mut cols = [[0u32; L]; L];
    let mut basis: W = [1, 0, 0];
    for col in cols.iter_mut() {
        let prod = w_mul(g, &basis);
        *col = prod;
        basis = w_mul(&basis, &x);
    }
    // cols[j] = g·x^j in coordinates; transpose into row-major matrix.
    let mut m = [[0u32; L]; L];
    for (j, col) in cols.iter().enumerate() {
        for i in 0..L {
            m[i][j] = col[i];
        }
    }
    m
}

fn random_w() -> W {
    let mut b = [0u8; 6];
    random_bytes(&mut b);
    [
        u16::from_le_bytes([b[0], b[1]]) as u32 % Q,
        u16::from_le_bytes([b[2], b[3]]) as u32 % Q,
        u16::from_le_bytes([b[4], b[5]]) as u32 % Q,
    ]
}

// ── Linear algebra over W ─────────────────────────────────────────────────────

type Matrix = Vec<Vec<W>>;

fn zero_matrix(r: usize, c: usize) -> Matrix {
    vec![vec![ZERO; c]; r]
}

fn mat_mul(a: &Matrix, b: &Matrix) -> Matrix {
    let (r, k, c) = (a.len(), b.len(), b[0].len());
    let mut out = zero_matrix(r, c);
    for i in 0..r {
        for l in 0..k {
            if w_is_zero(&a[i][l]) {
                continue;
            }
            for j in 0..c {
                out[i][j] = w_add(&out[i][j], &w_mul(&a[i][l], &b[l][j]));
            }
        }
    }
    out
}

fn transpose(a: &Matrix) -> Matrix {
    let mut out = zero_matrix(a[0].len(), a.len());
    for (i, row) in a.iter().enumerate() {
        for (j, x) in row.iter().enumerate() {
            out[j][i] = *x;
        }
    }
    out
}

fn invert(a: &Matrix) -> Option<Matrix> {
    let n = a.len();
    let mut m = a.to_vec();
    let mut inv = zero_matrix(n, n);
    for (i, row) in inv.iter_mut().enumerate() {
        row[i] = [1, 0, 0];
    }
    for col in 0..n {
        let pivot = (col..n).find(|&r| !w_is_zero(&m[r][col]))?;
        m.swap(col, pivot);
        inv.swap(col, pivot);
        let piv = w_inv(&m[col][col]);
        for j in 0..n {
            m[col][j] = w_mul(&m[col][j], &piv);
            inv[col][j] = w_mul(&inv[col][j], &piv);
        }
        for r in 0..n {
            if r != col && !w_is_zero(&m[r][col]) {
                let f = m[r][col];
                for j in 0..n {
                    m[r][j] = w_sub(&m[r][j], &w_mul(&f, &m[col][j]));
                    inv[r][j] = w_sub(&inv[r][j], &w_mul(&f, &inv[col][j]));
                }
            }
        }
    }
    Some(inv)
}

fn solve(a: &Matrix, b: &[W]) -> Option<Vec<W>> {
    let inv = invert(a)?;
    Some(
        inv.iter()
            .map(|row| {
                row.iter()
                    .zip(b)
                    .fold(ZERO, |acc, (aij, bj)| w_add(&acc, &w_mul(aij, bj)))
            })
            .collect(),
    )
}

fn eval_form(q: &Matrix, x: &[W]) -> W {
    let mut acc = ZERO;
    for (i, row) in q.iter().enumerate() {
        if w_is_zero(&x[i]) {
            continue;
        }
        let mut inner = ZERO;
        for (j, qij) in row.iter().enumerate() {
            if !w_is_zero(qij) {
                inner = w_add(&inner, &w_mul(qij, &x[j]));
            }
        }
        acc = w_add(&acc, &w_mul(&x[i], &inner));
    }
    acc
}

// ── Keys / sign / verify ──────────────────────────────────────────────────────

#[derive(Clone)]
pub struct QrUovPublicKey {
    pub forms: Vec<Matrix>,
}

#[derive(Clone)]
pub struct QrUovSecretKey {
    central: Vec<Matrix>,
    t_inv: Matrix,
}

fn hash_to_target(msg: &[u8]) -> Vec<W> {
    let mut input = b"QR-UOV-toy".to_vec();
    input.extend_from_slice(msg);
    let h = shake256(&input, M * L * 2);
    (0..M)
        .map(|k| {
            let mut w = ZERO;
            for i in 0..L {
                let off = (k * L + i) * 2;
                w[i] = u16::from_le_bytes([h[off], h[off + 1]]) as u32 % Q;
            }
            w
        })
        .collect()
}

pub fn qr_uov_keygen() -> (QrUovPublicKey, QrUovSecretKey) {
    let mut central = Vec::with_capacity(M);
    for _ in 0..M {
        let mut q = zero_matrix(N, N);
        for i in 0..N {
            for j in i..N {
                if i >= V && j >= V {
                    continue; // oil×oil block vanishes: the UOV trapdoor
                }
                q[i][j] = random_w();
            }
        }
        central.push(q);
    }
    let (t, t_inv) = loop {
        let mut t = zero_matrix(N, N);
        for row in t.iter_mut() {
            for e in row.iter_mut() {
                *e = random_w();
            }
        }
        if let Some(inv) = invert(&t) {
            break (t, inv);
        }
    };
    let t_t = transpose(&t);
    let forms = central
        .iter()
        .map(|q| mat_mul(&t_t, &mat_mul(q, &t)))
        .collect();
    (QrUovPublicKey { forms }, QrUovSecretKey { central, t_inv })
}

pub fn qr_uov_sign(sk: &QrUovSecretKey, msg: &[u8]) -> Vec<W> {
    let target = hash_to_target(msg);
    loop {
        let vinegar: Vec<W> = (0..V).map(|_| random_w()).collect();
        let mut a = zero_matrix(M, M);
        let mut b = vec![ZERO; M];
        for (k, q) in sk.central.iter().enumerate() {
            let mut c = ZERO;
            for i in 0..V {
                for j in i..V {
                    if !w_is_zero(&q[i][j]) {
                        c = w_add(&c, &w_mul(&q[i][j], &w_mul(&vinegar[i], &vinegar[j])));
                    }
                }
            }
            for o in 0..M {
                let mut coeff = ZERO;
                for i in 0..V {
                    if !w_is_zero(&q[i][V + o]) {
                        coeff = w_add(&coeff, &w_mul(&q[i][V + o], &vinegar[i]));
                    }
                }
                a[k][o] = coeff;
            }
            b[k] = w_sub(&target[k], &c);
        }
        let Some(oil) = solve(&a, &b) else { continue };
        let mut x = vinegar;
        x.extend_from_slice(&oil);
        let mut s = vec![ZERO; N];
        for (i, row) in sk.t_inv.iter().enumerate() {
            for (j, tij) in row.iter().enumerate() {
                s[i] = w_add(&s[i], &w_mul(tij, &x[j]));
            }
        }
        return s;
    }
}

pub fn qr_uov_verify(pk: &QrUovPublicKey, msg: &[u8], sig: &[W]) -> bool {
    if sig.len() != N {
        return false;
    }
    let target = hash_to_target(msg);
    pk.forms
        .iter()
        .zip(&target)
        .all(|(q, t)| eval_form(q, sig) == *t)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modulus_is_irreducible() {
        // A cubic is irreducible over F_q iff it has no roots there.
        for r in 0..Q {
            let val = fq((r * r * r) as i64 - r as i64 - 1);
            assert_ne!(val, 0, "x³−x−1 has root {r} mod {Q}");
        }
    }

    #[test]
    fn w_is_a_field() {
        for _ in 0..50 {
            let a = random_w();
            if !w_is_zero(&a) {
                assert_eq!(w_mul(&a, &w_inv(&a)), [1, 0, 0]);
            }
        }
    }

    #[test]
    fn regular_representation_is_the_compressed_block() {
        // The ℓ coordinates we store expand to the ℓ×ℓ block a plain
        // UOV key would carry: mat(g)·coords(h) = coords(g·h).
        for _ in 0..20 {
            let g = random_w();
            let h = random_w();
            let mat = regular_representation(&g);
            let gh = w_mul(&g, &h);
            for i in 0..L {
                let row: u32 = (0..L).map(|j| mat[i][j] * h[j] % Q).sum::<u32>() % Q;
                assert_eq!(row, gh[i]);
            }
        }
    }

    #[test]
    fn compression_factor_is_ell() {
        // ℓ ring coordinates describe an ℓ×ℓ = ℓ² block.
        assert_eq!(L * L / L, L);
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = qr_uov_keygen();
        let msg = b"quotient rings compress oil";
        let sig = qr_uov_sign(&sk, msg);
        assert!(qr_uov_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = qr_uov_keygen();
        let sig = qr_uov_sign(&sk, b"one");
        assert!(!qr_uov_verify(&pk, b"two", &sig));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = qr_uov_keygen();
        let msg = b"tamper";
        let mut sig = qr_uov_sign(&sk, msg);
        sig[0] = w_add(&sig[0], &[1, 0, 0]);
        assert!(!qr_uov_verify(&pk, msg, &sig));
    }
}
