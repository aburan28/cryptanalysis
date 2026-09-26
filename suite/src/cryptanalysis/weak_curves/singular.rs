//! The discrete logarithm on a *singular* Weierstrass cubic
//! `y² = x³ + a·x + b` with `4a³ + 27b² ≡ 0 (mod p)` — a "curve" that is
//! not an elliptic curve, and a perennial CTF trap.
//!
//! # Mathematics (Washington, *Elliptic Curves*, §2.9)
//!
//! A singular cubic has exactly one singular point, `(x₀, 0)` with `x₀`
//! a repeated root of `f(x) = x³ + ax + b`.  The chord-and-tangent law
//! still makes the *non-singular* points `E_ns(F_p)` a group, and that
//! group is isomorphic to a much weaker one:
//!
//! - **Cusp** (`a = b = 0`, triple root `x₀ = 0`): `y² = x³`, and
//!   `(x, y) ↦ x/y` is an isomorphism `E_ns(F_p) → (F_p, +)`.  The DLP is
//!   a single division.
//! - **Node** (double root `x₀ = −3b/(2a)`, simple root `−2x₀`): with
//!   `u = x − x₀` the curve is `y² = u²(u + β)`, `β = 3x₀ ≠ 0`, whose
//!   tangents at the node have slopes `±α`, `α² = β`.  Then
//!   `(u, y) ↦ (y + αu)/(y − αu)` is an isomorphism onto
//!   - `F_p*` (order `p − 1`) when `β` is a square in `F_p` (*split*);
//!   - the norm-one subgroup of `F_{p²}*` (order `p + 1`) when it is not
//!     (*non-split*), with `α = √β ∈ F_{p²} = F_p[t]/(t² − β)`.
//!
//!   The image DLP is solved by Pohlig–Hellman over the factorisation of
//!   `p ∓ 1` ([`super::dlp`]); index calculus in `F_p*` would be faster
//!   still but is not implemented.
//!
//! The recovered scalar is verified by scalar multiplication on the
//! singular cubic itself with the crate's point arithmetic (the chord
//! formulas are valid on `E_ns`).
//!
//! References: L. C. Washington, *Elliptic Curves: Number Theory and
//! Cryptography*, 2nd ed., Thm. 2.30–2.31; J. H. Silverman, *The
//! Arithmetic of Elliptic Curves*, Prop. III.2.5.

use super::arith::{factor, sqrt_mod_prime, AffinePoint, Ec, FactorOptions};
use super::dlp::{pohlig_hellman, PrimePowerStep, SolverOptions};
use super::fpk::{Fpk, FpkElem, FpkMulGroup};
use super::WeakCurveError;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde::Serialize;
use std::time::Instant;

/// Type of singularity.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum SingularKind {
    /// `y² = x³` after translation: group `(F_p, +)`.
    Cusp,
    /// Node with tangent slopes in `F_p`: group `F_p*`.
    SplitNode,
    /// Node with tangent slopes in `F_{p²} \ F_p`: norm-one subgroup of
    /// `F_{p²}*`.
    NonSplitNode,
}

/// Classification of a singular cubic.
#[derive(Clone, Debug, Serialize)]
pub struct SingularInfo {
    /// Cusp or node.
    pub kind: SingularKind,
    /// x-coordinate of the singular point `(x₀, 0)`.
    #[serde(serialize_with = "super::ser::big")]
    pub singular_x: BigUint,
    /// `β = 3x₀` (tangent slopes are `±√β`); zero for a cusp.
    #[serde(serialize_with = "super::ser::big")]
    pub beta: BigUint,
    /// Order of the group of non-singular points: `p`, `p − 1` or `p + 1`.
    #[serde(serialize_with = "super::ser::big")]
    pub group_order: BigUint,
}

/// Result of [`singular_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct SingularOutcome {
    /// Recovered `d` (mod `ord(G)`), verified by scalar multiplication.
    #[serde(serialize_with = "super::ser::big")]
    pub scalar: BigUint,
    /// Classification.
    pub info: SingularInfo,
    /// Exact order of `G`.
    #[serde(serialize_with = "super::ser::big")]
    pub order_of_g: BigUint,
    /// Pohlig–Hellman steps in the image group (empty for a cusp).
    pub dlp_steps: Vec<PrimePowerStep>,
    /// Wall-clock milliseconds.
    pub elapsed_ms: f64,
}

/// Classify `y² = x³ + ax + b` over `F_p` (`p > 3` prime); `None` if the
/// cubic is non-singular.
pub fn classify_singular(p: &BigUint, a: &BigUint, b: &BigUint) -> Option<SingularInfo> {
    let ec = Ec::new(p, a, b);
    if !ec.discriminant().is_zero() {
        return None;
    }
    if ec.a.is_zero() {
        return Some(SingularInfo {
            kind: SingularKind::Cusp,
            singular_x: BigUint::zero(),
            beta: BigUint::zero(),
            group_order: p.clone(),
        });
    }
    let two_a_inv = ((&ec.a << 1u32) % p).modinv(p)?;
    let x0 = (p - (&ec.b * 3u32) % p) % p * two_a_inv % p;
    let beta = (&x0 * 3u32) % p;
    let split = sqrt_mod_prime(&beta, p).is_some();
    Some(SingularInfo {
        kind: if split {
            SingularKind::SplitNode
        } else {
            SingularKind::NonSplitNode
        },
        singular_x: x0,
        beta,
        group_order: if split { p - 1u32 } else { p + 1u32 },
    })
}

/// **Singular-curve attack**: solve `Q = d·G` on a singular cubic by
/// mapping to `(F_p, +)`, `F_p*` or the norm-one torus in `F_{p²}*`.
pub fn singular_attack(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    opts: &SolverOptions,
) -> Result<SingularOutcome, WeakCurveError> {
    let t0 = Instant::now();
    let ec = Ec::from_params(curve);
    let p = &ec.p;
    if p <= &BigUint::from(3u32) || !super::arith::is_probable_prime(p) {
        return Err(WeakCurveError::InvalidInput("p must be a prime > 3".into()));
    }
    let info = classify_singular(p, &ec.a, &ec.b)
        .ok_or_else(|| WeakCurveError::NotApplicable("the cubic is non-singular".into()))?;
    let gl = ec.import(g);
    let ql = ec.import(q);
    if !ec.is_on_curve(&gl) || !ec.is_on_curve(&ql) {
        return Err(WeakCurveError::InvalidInput(
            "point not on the cubic".into(),
        ));
    }
    let singular = AffinePoint::Affine(info.singular_x.clone(), BigUint::zero());
    if gl == singular || ql == singular {
        return Err(WeakCurveError::InvalidInput(
            "the singular point is not in the group".into(),
        ));
    }
    let AffinePoint::Affine(gx, gy) = &gl else {
        return Err(WeakCurveError::InvalidInput("G is the identity".into()));
    };
    let x0 = &info.singular_x;
    let (scalar, order_of_g, steps) = match info.kind {
        SingularKind::Cusp => {
            // φ(x, y) = x / y  (x₀ = 0).
            let phi = |x: &BigUint, y: &BigUint| (x * y.modinv(p).expect("y ≠ 0")) % p;
            let tg = phi(gx, gy);
            let d = match &ql {
                AffinePoint::Infinity => BigUint::zero(),
                AffinePoint::Affine(qx, qy) => (phi(qx, qy) * tg.modinv(p).expect("φ(G) ≠ 0")) % p,
            };
            (d, p.clone(), Vec::new())
        }
        SingularKind::SplitNode | SingularKind::NonSplitNode => {
            let field = if info.kind == SingularKind::SplitNode {
                Fpk::with_modulus(p, &[BigUint::zero(), BigUint::one()])
            } else {
                Fpk::with_modulus(p, &[p - &info.beta, BigUint::zero(), BigUint::one()])
            }
            .ok_or_else(|| WeakCurveError::SolverFailed("bad torus modulus".into()))?;
            // α: √β in F_p, or the class of t in F_p[t]/(t² − β).
            let alpha: FpkElem = if info.kind == SingularKind::SplitNode {
                field.from_base(&sqrt_mod_prime(&info.beta, p).expect("square"))
            } else {
                vec![BigUint::zero(), BigUint::one()]
            };
            let phi = |pt: &AffinePoint| -> FpkElem {
                match pt {
                    AffinePoint::Infinity => field.one(),
                    AffinePoint::Affine(x, y) => {
                        let u = field.from_base(&super::arith::sub_mod(x, x0, p));
                        let yv = field.from_base(y);
                        let au = field.mul(&alpha, &u);
                        let num = field.add(&yv, &au);
                        let den = field.sub(&yv, &au);
                        field.mul(&num, &field.inv(&den).expect("non-singular point"))
                    }
                }
            };
            let hg = phi(&gl);
            let hq = phi(&ql);
            let fac = factor(&info.group_order, &FactorOptions::default());
            if !fac.is_complete() {
                return Err(WeakCurveError::SolverFailed(format!(
                    "could not factor the image group order {}",
                    info.group_order
                )));
            }
            let grp = FpkMulGroup(&field);
            let mut rng = super::arith::seeded_rng(opts.seed);
            let sol = pohlig_hellman(&grp, &hg, &hq, &fac.factors, opts, &mut rng)?;
            (sol.d, sol.order, sol.steps)
        }
    };
    if g.scalar_mul(&scalar, &curve.a_fe()) != *q {
        return Err(WeakCurveError::VerificationFailed);
    }
    Ok(SingularOutcome {
        scalar,
        info,
        order_of_g,
        dlp_steps: steps,
        elapsed_ms: t0.elapsed().as_secs_f64() * 1e3,
    })
}

#[cfg(test)]
mod tests {
    use super::super::arith::seeded_rng;
    use super::*;
    use num_bigint::RandBigInt;

    /// A singular cubic `y² = (x − x₀)²(x + 2x₀)` (node) or `y² = x³`
    /// (cusp), shifted by nothing, with a random non-singular point.
    fn singular_curve(p: &BigUint, x0: &BigUint, seed: u64) -> CurveParams {
        // a = −3x₀², b = 2x₀³.
        let a = (p - (x0 * x0 * 3u32) % p) % p;
        let b = (x0 * x0 * x0 * 2u32) % p;
        let ec = Ec::new(p, &a, &b);
        let mut rng = seeded_rng(seed);
        let g = loop {
            let r = ec.random_point(&mut rng);
            if let AffinePoint::Affine(_, y) = &r {
                if !y.is_zero() {
                    break r;
                }
            }
        };
        let AffinePoint::Affine(gx, gy) = g else {
            unreachable!()
        };
        CurveParams {
            name: "singular",
            p: p.clone(),
            a,
            b,
            gx,
            gy,
            n: BigUint::zero(),
            h: 1,
        }
    }

    fn run(curve: &CurveParams, secret: &BigUint) -> SingularOutcome {
        let g = curve.generator();
        let q = g.scalar_mul(secret, &curve.a_fe());
        singular_attack(curve, &g, &q, &SolverOptions::default()).unwrap()
    }

    #[test]
    fn cusp_256_bit() {
        // P-256's prime; y² = x³.
        let p = crate::ecc::curve::CurveParams::p256().p;
        let curve = singular_curve(&p, &BigUint::zero(), 1);
        let secret = seeded_rng(2).gen_biguint_below(&p);
        let out = run(&curve, &secret);
        assert_eq!(out.info.kind, SingularKind::Cusp);
        assert_eq!(out.scalar, secret);
    }

    #[test]
    fn split_and_nonsplit_nodes() {
        // p − 1 and p + 1 both smooth enough for rho at 62 bits.
        let p = BigUint::from(2_305_843_009_213_693_951u64); // 2^61 − 1
        let mut saw = (false, false);
        for x0 in 1u64..40 {
            let curve = singular_curve(&p, &BigUint::from(x0), x0);
            let info = classify_singular(&p, &curve.a, &curve.b).unwrap();
            let secret = BigUint::from(0x1234_5678_9abc_u64 * x0);
            let out = run(&curve, &secret);
            assert_eq!(
                curve.generator().scalar_mul(&out.scalar, &curve.a_fe()),
                curve.generator().scalar_mul(&secret, &curve.a_fe())
            );
            assert_eq!(out.scalar, &secret % &out.order_of_g);
            match info.kind {
                SingularKind::SplitNode => saw.0 = true,
                SingularKind::NonSplitNode => saw.1 = true,
                SingularKind::Cusp => unreachable!(),
            }
            if saw.0 && saw.1 {
                break;
            }
        }
        assert!(saw.0 && saw.1, "both node types exercised");
    }

    #[test]
    fn nonsingular_is_rejected() {
        let curve = CurveParams::p256();
        let g = curve.generator();
        let r = singular_attack(&curve, &g, &g, &SolverOptions::default());
        assert!(matches!(r, Err(WeakCurveError::NotApplicable(_))));
    }
}
