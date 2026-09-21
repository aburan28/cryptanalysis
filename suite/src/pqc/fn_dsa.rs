//! **FN-DSA** — FFT over NTRU-lattices Digital Signature Algorithm
//! (draft FIPS 206; the standardised form of **Falcon**,
//! Fouque–Hoffstein–Kirchner–Lyubashevsky–Pornin–Prest–Ricosset–
//! Seiler–Whyte–Zhang).
//!
//! # The scheme: GPV hash-and-sign on an NTRU lattice
//! Work in `R = Z[x]/(xⁿ + 1)`.  The secret key is a short basis of
//! the NTRU lattice: polynomials `f, g` (small) completed with `F, G`
//! satisfying the **NTRU equation**
//!
//! ```text
//! f·G − g·F = q      in R,
//! ```
//!
//! so that `B = [[g, −f], [G, −F]]` generates the lattice
//! `Λ = {(u, v) : u + v·h ≡ 0 (mod q)}` where `h = g·f⁻¹ mod q` is the
//! public key.  Following Gentry–Peikert–Vaikuntanathan:
//!
//! - **Sign**: hash the (salted) message to `c ∈ Z_qⁿ`; use the secret
//!   short basis to find a lattice point near `(c, 0)`; the difference
//!   `(s₁, s₂)` is a *short* solution of `s₁ + s₂·h ≡ c`.  Publish
//!   `(salt, s₂)`.
//! - **Verify**: recompute `s₁ = c − s₂·h mod q` (centred) and accept
//!   iff `‖(s₁, s₂)‖ ≤ β`.  Forging needs a short solution without a
//!   short basis — the approximate closest-vector problem on an NTRU
//!   lattice.
//!
//! # This implementation
//! Educational, `n = 16, q = 257` (real Falcon: `n = 512/1024,
//! q = 12289`).  Faithful in structure, with two documented
//! simplifications:
//!
//! - **Keygen** solves the NTRU equation exactly — resultants and
//!   Bézout coefficients via exact rational elimination over `Z`,
//!   then Babai-reduces `(F, G)` against `(f, g)` — the same
//!   mathematics as Falcon's `NTRUSolve`, minus its recursive
//!   field-tower optimisation.
//! - **Signing** uses the deterministic Babai nearest-plane algorithm
//!   (floating-point Gram–Schmidt) instead of Falcon's randomised
//!   `ffSampling` discrete-Gaussian sampler.  This is exactly the
//!   simplification that *broke* GGH/NTRUSign (Nguyen–Regev 2006
//!   "learning a parallelepiped"): each signature leaks the secret
//!   basis's shape, and a few thousand signatures reveal it.  Falcon's
//!   whole reason for FFT Gaussian sampling is to destroy that leak —
//!   which is also why FIPS 206 is the hardest standard to implement.
//!
//! Toy parameters, not constant-time; see SECURITY.md.

use crate::hash::sha3::shake256;
use crate::utils::random::random_bytes;
use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};

/// Ring degree (real FN-DSA: 512 or 1024).
pub const N: usize = 16;
/// Modulus (real FN-DSA: 12289).
pub const Q: i64 = 257;
/// Squared norm bound β² on (s₁, s₂).
pub const BOUND: i64 = 3500;
/// Signature salt length in bytes.
pub const SALT_BYTES: usize = 16;

// ── Exact rational arithmetic (for the NTRU equation) ────────────────────────

#[derive(Clone)]
struct Frac {
    n: BigInt,
    d: BigInt, // always > 0
}

impl Frac {
    fn from_int(v: &BigInt) -> Frac {
        Frac {
            n: v.clone(),
            d: BigInt::one(),
        }
    }
    fn reduce(mut self) -> Frac {
        if self.d.is_negative() {
            self.n = -self.n;
            self.d = -self.d;
        }
        let g = self.n.gcd(&self.d);
        if !g.is_zero() && !g.is_one() {
            self.n /= &g;
            self.d /= &g;
        }
        self
    }
    fn sub(&self, o: &Frac) -> Frac {
        Frac {
            n: &self.n * &o.d - &o.n * &self.d,
            d: &self.d * &o.d,
        }
        .reduce()
    }
    fn mul(&self, o: &Frac) -> Frac {
        Frac {
            n: &self.n * &o.n,
            d: &self.d * &o.d,
        }
        .reduce()
    }
    fn div(&self, o: &Frac) -> Frac {
        Frac {
            n: &self.n * &o.d,
            d: &self.d * &o.n,
        }
        .reduce()
    }
    fn is_zero(&self) -> bool {
        self.n.is_zero()
    }
}

/// Solve the square system `A·x = b` exactly over Q by Gaussian
/// elimination with `Frac` entries.  Returns `None` if singular.
fn solve_rational(a: &[Vec<BigInt>], b: &[BigInt]) -> Option<Vec<Frac>> {
    let n = a.len();
    let mut m: Vec<Vec<Frac>> = a
        .iter()
        .zip(b)
        .map(|(row, bi)| {
            let mut r: Vec<Frac> = row.iter().map(Frac::from_int).collect();
            r.push(Frac::from_int(bi));
            r
        })
        .collect();
    for col in 0..n {
        let pivot = (col..n).find(|&r| !m[r][col].is_zero())?;
        m.swap(col, pivot);
        let piv = m[col][col].clone();
        for j in col..=n {
            m[col][j] = m[col][j].div(&piv);
        }
        for r in 0..n {
            if r != col && !m[r][col].is_zero() {
                let f = m[r][col].clone();
                for j in col..=n {
                    let t = m[col][j].mul(&f);
                    m[r][j] = m[r][j].sub(&t);
                }
            }
        }
    }
    Some(m.into_iter().map(|row| row[n].clone()).collect())
}

// ── Polynomial arithmetic in Z[x]/(xⁿ + 1) ────────────────────────────────────

/// Negacyclic product of BigInt polynomials.
fn poly_mul_big(a: &[BigInt], b: &[BigInt]) -> Vec<BigInt> {
    let mut out = vec![BigInt::zero(); N];
    for i in 0..N {
        if a[i].is_zero() {
            continue;
        }
        for j in 0..N {
            let k = i + j;
            let term = &a[i] * &b[j];
            if k < N {
                out[k] += term;
            } else {
                out[k - N] -= term; // xⁿ = −1
            }
        }
    }
    out
}

/// The negacyclic multiplication matrix of `p`: column j is `p·xʲ`.
fn mul_matrix_big(p: &[BigInt]) -> Vec<Vec<BigInt>> {
    let mut m = vec![vec![BigInt::zero(); N]; N];
    for j in 0..N {
        for i in 0..N {
            let k = i + j;
            if k < N {
                m[k][j] += &p[i];
            } else {
                m[k - N][j] -= &p[i];
            }
        }
    }
    m
}

/// The adjoint `p̄(x) = p(1/x)·(−1)^…` in the negacyclic ring:
/// coefficient i of p̄ is `p₀` for i = 0 and `−p_{n−i}` otherwise.
/// Satisfies `(p·q)‾ = p̄·q̄` and makes `p·p̄` "self-adjoint".
fn poly_adjoint_big(p: &[BigInt]) -> Vec<BigInt> {
    let mut out = vec![BigInt::zero(); N];
    out[0] = p[0].clone();
    for i in 1..N {
        out[i] = -p[N - i].clone();
    }
    out
}

fn poly_mul_mod_q(a: &[i64], b: &[i64]) -> Vec<i64> {
    let mut out = vec![0i64; N];
    for i in 0..N {
        // Reduce each operand into [0, Q) *before* multiplying.  This is
        // a no-op for the internal callers (their coefficients are
        // already reduced) but is essential on the verification path,
        // where `a` is the untrusted signature `sig.s2`: without it,
        // `a[i] * b[j]` on an adversarially large `i64` would overflow
        // (debug panic / release wraparound).  After reduction the
        // product is < Q² ≈ 2²⁶, comfortably inside i64.
        let ai = a[i].rem_euclid(Q);
        if ai == 0 {
            continue;
        }
        for j in 0..N {
            let k = i + j;
            let t = ai * b[j].rem_euclid(Q) % Q;
            if k < N {
                out[k] = (out[k] + t).rem_euclid(Q);
            } else {
                out[k - N] = (out[k - N] - t).rem_euclid(Q);
            }
        }
    }
    out
}

/// Inverse of `p` in Z_q[x]/(xⁿ+1) by Gaussian elimination on the
/// multiplication matrix; `None` if not invertible.
fn poly_inv_mod_q(p: &[i64]) -> Option<Vec<i64>> {
    let inv_mod = |a: i64| -> Option<i64> {
        // Fermat: q prime.
        let mut r = 1i64;
        let mut b = a.rem_euclid(Q);
        if b == 0 {
            return None;
        }
        let mut e = Q - 2;
        while e > 0 {
            if e & 1 == 1 {
                r = r * b % Q;
            }
            b = b * b % Q;
            e >>= 1;
        }
        Some(r)
    };
    // Multiplication matrix over Z_q.
    let mut m = vec![vec![0i64; N]; N];
    for j in 0..N {
        for i in 0..N {
            let k = i + j;
            if k < N {
                m[k][j] = (m[k][j] + p[i]).rem_euclid(Q);
            } else {
                m[k - N][j] = (m[k - N][j] - p[i]).rem_euclid(Q);
            }
        }
    }
    let mut inv = vec![vec![0i64; N]; N];
    for (i, row) in inv.iter_mut().enumerate() {
        row[i] = 1;
    }
    for col in 0..N {
        let pivot = (col..N).find(|&r| m[r][col] != 0)?;
        m.swap(col, pivot);
        inv.swap(col, pivot);
        let piv = inv_mod(m[col][col])?;
        for j in 0..N {
            m[col][j] = m[col][j] * piv % Q;
            inv[col][j] = inv[col][j] * piv % Q;
        }
        for r in 0..N {
            if r != col && m[r][col] != 0 {
                let f = m[r][col];
                for j in 0..N {
                    m[r][j] = (m[r][j] - f * m[col][j]).rem_euclid(Q);
                    inv[r][j] = (inv[r][j] - f * inv[col][j]).rem_euclid(Q);
                }
            }
        }
    }
    // First column of the inverse matrix = p⁻¹ (action on 1).
    Some((0..N).map(|i| inv[i][0]).collect())
}

// ── NTRU equation: find F, G with f·G − g·F = q ──────────────────────────────

/// Bézout data for `f`: (ρ_f, u_f) with `f·u_f ≡ ρ_f (mod xⁿ+1)` and
/// `ρ_f = Res(f, xⁿ+1) ∈ Z`.  Obtained by solving `f·u = ρ·e₀` over Q:
/// the solution of `M_f·u = e₀` has denominator dividing det M_f = ρ_f.
fn bezout(f: &[i64]) -> Option<(BigInt, Vec<BigInt>)> {
    let fb: Vec<BigInt> = f.iter().map(|&c| BigInt::from(c)).collect();
    let m = mul_matrix_big(&fb);
    let mut e0 = vec![BigInt::zero(); N];
    e0[0] = BigInt::one();
    let sol = solve_rational(&m, &e0)?;
    // Common denominator D: u = D·sol must be integral with f·u = D·e₀.
    let mut d = BigInt::one();
    for s in &sol {
        d = &d / d.gcd(&s.d) * &s.d; // lcm
    }
    let u: Vec<BigInt> = sol.iter().map(|s| &s.n * (&d / &s.d)).collect();
    Some((d, u))
}

/// Solve a square f64 system by Gaussian elimination with partial
/// pivoting.  Used only to *estimate* the Babai coefficient `k`; the
/// key material itself stays exact BigInt.
fn solve_f64(a: &[Vec<f64>], b: &[f64]) -> Option<Vec<f64>> {
    let n = a.len();
    let mut m: Vec<Vec<f64>> = a
        .iter()
        .zip(b)
        .map(|(row, &bi)| {
            let mut r = row.clone();
            r.push(bi);
            r
        })
        .collect();
    for col in 0..n {
        let pivot = (col..n).max_by(|&x, &y| {
            m[x][col]
                .abs()
                .partial_cmp(&m[y][col].abs())
                .unwrap_or(std::cmp::Ordering::Equal)
        })?;
        if m[pivot][col].abs() < 1e-12 {
            return None;
        }
        m.swap(col, pivot);
        for r in 0..n {
            if r != col {
                let f = m[r][col] / m[col][col];
                for j in col..=n {
                    let t = f * m[col][j];
                    m[r][j] -= t;
                }
            }
        }
    }
    Some((0..n).map(|i| m[i][n] / m[i][i]).collect())
}

/// One step of Babai reduction: `(F, G) −= round((F·f̄ + G·ḡ)/(f·f̄ + g·ḡ))·(f, g)`.
/// `k` is estimated in floating point (any rounding slop just costs an
/// extra iteration); the subtraction is exact.
fn reduce_fg(f: &[BigInt], g: &[BigInt], big_f: &mut [BigInt], big_g: &mut [BigInt]) -> bool {
    use num_traits::ToPrimitive;
    let f_adj = poly_adjoint_big(f);
    let g_adj = poly_adjoint_big(g);
    let mut num = poly_mul_big(big_f, &f_adj);
    let num2 = poly_mul_big(big_g, &g_adj);
    for (a, b) in num.iter_mut().zip(num2) {
        *a += b;
    }
    let mut den = poly_mul_big(f, &f_adj);
    let den2 = poly_mul_big(g, &g_adj);
    for (a, b) in den.iter_mut().zip(den2) {
        *a += b;
    }
    // k ≈ num/den in Q[x]/(xⁿ+1): solve den·k = num, round.
    let m = mul_matrix_big(&den);
    let mf: Vec<Vec<f64>> = m
        .iter()
        .map(|row| row.iter().map(|c| c.to_f64().unwrap_or(0.0)).collect())
        .collect();
    let numf: Vec<f64> = num.iter().map(|c| c.to_f64().unwrap_or(0.0)).collect();
    let Some(sol) = solve_f64(&mf, &numf) else {
        return false;
    };
    // k can start resultant-sized (≫ 2⁶³), so convert via BigInt.
    use num_traits::FromPrimitive;
    let k: Vec<BigInt> = sol
        .iter()
        .map(|&s| BigInt::from_f64(s.round()).unwrap_or_else(BigInt::zero))
        .collect();
    if k.iter().all(|c| c.is_zero()) {
        return false;
    }
    let kf = poly_mul_big(&k, f);
    let kg = poly_mul_big(&k, g);
    for i in 0..N {
        big_f[i] -= &kf[i];
        big_g[i] -= &kg[i];
    }
    true
}

/// Solve `f·G − g·F = q` and reduce (F, G) to small size.
fn ntru_solve(f: &[i64], g: &[i64]) -> Option<(Vec<i64>, Vec<i64>)> {
    let (rho_f, u_f) = bezout(f)?;
    let (rho_g, u_g) = bezout(g)?;
    let ext = rho_f.extended_gcd(&rho_g);
    if ext.gcd != BigInt::one() {
        return None; // resultants not coprime — resample f, g
    }
    // f·(q·a·u_f) − g·(−q·b·u_g) = q(a·ρ_f + b·ρ_g) = q.
    let qq = BigInt::from(Q);
    let mut big_g: Vec<BigInt> = u_f.iter().map(|c| &qq * &ext.x * c).collect();
    let mut big_f: Vec<BigInt> = u_g.iter().map(|c| -(&qq * &ext.y * c)).collect();

    let fb: Vec<BigInt> = f.iter().map(|&c| BigInt::from(c)).collect();
    let gb: Vec<BigInt> = g.iter().map(|&c| BigInt::from(c)).collect();
    for _ in 0..64 {
        if !reduce_fg(&fb, &gb, &mut big_f, &mut big_g) {
            break;
        }
    }
    let to_i64 =
        |v: &[BigInt]| -> Option<Vec<i64>> { v.iter().map(|c| i64::try_from(c).ok()).collect() };
    Some((to_i64(&big_f)?, to_i64(&big_g)?))
}

// ── Keys ──────────────────────────────────────────────────────────────────────

/// Public key: `h = g·f⁻¹ mod q`.
#[derive(Clone, Debug, PartialEq)]
pub struct FnDsaPublicKey {
    pub h: Vec<i64>,
}

/// Secret key: the short basis rows (g, −f), (G, −F) of the NTRU lattice.
#[derive(Clone, Debug)]
pub struct FnDsaSecretKey {
    f: Vec<i64>,
    g: Vec<i64>,
    big_f: Vec<i64>,
    big_g: Vec<i64>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct FnDsaSignature {
    pub salt: Vec<u8>,
    pub s2: Vec<i64>,
}

fn random_small_poly() -> Vec<i64> {
    // Coefficients in {−2,…,2}, a toy stand-in for Falcon's discrete
    // Gaussian with σ ≈ 1.17·√(q/2n).
    let mut b = vec![0u8; N];
    random_bytes(&mut b);
    b.iter().map(|&x| (x % 5) as i64 - 2).collect()
}

pub fn fn_dsa_keygen() -> (FnDsaPublicKey, FnDsaSecretKey) {
    loop {
        let f = random_small_poly();
        let g = random_small_poly();
        let Some(f_inv) = poly_inv_mod_q(&f) else {
            continue;
        };
        let Some((big_f, big_g)) = ntru_solve(&f, &g) else {
            continue;
        };
        // Reject if the completed basis is still too skewed for Babai
        // to land inside the verification bound.
        let norm2: i64 = big_f.iter().chain(&big_g).map(|c| c * c).sum();
        if norm2 > 64 * BOUND {
            continue;
        }
        let h = poly_mul_mod_q(&g, &f_inv);
        return (FnDsaPublicKey { h }, FnDsaSecretKey { f, g, big_f, big_g });
    }
}

// ── Babai nearest-plane on the 2n-dimensional secret basis ──────────────────

/// Basis rows of Λ = {(u,v) : u + v·h ≡ 0 mod q}: n negacyclic shifts
/// of (g, −f) and n of (G, −F).
fn secret_basis(sk: &FnDsaSecretKey) -> Vec<Vec<f64>> {
    let mut rows = Vec::with_capacity(2 * N);
    let shift = |p: &[i64], s: usize| -> Vec<i64> {
        // p·xˢ in the negacyclic ring.
        let mut out = vec![0i64; N];
        for (i, &c) in p.iter().enumerate() {
            let k = i + s;
            if k < N {
                out[k] += c;
            } else {
                out[k - N] -= c;
            }
        }
        out
    };
    for s in 0..N {
        let a = shift(&sk.g, s);
        let b = shift(&sk.f, s);
        rows.push(
            a.iter()
                .map(|&x| x as f64)
                .chain(b.iter().map(|&x| -x as f64))
                .collect(),
        );
    }
    for s in 0..N {
        let a = shift(&sk.big_g, s);
        let b = shift(&sk.big_f, s);
        rows.push(
            a.iter()
                .map(|&x| x as f64)
                .chain(b.iter().map(|&x| -x as f64))
                .collect(),
        );
    }
    rows
}

/// Babai nearest-plane: the lattice point (as integer combination of
/// `basis` rows) closest to `target` along the Gram–Schmidt directions.
fn nearest_plane(basis: &[Vec<f64>], target: &[f64]) -> Vec<f64> {
    let m = basis.len();
    let dim = target.len();
    // Gram–Schmidt.
    let mut gs: Vec<Vec<f64>> = Vec::with_capacity(m);
    let mut mu = vec![vec![0f64; m]; m];
    for i in 0..m {
        let mut v = basis[i].clone();
        for j in 0..i {
            let dot: f64 = basis[i].iter().zip(&gs[j]).map(|(a, b)| a * b).sum();
            let nrm: f64 = gs[j].iter().map(|x| x * x).sum();
            mu[i][j] = dot / nrm;
            for k in 0..dim {
                v[k] -= mu[i][j] * gs[j][k];
            }
        }
        gs.push(v);
    }
    // Nearest plane, top row down.
    let mut t = target.to_vec();
    let mut result = vec![0f64; dim];
    for i in (0..m).rev() {
        let dot: f64 = t.iter().zip(&gs[i]).map(|(a, b)| a * b).sum();
        let nrm: f64 = gs[i].iter().map(|x| x * x).sum();
        let c = (dot / nrm).round();
        for k in 0..dim {
            t[k] -= c * basis[i][k];
            result[k] += c * basis[i][k];
        }
    }
    result
}

fn hash_to_point(salt: &[u8], msg: &[u8]) -> Vec<i64> {
    let mut input = b"FN-DSA-toy".to_vec();
    input.extend_from_slice(salt);
    input.extend_from_slice(msg);
    let h = shake256(&input, 2 * N);
    (0..N)
        .map(|i| (u16::from_le_bytes([h[2 * i], h[2 * i + 1]]) as i64).rem_euclid(Q))
        .collect()
}

fn centered(x: i64) -> i64 {
    let r = x.rem_euclid(Q);
    if r > Q / 2 {
        r - Q
    } else {
        r
    }
}

pub fn fn_dsa_sign(sk: &FnDsaSecretKey, msg: &[u8]) -> FnDsaSignature {
    let basis = secret_basis(sk);
    loop {
        let mut salt = vec![0u8; SALT_BYTES];
        random_bytes(&mut salt);
        let c = hash_to_point(&salt, msg);

        let mut target: Vec<f64> = c.iter().map(|&x| x as f64).collect();
        target.extend(std::iter::repeat_n(0f64, N));
        let v = nearest_plane(&basis, &target);

        let s1: Vec<i64> = (0..N)
            .map(|i| (c[i] as f64 - v[i]).round() as i64)
            .collect();
        let s2: Vec<i64> = (0..N).map(|i| (-v[N + i]).round() as i64).collect();
        let norm2: i64 = s1.iter().chain(&s2).map(|x| x * x).sum();
        if norm2 <= BOUND {
            return FnDsaSignature { salt, s2 };
        }
        // Rare with an accepted basis: fresh salt, new target, retry.
    }
}

pub fn fn_dsa_verify(pk: &FnDsaPublicKey, msg: &[u8], sig: &FnDsaSignature) -> bool {
    if sig.s2.len() != N || sig.salt.len() != SALT_BYTES {
        return false;
    }
    // Reject out-of-range coefficients before any squaring.  A genuine
    // signature has ‖(s1, s2)‖² ≤ BOUND, so |s2[i]| ≤ √BOUND; anything
    // larger cannot verify anyway, and rejecting it here keeps the
    // norm computation from overflowing i64 on an adversarial `s2`
    // (Falcon's decoder likewise bounds coefficient magnitudes).  The
    // bound is written as a two-sided compare rather than `abs()` so
    // that i64::MIN (whose `abs()` itself overflows) is handled.
    if sig.s2.iter().any(|&x| !(-BOUND..=BOUND).contains(&x)) {
        return false;
    }
    let c = hash_to_point(&sig.salt, msg);
    let s2h = poly_mul_mod_q(&sig.s2, &pk.h);
    let s1: Vec<i64> = (0..N).map(|i| centered(c[i] - s2h[i])).collect();
    let norm2: i64 =
        s1.iter().map(|x| x * x).sum::<i64>() + sig.s2.iter().map(|x| x * x).sum::<i64>();
    norm2 <= BOUND
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ntru_equation_holds() {
        // The heart of keygen: f·G − g·F = q exactly in Z[x]/(xⁿ+1).
        let (_, sk) = fn_dsa_keygen();
        let fb: Vec<BigInt> = sk.f.iter().map(|&c| BigInt::from(c)).collect();
        let gb: Vec<BigInt> = sk.g.iter().map(|&c| BigInt::from(c)).collect();
        let fg: Vec<BigInt> = sk.big_g.iter().map(|&c| BigInt::from(c)).collect();
        let gf: Vec<BigInt> = sk.big_f.iter().map(|&c| BigInt::from(c)).collect();
        let lhs1 = poly_mul_big(&fb, &fg);
        let lhs2 = poly_mul_big(&gb, &gf);
        assert_eq!(lhs1[0].clone() - &lhs2[0], BigInt::from(Q));
        for i in 1..N {
            assert_eq!(lhs1[i], lhs2[i], "coefficient {i}");
        }
    }

    #[test]
    fn public_key_relation() {
        // g ≡ f·h (mod q): both basis rows lie in the q-ary lattice.
        let (pk, sk) = fn_dsa_keygen();
        let fh = poly_mul_mod_q(&sk.f, &pk.h);
        for i in 0..N {
            assert_eq!(fh[i], sk.g[i].rem_euclid(Q));
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = fn_dsa_keygen();
        let msg = b"hash-and-sign on NTRU lattices";
        let sig = fn_dsa_sign(&sk, msg);
        assert!(fn_dsa_verify(&pk, msg, &sig));
    }

    #[test]
    fn several_messages_roundtrip() {
        let (pk, sk) = fn_dsa_keygen();
        for i in 0u8..5 {
            let msg = [i; 7];
            let sig = fn_dsa_sign(&sk, &msg);
            assert!(fn_dsa_verify(&pk, &msg, &sig), "message {i}");
        }
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = fn_dsa_keygen();
        let sig = fn_dsa_sign(&sk, b"one");
        assert!(!fn_dsa_verify(&pk, b"two", &sig));
    }

    #[test]
    fn verify_handles_adversarial_signature_without_overflow() {
        // `sig.s2` is untrusted: extreme i64 coordinates must be rejected
        // without overflowing the modular multiply or the norm (no debug
        // panic, no release wraparound).
        let (pk, _) = fn_dsa_keygen();
        let sig = FnDsaSignature {
            salt: vec![0u8; SALT_BYTES],
            s2: vec![i64::MAX; N],
        };
        assert!(!fn_dsa_verify(&pk, b"m", &sig));
        let sig2 = FnDsaSignature {
            salt: vec![0u8; SALT_BYTES],
            s2: vec![i64::MIN; N],
        };
        assert!(!fn_dsa_verify(&pk, b"m", &sig2));
    }

    #[test]
    fn tampered_signature_rejected() {
        let (pk, sk) = fn_dsa_keygen();
        let msg = b"tamper";
        let mut sig = fn_dsa_sign(&sk, msg);
        sig.s2[0] += 40;
        assert!(!fn_dsa_verify(&pk, msg, &sig));
    }

    #[test]
    fn zero_s2_forgery_fails() {
        // s2 = 0 forces s1 = c, essentially uniform mod q: far above β.
        let (pk, _) = fn_dsa_keygen();
        let sig = FnDsaSignature {
            salt: vec![0u8; SALT_BYTES],
            s2: vec![0; N],
        };
        assert!(!fn_dsa_verify(&pk, b"forgery", &sig));
    }
}
