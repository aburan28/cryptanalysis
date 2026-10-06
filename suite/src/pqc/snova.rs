//! **SNOVA** — UOV over a noncommutative matrix ring
//! (Wang–Tseng–Kuan–Chou 2022; NIST additional-signatures round 3).
//!
//! # The idea
//! Like QR-UOV, SNOVA shrinks UOV keys by giving matrix entries
//! algebraic structure — but where QR-UOV uses a *commutative* quotient
//! ring, SNOVA uses the **full matrix ring** `R = M_ℓ(F_q)` of ℓ×ℓ
//! matrices.  Variables, coefficients and equation values are all ring
//! elements, so one ring equation packs ℓ² field equations and the
//! variable count drops by ℓ² — very small keys for the multivariate
//! family.  The noncommutativity (`AB ≠ BA`) is a feature: it blocks
//! the algebraic manipulations that broke earlier structured-UOV
//! proposals.
//!
//! # Scheme (educational rendition)
//! Central map: ring-valued quadratic forms over ring variables
//! `X = (X₁,…,X_n)`, `n = v + o`:
//!
//! ```text
//! F_k(X) = Σ_{(i,j) not both oil}  Xᵢᵀ · Q_k[i][j] · Xⱼ      ∈ R
//! ```
//!
//! The missing oil×oil terms make each `F_k` *R-affine* in the oil
//! variables once vinegars are fixed; expanding over `F_q` gives an
//! `(m·ℓ²) × (o·ℓ²)` linear system, solved by Gaussian elimination.
//! The secret change of variables `T` (invertible over R) hides the
//! structure: `P_k[a][b] = Σ_{i,j} T[i][a]ᵀ · Q_k[i][j] · T[j][b]`.
//!
//! *Simplification*: real SNOVA's central map uses additional public
//! left/right multiplier matrices (`A_α, B_α, Q_α1, Q_α2`) around each
//! term, chosen from `F_q[S]` for a symmetric `S`; we use one
//! coefficient per term.  The trapdoor mechanics, the ring structure
//! and the sign/verify flow are the same.  Toy parameters `q = 16,
//! ℓ = 2, v = 8, o = 4, m = 4` (real SNOVA e.g. `q = 16, ℓ = 4,
//! v = 24, o = 5`); not constant-time; see SECURITY.md.

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

/// Ring dimension: R = M_ℓ(F_16).
pub const L: usize = 2;
/// Vinegar ring-variables.
pub const V: usize = 8;
/// Oil ring-variables.
pub const O: usize = 4;
/// Total ring-variables.
pub const N: usize = V + O;
/// Ring-valued equations (each is ℓ² field equations, so the oil
/// degrees of freedom O·ℓ² must be ≥ M·ℓ²).
pub const M: usize = 4;

// ── GF(16) (polynomial x⁴ + x + 1) ───────────────────────────────────────────

fn gf_mul(a: u8, b: u8) -> u8 {
    let (mut a, mut b, mut r) = (a, b, 0u8);
    while b != 0 {
        if b & 1 == 1 {
            r ^= a;
        }
        a <<= 1;
        if a & 0x10 != 0 {
            a ^= 0x13;
        }
        b >>= 1;
    }
    r & 0x0f
}

fn gf_inv(a: u8) -> u8 {
    let mut result = 1u8;
    let mut base = a;
    for _ in 0..3 {
        base = gf_mul(base, base);
        result = gf_mul(result, base);
    }
    result
}

// ── The ring R = M₂(F_16): row-major [a, b, c, d] ────────────────────────────

/// A 2×2 matrix over GF(16).
pub type R = [u8; 4];

const R_ZERO: R = [0; 4];

fn r_add(a: &R, b: &R) -> R {
    [a[0] ^ b[0], a[1] ^ b[1], a[2] ^ b[2], a[3] ^ b[3]]
}

fn r_mul(a: &R, b: &R) -> R {
    [
        gf_mul(a[0], b[0]) ^ gf_mul(a[1], b[2]),
        gf_mul(a[0], b[1]) ^ gf_mul(a[1], b[3]),
        gf_mul(a[2], b[0]) ^ gf_mul(a[3], b[2]),
        gf_mul(a[2], b[1]) ^ gf_mul(a[3], b[3]),
    ]
}

fn r_transpose(a: &R) -> R {
    [a[0], a[2], a[1], a[3]]
}

fn random_r() -> R {
    let mut b = [0u8; 4];
    random_bytes(&mut b);
    [b[0] & 0x0f, b[1] & 0x0f, b[2] & 0x0f, b[3] & 0x0f]
}

// ── F_16 linear algebra (for the signer's expanded system and T) ────────────

type FqMatrix = Vec<Vec<u8>>;

fn fq_invert(a: &FqMatrix) -> Option<FqMatrix> {
    let n = a.len();
    let mut m = a.to_vec();
    let mut inv: FqMatrix = vec![vec![0u8; n]; n];
    for (i, row) in inv.iter_mut().enumerate() {
        row[i] = 1;
    }
    for col in 0..n {
        let pivot = (col..n).find(|&r| m[r][col] != 0)?;
        m.swap(col, pivot);
        inv.swap(col, pivot);
        let piv = gf_inv(m[col][col]);
        for j in 0..n {
            m[col][j] = gf_mul(m[col][j], piv);
            inv[col][j] = gf_mul(inv[col][j], piv);
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

fn fq_solve(a: &FqMatrix, b: &[u8]) -> Option<Vec<u8>> {
    let inv = fq_invert(a)?;
    Some(
        inv.iter()
            .map(|row| {
                row.iter()
                    .zip(b)
                    .fold(0u8, |acc, (&x, &y)| acc ^ gf_mul(x, y))
            })
            .collect(),
    )
}

// ── The secret map T: an N×N invertible matrix over R ───────────────────────
//
// Stored flattened as a 2N×2N F_16 matrix so that invertibility and
// inversion reduce to plain Gaussian elimination; any 2N×2N matrix
// decomposes back into N×N ring blocks.

fn t_block(t: &FqMatrix, i: usize, j: usize) -> R {
    [
        t[2 * i][2 * j],
        t[2 * i][2 * j + 1],
        t[2 * i + 1][2 * j],
        t[2 * i + 1][2 * j + 1],
    ]
}

/// Apply an R-blocked matrix to a vector of ring elements.
fn t_apply(t: &FqMatrix, x: &[R]) -> Vec<R> {
    (0..x.len())
        .map(|i| {
            let mut acc = R_ZERO;
            for (j, xj) in x.iter().enumerate() {
                acc = r_add(&acc, &r_mul(&t_block(t, i, j), xj));
            }
            acc
        })
        .collect()
}

// ── Keys / sign / verify ──────────────────────────────────────────────────────

type RingForm = Vec<Vec<R>>; // N×N coefficients in R

#[derive(Clone)]
pub struct SnovaPublicKey {
    pub forms: Vec<RingForm>,
}

#[derive(Clone)]
pub struct SnovaSecretKey {
    central: Vec<RingForm>,
    t_inv: FqMatrix,
}

/// Evaluate F_k(X) = Σ Xᵢᵀ Q[i][j] Xⱼ over the ring.
fn eval_ring_form(q: &RingForm, x: &[R]) -> R {
    let mut acc = R_ZERO;
    for (i, row) in q.iter().enumerate() {
        for (j, qij) in row.iter().enumerate() {
            if *qij != R_ZERO {
                acc = r_add(&acc, &r_mul(&r_transpose(&x[i]), &r_mul(qij, &x[j])));
            }
        }
    }
    acc
}

fn hash_to_target(msg: &[u8]) -> Vec<R> {
    let mut input = b"SNOVA-toy".to_vec();
    input.extend_from_slice(msg);
    let h = shake256(&input, M * 4);
    (0..M)
        .map(|k| {
            [
                h[4 * k] & 0x0f,
                h[4 * k + 1] & 0x0f,
                h[4 * k + 2] & 0x0f,
                h[4 * k + 3] & 0x0f,
            ]
        })
        .collect()
}

pub fn snova_keygen() -> (SnovaPublicKey, SnovaSecretKey) {
    // Central map: coefficients in R, oil×oil terms zero.
    let mut central = Vec::with_capacity(M);
    for _ in 0..M {
        let mut q: RingForm = vec![vec![R_ZERO; N]; N];
        for i in 0..N {
            for j in 0..N {
                if i >= V && j >= V {
                    continue;
                }
                q[i][j] = random_r();
            }
        }
        central.push(q);
    }
    // Invertible T over R (as a flattened 2N×2N F_16 matrix).
    let (t, t_inv) = loop {
        let mut t: FqMatrix = vec![vec![0u8; 2 * N]; 2 * N];
        for row in t.iter_mut() {
            let mut buf = vec![0u8; 2 * N];
            random_bytes(&mut buf);
            for (e, b) in row.iter_mut().zip(&buf) {
                *e = b & 0x0f;
            }
        }
        if let Some(inv) = fq_invert(&t) {
            break (t, inv);
        }
    };
    // Public coefficients: P_k[a][b] = Σ_{i,j} T[i][a]ᵀ Q[i][j] T[j][b].
    // (Order matters — R is noncommutative.)
    let mut forms = Vec::with_capacity(M);
    for q in &central {
        let mut p: RingForm = vec![vec![R_ZERO; N]; N];
        for a in 0..N {
            for b in 0..N {
                let mut acc = R_ZERO;
                for i in 0..N {
                    let tia_t = r_transpose(&t_block(&t, i, a));
                    for j in 0..N {
                        if q[i][j] != R_ZERO {
                            let term = r_mul(&tia_t, &r_mul(&q[i][j], &t_block(&t, j, b)));
                            acc = r_add(&acc, &term);
                        }
                    }
                }
                p[a][b] = acc;
            }
        }
        forms.push(p);
    }
    (SnovaPublicKey { forms }, SnovaSecretKey { central, t_inv })
}

pub fn snova_sign(sk: &SnovaSecretKey, msg: &[u8]) -> Vec<R> {
    let target = hash_to_target(msg);
    let unknowns = O * 4; // each oil ring-variable has ℓ² field entries
    loop {
        let mut x: Vec<R> = (0..V).map(|_| random_r()).collect();
        x.extend(std::iter::repeat_n(R_ZERO, O));

        // Constants: F_k(vinegars, oils = 0).
        let consts: Vec<R> = sk.central.iter().map(|q| eval_ring_form(q, &x)).collect();

        // Expanded linear system over F_16: M·ℓ² equations in O·ℓ²
        // unknowns.  Columns from unit oil entries (no oil×oil terms,
        // so F is affine in the oil entries jointly).
        let mut a: FqMatrix = vec![vec![0u8; unknowns]; M * 4];
        let mut b = vec![0u8; M * 4];
        for k in 0..M {
            for e in 0..4 {
                b[k * 4 + e] = target[k][e] ^ consts[k][e];
            }
        }
        for oil in 0..O {
            for entry in 0..4 {
                let mut xu = x.clone();
                xu[V + oil][entry] = 1;
                for (k, q) in sk.central.iter().enumerate() {
                    let val = eval_ring_form(q, &xu);
                    for e in 0..4 {
                        a[k * 4 + e][oil * 4 + entry] = val[e] ^ consts[k][e];
                    }
                }
            }
        }
        let Some(sol) = fq_solve(&a, &b) else {
            continue;
        };
        for oil in 0..O {
            for entry in 0..4 {
                x[V + oil][entry] = sol[oil * 4 + entry];
            }
        }
        return t_apply(&sk.t_inv, &x);
    }
}

pub fn snova_verify(pk: &SnovaPublicKey, msg: &[u8], sig: &[R]) -> bool {
    if sig.len() != N {
        return false;
    }
    let target = hash_to_target(msg);
    pk.forms
        .iter()
        .zip(&target)
        .all(|(p, t)| eval_ring_form(p, sig) == *t)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ring_is_noncommutative() {
        // The defining feature vs. QR-UOV: AB ≠ BA in M₂(F_16).
        let a: R = [1, 1, 0, 1];
        let b: R = [1, 0, 1, 1];
        assert_ne!(r_mul(&a, &b), r_mul(&b, &a));
    }

    #[test]
    fn oil_degrees_of_freedom_match_equations() {
        assert_eq!(O * L * L, M * L * L);
    }

    #[test]
    fn public_map_matches_central_composition() {
        // P(s) computed from public coefficients equals F(T·s) — the
        // identity that makes verification meaningful.
        let (pk, sk) = snova_keygen();
        let s: Vec<R> = (0..N).map(|_| random_r()).collect();
        let t = fq_invert(&sk.t_inv).unwrap();
        let x = t_apply(&t, &s);
        for (p, q) in pk.forms.iter().zip(&sk.central) {
            assert_eq!(eval_ring_form(p, &s), eval_ring_form(q, &x));
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = snova_keygen();
        let msg = b"noncommutative oil";
        let sig = snova_sign(&sk, msg);
        assert!(snova_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = snova_keygen();
        let sig = snova_sign(&sk, b"one");
        assert!(!snova_verify(&pk, b"two", &sig));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = snova_keygen();
        let msg = b"tamper";
        let mut sig = snova_sign(&sk, msg);
        sig[0][0] ^= 1;
        assert!(!snova_verify(&pk, msg, &sig));
    }
}
