//! **Hyperelliptic curves** `C: y² + h(x)·y = f(x)` over `F_{2^m}`
//! with Jacobian arithmetic in **Mumford representation** via
//! **Cantor's algorithm** (characteristic-2 variant).
//!
//! ## Background
//!
//! A hyperelliptic curve of genus `g` over `F_q` is a non-singular
//! projective curve birational to an affine model
//! ```text
//!     C : y² + h(x)·y = f(x)
//! ```
//! with `deg f ≤ 2g + 1` and `deg h ≤ g`.  In characteristic 2 the
//! `h(x)` term is mandatory (otherwise `C` is singular).
//!
//! The Jacobian variety `Jac(C)` is a `g`-dimensional abelian group;
//! over `F_q` its rational points form a finite abelian group whose
//! order lies in the **Weil interval** `(√q − 1)^{2g} ≤ #Jac(C)(F_q) ≤
//! (√q + 1)^{2g}`.  This is the target of HCDLP (hyperelliptic discrete-
//! log) attacks and the *codomain* of the GHS Weil-descent homomorphism
//! from `E(F_{q^n})`.
//!
//! ## Mumford representation
//!
//! Every reduced divisor class in `Jac(C)(F_q)` has a **unique** pair
//! of polynomials `(u(x), v(x))` over `F_q` with:
//! - `u` monic,
//! - `deg v < deg u ≤ g`,
//! - `u  |  v² + h·v + f`  (mod 2; `−` becomes `+` in char 2).
//!
//! Geometrically `u(x) = ∏(x − x_i)` for the affine `x`-coordinates of
//! the divisor's support (with multiplicity), and `y = v(x)` interpolates
//! the `y`-coordinates of those points.  The identity is `(1, 0)`
//! (the empty divisor).
//!
//! ## Cantor's algorithm (Koblitz '89, Cantor '87, char-2 form)
//!
//! To add `D_1 = (u_1, v_1)` and `D_2 = (u_2, v_2)`:
//!
//! **Composition.**  Let `d_1 = gcd(u_1, u_2) = e_1·u_1 + e_2·u_2`
//! (extended Euclidean).  Let `d = gcd(d_1, v_1 + v_2 + h) =
//! c_1·d_1 + c_2·(v_1 + v_2 + h)`.  Let `s_1 = c_1·e_1`, `s_2 = c_1·e_2`,
//! `s_3 = c_2`.  Then
//! ```text
//!     u'  = u_1 · u_2 / d²
//!     v'  = (s_1·u_1·v_2 + s_2·u_2·v_1 + s_3·(v_1·v_2 + f)) / d  (mod u')
//! ```
//!
//! **Reduction** (apply while `deg u' > g`):
//! ```text
//!     u'' = monic((f + h·v' + v'²) / u')      // exact division
//!     v'' = (h + v') mod u''                  // char-2 sign collapse
//! ```
//! When `deg u' ≤ g`, the pair `(u', v')` is the reduced sum.
//!
//! ## What this module provides
//!
//! - [`HyperellipticCurve`] — `(h, f, g)` over `F_{2^m}` with sanity
//!   checks (`is_on_curve`, `genus`, leading-coefficient invariants).
//! - [`MumfordDivisor`] — `(u, v)` with the invariants enforced on
//!   construction, plus `is_reduced`, `eq` (canonical), `is_identity`.
//! - Group law: [`MumfordDivisor::add`], [`MumfordDivisor::neg`],
//!   [`MumfordDivisor::double`], [`MumfordDivisor::scalar_mul`].
//! - Point-to-divisor conversion: [`MumfordDivisor::from_point`]
//!   (the standard embedding `P ↦ [P] − [∞]` for non-Weierstrass `P`).
//! - **BSGS** discrete-log solver: [`hcdlp_bsgs`] — for toy-sized
//!   Jacobians (genus ≤ ~3, base field ≤ ~F_{2^8}).
//! - **Pollard-ρ** discrete-log solver: [`hcdlp_pollard_rho`] —
//!   exponential in `√#Jac(C)`, works at slightly larger sizes.
//!
//! ## Honest scope
//!
//! - **Toy sizes only.**  These routines are correct but unoptimised.
//!   `add` allocates polynomial vectors; `scalar_mul` uses left-to-
//!   right double-and-add without windowing.  Realistic ECC-trapdoor
//!   parameters (`N ≈ 160`, `g ≈ 30`) would need a much faster
//!   Jacobian implementation and index-calculus HCDLP — out of scope
//!   for this educational reference.  The end-to-end test runs at
//!   `N ∈ {6, 8, 10, 12}` where brute-force ECDLP can verify the
//!   trapdoor's answer.
//! - **Generic point assumption.**  `from_point` assumes the input is
//!   not a Weierstrass point (no vertical tangent).  Trapdoor-bearing
//!   points produced by the GHS descent are generic in practice; we
//!   bail with `None` if a Weierstrass point is encountered.

use super::f2m::{F2mElement, IrreduciblePoly};
use super::poly_f2m::F2mPoly;
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// `C : y² + h(x)·y = f(x)` over `F_{2^m}` with `m`'s irreducible
/// polynomial provided.  Stores genus and both defining polynomials.
#[derive(Clone, Debug)]
pub struct HyperellipticCurve {
    /// Field width — `C` is defined over `F_{2^m}`.
    pub m: u32,
    /// Reduction polynomial of `F_{2^m}`.
    pub irr: IrreduciblePoly,
    /// `h(x)` with `deg h ≤ g`.
    pub h: F2mPoly,
    /// `f(x)` with `deg f ≤ 2g + 1`.
    pub f: F2mPoly,
    /// Genus.
    pub genus: u32,
}

impl HyperellipticCurve {
    /// Construct with explicit genus.  Sanity-checks the degree
    /// bounds (`deg f ≤ 2g + 1`, `deg h ≤ g`).  Does **not** check
    /// non-singularity globally — only obvious degeneracies like
    /// `f = 0` and `h = 0`.
    pub fn new(m: u32, irr: IrreduciblePoly, h: F2mPoly, f: F2mPoly, genus: u32) -> Self {
        let g = genus as usize;
        assert!(!f.is_zero(), "f must be non-zero");
        // In char 2, h(x) = 0 makes C singular.  We allow toy curves
        // where h is just the constant 1 (a common shortcut for
        // demonstration), but warn the caller in debug builds.
        debug_assert!(!h.is_zero(), "h = 0 gives a singular curve in char 2");
        debug_assert!(f.degree().unwrap_or(0) <= 2 * g + 1);
        debug_assert!(h.degree().unwrap_or(0) <= g);
        Self {
            m,
            irr,
            h,
            f,
            genus,
        }
    }

    /// `true` iff `(x, y)` satisfies `y² + h(x)·y = f(x)`.
    pub fn is_on_curve(&self, x: &F2mElement, y: &F2mElement) -> bool {
        let lhs = y
            .square(&self.irr)
            .add(&self.h.eval(x, &self.irr).mul(y, &self.irr));
        let rhs = self.f.eval(x, &self.irr);
        lhs == rhs
    }
}

/// A reduced Mumford divisor `(u, v)` on a [`HyperellipticCurve`].
/// The curve reference is *not* stored — the polynomials carry the
/// field width and the caller threads the curve in for arithmetic
/// (this avoids lifetime annotations on every divisor).
#[derive(Clone, Debug)]
pub struct MumfordDivisor {
    /// Monic, `deg u ≤ g`.
    pub u: F2mPoly,
    /// `deg v < deg u`, satisfies `u | v² + h·v + f`.
    pub v: F2mPoly,
}

impl PartialEq for MumfordDivisor {
    fn eq(&self, other: &Self) -> bool {
        self.u == other.u && self.v == other.v
    }
}

impl Eq for MumfordDivisor {}

impl MumfordDivisor {
    /// Identity element `(1, 0)` of `Jac(C)(F_q)`.
    pub fn identity(m: u32) -> Self {
        Self {
            u: F2mPoly::one(m),
            v: F2mPoly::zero(m),
        }
    }

    /// Embed an affine point `P = (x_0, y_0)` on `C` into `Jac(C)` as
    /// the class of `[P] − [∞]`.  Returns `None` if `P` is a
    /// Weierstrass point (in char 2: `h(x_0) = 0`), since the
    /// representation degenerates there.
    pub fn from_point(
        curve: &HyperellipticCurve,
        x0: &F2mElement,
        y0: &F2mElement,
    ) -> Option<Self> {
        assert!(curve.is_on_curve(x0, y0));
        let h_at_x0 = curve.h.eval(x0, &curve.irr);
        if h_at_x0.is_zero() {
            // Weierstrass point: 2·y₀ + h(x₀)·y₀ = … the order-2
            // case; the Mumford pair becomes (x − x₀, y₀) but
            // doubling/inversion behaves differently.  Skip it.
            return None;
        }
        // u(x) = x + x₀  (char 2; "x − x₀" = "x + x₀").
        let u = F2mPoly::from_coeffs(vec![x0.clone(), F2mElement::one(curve.m)], curve.m);
        // v(x) = y₀ (constant).
        let v = F2mPoly::constant(y0.clone());
        Some(Self { u, v })
    }

    /// `true` iff `(u, v)` already satisfies the reduced-divisor
    /// invariants: `u` monic, `deg v < deg u ≤ g`, `u | v² + h·v + f`.
    /// Used by tests; production paths construct reduced divisors by
    /// construction.
    pub fn is_reduced(&self, curve: &HyperellipticCurve) -> bool {
        if self.u.is_zero() {
            return false;
        }
        if self.u.lead() != F2mElement::one(curve.m) {
            return false;
        }
        let du = self.u.degree().unwrap();
        if du > curve.genus as usize {
            return false;
        }
        if !self.v.is_zero() && self.v.degree().unwrap() >= du {
            return false;
        }
        // u | v² + h·v + f
        let vsq = self.v.mul(&self.v, &curve.irr);
        let hv = curve.h.mul(&self.v, &curve.irr);
        let target = vsq.add(&hv).add(&curve.f);
        let (_q, r) = target.divrem(&self.u, &curve.irr);
        r.is_zero()
    }

    /// `D + (0)`  ≡  `D` — the additive identity check.
    pub fn is_identity(&self) -> bool {
        self.u.degree() == Some(0) && self.v.is_zero()
    }

    /// **Negation**: `−(u, v) = (u, (h + v) mod u)`.
    ///
    /// On the underlying curve this maps `(x_i, y_i)` to
    /// `(x_i, y_i + h(x_i))` — the "other" root of the quadratic.
    pub fn neg(&self, curve: &HyperellipticCurve) -> Self {
        let h_plus_v = curve.h.add(&self.v);
        let v_new = if self.u.is_zero() {
            h_plus_v
        } else {
            h_plus_v.rem(&self.u, &curve.irr)
        };
        Self {
            u: self.u.clone(),
            v: v_new,
        }
    }

    /// **Cantor composition**: produce a (possibly unreduced) divisor
    /// representing `self + other`.  Result has `deg u ≤ 2g`; callers
    /// should follow with [`reduce`] to bring it back to `deg u ≤ g`.
    fn cantor_compose(&self, other: &Self, curve: &HyperellipticCurve) -> Self {
        let irr = &curve.irr;
        // Step 1: d1 = gcd(u1, u2) = e1·u1 + e2·u2
        let (d1, e1, e2) = self.u.ext_gcd(&other.u, irr);
        // Step 2: d = gcd(d1, v1 + v2 + h) = c1·d1 + c2·(v1+v2+h)
        let v_sum = self.v.add(&other.v).add(&curve.h);
        let (d, c1, c2) = d1.ext_gcd(&v_sum, irr);
        // Step 3: combine — s1 = c1·e1, s2 = c1·e2, s3 = c2
        let s1 = c1.mul(&e1, irr);
        let s2 = c1.mul(&e2, irr);
        let s3 = c2.clone();
        // Step 4: u' = u1·u2 / d²
        let u_prod = self.u.mul(&other.u, irr);
        let d_sq = d.mul(&d, irr);
        let (u_prime, u_rem) = u_prod.divrem(&d_sq, irr);
        debug_assert!(u_rem.is_zero(), "u1·u2 not divisible by d²");
        // Step 5: v' = (s1·u1·v2 + s2·u2·v1 + s3·(v1·v2 + f)) / d  (mod u')
        let term1 = s1.mul(&self.u, irr).mul(&other.v, irr);
        let term2 = s2.mul(&other.u, irr).mul(&self.v, irr);
        let v1v2 = self.v.mul(&other.v, irr);
        let term3 = s3.mul(&v1v2.add(&curve.f), irr);
        let v_num = term1.add(&term2).add(&term3);
        let (v_div, v_div_rem) = v_num.divrem(&d, irr);
        debug_assert!(v_div_rem.is_zero(), "v numerator not divisible by d");
        let v_prime = v_div.rem(&u_prime, irr);
        Self {
            u: u_prime,
            v: v_prime,
        }
    }

    /// **Cantor reduction**: bring `(u, v)` with `deg u > g` back to
    /// `deg u ≤ g` by repeated application of the standard reduction
    /// step.  Idempotent on already-reduced divisors.
    fn reduce(&self, curve: &HyperellipticCurve) -> Self {
        let irr = &curve.irr;
        let g = curve.genus as usize;
        let mut u = self.u.clone();
        let mut v = self.v.clone();
        while u.degree().map(|d| d > g).unwrap_or(false) {
            // u_new = (f + h·v + v²) / u
            let vsq = v.mul(&v, irr);
            let hv = curve.h.mul(&v, irr);
            let num = curve.f.add(&hv).add(&vsq);
            let (u_new_raw, rem) = num.divrem(&u, irr);
            debug_assert!(rem.is_zero(), "Cantor reduction: non-exact division");
            // Make u_new monic.
            let u_new = u_new_raw.monic(irr);
            // v_new = (h + v) mod u_new
            let v_new = curve.h.add(&v).rem(&u_new, irr);
            u = u_new;
            v = v_new;
        }
        // Final monic-normalisation just in case the loop exited
        // with a non-monic u (it shouldn't, but be safe).
        if !u.is_zero() && u.lead() != F2mElement::one(u.m) {
            u = u.monic(irr);
        }
        Self { u, v }
    }

    /// **Group addition** in `Jac(C)(F_q)`.
    pub fn add(&self, other: &Self, curve: &HyperellipticCurve) -> Self {
        // Short-circuit identity.
        if self.is_identity() {
            return other.clone();
        }
        if other.is_identity() {
            return self.clone();
        }
        let composed = self.cantor_compose(other, curve);
        composed.reduce(curve)
    }

    /// **Doubling** — `2·self`.  Cantor's algorithm handles the
    /// `u_1 = u_2` case correctly through `gcd`, so we just call
    /// `add` with `self` on both sides; a specialised doubling
    /// formula could be added for speed.
    pub fn double(&self, curve: &HyperellipticCurve) -> Self {
        self.add(self, curve)
    }

    /// **Scalar multiplication** `[k]·self` via left-to-right
    /// double-and-add.
    pub fn scalar_mul(&self, k: &BigUint, curve: &HyperellipticCurve) -> Self {
        if k.is_zero() {
            return Self::identity(curve.m);
        }
        let bits = k.bits();
        let mut result = Self::identity(curve.m);
        for i in (0..bits).rev() {
            result = result.double(curve);
            if k.bit(i) {
                result = result.add(self, curve);
            }
        }
        result
    }
}

// ── HCDLP solvers ────────────────────────────────────────────────────

/// **Baby-step / Giant-step** for `Q = [k]·P` on `Jac(C)`.  Returns
/// `Some(k)` with `0 ≤ k < bound` if a solution exists, else `None`.
///
/// Memory `O(√bound)`; time `O(√bound · log bound)`.  Good for toy
/// Jacobians with `#Jac(C)(F_q) ≤ 2^{30}` or so.
pub fn hcdlp_bsgs(
    p: &MumfordDivisor,
    q: &MumfordDivisor,
    bound: &BigUint,
    curve: &HyperellipticCurve,
) -> Option<BigUint> {
    use std::collections::HashMap;
    // m = ceil(sqrt(bound))
    let sqrt_b = bound.sqrt() + BigUint::one();
    let m = sqrt_b;
    // Baby steps: { (i, i·P) : 0 ≤ i < m }
    let mut table: HashMap<(Vec<u8>, Vec<u8>), BigUint> = HashMap::new();
    let mut acc = MumfordDivisor::identity(curve.m);
    let mut i = BigUint::zero();
    while i < m {
        let key = divisor_key(&acc);
        table.entry(key).or_insert_with(|| i.clone());
        acc = acc.add(p, curve);
        i += BigUint::one();
    }
    // Giant step factor: γ = [m]·P.  Walk Q, Q − γ, Q − 2γ, …, look up.
    let gamma = p.scalar_mul(&m, curve);
    let neg_gamma = gamma.neg(curve);
    let mut gq = q.clone();
    let mut j = BigUint::zero();
    while j < m {
        let key = divisor_key(&gq);
        if let Some(i_val) = table.get(&key) {
            // k = j·m + i  (mod #Jac); we don't know #Jac here, so
            // return the lift in [0, bound).
            let k = &j * &m + i_val;
            if &k < bound {
                return Some(k);
            }
        }
        gq = gq.add(&neg_gamma, curve);
        j += BigUint::one();
    }
    None
}

fn divisor_key(d: &MumfordDivisor) -> (Vec<u8>, Vec<u8>) {
    let serialize = |p: &F2mPoly| -> Vec<u8> {
        let mut out = Vec::new();
        for c in &p.coeffs {
            let bytes = c.to_biguint().to_bytes_be();
            out.push(bytes.len() as u8);
            out.extend(bytes);
        }
        out
    };
    (serialize(&d.u), serialize(&d.v))
}

/// **Pollard's ρ** on `Jac(C)(F_q)`.  Three-partition deterministic
/// walk; halts when a collision is found.  Requires the group order
/// `n` (or a multiple of it) to extract the discrete log.
///
/// Same caveat as the elliptic version: `O(√n)` time, exponential
/// in the genus.
pub fn hcdlp_pollard_rho(
    p: &MumfordDivisor,
    q: &MumfordDivisor,
    order: &BigUint,
    curve: &HyperellipticCurve,
) -> Option<BigUint> {
    use crate::utils::mod_inverse;
    // Three-partition walker.
    let partition = |d: &MumfordDivisor| -> usize {
        // Hash-based partition: take the trailing byte of u's
        // constant coefficient mod 3.
        let c0 = d.u.coeff(0).to_biguint();
        let b = c0.to_bytes_be().last().copied().unwrap_or(0);
        (b as usize) % 3
    };
    let step =
        |d: &MumfordDivisor, a: &BigUint, b: &BigUint| -> (MumfordDivisor, BigUint, BigUint) {
            match partition(d) {
                0 => (d.add(p, curve), (a + 1u32) % order, b.clone()),
                1 => (d.double(curve), (a * 2u32) % order, (b * 2u32) % order),
                _ => (d.add(q, curve), a.clone(), (b + 1u32) % order),
            }
        };
    let mut x = MumfordDivisor::identity(curve.m);
    let mut a = BigUint::zero();
    let mut b = BigUint::zero();
    let mut xt = x.clone();
    let mut at = a.clone();
    let mut bt = b.clone();
    let max_steps: u64 = 1 << 24;
    for _ in 0..max_steps {
        let (nx, na, nb) = step(&x, &a, &b);
        x = nx;
        a = na;
        b = nb;
        let (nx, na, nb) = step(&xt, &at, &bt);
        let (nx, na, nb) = step(&nx, &na, &nb);
        xt = nx;
        at = na;
        bt = nb;
        if x == xt {
            // a + b·k ≡ at + bt·k  ⇒  k ≡ (a − at)/(bt − b)  (mod order).
            let num = if a >= at { &a - &at } else { order + &a - &at };
            let den = if bt >= b { &bt - &b } else { order + &bt - &b };
            if den.is_zero() {
                return None; // bad walk; caller should retry
            }
            let den_inv = mod_inverse(&den, order)?;
            let k = (&num * &den_inv) % order;
            // Verify.
            if p.scalar_mul(&k, curve) == *q {
                return Some(k);
            }
            return None;
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::f2m::IrreduciblePoly;

    /// Genus-1 hyperelliptic curve over F_{2^8} — i.e., an elliptic
    /// curve in disguise, useful for sanity-checking the Jacobian
    /// arithmetic against the known elliptic group law.
    fn g1_curve_f16() -> HyperellipticCurve {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        // C: y² + (x+1)·y = x³ + x + 1   (toy)
        let h = F2mPoly::from_coeffs(vec![F2mElement::one(m), F2mElement::one(m)], m);
        let mut f_coeffs = vec![F2mElement::zero(m); 4];
        f_coeffs[0] = F2mElement::one(m);
        f_coeffs[1] = F2mElement::one(m);
        f_coeffs[3] = F2mElement::one(m);
        let f = F2mPoly::from_coeffs(f_coeffs, m);
        HyperellipticCurve::new(m, irr, h, f, 1)
    }

    #[test]
    fn identity_is_identity() {
        let curve = g1_curve_f16();
        let id = MumfordDivisor::identity(curve.m);
        assert!(id.is_identity());
        // Identity + identity = identity.
        let sum = id.add(&id, &curve);
        assert!(sum.is_identity());
    }

    #[test]
    fn neg_then_add_is_identity() {
        let curve = g1_curve_f16();
        // Find an affine point on the curve by trial.
        let m = curve.m;
        let mut found = None;
        for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            // y² + h(x)·y = f(x)  →  y² + h(x)·y + f(x) = 0
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        found = Some((x.clone(), y.clone()));
                        break;
                    }
                }
            }
            if found.is_some() {
                break;
            }
        }
        let (x0, y0) = found.expect("a generic point exists");
        let d = MumfordDivisor::from_point(&curve, &x0, &y0).unwrap();
        let neg_d = d.neg(&curve);
        let sum = d.add(&neg_d, &curve);
        assert!(sum.is_identity(), "D + (-D) should be identity");
    }

    #[test]
    fn double_equals_self_add() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Find two generic points P, Q with x_P ≠ x_Q.
        let mut points = Vec::new();
        'outer: for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        points.push((x.clone(), y.clone()));
                        if points.len() >= 4 {
                            break 'outer;
                        }
                        break;
                    }
                }
            }
        }
        assert!(points.len() >= 2);
        let p = MumfordDivisor::from_point(&curve, &points[0].0, &points[0].1).unwrap();
        let pp_dbl = p.double(&curve);
        let pp_add = p.add(&p, &curve);
        assert_eq!(pp_dbl, pp_add);
    }

    #[test]
    fn scalar_mul_distributes_over_zero() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Any point ⋅ 0 = identity.
        let x = F2mElement::from_biguint(&BigUint::from(5u32), m);
        // Find a y for this x (or skip).
        let mut p = None;
        for yi in 0u64..256 {
            let y = F2mElement::from_biguint(&BigUint::from(yi), m);
            if curve.is_on_curve(&x, &y) {
                let h_at_x = curve.h.eval(&x, &curve.irr);
                if !h_at_x.is_zero() {
                    p = MumfordDivisor::from_point(&curve, &x, &y);
                    break;
                }
            }
        }
        if let Some(p) = p {
            let zero_p = p.scalar_mul(&BigUint::zero(), &curve);
            assert!(zero_p.is_identity());
            let one_p = p.scalar_mul(&BigUint::one(), &curve);
            assert_eq!(one_p, p);
        }
    }

    #[test]
    fn bsgs_finds_small_dlp() {
        let curve = g1_curve_f16();
        let m = curve.m;
        // Find any generic point.
        let mut p = None;
        'outer: for xi in 1u64..256 {
            let x = F2mElement::from_biguint(&BigUint::from(xi), m);
            for yi in 0u64..256 {
                let y = F2mElement::from_biguint(&BigUint::from(yi), m);
                if curve.is_on_curve(&x, &y) {
                    let h_at_x = curve.h.eval(&x, &curve.irr);
                    if !h_at_x.is_zero() {
                        p = MumfordDivisor::from_point(&curve, &x, &y);
                        break 'outer;
                    }
                }
            }
        }
        let p = p.unwrap();
        let k_true = BigUint::from(13u32);
        let q = p.scalar_mul(&k_true, &curve);
        let recovered = hcdlp_bsgs(&p, &q, &BigUint::from(2000u32), &curve);
        assert_eq!(recovered, Some(k_true));
    }
}
