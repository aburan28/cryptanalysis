//! **MAYO** — whipped Unbalanced Oil-and-Vinegar signatures
//! (Beullens 2021; NIST additional-signatures round 3).
//!
//! # The problem MAYO solves
//! Plain UOV needs an oil space of dimension `m` (one oil variable per
//! equation), which forces huge public keys.  MAYO uses a *deliberately
//! too small* oil space of dimension `o < m` — the central map alone
//! can no longer be inverted (only `o` degrees of freedom for `m`
//! equations).  The fix is **whipping**: evaluate the same public map
//! `P` on `k` different inputs and combine the results into a larger
//! map
//!
//! ```text
//! P*(x₁,…,x_k) = Σᵢ Eᵢ·P(xᵢ)  +  Σ_{i<j} E_{ij}·P'(xᵢ,xⱼ)
//! ```
//!
//! where `P'(x,y) = P(x+y) − P(x) − P(y)` is the *polar form* (bilinear)
//! and the `E` matrices are public invertible "emulsifiers".  Every
//! `xᵢ` contributes `o` oil degrees of freedom, so `k·o ≥ m` restores
//! invertibility while the public key stays one small-`o` UOV map.
//!
//! # Sign / verify
//! - Sign: hash to `t ∈ F_q^m`; fix random vinegars in all `k` inputs;
//!   the whipped system is *linear* in the `k·o` stacked oil variables
//!   (oil×oil parts vanish in both `P(xᵢ)` and the polar forms); solve
//!   and un-scramble through `T⁻¹`.
//! - Verify: recompute `P*(s₁,…,s_k)` from the public map and compare.
//!
//! # This implementation
//! Toy parameters `q = 16, n = 20, o = 4, m = 12, k = 4` (real MAYO₁
//! uses `q = 16, n = 86, o = 8, m = 78, k = 10`).  Emulsifiers are
//! powers of the companion matrix of a fixed degree-`m` polynomial, as
//! in the spec (the spec's polynomial is irreducible; ours is merely
//! invertible, which suffices for the mechanics).  Educational: toy
//! sizes, no constant-time guarantees, no key compression (real MAYO
//! seeds most of the key material from SHAKE).

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;

pub const Q: u8 = 16;
/// Total variables per input.
pub const N: usize = 20;
/// Oil-space dimension (deliberately < M — the MAYO twist).
pub const O: usize = 4;
/// Vinegar variables.
pub const V: usize = N - O;
/// Equations.
pub const M: usize = 12;
/// Whipping factor; K·O ≥ M restores invertibility.
pub const K: usize = 4;

// The MAYO premise: o < m, so the un-whipped central map cannot be inverted
// (o unknowns, m equations), while k whipped copies give enough equations.
const _: () = {
    assert!(O < M);
    assert!(K * O >= M);
};

// ── GF(16) arithmetic (polynomial x⁴ + x + 1) ────────────────────────────────

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
        base = gf_mul(base, base); // a², a⁴, a⁸
        result = gf_mul(result, base); // a^14 = a^{-1}
    }
    result
}

// ── Matrices over GF(16) ──────────────────────────────────────────────────────

type Matrix = Vec<Vec<u8>>;

fn zero_matrix(r: usize, c: usize) -> Matrix {
    vec![vec![0u8; c]; r]
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

fn mat_vec(a: &Matrix, x: &[u8]) -> Vec<u8> {
    a.iter()
        .map(|row| {
            row.iter()
                .zip(x)
                .fold(0u8, |acc, (&aij, &xj)| acc ^ gf_mul(aij, xj))
        })
        .collect()
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

/// Solve the (possibly underdetermined) system `A·x = b` with `A`
/// `rows × cols`, `cols ≥ rows`.  Free variables are set to zero.
/// Returns `None` if the system is inconsistent or rank-deficient.
fn solve_underdetermined(a: &Matrix, b: &[u8]) -> Option<Vec<u8>> {
    let rows = a.len();
    let cols = a[0].len();
    let mut m: Matrix = a.to_vec();
    let mut rhs = b.to_vec();
    let mut pivot_col = vec![usize::MAX; rows];
    let mut row = 0;
    for col in 0..cols {
        if row == rows {
            break;
        }
        let Some(p) = (row..rows).find(|&r| m[r][col] != 0) else {
            continue;
        };
        m.swap(row, p);
        rhs.swap(row, p);
        let inv = gf_inv(m[row][col]);
        for j in 0..cols {
            m[row][j] = gf_mul(m[row][j], inv);
        }
        rhs[row] = gf_mul(rhs[row], inv);
        for r in 0..rows {
            if r != row && m[r][col] != 0 {
                let f = m[r][col];
                for j in 0..cols {
                    m[r][j] ^= gf_mul(f, m[row][j]);
                }
                rhs[r] ^= gf_mul(f, rhs[row]);
            }
        }
        pivot_col[row] = col;
        row += 1;
    }
    if row < rows {
        return None; // rank-deficient: retry with fresh vinegars
    }
    let mut x = vec![0u8; cols];
    for r in 0..rows {
        x[pivot_col[r]] = rhs[r];
    }
    Some(x)
}

// ── Emulsifier matrices ───────────────────────────────────────────────────────

/// Public emulsifiers: `E_c` = c-th power of the companion matrix of
/// `z^m + z³ + 1` over GF(16).  Invertible (constant term ≠ 0), and
/// distinct powers keep the k whipped copies from collapsing into one.
fn emulsifiers(count: usize) -> Vec<Matrix> {
    let mut companion = zero_matrix(M, M);
    for i in 1..M {
        companion[i][i - 1] = 1;
    }
    companion[0][M - 1] = 1; // −1 coefficient of z^0 term
    companion[3][M - 1] ^= 1; // −1 coefficient of z³ term
    let mut e = zero_matrix(M, M);
    for (i, row) in e.iter_mut().enumerate() {
        row[i] = 1;
    }
    let mut out = Vec::with_capacity(count);
    for _ in 0..count {
        out.push(e.clone());
        e = mat_mul(&companion, &e);
    }
    out
}

/// Emulsifier index for the pair term (i, j), i < j.
fn pair_index(i: usize, j: usize) -> usize {
    K + (i * (2 * K - i - 1)) / 2 + (j - i - 1)
}

// ── Keys ──────────────────────────────────────────────────────────────────────

#[derive(Clone)]
pub struct MayoPublicKey {
    /// The m public quadratic forms (full n×n matrices).
    pub forms: Vec<Matrix>,
}

#[derive(Clone)]
pub struct MayoSecretKey {
    central: Vec<Matrix>,
    t_inv: Matrix,
}

/// A MAYO signature: the k whipped inputs, each in `F_q^n`.
#[derive(Clone, Debug, PartialEq)]
pub struct MayoSignature {
    pub inputs: Vec<Vec<u8>>,
}

fn hash_to_target(msg: &[u8]) -> Vec<u8> {
    let mut input = b"MAYO-toy".to_vec();
    input.extend_from_slice(msg);
    shake256(&input, M).iter().map(|b| b & 0x0f).collect()
}

fn random_gf16_vec(len: usize) -> Vec<u8> {
    let mut buf = vec![0u8; len];
    random_bytes(&mut buf);
    buf.iter().map(|b| b & 0x0f).collect()
}

pub fn mayo_keygen() -> (MayoPublicKey, MayoSecretKey) {
    // Central map: m upper-triangular forms, zero oil×oil block
    // (variables 0..V vinegar, V..N oil — only O of them, O < M).
    let mut central = Vec::with_capacity(M);
    for _ in 0..M {
        let mut q = zero_matrix(N, N);
        for i in 0..N {
            for j in i..N {
                if i >= V && j >= V {
                    continue;
                }
                let mut b = [0u8; 1];
                random_bytes(&mut b);
                q[i][j] = b[0] & 0x0f;
            }
        }
        central.push(q);
    }
    let (t, t_inv) = loop {
        let mut t = zero_matrix(N, N);
        for row in t.iter_mut() {
            let r = random_gf16_vec(N);
            row.copy_from_slice(&r);
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
    (MayoPublicKey { forms }, MayoSecretKey { central, t_inv })
}

/// Evaluate one quadratic form `x^T Q x`.
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

/// Polar form of one quadratic form: `x^T (Q + Qᵀ) y`.
fn eval_polar(q: &Matrix, x: &[u8], y: &[u8]) -> u8 {
    let mut acc = 0u8;
    for i in 0..q.len() {
        for j in 0..q.len() {
            let sym = q[i][j] ^ q[j][i];
            if sym != 0 {
                acc ^= gf_mul(sym, gf_mul(x[i], y[j]));
            }
        }
    }
    acc
}

/// Evaluate the whipped map `P*` on k inputs, for any family of m
/// forms (public or central).
fn eval_whipped(forms: &[Matrix], inputs: &[Vec<u8>]) -> Vec<u8> {
    let e = emulsifiers(K + K * (K - 1) / 2);
    let mut acc = vec![0u8; M];
    for i in 0..K {
        let p: Vec<u8> = forms.iter().map(|q| eval_form(q, &inputs[i])).collect();
        let ep = mat_vec(&e[i], &p);
        for (a, v) in acc.iter_mut().zip(ep) {
            *a ^= v;
        }
    }
    for i in 0..K {
        for j in (i + 1)..K {
            let p: Vec<u8> = forms
                .iter()
                .map(|q| eval_polar(q, &inputs[i], &inputs[j]))
                .collect();
            let ep = mat_vec(&e[pair_index(i, j)], &p);
            for (a, v) in acc.iter_mut().zip(ep) {
                *a ^= v;
            }
        }
    }
    acc
}

pub fn mayo_sign(sk: &MayoSecretKey, msg: &[u8]) -> MayoSignature {
    let target = hash_to_target(msg);
    let e = emulsifiers(K + K * (K - 1) / 2);
    loop {
        // Fix random vinegars in every copy; oils are the unknowns.
        let vins: Vec<Vec<u8>> = (0..K).map(|_| random_gf16_vec(V)).collect();

        // Build the m × (K·O) linear system over the stacked oils.
        // Contribution of copy i alone: E_i · [ const_i + L_i·oil_i ].
        // Contribution of pair (i,j): E_ij · [ const_ij + terms linear
        // in oil_i and oil_j ] (the oil×oil part of the polar form
        // vanishes because the central oil×oil block is zero).
        let mut a = zero_matrix(M, K * O);
        let mut b = target.clone();

        let with_oils = |vin: &[u8], oil: &[u8]| -> Vec<u8> {
            let mut x = vin.to_vec();
            x.extend_from_slice(oil);
            x
        };
        let zero_oil = vec![0u8; O];
        let mut unit_oils = Vec::with_capacity(O);
        for o in 0..O {
            let mut u = vec![0u8; O];
            u[o] = 1;
            unit_oils.push(u);
        }

        for i in 0..K {
            let xi0 = with_oils(&vins[i], &zero_oil);
            // Constant part of P(x_i).
            let c: Vec<u8> = sk.central.iter().map(|q| eval_form(q, &xi0)).collect();
            let ec = mat_vec(&e[i], &c);
            for (bk, v) in b.iter_mut().zip(ec) {
                *bk ^= v;
            }
            // Linear part in oil_i: F(vin, u_o) − F(vin, 0) per unit oil.
            for o in 0..O {
                let xi = with_oils(&vins[i], &unit_oils[o]);
                let col: Vec<u8> = sk
                    .central
                    .iter()
                    .zip(&c)
                    .map(|(q, &c0)| eval_form(q, &xi) ^ c0)
                    .collect();
                let ecol = mat_vec(&e[i], &col);
                for k in 0..M {
                    a[k][i * O + o] ^= ecol[k];
                }
            }
        }
        for i in 0..K {
            for j in (i + 1)..K {
                let xi0 = with_oils(&vins[i], &zero_oil);
                let xj0 = with_oils(&vins[j], &zero_oil);
                let c: Vec<u8> = sk
                    .central
                    .iter()
                    .map(|q| eval_polar(q, &xi0, &xj0))
                    .collect();
                let ec = mat_vec(&e[pair_index(i, j)], &c);
                for (bk, v) in b.iter_mut().zip(ec) {
                    *bk ^= v;
                }
                // Linear in oil_i: F'((vin_i, u), (vin_j, 0)) − const.
                for o in 0..O {
                    let xi = with_oils(&vins[i], &unit_oils[o]);
                    let col: Vec<u8> = sk
                        .central
                        .iter()
                        .zip(&c)
                        .map(|(q, &c0)| eval_polar(q, &xi, &xj0) ^ c0)
                        .collect();
                    let ecol = mat_vec(&e[pair_index(i, j)], &col);
                    for k in 0..M {
                        a[k][i * O + o] ^= ecol[k];
                    }
                }
                // Linear in oil_j.
                for o in 0..O {
                    let xj = with_oils(&vins[j], &unit_oils[o]);
                    let col: Vec<u8> = sk
                        .central
                        .iter()
                        .zip(&c)
                        .map(|(q, &c0)| eval_polar(q, &xi0, &xj) ^ c0)
                        .collect();
                    let ecol = mat_vec(&e[pair_index(i, j)], &col);
                    for k in 0..M {
                        a[k][j * O + o] ^= ecol[k];
                    }
                }
            }
        }

        let Some(oils) = solve_underdetermined(&a, &b) else {
            continue;
        };

        // Assemble central-coordinate inputs and map through T⁻¹.
        let inputs: Vec<Vec<u8>> = (0..K)
            .map(|i| {
                let w = with_oils(&vins[i], &oils[i * O..(i + 1) * O]);
                mat_vec(&sk.t_inv, &w)
            })
            .collect();
        return MayoSignature { inputs };
    }
}

pub fn mayo_verify(pk: &MayoPublicKey, msg: &[u8], sig: &MayoSignature) -> bool {
    if sig.inputs.len() != K || sig.inputs.iter().any(|x| x.len() != N) {
        return false;
    }
    eval_whipped(&pk.forms, &sig.inputs) == hash_to_target(msg)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gf16_inverses() {
        for a in 1..16u8 {
            assert_eq!(gf_mul(a, gf_inv(a)), 1, "a = {a}");
        }
    }

    #[test]
    fn emulsifiers_are_invertible() {
        for (c, e) in emulsifiers(K + K * (K - 1) / 2).iter().enumerate() {
            assert!(invert(e).is_some(), "E_{c} singular");
        }
    }

    #[test]
    fn whipped_map_consistency() {
        // P = F ∘ T pointwise implies P* = F* on matched inputs — the
        // identity that makes signing work.  Check on random data.
        let (pk, sk) = mayo_keygen();
        let inputs: Vec<Vec<u8>> = (0..K).map(|_| random_gf16_vec(N)).collect();
        let via_public = eval_whipped(&pk.forms, &inputs);
        // Central inputs: w_i = T x_i, i.e. x_i = T⁻¹ w_i ⇒ w_i = T x_i.
        // We only have T⁻¹ in the secret key, so check the inverse way:
        let central_inputs: Vec<Vec<u8>> = inputs
            .iter()
            .map(|x| mat_vec(&invert(&sk.t_inv).unwrap(), x))
            .collect();
        let via_central = eval_whipped(&sk.central, &central_inputs);
        assert_eq!(via_public, via_central);
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = mayo_keygen();
        let msg = b"oil, vinegar, and a whisk";
        let sig = mayo_sign(&sk, msg);
        assert!(mayo_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = mayo_keygen();
        let sig = mayo_sign(&sk, b"one");
        assert!(!mayo_verify(&pk, b"two", &sig));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = mayo_keygen();
        let msg = b"tamper";
        let mut sig = mayo_sign(&sk, msg);
        sig.inputs[0][0] ^= 1;
        assert!(!mayo_verify(&pk, msg, &sig));
    }

    #[test]
    fn malformed_signature_rejected() {
        let (pk, sk) = mayo_keygen();
        let msg = b"shape";
        let mut sig = mayo_sign(&sk, msg);
        sig.inputs.pop();
        assert!(!mayo_verify(&pk, msg, &sig));
    }
}
