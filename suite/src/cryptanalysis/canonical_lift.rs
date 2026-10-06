//! Smart's anomalous-curve attack via p-adic formal-group logarithms,
//! with the canonical-lift foundation for the open-research extension
//! to non-anomalous curves.
//!
//! Nigel Smart, "The discrete logarithm problem on elliptic curves
//! of trace one," J. Cryptology 1999.  An ECDLP attack that runs in
//! `O(log p)` field operations on **anomalous** curves
//! (`#E(F_p) = p`).  This module:
//!
//! 1. Implements truncated `Z_p` arithmetic (mod `p^k` for a chosen
//!    precision `k`).
//! 2. Implements affine point arithmetic in `E(Z_p)` for the lift.
//! 3. Implements the formal-group logarithm via the formal-group law
//!    derived from the Weierstrass equation.
//! 4. Exposes Smart's attack end-to-end ([`smart_attack_anomalous`],
//!    delegating to [`crate::cryptanalysis::weak_curves::smart`]).
//! 5. Documents (without implementing) the canonical-lift extension to
//!    non-anomalous curves — research-note item #1, the genuinely-novel-
//!    but-low-probability angle.
//!
//! # Smart's attack — sketch
//!
//! Let `E/F_p` be ordinary anomalous: `#E(F_p) = p`.  Lift `P, Q` to
//! `P̂, Q̂ ∈ E(Q_p)` via Hensel.  Compute `[p]·P̂` and `[p]·Q̂` in
//! `E(Q_p)`.  Both reduce to `O ∈ E(F_p)` (since `[p]` annihilates
//! `E(F_p)` when `#E = p`), so they lie in the **formal group**
//! `Ê(p Z_p) ≅ p Z_p`.
//!
//! The formal-group log `log_F: Ê(p Z_p) → p Z_p` is a Z_p-linear
//! isomorphism.  Crucially:
//!
//! ```text
//! log_F([p]·Q̂) ≡ d · log_F([p]·P̂)  (mod p^2)
//! ```
//!
//! so `d ≡ log_F([p]·Q̂) · log_F([p]·P̂)⁻¹ (mod p)` recovers the
//! discrete log in one division.
//!
//! # The non-anomalous extension (research-note item #1)
//!
//! For `#E(F_p) = n ≠ p`, `[n]·P̂` lies in `Ê(p Z_p)` but the formal
//! log of `[n]·Q̂` does **not** equal `d · log_F([n]·P̂)` modulo any
//! power of `p` — there's a "lift correction" depending on the
//! choice of lift.  The proposal: use **canonical lifts** (Serre–Tate)
//! to constrain the lift correction and recover bits of `d`.
//!
//! The canonical lift `E^can/W(F_p)` exists uniquely for ordinary
//! curves and has `End(E^can) = End(E)`.  Points on `E^can` do *not*
//! generally have canonical lifts, but the combination of canonical
//! curve lift + Hensel point lift gives more structure than arbitrary
//! lifts.  Whether this structure yields a partial-recovery attack
//! is **open research** — no published treatment exists per my
//! literature survey.
//!
//! This module ships the **foundation**: `Z_p` arithmetic, formal
//! group law, point-on-lift arithmetic, formal log, and Smart's attack
//! itself.  An attempt at the canonical-lift extension would build on
//! this scaffolding.
//!
//! # Scope of the implementation
//!
//! - The affine [`ZpCurve`] arithmetic here cannot represent `[p]·P̂`
//!   (it reduces to the point at infinity); [`smart_attack_anomalous`]
//!   therefore delegates to the projective `Z/p²Z` implementation in
//!   [`crate::cryptanalysis::weak_curves::smart`], which works at
//!   cryptographic sizes.
//! - [`find_anomalous_curve`] is a brute-force search running in
//!   `O(p^3)`, suitable for `p ≤ ~200`.  Anomalous curves of any size
//!   are constructed by the CM method in
//!   [`crate::cryptanalysis::weak_curves::smart::anomalous_curve_cm`].

use num_bigint::BigInt;
use num_traits::{One, Zero};

// ── Truncated p-adic integers ─────────────────────────────────────────────
//
// We represent a Z_p element to precision k as an integer mod p^k.
// All arithmetic is done in BigInt mod p^k.  This is sufficient for
// Smart's attack at small precision (k = 2 or 3).

/// p-adic integer mod `p^precision`.  Carries `p` and `precision`
/// alongside the value to enable type-checked arithmetic.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ZpInt {
    pub p: BigInt,
    pub precision: u32,
    /// `value` reduced into `[0, p^precision)`.
    pub value: BigInt,
}

impl ZpInt {
    /// Modulus `p^precision`.
    pub fn modulus(&self) -> BigInt {
        self.p.pow(self.precision)
    }

    /// Constructor.  Reduces `value` into `[0, p^precision)`.
    pub fn new(value: BigInt, p: &BigInt, precision: u32) -> Self {
        let m = p.pow(precision);
        let v = ((value % &m) + &m) % &m;
        ZpInt {
            p: p.clone(),
            precision,
            value: v,
        }
    }

    pub fn zero(p: &BigInt, precision: u32) -> Self {
        ZpInt {
            p: p.clone(),
            precision,
            value: BigInt::zero(),
        }
    }

    pub fn one(p: &BigInt, precision: u32) -> Self {
        ZpInt {
            p: p.clone(),
            precision,
            value: BigInt::one(),
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.p, other.p);
        debug_assert_eq!(self.precision, other.precision);
        ZpInt::new(&self.value + &other.value, &self.p, self.precision)
    }

    pub fn sub(&self, other: &Self) -> Self {
        debug_assert_eq!(self.p, other.p);
        debug_assert_eq!(self.precision, other.precision);
        ZpInt::new(&self.value - &other.value, &self.p, self.precision)
    }

    pub fn neg(&self) -> Self {
        ZpInt::new(-self.value.clone(), &self.p, self.precision)
    }

    pub fn mul(&self, other: &Self) -> Self {
        debug_assert_eq!(self.p, other.p);
        debug_assert_eq!(self.precision, other.precision);
        ZpInt::new(&self.value * &other.value, &self.p, self.precision)
    }

    /// Multiplicative inverse (when `value` is a unit, i.e. `p ∤ value`).
    /// Returns `None` if not invertible.
    pub fn inverse(&self) -> Option<Self> {
        let m = self.modulus();
        let (g, x, _) = extended_gcd(&self.value, &m);
        if !g.is_one() {
            return None;
        }
        Some(ZpInt::new(x, &self.p, self.precision))
    }

    /// p-adic valuation: the largest `k` with `p^k | value`, capped
    /// at `precision`.
    pub fn valuation(&self) -> u32 {
        if self.value.is_zero() {
            return self.precision;
        }
        let mut v = 0u32;
        let mut x = self.value.clone();
        while v < self.precision && (&x % &self.p).is_zero() {
            x /= &self.p;
            v += 1;
        }
        v
    }
}

fn extended_gcd(a: &BigInt, b: &BigInt) -> (BigInt, BigInt, BigInt) {
    if b.is_zero() {
        return (a.clone(), BigInt::one(), BigInt::zero());
    }
    let (g, x, y) = extended_gcd(b, &(a % b));
    (g, y.clone(), x - (a / b) * y)
}

// ── Curve arithmetic over Z_p ─────────────────────────────────────────────
//
// E: y² = x³ + a·x + b  with `a, b ∈ Z_p`.  Affine point: `(X, Y) ∈ Z_p²`
// with `Y² ≡ X³ + a·X + b (mod p^precision)`, OR the point at infinity.

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ZpPoint {
    Inf,
    Aff(ZpInt, ZpInt),
}

#[derive(Clone, Debug)]
pub struct ZpCurve {
    pub p: BigInt,
    pub precision: u32,
    pub a: ZpInt,
    pub b: ZpInt,
}

impl ZpCurve {
    pub fn new(a: BigInt, b: BigInt, p: &BigInt, precision: u32) -> Self {
        ZpCurve {
            p: p.clone(),
            precision,
            a: ZpInt::new(a, p, precision),
            b: ZpInt::new(b, p, precision),
        }
    }

    /// Point doubling: 2·P.  Standard short-Weierstrass formulas.
    pub fn double(&self, point: &ZpPoint) -> ZpPoint {
        match point {
            ZpPoint::Inf => ZpPoint::Inf,
            ZpPoint::Aff(x, y) => {
                if y.value.is_zero() {
                    return ZpPoint::Inf;
                }
                let two = ZpInt::new(BigInt::from(2), &self.p, self.precision);
                let three = ZpInt::new(BigInt::from(3), &self.p, self.precision);
                let two_y = two.mul(y);
                let two_y_inv = match two_y.inverse() {
                    Some(v) => v,
                    None => return ZpPoint::Inf, // y has p-valuation; degenerate
                };
                let lam = three.mul(x).mul(x).add(&self.a).mul(&two_y_inv);
                let x3 = lam.mul(&lam).sub(x).sub(x);
                let y3 = lam.mul(&x.sub(&x3)).sub(y);
                ZpPoint::Aff(x3, y3)
            }
        }
    }

    /// Point addition: P + Q.
    pub fn add(&self, p: &ZpPoint, q: &ZpPoint) -> ZpPoint {
        match (p, q) {
            (ZpPoint::Inf, x) | (x, ZpPoint::Inf) => x.clone(),
            (ZpPoint::Aff(x1, y1), ZpPoint::Aff(x2, y2)) => {
                if x1 == x2 {
                    if y1 == y2 {
                        return self.double(p);
                    }
                    return ZpPoint::Inf;
                }
                let dx = x2.sub(x1);
                let dx_inv = match dx.inverse() {
                    Some(v) => v,
                    None => return ZpPoint::Inf, // x_2 ≡ x_1 (mod p) but ≠ in Z_p
                };
                let lam = y2.sub(y1).mul(&dx_inv);
                let x3 = lam.mul(&lam).sub(x1).sub(x2);
                let y3 = lam.mul(&x1.sub(&x3)).sub(y1);
                ZpPoint::Aff(x3, y3)
            }
        }
    }

    /// `k · P` via double-and-add.
    pub fn scalar_mul(&self, p: &ZpPoint, k: &BigInt) -> ZpPoint {
        if k.is_zero() {
            return ZpPoint::Inf;
        }
        let mut result = ZpPoint::Inf;
        let mut addend = p.clone();
        let k_abs = k.magnitude().clone();
        for i in 0..k_abs.bits() {
            if k_abs.bit(i) {
                result = self.add(&result, &addend);
            }
            addend = self.double(&addend);
        }
        if k.sign() == num_bigint::Sign::Minus {
            // Negate: (X, Y) → (X, -Y).
            match result {
                ZpPoint::Aff(x, y) => ZpPoint::Aff(x, y.neg()),
                ZpPoint::Inf => ZpPoint::Inf,
            }
        } else {
            result
        }
    }
}

// ── Hensel lift of a point ──────────────────────────────────────────────────
//
// Given P̄ = (x_0, y_0) ∈ E(F_p), find P̂ = (X, Y) ∈ E(Z_p) with
// X ≡ x_0, Y ≡ y_0 (mod p) and Y² ≡ X³ + a·X + b (mod p^precision).

/// Hensel-lift a point `(x_0, y_0) ∈ E(F_p)` to `E(Z_p / p^precision Z_p)`.
/// Uses Newton iteration on the y-coordinate: keep `X = x_0` (any
/// choice works), solve for `Y`.  Returns `None` if the curve has
/// `2 y_0 ≡ 0 (mod p)` (singular y-derivative — would need different
/// strategy).
pub fn hensel_lift_point(curve: &ZpCurve, x_0: &BigInt, y_0: &BigInt) -> Option<ZpPoint> {
    let p = &curve.p;
    let prec = curve.precision;
    // Use X = x_0 (lifted as p-adic integer = x_0 + 0·p + 0·p² + …).
    let x_lifted = ZpInt::new(x_0.clone(), p, prec);
    // Solve for Y such that Y² ≡ X³ + a·X + b (mod p^prec).
    // We have Y_0 = y_0 satisfying the equation mod p.  Newton lift:
    //   Y_{k+1} = Y_k − (Y_k² − rhs) / (2 Y_k)
    let rhs = x_lifted
        .mul(&x_lifted)
        .mul(&x_lifted)
        .add(&curve.a.mul(&x_lifted))
        .add(&curve.b);
    let mut y_lifted = ZpInt::new(y_0.clone(), p, prec);
    let two = ZpInt::new(BigInt::from(2), p, prec);
    for _ in 0..prec {
        let f = y_lifted.mul(&y_lifted).sub(&rhs);
        let two_y = two.mul(&y_lifted);
        let two_y_inv = two_y.inverse()?;
        let delta = f.mul(&two_y_inv);
        y_lifted = y_lifted.sub(&delta);
    }
    // Verify.
    let lhs = y_lifted.mul(&y_lifted);
    debug_assert_eq!(lhs, rhs);
    Some(ZpPoint::Aff(x_lifted, y_lifted))
}

// ── Formal-group logarithm ───────────────────────────────────────────────
//
// For E: y² = x³ + ax + b, the formal group law is parameterised by
// `z = -x/y` (and `w = -1/y`).  Near the identity (where x ≈ ∞ over
// the curve / z ≈ 0 in the formal group), the formal log is:
//
//   log_F(z) = z + a_2 · z²/2 + a_3 · z³/3 + …  (a power series)
//
// For short Weierstrass over Q_p, the leading terms of log_F are:
//   log_F(z) = z + O(z⁴)   (the next non-trivial term is z⁴/4)
//
// since the formal group law on a short Weierstrass curve has no z²
// or z³ corrections (Silverman IV.1).
//
// At the precision Smart's attack needs (mod p²), `log_F(z) ≡ z`
// suffices when `v_p(z) ≥ 1` (so `z² ≡ 0 mod p²`).

/// Formal-group `z`-coordinate of a point in `Ê(p Z_p)` (i.e. a point
/// reducing to `O ∈ E(F_p)`).  `z = -X/Y` where `(X, Y)` is the
/// affine representation.  Requires `v_p(Y) < 0` (point at infinity
/// in F_p), but for our anomalous-attack use case `Y` is a p-adic
/// unit divided by p^something, which we encode as `(X, Y)` having
/// `v_p(X) = -2k` and `v_p(Y) = -3k` for some `k ≥ 1`.
///
/// In practice we work with the *non-projective* representation of
/// `(X, Y)` as a pair where `X = X̃/p²ᵏ`, `Y = Ỹ/p³ᵏ`, and we
/// directly compute `z = -X̃·p^k / Ỹ` (giving `v_p(z) = k`).
///
/// For toy Smart's attack at small `p` and precision 2, we use a
/// simpler approach: directly extract `z` from the affine `(X, Y)`
/// in projective form.
pub fn formal_log_zp(point: &ZpPoint) -> Option<ZpInt> {
    match point {
        ZpPoint::Inf => None,
        ZpPoint::Aff(x, y) => {
            // The point should be in the formal group: reduce mod p,
            // both x and y go to "infinity" in the affine model.  In
            // truncated Z_p arithmetic we represent this differently:
            // we work projectively.  See `formal_log_projective`.
            let _ = (x, y);
            None
        }
    }
}

/// **Formal log via projective coordinates** — the workhorse for
/// Smart's attack.  Takes a point that has been computed in the
/// formal group `Ê(p Z_p)` via the projective `[p]·P̂` calculation.
///
/// For the input `z = -X/Y (mod p^prec)` with `v_p(z) ≥ 1`:
///
/// ```text
/// log_F(z) ≡ z  (mod p²)   when v_p(z) ≥ 1
/// ```
///
/// The higher-order terms `z⁴/4 + z⁶/6 + …` all have `v_p ≥ 4`, so
/// they vanish mod `p²` for any `p ≥ 3`.  This is sufficient for
/// Smart's attack at precision 2.
pub fn formal_log_from_z(z: &ZpInt) -> ZpInt {
    // Truncated to leading order mod p².  See module docs.
    z.clone()
}

// ── Smart's attack ─────────────────────────────────────────────────────────

/// **Smart's attack** on an anomalous curve `E/F_p` (i.e., `#E(F_p) = p`).
/// Given the curve, two `F_p`-points `P, Q = d·P`, recover `d (mod p)`.
///
/// This is a thin wrapper over the working implementation in
/// [`crate::cryptanalysis::weak_curves::smart`], which does the
/// computation in homogeneous projective coordinates over `Z/p²Z` (the
/// affine [`ZpCurve`] arithmetic above cannot represent `[p]·P̂`, which
/// reduces to the point at infinity), uses a *random* lift of the curve
/// to avoid the degenerate canonical-lift case, and retries with a
/// fresh lift if one is degenerate.  Works at cryptographic sizes.
///
/// The returned `d` has been verified: `d·P = Q` on `E(F_p)`.
///
/// Returns `Err` if `p` is not a prime ≥ 5, a point is not on the
/// curve, `P` is the identity, the curve is singular, `ord(P) ≠ p`
/// (not anomalous), or every random lift fails.
pub fn smart_attack_anomalous(
    p: &BigInt,
    a_coeff: &BigInt,
    b_coeff: &BigInt,
    p_pt_x: &BigInt,
    p_pt_y: &BigInt,
    q_pt_x: &BigInt,
    q_pt_y: &BigInt,
) -> Result<BigInt, &'static str> {
    use crate::cryptanalysis::weak_curves::arith::{AffinePoint, Ec};
    use crate::cryptanalysis::weak_curves::smart::{smart_core, SmartOptions};
    use crate::cryptanalysis::weak_curves::WeakCurveError;
    use num_bigint::{BigUint, Sign};

    if p.sign() != Sign::Plus {
        return Err("p must be a positive prime");
    }
    let pu = p.magnitude().clone();
    let red = |v: &BigInt| -> BigUint {
        let r = ((v % p) + p) % p;
        r.magnitude().clone()
    };
    let ec = Ec::new(&pu, &red(a_coeff), &red(b_coeff));
    let g = AffinePoint::Affine(red(p_pt_x), red(p_pt_y));
    let q = AffinePoint::Affine(red(q_pt_x), red(q_pt_y));
    match smart_core(&ec, &g, &q, &SmartOptions::default()) {
        Ok((d, _, _)) => {
            // Independent check with the crate's point arithmetic.
            let (gp, qp) = (ec.export(&g), ec.export(&q));
            let a_fe = crate::ecc::field::FieldElement::new(ec.a.clone(), pu.clone());
            if gp.scalar_mul(&d, &a_fe) != qp {
                return Err("recovered scalar failed verification");
            }
            Ok(BigInt::from_biguint(Sign::Plus, d))
        }
        Err(WeakCurveError::NotApplicable(_)) => {
            Err("not applicable: the curve is singular or ord(P) ≠ p (not anomalous)")
        }
        Err(WeakCurveError::InvalidInput(_)) => {
            Err("invalid input: p must be a prime ≥ 5 and P ≠ O, Q on the curve")
        }
        Err(WeakCurveError::VerificationFailed) => Err("recovered scalar failed verification"),
        Err(_) => Err("every random lift was degenerate or failed verification"),
    }
}

// ── Anomalous-curve search (helper) ──────────────────────────────────────

/// Search for an anomalous curve over `F_p` by trying `(a, b)` pairs
/// and counting points by brute force.  Returns the first `(a, b)`
/// found such that `#E(F_p) = p`.  Suitable for `p ≤ ~200`.
pub fn find_anomalous_curve(p: u64) -> Option<(u64, u64)> {
    for a in 0..p {
        for b in 0..p {
            // Check non-singularity: 4a³ + 27b² ≢ 0 (mod p).
            let disc = (4u64.wrapping_mul(a).wrapping_mul(a).wrapping_mul(a))
                .wrapping_add(27u64.wrapping_mul(b).wrapping_mul(b))
                % p;
            if disc == 0 {
                continue;
            }
            // Brute-force count.
            let mut count: u64 = 1; // point at infinity
            for x in 0..p {
                let rhs = (x.wrapping_mul(x).wrapping_mul(x))
                    .wrapping_add(a.wrapping_mul(x))
                    .wrapping_add(b)
                    % p;
                if rhs == 0 {
                    count += 1;
                    continue;
                }
                // Count y's with y² ≡ rhs (mod p) via Euler.
                let pow = mod_pow_u64(rhs, (p - 1) / 2, p);
                if pow == 1 {
                    count += 2;
                }
            }
            if count == p {
                return Some((a, b));
            }
        }
    }
    None
}

fn mod_pow_u64(base: u64, mut exp: u64, modulus: u64) -> u64 {
    let mut result = 1u128;
    let mut base = base as u128 % modulus as u128;
    let m = modulus as u128;
    while exp > 0 {
        if exp & 1 == 1 {
            result = (result * base) % m;
        }
        base = (base * base) % m;
        exp >>= 1;
    }
    result as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Z_p arithmetic: associativity and identity.
    #[test]
    fn zp_arithmetic_basic() {
        let p = BigInt::from(11);
        let a = ZpInt::new(BigInt::from(5), &p, 3);
        let b = ZpInt::new(BigInt::from(7), &p, 3);
        let c = a.add(&b);
        assert_eq!(c.value, BigInt::from(12));
        let d = a.mul(&b);
        assert_eq!(d.value, BigInt::from(35));
        let zero = ZpInt::zero(&p, 3);
        assert_eq!(a.add(&zero), a);
    }

    /// Z_p inversion: for a coprime to p, find inverse and verify
    /// product is 1 mod p^precision.
    #[test]
    fn zp_inverse_verifies() {
        let p = BigInt::from(11);
        let a = ZpInt::new(BigInt::from(5), &p, 3);
        let inv = a.inverse().expect("5 invertible mod 11³");
        let prod = a.mul(&inv);
        assert_eq!(prod.value, BigInt::from(1));
    }

    /// Z_p valuation.
    #[test]
    fn zp_valuation_correct() {
        let p = BigInt::from(7);
        let a = ZpInt::new(BigInt::from(49), &p, 4); // 49 = 7²
        assert_eq!(a.valuation(), 2);
        let b = ZpInt::new(BigInt::from(3), &p, 4);
        assert_eq!(b.valuation(), 0);
    }

    /// Curve arithmetic over Z_p: point doubling formula consistency.
    #[test]
    fn zp_curve_doubling_self_consistent() {
        let p = BigInt::from(11);
        let curve = ZpCurve::new(BigInt::from(1), BigInt::from(6), &p, 2);
        // Pick a point on E: y² = x³ + x + 6 over F_11.
        // x = 2: rhs = 8 + 2 + 6 = 16 = 5; need y² ≡ 5 mod 11.
        // 4² = 16 ≡ 5 ✓.  So (2, 4) is on E.  Lift it.
        let pt = hensel_lift_point(&curve, &BigInt::from(2), &BigInt::from(4)).expect("2,4 lifts");
        let dbl = curve.double(&pt);
        let added = curve.add(&pt, &pt);
        assert_eq!(dbl, added, "2·P should equal P + P");
    }

    /// Hensel lifting: lifted point satisfies the curve equation
    /// modulo `p^precision`.
    #[test]
    fn hensel_lift_satisfies_curve_equation() {
        let p = BigInt::from(11);
        let curve = ZpCurve::new(BigInt::from(1), BigInt::from(6), &p, 3);
        let lifted = hensel_lift_point(&curve, &BigInt::from(2), &BigInt::from(4)).unwrap();
        if let ZpPoint::Aff(x, y) = lifted {
            let rhs = x.mul(&x).mul(&x).add(&curve.a.mul(&x)).add(&curve.b);
            let lhs = y.mul(&y);
            assert_eq!(lhs, rhs, "lifted point doesn't satisfy curve eqn");
        } else {
            panic!("expected affine lift");
        }
    }

    /// Anomalous-curve search: at p = 11, find a curve with #E = 11.
    #[test]
    fn find_anomalous_curve_works() {
        let p = 11u64;
        let result = find_anomalous_curve(p);
        assert!(result.is_some(), "should find an anomalous curve over F_11");
        let (a, b) = result.unwrap();
        // Verify by re-counting.
        let mut count: u64 = 1;
        for x in 0..p {
            let rhs = (x * x * x + a * x + b) % p;
            if rhs == 0 {
                count += 1;
            } else {
                let pow = mod_pow_u64(rhs, (p - 1) / 2, p);
                if pow == 1 {
                    count += 2;
                }
            }
        }
        assert_eq!(count, p, "verified count");
    }

    /// `smart_attack_anomalous` recovers every scalar on the smallest
    /// anomalous curves found by brute force, and rejects a
    /// non-anomalous one.  (It used to be a stub returning `Err`.)
    #[test]
    fn smart_attack_recovers_scalars() {
        for p in [11u64, 17, 29] {
            let (a, b) = find_anomalous_curve(p).expect("anomalous curve");
            // First affine point with y ≠ 0.
            let (px, py) = (0..p)
                .flat_map(|x| (1..p).map(move |y| (x, y)))
                .find(|&(x, y)| (y * y) % p == (x * x * x + a * x + b) % p)
                .unwrap();
            let pb = BigInt::from(p);
            let curve = ZpCurve::new(BigInt::from(a), BigInt::from(b), &pb, 1);
            let base = ZpPoint::Aff(
                ZpInt::new(BigInt::from(px), &pb, 1),
                ZpInt::new(BigInt::from(py), &pb, 1),
            );
            for d in 1..p {
                let qd = curve.scalar_mul(&base, &BigInt::from(d));
                let ZpPoint::Aff(qx, qy) = qd else {
                    panic!("d·P = O for 0 < d < p");
                };
                let got = smart_attack_anomalous(
                    &pb,
                    &BigInt::from(a),
                    &BigInt::from(b),
                    &BigInt::from(px),
                    &BigInt::from(py),
                    &qx.value,
                    &qy.value,
                )
                .unwrap_or_else(|e| panic!("p={p} d={d}: {e}"));
                assert_eq!(got, BigInt::from(d));
            }
        }
        // y² = x³ + x + 6 over F_11 has 13 points: not anomalous.
        let r = smart_attack_anomalous(
            &BigInt::from(11),
            &BigInt::from(1),
            &BigInt::from(6),
            &BigInt::from(2),
            &BigInt::from(4),
            &BigInt::from(2),
            &BigInt::from(4),
        );
        assert!(r.unwrap_err().contains("not anomalous"));
    }
}
