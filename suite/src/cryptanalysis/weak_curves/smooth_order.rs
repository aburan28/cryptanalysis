//! Pohlig–Hellman on `E(F_p)` with real per-prime solvers.
//!
//! The order `n` of `G` is factored ([`super::arith::factor`]: trial
//! division, Miller–Rabin, Pollard–Brent) or taken from the caller;
//! the exact order of `G` is derived from it; each prime-power part is
//! solved digit by digit with BSGS (small primes) or distinguished-point
//! Pollard rho with batched affine additions (large primes); and the
//! residues are combined by the CRT ([`super::dlp::pohlig_hellman`]).
//!
//! Cost: `Σ eᵢ·√qᵢ` group operations for `n = ∏ qᵢ^{eᵢ}` — the DLP is as
//! hard as the largest prime factor of the order, which is why standard
//! curves have prime (or near-prime) order.  A 128-bit order whose
//! largest prime factor has 40 bits falls in a few seconds.
//!
//! References: S. Pohlig and M. Hellman, IEEE Trans. IT 24 (1978);
//! E. Teske, Math. Comp. 70 (2001); P. C. van Oorschot and M. J. Wiener,
//! J. Cryptology 12 (1999).

use super::arith::{factor, is_probable_prime, AffinePoint, Ec, FactorOptions};
use super::dlp::{pohlig_hellman, PrimePowerStep, SolverOptions};
use super::WeakCurveError;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde::Serialize;
use std::time::Instant;

/// Options for [`pohlig_hellman_attack`].
#[derive(Clone, Debug, Default, Serialize)]
pub struct PohligHellmanOptions {
    /// Factoring budget (ignored when a factorisation is supplied).
    pub factor: FactorOptions,
    /// Prime-order solver tuning.
    pub solver: SolverOptions,
}

/// Result of [`pohlig_hellman_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct PohligHellmanOutcome {
    /// Recovered `d mod ord(G)`, verified by scalar multiplication.
    #[serde(serialize_with = "super::ser::big")]
    pub scalar: BigUint,
    /// Exact order of `G`.
    #[serde(serialize_with = "super::ser::big")]
    pub order_of_g: BigUint,
    /// Factorisation of `ord(G)`.
    #[serde(serialize_with = "super::ser::big_pairs")]
    pub factors: Vec<(BigUint, u32)>,
    /// Bits of the largest prime factor (the cost driver).
    pub largest_prime_bits: u64,
    /// Whether the factorisation came from the caller.
    pub factorization_supplied: bool,
    /// Per-prime-power steps.
    pub steps: Vec<PrimePowerStep>,
    /// Group operations in the digit solves.
    pub group_ops: u64,
    /// Milliseconds factoring the order.
    pub factor_ms: f64,
    /// Milliseconds in the discrete-log solves.
    pub dlp_ms: f64,
    /// Total milliseconds.
    pub elapsed_ms: f64,
}

/// Check a caller-supplied factorisation of `order`.
pub(crate) fn check_factorization(
    order: &BigUint,
    factors: &[(BigUint, u32)],
) -> Result<(), WeakCurveError> {
    let prod = factors
        .iter()
        .fold(BigUint::one(), |acc, (q, e)| acc * q.pow(*e));
    if &prod != order {
        return Err(WeakCurveError::InvalidInput(
            "supplied factorisation does not multiply to the order".into(),
        ));
    }
    if let Some((q, _)) = factors.iter().find(|(q, _)| !is_probable_prime(q)) {
        return Err(WeakCurveError::InvalidInput(format!(
            "supplied factor {q} is not prime"
        )));
    }
    Ok(())
}

/// **Pohlig–Hellman attack** on `Q = d·G` where `order·G = O`.
///
/// `factorization`, if given, must be the complete prime factorisation
/// of `order`; otherwise `order` is factored within `opts.factor`.  The
/// result is `d mod ord(G)` (the exact order of `G` is computed), and it
/// is verified with the crate's [`Point::scalar_mul`].
pub fn pohlig_hellman_attack(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    order: &BigUint,
    factorization: Option<&[(BigUint, u32)]>,
    opts: &PohligHellmanOptions,
) -> Result<PohligHellmanOutcome, WeakCurveError> {
    let t0 = Instant::now();
    let ec = Ec::from_params(curve);
    let gl = ec.import(g);
    let ql = ec.import(q);
    if gl == AffinePoint::Infinity {
        return Err(WeakCurveError::InvalidInput("G is the identity".into()));
    }
    if !ec.is_on_curve(&gl) || !ec.is_on_curve(&ql) {
        return Err(WeakCurveError::InvalidInput(
            "point not on the curve".into(),
        ));
    }
    if order.is_zero() || ec.mul(&gl, order) != AffinePoint::Infinity {
        return Err(WeakCurveError::InvalidInput("order·G ≠ O".into()));
    }
    let (factors, supplied) = match factorization {
        Some(f) => {
            check_factorization(order, f)?;
            (f.to_vec(), true)
        }
        None => {
            let f = factor(order, &opts.factor);
            if !f.is_complete() {
                return Err(WeakCurveError::SolverFailed(format!(
                    "could not factor the order within the budget; unfactored part(s): {}",
                    f.unfactored
                        .iter()
                        .map(|c| format!("{} bits", c.bits()))
                        .collect::<Vec<_>>()
                        .join(", ")
                )));
            }
            (f.factors, false)
        }
    };
    let factor_ms = t0.elapsed().as_secs_f64() * 1e3;
    let t1 = Instant::now();
    let mut rng = super::arith::seeded_rng(opts.solver.seed);
    let sol = pohlig_hellman(&ec, &gl, &ql, &factors, &opts.solver, &mut rng)?;
    let dlp_ms = t1.elapsed().as_secs_f64() * 1e3;
    if g.scalar_mul(&sol.d, &curve.a_fe()) != *q {
        return Err(WeakCurveError::VerificationFailed);
    }
    let largest_prime_bits = sol
        .order_factors
        .iter()
        .map(|(q, _)| q.bits())
        .max()
        .unwrap_or(0);
    Ok(PohligHellmanOutcome {
        scalar: sol.d,
        order_of_g: sol.order,
        factors: sol.order_factors,
        largest_prime_bits,
        factorization_supplied: supplied,
        steps: sol.steps,
        group_ops: sol.group_ops,
        factor_ms,
        dlp_ms,
        elapsed_ms: t0.elapsed().as_secs_f64() * 1e3,
    })
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    fn big(s: &str) -> BigUint {
        BigUint::parse_bytes(s.as_bytes(), 10).unwrap()
    }

    /// `y² = x³ + 2` over a 128-bit prime, found by the CM method for
    /// `j = 0` (`p ≡ 1 mod 3`, the six twists have traces ±t, ±(t±3v)/2
    /// with `4p = t² + 3v²`) and a search for a twist whose order has a
    /// largest prime factor of 40 bits:
    /// `#E = 3²·87721·1350388531·414225013639·669550864369`, with
    /// `E[3] ⊂ E(F_p)`, so `G` has order `#E/9`.
    pub(crate) fn curve128() -> (CurveParams, BigUint) {
        let curve = CurveParams {
            name: "cm-j0-128",
            p: big("295681886263824732693820920129885041569"),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: big("292999454487241629135152166766043019954"),
            gy: big("24885659077271486073460513969014021704"),
            n: big("32853542918202748079124507022600258141"),
            h: 9,
        };
        (curve, big("295681886263824732712120563203402323269"))
    }

    #[test]
    fn ph_128_bit_order_40_bit_largest_prime() {
        let (curve, full_order) = curve128();
        let g = curve.generator();
        let d = big("12345678901234567890123456789012345678") % &curve.n;
        let q = g.scalar_mul(&d, &curve.a_fe());
        // Factor the full group order ourselves; G's order is #E/9.
        let out =
            pohlig_hellman_attack(&curve, &g, &q, &full_order, None, &Default::default()).unwrap();
        assert_eq!(out.order_of_g, curve.n);
        assert_eq!(out.scalar, d);
        assert_eq!(out.largest_prime_bits, 40);
        assert!(!out.factorization_supplied);
    }

    #[test]
    fn ph_with_supplied_factorization() {
        let (curve, _) = curve128();
        // Work in the subgroup of order 87721 · 1350388531 (fast).
        let g = curve
            .generator()
            .scalar_mul(&big("277344715925253264128791"), &curve.a_fe());
        let order = big("118457432327851"); // 87721 · 1350388531
        let d = big("98765432109876");
        let q = g.scalar_mul(&d, &curve.a_fe());
        let facs = vec![(BigUint::from(87721u32), 1), (big("1350388531"), 1)];
        let out = pohlig_hellman_attack(
            &curve,
            &g,
            &q,
            &order,
            Some(&facs),
            &PohligHellmanOptions::default(),
        )
        .unwrap();
        assert_eq!(out.scalar, d % &order);
        assert!(out.factorization_supplied);
        // A wrong factorisation is rejected, not trusted.
        let bad = vec![(BigUint::from(87721u32), 1), (big("1350388533"), 1)];
        assert!(pohlig_hellman_attack(
            &curve,
            &g,
            &q,
            &order,
            Some(&bad),
            &PohligHellmanOptions::default()
        )
        .is_err());
    }

    #[test]
    fn ph_rejects_point_outside_subgroup() {
        let (curve, _) = curve128();
        let g = curve
            .generator()
            .scalar_mul(&big("277344715925253264128791"), &curve.a_fe());
        let order = big("118457432327851");
        // A point of order dividing 414225013639·669550864369·…, not in ⟨g⟩.
        let q = curve
            .generator()
            .scalar_mul(&big("118457432327851"), &curve.a_fe());
        let r = pohlig_hellman_attack(&curve, &g, &q, &order, None, &Default::default());
        assert!(matches!(r, Err(WeakCurveError::NotInSubgroup)));
    }
}
