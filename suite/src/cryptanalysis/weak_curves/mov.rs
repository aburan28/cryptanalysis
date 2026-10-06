//! MOV / Frey–Rück reduction with a real pairing: the reduced Tate
//! pairing computed by Miller's algorithm over `F_{p^k}`.
//!
//! # The reduction (Menezes–Okamoto–Vanstone 1993; Frey–Rück 1994)
//!
//! Let `G ∈ E(F_p)` have prime order `n ∤ p`, and let `k` be the
//! embedding degree: the least `k` with `n | p^k − 1`, so `μ_n ⊂
//! F_{p^k}*`.  The reduced Tate pairing
//!
//! ```text
//! t_n(P, R) = f_{n,P}(D_R)^{(p^k − 1)/n} ∈ μ_n,
//! ```
//!
//! where `div(f_{n,P}) = n(P) − n(O)` and `D_R = (R + S) − (S)` is a
//! divisor equivalent to `(R) − (O)` with support disjoint from that of
//! `f_{n,P}`, is bilinear and non-degenerate on `E(F_{p^k})[n] ×
//! E(F_{p^k})/nE(F_{p^k})`.  Choosing `R` of order `n` with
//! `α = t_n(G, R) ≠ 1` and setting `β = t_n(Q, R)`, bilinearity gives
//! `β = α^d` for `Q = d·G`: the elliptic-curve DLP becomes a DLP in the
//! order-`n` subgroup of `F_{p^k}*`.
//!
//! Steps as implemented:
//!
//! 1. `k` from [`embedding_degree`] (bounded, default `k ≤ 12`).
//! 2. `#E(F_{p^k}) = p^k + 1 − t_k` from the trace `t = p + 1 − #E(F_p)`
//!    via `t₀ = 2, t₁ = t, t_{i+1} = t·t_i − p·t_{i−1}` (the roots of the
//!    Frobenius characteristic polynomial).  `#E(F_p)` is taken from the
//!    caller and checked against the Hasse bound and random points.
//! 3. `F_{p^k} = F_p[t]/(f)` with a random irreducible `f`
//!    ([`super::fpk::Fpk`]); `E(F_{p^k})` in affine coordinates.
//! 4. `R` = a random point of `E(F_{p^k})` times the `n`-free part of
//!    `#E(F_{p^k})`, then multiplied by `n` until the next multiple is
//!    `O`: a point of order exactly `n`.
//! 5. Miller's algorithm evaluates `f_{n,P}` at `R + S` and `S` for a
//!    random `S`, keeping numerator and denominator separate so the
//!    loop does no field inversions; a zero factor (support collision)
//!    triggers a new `S`.
//! 6. The target DLP is solved generically ([`super::dlp`]: BSGS or
//!    Pollard rho in `F_{p^k}*`), and `d` is verified on the curve.
//!
//! # What this does and does not buy
//!
//! The reduction is polynomial time; what it buys depends on the
//! finite-field DLP solver.  Index calculus / the number field sieve
//! in `F_{p^k}` — the subexponential algorithms that make MOV a real
//! attack on e.g. supersingular curves over 256-bit fields
//! (`F_{p²}` of 512 bits) — are **out of scope here**.  With only
//! generic algorithms in `F_{p^k}*`, solving the transferred DLP costs
//! the same `√n` as Pollard rho on the curve.  The tests demonstrate
//! that the DLP genuinely moves into the finite field (a 256-bit
//! supersingular curve with a ~36-bit prime `n`, and ordinary MNT-type
//! curves with `k = 3, 4, 6`); they do not demonstrate a speed-up, and
//! the dispatcher in [`super`] does not pick MOV over Pohlig–Hellman on
//! cost grounds.
//!
//! References: A. Menezes, T. Okamoto, S. Vanstone, *Reducing elliptic
//! curve logarithms to logarithms in a finite field*, IEEE Trans. IT 39
//! (1993); G. Frey, H.-G. Rück, *A remark concerning m-divisibility and
//! the discrete logarithm in the divisor class group of curves*, Math.
//! Comp. 62 (1994); V. S. Miller, *The Weil pairing, and its efficient
//! calculation*, J. Cryptology 17 (2004); R. Balasubramanian and N.
//! Koblitz, *The improbability that an elliptic curve has subexponential
//! discrete log problem under the MOV algorithm*, J. Cryptology 11
//! (1998); A. Miyaji, M. Nakabayashi, S. Takano, *New explicit
//! conditions of elliptic curve traces for FR-reduction*, IEICE Trans.
//! E84-A (2001) for the MNT families used in the tests.

use super::arith::{is_probable_prime, AffinePoint, Ec};
use super::dlp::{solve_prime_order, PrimeSolver, SolverOptions};
use super::fpk::{Fpk, FpkElem, FpkMulGroup};
use super::WeakCurveError;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, Zero};
use rand::Rng;
use serde::Serialize;
use std::time::Instant;

/// Smallest `k ≤ max_k` with `n | p^k − 1`, or `None`.
pub fn embedding_degree(p: &BigUint, n: &BigUint, max_k: u32) -> Option<u32> {
    if n <= &BigUint::one() {
        return None;
    }
    let pm = p % n;
    if pm.is_zero() {
        return None;
    }
    let mut acc = pm.clone();
    for k in 1..=max_k {
        if acc.is_one() {
            return Some(k);
        }
        acc = (&acc * &pm) % n;
    }
    None
}

/// `#E(F_{p^k})` from `#E(F_p)` via the Frobenius trace recurrence.
pub fn curve_order_extension(p: &BigUint, order_fp: &BigUint, k: u32) -> BigUint {
    let p_i = BigInt::from_biguint(Sign::Plus, p.clone());
    let t: BigInt = &p_i + 1 - BigInt::from_biguint(Sign::Plus, order_fp.clone());
    let mut t_prev = BigInt::from(2);
    let mut t_cur = t.clone();
    for _ in 1..k {
        let next = &t * &t_cur - &p_i * &t_prev;
        t_prev = t_cur;
        t_cur = next;
    }
    let tk = if k == 0 { BigInt::from(2) } else { t_cur };
    let n: BigInt = p_i.pow(k) + 1 - tk;
    n.to_biguint().expect("positive")
}

/// Options for [`mov_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct MovOptions {
    /// Largest embedding degree to try.
    pub max_k: u32,
    /// Random `(R, S)` choices before giving up on a non-degenerate
    /// pairing value.
    pub max_pairing_attempts: usize,
    /// Solver options for the DLP in `F_{p^k}*`.
    pub solver: SolverOptions,
}

impl Default for MovOptions {
    fn default() -> Self {
        MovOptions {
            max_k: 12,
            max_pairing_attempts: 16,
            solver: SolverOptions::default(),
        }
    }
}

/// Result of [`mov_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct MovOutcome {
    /// Recovered `d`, verified by scalar multiplication.
    #[serde(serialize_with = "super::ser::big")]
    pub scalar: BigUint,
    /// Embedding degree `k`.
    pub embedding_degree: u32,
    /// Prime order `n` of `G`.
    #[serde(serialize_with = "super::ser::big")]
    pub subgroup_order: BigUint,
    /// `#E(F_p)` used for the trace.
    #[serde(serialize_with = "super::ser::big")]
    pub curve_order: BigUint,
    /// `#E(F_{p^k})`.
    #[serde(serialize_with = "super::ser::big")]
    pub curve_order_extension: BigUint,
    /// Bit size of `p^k`, the field the DLP moved to.
    pub target_field_bits: u64,
    /// Pairing value `α = t_n(G, R)` (coefficients, decimal).
    pub alpha: Vec<String>,
    /// Pairing value `β = t_n(Q, R)`.
    pub beta: Vec<String>,
    /// `(R, S)` choices tried.
    pub pairing_attempts: usize,
    /// Solver for the order-`n` DLP in `F_{p^k}*`.
    pub dlp_solver: PrimeSolver,
    /// Group operations in `F_{p^k}*`.
    pub dlp_group_ops: u64,
    /// Milliseconds building `F_{p^k}` and computing both pairings.
    pub pairing_ms: f64,
    /// Milliseconds solving the finite-field DLP.
    pub dlp_ms: f64,
    /// Total milliseconds.
    pub elapsed_ms: f64,
}

// ── E(F_{p^k}) ───────────────────────────────────────────────────────────

#[derive(Clone, Debug, PartialEq)]
enum XPoint {
    Inf,
    Aff(FpkElem, FpkElem),
}

struct ExtCurve<'a> {
    f: &'a Fpk,
    a: FpkElem,
    b: FpkElem,
}

impl ExtCurve<'_> {
    /// Slope of the line through `t` and `u` (tangent if equal), or
    /// `None` for a vertical line.
    fn slope(&self, t: &XPoint, u: &XPoint) -> Option<FpkElem> {
        let f = self.f;
        match (t, u) {
            (XPoint::Aff(x1, y1), XPoint::Aff(x2, y2)) => {
                if x1 == x2 {
                    if y1 != y2 || f.is_zero(y1) {
                        return None;
                    }
                    let three = f.from_base(&BigUint::from(3u32));
                    let num = f.add(&f.mul(&three, &f.sqr(x1)), &self.a);
                    let den = f.add(y1, y1);
                    Some(f.mul(&num, &f.inv(&den)?))
                } else {
                    let num = f.sub(y2, y1);
                    let den = f.sub(x2, x1);
                    Some(f.mul(&num, &f.inv(&den)?))
                }
            }
            _ => None,
        }
    }

    fn add(&self, t: &XPoint, u: &XPoint) -> XPoint {
        match (t, u) {
            (XPoint::Inf, v) | (v, XPoint::Inf) => v.clone(),
            (XPoint::Aff(x1, y1), XPoint::Aff(x2, _)) => match self.slope(t, u) {
                None => XPoint::Inf,
                Some(l) => {
                    let f = self.f;
                    let x3 = f.sub(&f.sub(&f.sqr(&l), x1), x2);
                    let y3 = f.sub(&f.mul(&l, &f.sub(x1, &x3)), y1);
                    XPoint::Aff(x3, y3)
                }
            },
        }
    }

    fn mul(&self, pt: &XPoint, k: &BigUint) -> XPoint {
        let mut acc = XPoint::Inf;
        for i in (0..k.bits()).rev() {
            acc = self.add(&acc, &acc);
            if k.bit(i) {
                acc = self.add(&acc, pt);
            }
        }
        acc
    }

    fn random_point<R: Rng + ?Sized>(&self, rng: &mut R) -> XPoint {
        let f = self.f;
        loop {
            let x = f.random(rng);
            let rhs = f.add(&f.mul(&f.add(&f.sqr(&x), &self.a), &x), &self.b);
            if let Some(y) = f.sqrt(&rhs, rng) {
                return XPoint::Aff(x, y);
            }
        }
    }

    /// Line `g_{T,U} = l_{T,U}/v_{T+U}` evaluated at `at`, returned as
    /// `(numerator, denominator, T + U)`.
    fn line(&self, t: &XPoint, u: &XPoint, at: &(FpkElem, FpkElem)) -> (FpkElem, FpkElem, XPoint) {
        let f = self.f;
        let (XPoint::Aff(xt, yt), XPoint::Aff(_, _)) = (t, u) else {
            unreachable!("Miller loop never adds the identity");
        };
        match self.slope(t, u) {
            None => {
                // Vertical line x − x_T; T + U = O, denominator 1.
                (f.sub(&at.0, xt), f.one(), XPoint::Inf)
            }
            Some(l) => {
                let sum = self.add(t, u);
                let XPoint::Aff(xs, _) = &sum else {
                    unreachable!("non-vertical line meets a third affine point");
                };
                let num = f.sub(&f.sub(&at.1, yt), &f.mul(&l, &f.sub(&at.0, xt)));
                let den = f.sub(&at.0, xs);
                (num, den, sum)
            }
        }
    }

    /// `f_{n,P}(R₁)/f_{n,P}(R₂)` by Miller's algorithm, or `None` when a
    /// factor vanishes (the evaluation points meet the support).
    fn miller_ratio(
        &self,
        p: &XPoint,
        n: &BigUint,
        r1: &(FpkElem, FpkElem),
        r2: &(FpkElem, FpkElem),
    ) -> Option<FpkElem> {
        let f = self.f;
        let mut num = f.one();
        let mut den = f.one();
        let mut t = p.clone();
        let bits = n.bits();
        for i in (0..bits - 1).rev() {
            let (l1, v1, sum) = self.line(&t, &t, r1);
            let (l2, v2, _) = self.line(&t, &t, r2);
            num = f.mul(&f.sqr(&num), &f.mul(&l1, &v2));
            den = f.mul(&f.sqr(&den), &f.mul(&v1, &l2));
            t = sum;
            if n.bit(i) {
                let (l1, v1, sum) = self.line(&t, p, r1);
                let (l2, v2, _) = self.line(&t, p, r2);
                num = f.mul(&num, &f.mul(&l1, &v2));
                den = f.mul(&den, &f.mul(&v1, &l2));
                t = sum;
            }
            if f.is_zero(&num) || f.is_zero(&den) {
                return None;
            }
        }
        debug_assert_eq!(t, XPoint::Inf);
        Some(f.mul(&num, &f.inv(&den)?))
    }

    /// Reduced Tate pairing `t_n(P, R)` with a random auxiliary `S`.
    fn tate<Rn: Rng + ?Sized>(
        &self,
        p: &XPoint,
        r: &XPoint,
        n: &BigUint,
        final_exp: &BigUint,
        rng: &mut Rn,
    ) -> Option<FpkElem> {
        for _ in 0..8 {
            let s = self.random_point(rng);
            let rs = self.add(r, &s);
            let (XPoint::Aff(x1, y1), XPoint::Aff(x2, y2)) = (&rs, &s) else {
                continue;
            };
            let at1 = (x1.clone(), y1.clone());
            let at2 = (x2.clone(), y2.clone());
            if let Some(v) = self.miller_ratio(p, n, &at1, &at2) {
                return Some(self.f.pow(&v, final_exp));
            }
        }
        None
    }
}

fn lift_point(f: &Fpk, pt: &AffinePoint) -> XPoint {
    match pt {
        AffinePoint::Infinity => XPoint::Inf,
        AffinePoint::Affine(x, y) => XPoint::Aff(f.from_base(x), f.from_base(y)),
    }
}

/// Check a claimed `#E(F_p)`: Hasse bound, divisibility by `n`, and
/// annihilation of a few random points.
pub(crate) fn check_curve_order<R: Rng + ?Sized>(
    ec: &Ec,
    order: &BigUint,
    n: &BigUint,
    rng: &mut R,
) -> Result<(), String> {
    let p = BigInt::from_biguint(Sign::Plus, ec.p.clone());
    let t: BigInt = &p + 1 - BigInt::from_biguint(Sign::Plus, order.clone());
    if &t * &t > &p * 4 {
        return Err(format!("#E = {order} violates the Hasse bound"));
    }
    if !(order % n).is_zero() {
        return Err(format!("n does not divide #E = {order}"));
    }
    for _ in 0..4 {
        let r = ec.random_point(rng);
        if ec.mul(&r, order) != AffinePoint::Infinity {
            return Err(format!("#E = {order} does not annihilate a random point"));
        }
    }
    Ok(())
}

/// **MOV / Frey–Rück attack**: transfer `Q = d·G` to `F_{p^k}*` with the
/// reduced Tate pairing and solve it there.
///
/// `n` must be the (prime) order of `G`; `curve_order` is `#E(F_p)`
/// (validated).  Fails with [`WeakCurveError::NotApplicable`] when the
/// embedding degree exceeds `opts.max_k`.
pub fn mov_attack(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    n: &BigUint,
    curve_order: &BigUint,
    opts: &MovOptions,
) -> Result<MovOutcome, WeakCurveError> {
    let t0 = Instant::now();
    let ec = Ec::from_params(curve);
    let p = &ec.p;
    if !is_probable_prime(p) || p < &BigUint::from(5u32) {
        return Err(WeakCurveError::InvalidInput("p must be a prime ≥ 5".into()));
    }
    if ec.discriminant().is_zero() {
        return Err(WeakCurveError::NotApplicable("curve is singular".into()));
    }
    if n < &BigUint::from(3u32) || !is_probable_prime(n) {
        return Err(WeakCurveError::NotApplicable(
            "MOV here needs ord(G) to be an odd prime (use Pohlig–Hellman to split it)".into(),
        ));
    }
    let gl = ec.import(g);
    let ql = ec.import(q);
    if !ec.is_on_curve(&gl) || !ec.is_on_curve(&ql) || gl == AffinePoint::Infinity {
        return Err(WeakCurveError::InvalidInput(
            "points not on the curve".into(),
        ));
    }
    if ec.mul(&gl, n) != AffinePoint::Infinity {
        return Err(WeakCurveError::InvalidInput("n·G ≠ O".into()));
    }
    if n == p {
        return Err(WeakCurveError::NotApplicable(
            "n = p (anomalous): no embedding degree; use Smart's attack".into(),
        ));
    }
    let k = embedding_degree(p, n, opts.max_k).ok_or_else(|| {
        WeakCurveError::NotApplicable(format!("embedding degree exceeds {}", opts.max_k))
    })?;
    let mut rng = super::arith::seeded_rng(opts.solver.seed ^ 0x006d_6f76);
    check_curve_order(&ec, curve_order, n, &mut rng).map_err(WeakCurveError::InvalidInput)?;
    let n_k = curve_order_extension(p, curve_order, k);
    // n-free part of #E(F_{p^k}).
    let mut cof = n_k.clone();
    while (&cof % n).is_zero() {
        cof /= n;
    }
    let field = Fpk::new(p, k as usize, &mut rng)?;
    let ext = ExtCurve {
        f: &field,
        a: field.from_base(&ec.a),
        b: field.from_base(&ec.b),
    };
    let final_exp = (field.size() - 1u32) / n;
    let gx = lift_point(&field, &gl);
    let qx = lift_point(&field, &ql);
    let one = field.one();
    let mut attempts = 0usize;
    let mut pair = None;
    while attempts < opts.max_pairing_attempts {
        attempts += 1;
        let mut r = ext.mul(&ext.random_point(&mut rng), &cof);
        if r == XPoint::Inf {
            continue;
        }
        loop {
            let next = ext.mul(&r, n);
            if next == XPoint::Inf {
                break;
            }
            r = next;
        }
        let Some(alpha) = ext.tate(&gx, &r, n, &final_exp, &mut rng) else {
            continue;
        };
        if alpha == one {
            continue; // R in the kernel of t_n(G, ·); pick another
        }
        let beta = if ql == AffinePoint::Infinity {
            one.clone()
        } else {
            match ext.tate(&qx, &r, n, &final_exp, &mut rng) {
                Some(b) => b,
                None => continue,
            }
        };
        pair = Some((alpha, beta));
        break;
    }
    let (alpha, beta) = pair.ok_or_else(|| {
        WeakCurveError::SolverFailed("no non-degenerate pairing value found".into())
    })?;
    debug_assert_eq!(field.pow(&alpha, n), one);
    let pairing_ms = t0.elapsed().as_secs_f64() * 1e3;
    let t1 = Instant::now();
    let grp = FpkMulGroup(&field);
    let (d, solver, ops) = solve_prime_order(&grp, &alpha, &beta, n, &opts.solver, &mut rng)?;
    let dlp_ms = t1.elapsed().as_secs_f64() * 1e3;
    if g.scalar_mul(&d, &curve.a_fe()) != *q {
        return Err(WeakCurveError::VerificationFailed);
    }
    let show = |v: &FpkElem| v.iter().map(|c| c.to_str_radix(10)).collect::<Vec<_>>();
    Ok(MovOutcome {
        scalar: d,
        embedding_degree: k,
        subgroup_order: n.clone(),
        curve_order: curve_order.clone(),
        curve_order_extension: n_k,
        target_field_bits: field.size().bits(),
        alpha: show(&alpha),
        beta: show(&beta),
        pairing_attempts: attempts,
        dlp_solver: solver,
        dlp_group_ops: ops,
        pairing_ms,
        dlp_ms,
        elapsed_ms: t0.elapsed().as_secs_f64() * 1e3,
    })
}

/// Pairing values `t_n(s·G, R)` for one random `R` of order `n`, for
/// the bilinearity test.
#[cfg(test)]
fn tate_for_test(
    curve: &CurveParams,
    n: &BigUint,
    curve_order: &BigUint,
    scalars: &[u64],
) -> (Fpk, Vec<FpkElem>) {
    let ec = Ec::from_params(curve);
    let mut rng = super::arith::seeded_rng(5);
    let k = embedding_degree(&ec.p, n, 12).unwrap();
    let field = Fpk::new(&ec.p, k as usize, &mut rng).unwrap();
    let ext = ExtCurve {
        f: &field,
        a: field.from_base(&ec.a),
        b: field.from_base(&ec.b),
    };
    let mut cof = curve_order_extension(&ec.p, curve_order, k);
    while (&cof % n).is_zero() {
        cof /= n;
    }
    let final_exp = (field.size() - 1u32) / n;
    let g = lift_point(&field, &ec.import(&curve.generator()));
    let mut r = ext.mul(&ext.random_point(&mut rng), &cof);
    while ext.mul(&r, n) != XPoint::Inf {
        r = ext.mul(&r, n);
    }
    let vals = scalars
        .iter()
        .map(|&s| {
            let ps = ext.mul(&g, &BigUint::from(s));
            ext.tate(&ps, &r, n, &final_exp, &mut rng).unwrap()
        })
        .collect();
    (field, vals)
}

#[cfg(test)]
mod tests {
    use super::super::arith::seeded_rng;
    use super::*;
    use num_bigint::RandBigInt;

    fn big(s: &str) -> BigUint {
        BigUint::parse_bytes(s.as_bytes(), 10).unwrap()
    }

    /// Supersingular `y² = x³ + x` over a `bits`-bit `p = 4·h·n − 1`
    /// (so `p ≡ 3 mod 4`, `#E = p + 1`, `k = 2`) with a prime `n` of
    /// `n_bits` bits.  Returns the curve (`n`, cofactor `4h`).
    fn supersingular_k2(bits: u64, n_bits: u64, seed: u64) -> CurveParams {
        let mut rng = seeded_rng(seed);
        let n = loop {
            let c = rng.gen_biguint(n_bits) | (BigUint::one() << (n_bits - 1)) | BigUint::one();
            if is_probable_prime(&c) {
                break c;
            }
        };
        let (p, h) = loop {
            let h = rng.gen_biguint(bits - n_bits - 2) | (BigUint::one() << (bits - n_bits - 3));
            let p = ((&h * &n) << 2u32) - 1u32;
            if p.bits() == bits && is_probable_prime(&p) {
                break (p, h);
            }
        };
        let ec = Ec::new(&p, &BigUint::one(), &BigUint::zero());
        let cof = &h << 2u32;
        let g = loop {
            let r = ec.mul(&ec.random_point(&mut rng), &cof);
            if r != AffinePoint::Infinity {
                break r;
            }
        };
        let AffinePoint::Affine(gx, gy) = g else {
            unreachable!()
        };
        // The cofactor 4h exceeds u32, so `h` is left 0 and callers pass
        // #E = p + 1 explicitly.
        CurveParams {
            name: "supersingular-k2",
            p,
            a: BigUint::one(),
            b: BigUint::zero(),
            gx,
            gy,
            n,
            h: 0,
        }
    }

    #[test]
    fn embedding_degree_and_extension_order() {
        assert_eq!(
            embedding_degree(&BigUint::from(19u32), &BigUint::from(3u32), 6),
            Some(1)
        );
        assert_eq!(
            embedding_degree(&BigUint::from(23u32), &BigUint::from(3u32), 6),
            Some(2)
        );
        assert_eq!(
            embedding_degree(&BigUint::from(101u32), &BigUint::from(97u32), 6),
            None
        );
        // y² = x³ + x over F_23: #E = 24, so #E(F_{23²}) = (23 + 1)².
        let e2 = curve_order_extension(&BigUint::from(23u32), &BigUint::from(24u32), 2);
        assert_eq!(e2, BigUint::from(576u32));
    }

    #[test]
    fn tate_pairing_is_bilinear_k2() {
        let curve = supersingular_k2(64, 24, 9);
        let order = &curve.p + 1u32;
        let (f, vals) = tate_for_test(&curve, &curve.n, &order, &[1, 2, 5, 1234]);
        assert_ne!(vals[0], f.one());
        assert_eq!(f.pow(&vals[0], &curve.n), f.one());
        assert_eq!(f.pow(&vals[0], &BigUint::from(2u32)), vals[1]);
        assert_eq!(f.pow(&vals[0], &BigUint::from(5u32)), vals[2]);
        assert_eq!(f.pow(&vals[0], &BigUint::from(1234u32)), vals[3]);
    }

    /// 256-bit supersingular curve, 36-bit prime subgroup: the DLP is
    /// moved to a 512-bit `F_{p²}` and solved there generically.
    #[test]
    fn mov_supersingular_256_bit_k2() {
        let curve = supersingular_k2(256, 36, 21);
        let order = &curve.p + 1u32;
        let g = curve.generator();
        let d = big("41234567890") % &curve.n;
        let q = g.scalar_mul(&d, &curve.a_fe());
        let out = mov_attack(&curve, &g, &q, &curve.n, &order, &MovOptions::default()).unwrap();
        assert_eq!(out.scalar, d);
        assert_eq!(out.embedding_degree, 2);
        assert!(out.target_field_bits >= 511); // p² for a 256-bit p
    }

    /// Supersingular `y² = x³ + b`, `p ≡ 2 (mod 3)` (`#E = p + 1`, `k = 2`).
    #[test]
    fn mov_supersingular_j0_k2() {
        // p = 6·n·h − 1 ≡ 2 mod 3 with n prime.
        let mut rng = seeded_rng(33);
        let n = BigUint::from(1_000_003u32);
        let p = loop {
            let h = rng.gen_biguint(40) | BigUint::one();
            let p = &h * &n * 6u32 - 1u32;
            if is_probable_prime(&p) {
                break p;
            }
        };
        let ec = Ec::new(&p, &BigUint::zero(), &BigUint::from(5u32));
        let cof = (&p + 1u32) / &n;
        let g = loop {
            let r = ec.mul(&ec.random_point(&mut rng), &cof);
            if r != AffinePoint::Infinity {
                break r;
            }
        };
        let AffinePoint::Affine(gx, gy) = g else {
            unreachable!()
        };
        let curve = CurveParams {
            name: "supersingular-j0",
            p: p.clone(),
            a: BigUint::zero(),
            b: BigUint::from(5u32),
            gx,
            gy,
            n: n.clone(),
            h: 0,
        };
        let gp = curve.generator();
        let d = BigUint::from(777_777u32);
        let q = gp.scalar_mul(&d, &curve.a_fe());
        let out = mov_attack(&curve, &gp, &q, &n, &(&p + 1u32), &MovOptions::default()).unwrap();
        assert_eq!(out.scalar, d);
        assert_eq!(out.embedding_degree, 2);
    }

    /// Ordinary MNT-type curves with prime order and `k = 3, 4, 6`,
    /// found by searching the MNT parametrisations at ~30 bits and then
    /// random `(a, b)` until `[N]R = O` (which certifies `#E = N` for
    /// prime `N > 4√p`).
    #[test]
    fn mov_mnt_curves_k3_k4_k6() {
        let cases: [(u32, u64, u64, u64, u64, u64, u64); 3] = [
            (
                3,
                806_289_707,
                806_240_527,
                565_246_982,
                678_128_134,
                322_256_778,
                319_081_046,
            ),
            (
                4,
                1_074_167_851,
                1_074_135_077,
                1_013_870_152,
                689_483_721,
                3_851_283,
                341_846_897,
            ),
            (
                6,
                1_074_135_077,
                1_074_167_851,
                591_694_560,
                1_006_828_055,
                896_518_891,
                410_619_860,
            ),
        ];
        for (k, p, n, a, b, gx, gy) in cases {
            let curve = CurveParams {
                name: "mnt-toy",
                p: BigUint::from(p),
                a: BigUint::from(a),
                b: BigUint::from(b),
                gx: BigUint::from(gx),
                gy: BigUint::from(gy),
                n: BigUint::from(n),
                h: 1,
            };
            let g = curve.generator();
            assert!(curve.is_on_curve(&g));
            let d = BigUint::from(123_456_789u32) % &curve.n;
            let q = g.scalar_mul(&d, &curve.a_fe());
            let out = mov_attack(&curve, &g, &q, &curve.n, &curve.n, &MovOptions::default())
                .unwrap_or_else(|e| panic!("k = {k}: {e}"));
            assert_eq!(out.embedding_degree, k);
            assert_eq!(out.scalar, d);
        }
    }

    #[test]
    fn mov_refuses_large_embedding_degree() {
        let curve = CurveParams {
            name: "ordinary-199",
            p: BigUint::from(211u32),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: BigUint::from(4u32),
            gy: BigUint::from(53u32),
            n: BigUint::from(199u32),
            h: 1,
        };
        let g = curve.generator();
        let r = mov_attack(
            &curve,
            &g,
            &g,
            &curve.n,
            &curve.n,
            &MovOptions {
                max_k: 6,
                ..MovOptions::default()
            },
        );
        assert!(matches!(r, Err(WeakCurveError::NotApplicable(_))));
    }
}
