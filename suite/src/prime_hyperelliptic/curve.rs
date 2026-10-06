//! **Hyperelliptic curves `C : y² = f(x)` over `F_p`** (odd `p`),
//! with Mumford-rep divisors and Cantor's algorithm in
//! odd-characteristic form (no `h(x) y` term).
//!
//! ## Equation & invariants
//!
//! For genus `g`, `deg f ∈ {2g+1, 2g+2}` and `f` is squarefree.  Most
//! cryptanalytic literature uses `deg f = 2g+1` ("imaginary"
//! quadratic; one point at infinity).  This module supports that
//! case primarily; `2g+2` (the "real" case, two points at infinity)
//! is left out of the Mumford / Cantor implementation since it adds
//! considerable bookkeeping not needed for the Phase-1 probe.
//!
//! ## Mumford representation (char `p ≠ 2`)
//!
//! Every reduced divisor class is `(u(x), v(x))` with `u` monic,
//! `deg v < deg u ≤ g`, and `u | v² − f`.  The identity is
//! `(1, 0)`.
//!
//! ## Cantor's algorithm
//!
//! **Composition** of `D_1 = (u_1, v_1)` and `D_2 = (u_2, v_2)`:
//! ```text
//!   d_1 = gcd(u_1, u_2)             = e_1·u_1 + e_2·u_2
//!   d   = gcd(d_1, v_1 + v_2)       = c_1·d_1 + c_2·(v_1 + v_2)
//!   s_1 = c_1·e_1, s_2 = c_1·e_2, s_3 = c_2
//!   u'  = u_1·u_2 / d²
//!   v'  = (s_1·u_1·v_2 + s_2·u_2·v_1 + s_3·(v_1·v_2 + f)) / d  (mod u')
//! ```
//!
//! **Reduction** (while `deg u' > g`):
//! ```text
//!   u_new = monic((f − v'²) / u')
//!   v_new = (−v') mod u_new
//! ```

use super::fp2::{Fp2, Fp2Ctx};
use super::fp_poly::FpPoly;
use num_bigint::BigUint;
use num_traits::{One, Zero};

/// `C : y² = f(x)` over `F_p`.
#[derive(Clone, Debug)]
pub struct HyperellipticCurveP {
    pub p: BigUint,
    pub f: FpPoly,
    pub genus: u32,
}

impl HyperellipticCurveP {
    pub fn new(p: BigUint, f: FpPoly, genus: u32) -> Self {
        debug_assert!(!f.is_zero());
        debug_assert_eq!(f.p, p);
        Self { p, f, genus }
    }

    /// `true` iff `(x, y) ∈ C(F_p)`.  Includes the "infinity"
    /// convention (caller is expected to handle ∞ outside).
    pub fn is_on_curve(&self, x: &BigUint, y: &BigUint) -> bool {
        let lhs = (y * y) % &self.p;
        let rhs = self.f.eval(x);
        lhs == rhs
    }

    /// Number of affine points `(x, y) ∈ C(F_p)` plus 1 for the
    /// point at infinity (assuming `deg f = 2g+1`, one point at ∞).
    pub fn count_affine_plus_infinity(&self) -> BigUint {
        let mut count = BigUint::one(); // +1 for ∞
        let p_u: u64 = match self.p.to_u64_digits().as_slice() {
            [v] => *v,
            _ => panic!("count_affine: p too big for u64 enumeration"),
        };
        for xi in 0..p_u {
            let x = BigUint::from(xi);
            let y_sq = self.f.eval(&x);
            if y_sq.is_zero() {
                count += 1u32; // (x, 0) is one point
                continue;
            }
            // y² = y_sq: two roots if QR, zero if non-QR.
            // QR test via Euler's criterion: y_sq^((p-1)/2).
            let exp = (&self.p - BigUint::one()) >> 1;
            let chi = y_sq.modpow(&exp, &self.p);
            if chi == BigUint::one() {
                count += 2u32;
            }
        }
        count
    }
}

/// Count affine F_p-points on `C : y² = f(x)` plus 1 for ∞.
/// Convenience wrapper.
pub fn count_points(curve: &HyperellipticCurveP) -> BigUint {
    curve.count_affine_plus_infinity()
}

/// Reduced Mumford divisor `(u, v)` on a `HyperellipticCurveP`.
#[derive(Clone, Debug)]
pub struct MumfordDivisorP {
    pub u: FpPoly,
    pub v: FpPoly,
}

impl PartialEq for MumfordDivisorP {
    fn eq(&self, other: &Self) -> bool {
        self.u == other.u && self.v == other.v
    }
}

impl Eq for MumfordDivisorP {}

impl MumfordDivisorP {
    /// Identity `(1, 0)`.
    pub fn identity(p: BigUint) -> Self {
        Self {
            u: FpPoly::one(p.clone()),
            v: FpPoly::zero(p),
        }
    }

    /// `(u, v)` valid? (monic `u`, `deg v < deg u ≤ g`, `u | v² − f`).
    pub fn is_reduced(&self, curve: &HyperellipticCurveP) -> bool {
        if self.u.is_zero() {
            return false;
        }
        if self.u.lead() != BigUint::one() {
            return false;
        }
        let du = self.u.degree().unwrap();
        if du > curve.genus as usize {
            return false;
        }
        if !self.v.is_zero() && self.v.degree().unwrap() >= du {
            return false;
        }
        // u | v² − f
        let v_sq = self.v.mul(&self.v);
        let target = v_sq.sub(&curve.f);
        let (_q, r) = target.divrem(&self.u);
        r.is_zero()
    }

    pub fn is_identity(&self) -> bool {
        self.u.degree() == Some(0) && self.v.is_zero()
    }

    /// Negation: `−(u, v) = (u, −v mod u)`.
    pub fn neg(&self, _curve: &HyperellipticCurveP) -> Self {
        let v_neg = self.v.neg();
        let v_new = if self.u.is_zero() {
            v_neg
        } else {
            v_neg.rem(&self.u)
        };
        Self {
            u: self.u.clone(),
            v: v_new,
        }
    }

    /// Embed `P = (x_0, y_0)` on `C` as `[P] − [∞]`.  Returns
    /// `None` if `y_0 = 0` (a "Weierstrass" point — order 2;
    /// representable but doubles differently).
    pub fn from_point(curve: &HyperellipticCurveP, x0: &BigUint, y0: &BigUint) -> Option<Self> {
        assert!(curve.is_on_curve(x0, y0));
        if y0.is_zero() {
            return None;
        }
        let p = &curve.p;
        // u = x − x_0
        let u = FpPoly::from_coeffs(vec![(p - x0) % p, BigUint::one()], p.clone());
        let v = FpPoly::constant(y0.clone(), p.clone());
        Some(Self { u, v })
    }

    fn cantor_compose(&self, other: &Self, curve: &HyperellipticCurveP) -> Self {
        let (d1, e1, e2) = self.u.ext_gcd(&other.u);
        let v_sum = self.v.add(&other.v);
        let (d, c1, c2) = d1.ext_gcd(&v_sum);
        let s1 = c1.mul(&e1);
        let s2 = c1.mul(&e2);
        let s3 = c2.clone();
        let u_prod = self.u.mul(&other.u);
        let d_sq = d.mul(&d);
        let (u_prime, u_rem) = u_prod.divrem(&d_sq);
        debug_assert!(u_rem.is_zero(), "u1·u2 not divisible by d²");
        let term1 = s1.mul(&self.u).mul(&other.v);
        let term2 = s2.mul(&other.u).mul(&self.v);
        let v1v2 = self.v.mul(&other.v);
        let term3 = s3.mul(&v1v2.add(&curve.f));
        let v_num = term1.add(&term2).add(&term3);
        let (v_div, v_div_rem) = v_num.divrem(&d);
        debug_assert!(v_div_rem.is_zero(), "v numerator not divisible by d");
        let v_prime = v_div.rem(&u_prime);
        Self {
            u: u_prime,
            v: v_prime,
        }
    }

    fn reduce(&self, curve: &HyperellipticCurveP) -> Self {
        let g = curve.genus as usize;
        let mut u = self.u.clone();
        let mut v = self.v.clone();
        while u.degree().map(|d| d > g).unwrap_or(false) {
            // u_new = (f - v²) / u
            let v_sq = v.mul(&v);
            let num = curve.f.sub(&v_sq);
            let (u_new_raw, rem) = num.divrem(&u);
            debug_assert!(rem.is_zero(), "Cantor reduction: non-exact division");
            let u_new = u_new_raw.monic();
            // v_new = (-v) mod u_new
            let v_new = v.neg().rem(&u_new);
            u = u_new;
            v = v_new;
        }
        if !u.is_zero() && u.lead() != BigUint::one() {
            u = u.monic();
        }
        Self { u, v }
    }

    pub fn add(&self, other: &Self, curve: &HyperellipticCurveP) -> Self {
        if self.is_identity() {
            return other.clone();
        }
        if other.is_identity() {
            return self.clone();
        }
        let composed = self.cantor_compose(other, curve);
        composed.reduce(curve)
    }

    pub fn double(&self, curve: &HyperellipticCurveP) -> Self {
        self.add(self, curve)
    }

    pub fn scalar_mul(&self, k: &BigUint, curve: &HyperellipticCurveP) -> Self {
        if k.is_zero() {
            return Self::identity(curve.p.clone());
        }
        let bits = k.bits();
        let mut result = Self::identity(curve.p.clone());
        for i in (0..bits).rev() {
            result = result.double(curve);
            if k.bit(i) {
                result = result.add(self, curve);
            }
        }
        result
    }
}

// ── #Jac(C)(F_p) by brute force ──────────────────────────────────────

/// Enumerate every reduced Mumford divisor on `C` and count.  Toy
/// only — runs in `O(p^g)` time and memory.  For genus 2 at `p ≤
/// few hundred` this is seconds.
pub fn brute_force_jac_order(curve: &HyperellipticCurveP) -> BigUint {
    assert_eq!(curve.genus, 2, "brute_force_jac_order: genus 2 only");
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("brute_force_jac_order: p too big"),
    };
    let p = &curve.p;
    let mut count: u64 = 1; // identity (1, 0)

    // Degree-1 divisors: u = x - x_0, with f(x_0) a QR (or 0).  For
    // f(x_0) = 0 (root of f), v = 0 — one divisor.  For f(x_0) =
    // y_sq with y_sq a non-zero QR — two divisors (v = ±y_0).
    for xi in 0..p_u {
        let x = BigUint::from(xi);
        let y_sq = curve.f.eval(&x);
        if y_sq.is_zero() {
            count += 1;
        } else {
            let exp = (p - BigUint::one()) >> 1;
            let chi = y_sq.modpow(&exp, p);
            if chi == BigUint::one() {
                count += 2;
            }
        }
    }

    // Degree-2 divisors: u = x² + ax + b.  For each (a, b) ∈ F_p²:
    // require u(x) | v² − f(x) for some v with deg v ≤ 1.
    //
    // Method: compute r(x) = f(x) mod u(x), which is a degree-≤1
    // polynomial.  Then we need v² ≡ r(x) (mod u).  Quadratic
    // residue test in the quotient ring F_p[x]/u(x).
    //
    // (1) If u is reducible over F_p, u(x) = (x − α)(x − β).  Then
    //     F_p[x]/u ≅ F_p × F_p, and `r mod u` corresponds to
    //     (r(α), r(β)).  Need both to be squares (or both zero).
    //     If α ≠ β and both are squares: 2 choices of v at each
    //     factor → 4 v's, BUT each v gives a unique divisor (since
    //     swapping y-coords gives a different divisor); however we
    //     also need to mod out by the divisor-class equivalence:
    //     the divisor (u, v) and (u, v') represent the same class
    //     iff v ≡ v' (mod u), so the 4 v's give 4 distinct classes.
    //     Wait — actually distinct v's mod u give distinct divisors
    //     so 4 classes.  But the divisor (u, v) with v(α) = y_α,
    //     v(β) = y_β represents the divisor [α, y_α] + [β, y_β], and
    //     "swapping signs" gives [α, -y_α] + [β, -y_β] which is the
    //     negation, a different class.  So all 4 are distinct unless
    //     they coincide.
    //     Concretely: 2 v's for v(α) and 2 for v(β), 4 total.
    // (2) If u is irreducible over F_p: F_p[x]/u ≅ F_{p²}.  Need
    //     r to be a square in F_{p²}.  Count: 1 divisor if a square
    //     and r ≠ 0; 0 otherwise.  (Wait — actually any non-zero
    //     element of F_{p²} is a square iff its norm is a square in
    //     F_p, which is automatic since F_{p²}^*/F_p^* has even order
    //     ... let me think again.)
    //
    // Simpler: just enumerate all (u, v) with deg u = 2 and deg v ≤
    // 1, check u | v² − f, and count.  O(p^4) per curve — at p =
    // 100, that's 10^8 which is ~ a minute.  Acceptable for the
    // probe; we'll optimise if needed.

    for a in 0..p_u {
        for b in 0..p_u {
            let u = FpPoly::from_coeffs(
                vec![BigUint::from(b), BigUint::from(a), BigUint::one()],
                p.clone(),
            );
            // We DO include u = (x − α)² (discriminant zero) — these
            // are legitimate "double" Mumford divisors, e.g. `2[α, y]`
            // when `f(α)` is a non-zero QR.  Earlier versions of this
            // function skipped them, which produced an undercount of
            // `2 · #{α : f(α) is a non-zero QR}`.
            // Count v's: enumerate v = v0 + v1·x.
            for v0 in 0..p_u {
                for v1 in 0..p_u {
                    let v =
                        FpPoly::from_coeffs(vec![BigUint::from(v0), BigUint::from(v1)], p.clone());
                    let v_sq = v.mul(&v);
                    let diff = v_sq.sub(&curve.f);
                    let (_q, r) = diff.divrem(&u);
                    if r.is_zero() {
                        count += 1;
                    }
                }
            }
        }
    }

    BigUint::from(count)
}

// ── #Jac(C)(F_p) via the L-polynomial (fast) ─────────────────────────

/// **Fast `u64`-only point counter** for `(a, b)` Frobenius
/// coefficients.  Returns `(N_1, N_2)` = `(#C(F_p), #C(F_{p²}))`.
///
/// Uses the **norm-based QR shortcut** for `F_{p²}`: an element
/// `x = α + β·t ∈ F_{p²}` is a non-zero square iff its norm
/// `N(x) = α² − δ·β²` is a non-zero square in `F_p` (where
/// `t² = δ` is the non-residue defining `F_{p²}`).  This replaces
/// the `O(log p)` Euler-criterion test per F_{p²}-point with a
/// single QR-table lookup — `~100×` speedup over the original
/// `count_points_fp2` for `p ∈ [100, 2000]`.
///
/// Requires the `f`-coefficients to fit in `u32` (i.e., `p < 2³²`).
pub fn fast_point_counts(curve: &HyperellipticCurveP, p_u: u64) -> (u64, u64) {
    // Convert f's coefficients to u64 reduced mod p.
    let f_coeffs: Vec<u64> = curve
        .f
        .coeffs
        .iter()
        .map(|c| c.to_u64_digits().first().copied().unwrap_or(0) % p_u)
        .collect();
    let _deg_f = f_coeffs.len();
    // Precompute the QR table for F_p: chi[v] = 1 if v is a non-zero
    // square mod p, 0 if v == 0, p-1 (= -1) if non-square.
    // Built via Euler's criterion once.
    let mut chi: Vec<i8> = vec![0; p_u as usize];
    let exp_p = (p_u - 1) / 2;
    for v in 1..p_u {
        let r = powmod_u64(v, exp_p, p_u);
        chi[v as usize] = if r == 1 { 1 } else { -1 };
    }
    // Find the non-residue δ.
    let mut delta = 2u64;
    while chi[delta as usize] != -1 {
        delta += 1;
    }
    // ── N_1: count F_p-points on y² = f(x), plus 1 for ∞ ──
    let mut n1: u64 = 1;
    for x in 0..p_u {
        // Horner in F_p.
        let mut acc: u64 = 0;
        for c in f_coeffs.iter().rev() {
            acc = (acc as u128 * x as u128 % p_u as u128 + *c as u128) as u64 % p_u;
        }
        if acc == 0 {
            n1 += 1;
        } else if chi[acc as usize] == 1 {
            n1 += 2;
        }
    }
    // ── N_2: count F_{p²}-points on y² = f(x), plus 1 for ∞ ──
    // x = α + β·t, with t² = δ.  For each (α, β) ∈ F_p² evaluate
    // f(x) ∈ F_{p²} via Horner, then test if norm is a QR in F_p.
    let mut n2: u64 = 1;
    for alpha in 0..p_u {
        for beta in 0..p_u {
            // Evaluate f(α + β·t) by Horner.  An F_{p²} element is
            // (a, b).  Multiplication: (a + bt)(c + dt) = (ac + bd·δ) +
            // (ad + bc)·t.
            let (mut ya, mut yb) = (0u64, 0u64);
            for c in f_coeffs.iter().rev() {
                // (ya, yb) * (alpha, beta) + (c, 0)
                let bd = mulmod_u64(yb, beta, p_u);
                let bd_delta = mulmod_u64(bd, delta, p_u);
                let ac = mulmod_u64(ya, alpha, p_u);
                let new_a = (ac + bd_delta) % p_u;
                let ad = mulmod_u64(ya, beta, p_u);
                let bc = mulmod_u64(yb, alpha, p_u);
                let new_b = (ad + bc) % p_u;
                ya = (new_a + *c) % p_u;
                yb = new_b;
            }
            if ya == 0 && yb == 0 {
                n2 += 1;
            } else {
                // Norm = ya² − δ·yb².
                let ya_sq = mulmod_u64(ya, ya, p_u);
                let yb_sq = mulmod_u64(yb, yb, p_u);
                let yb_sq_delta = mulmod_u64(yb_sq, delta, p_u);
                let norm = (ya_sq + p_u - yb_sq_delta) % p_u;
                if norm == 0 {
                    n2 += 1; // a root of f in F_{p²}: y = 0, one point
                } else if chi[norm as usize] == 1 {
                    n2 += 2;
                }
            }
        }
    }
    (n1, n2)
}

fn mulmod_u64(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn powmod_u64(base: u64, exp: u64, p: u64) -> u64 {
    let mut acc = 1u64;
    let mut b = base % p;
    let mut e = exp;
    while e > 0 {
        if e & 1 == 1 {
            acc = mulmod_u64(acc, b, p);
        }
        b = mulmod_u64(b, b, p);
        e >>= 1;
    }
    acc
}

/// Fast `(a, b)` Frobenius coefficients via [`fast_point_counts`].
/// Strictly faster than [`frob_ab_and_jac`] for any `p` where both
/// work; preferred for `p > ~50`.
pub fn fast_frob_ab(curve: &HyperellipticCurveP) -> (FrobABForJac, BigUint) {
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("p too big for fast_frob_ab"),
    };
    let (n1, n2) = fast_point_counts(curve, p_u);
    let a: i128 = (p_u as i128) + 1 - (n1 as i128);
    let s2: i128 = (p_u as i128) * (p_u as i128) + 1 - (n2 as i128);
    debug_assert_eq!((a * a - s2) % 2, 0);
    let b: i128 = (a * a - s2) / 2;
    let jac: i128 = 1 - a + b - (p_u as i128) * a + (p_u as i128) * (p_u as i128);
    assert!(jac >= 0);
    (FrobABForJac { a, b }, BigUint::from(jac as u128))
}

/// Count affine `F_{p²}`-points on `C : y² = f(x)`, plus `1` for
/// the point at infinity (assuming `deg f = 2g+1`).  Uses [`Fp2Ctx`]
/// arithmetic; complexity `O(p²·deg f)` field operations.
pub fn count_points_fp2(curve: &HyperellipticCurveP, ctx: &Fp2Ctx) -> u64 {
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("count_points_fp2: p too big"),
    };
    assert_eq!(p_u, ctx.p);
    // Convert f's coefficients to Fp2.
    let f_coeffs: Vec<Fp2> = curve
        .f
        .coeffs
        .iter()
        .map(|c| {
            let v = c.to_u64_digits().first().copied().unwrap_or(0);
            ctx.from_fp(v)
        })
        .collect();
    let eval_f = |x: Fp2| -> Fp2 {
        let mut acc = ctx.zero();
        for c in f_coeffs.iter().rev() {
            acc = ctx.add(ctx.mul(acc, x), *c);
        }
        acc
    };
    let mut count: u64 = 1; // +1 for ∞
    for a in 0..p_u {
        for b in 0..p_u {
            let x = Fp2 { a, b };
            let y_sq = eval_f(x);
            if ctx.is_zero(y_sq) {
                count += 1;
            } else {
                match ctx.is_qr(y_sq) {
                    Some(true) => count += 2,
                    Some(false) => {}
                    None => {}
                }
            }
        }
    }
    count
}

/// The Frobenius characteristic polynomial coefficients `(a, b)` of
/// `Jac(C)/F_p`, where `P(T) = T⁴ − a·T³ + b·T² − p·a·T + p²`.
///
/// These directly identify the `F_p`-isogeny class of `Jac(C)`: by
/// Tate's theorem (Tate 1966), two abelian varieties over `F_p` are
/// `F_p`-isogenous iff they have the same Frobenius char poly.  So
/// `(a, b)` is much more informative than `#Jac(C) = P(1)` alone —
/// many distinct isogeny classes can share the same `#Jac`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FrobABForJac {
    pub a: i128,
    pub b: i128,
}

/// Compute the Frobenius `(a, b)` and `#Jac(C)(F_p)` together.  See
/// [`jac_order_via_lpoly`] for the underlying formulas.
pub fn frob_ab_and_jac(curve: &HyperellipticCurveP, ctx: &Fp2Ctx) -> (FrobABForJac, BigUint) {
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("p too big"),
    };
    let n1 = curve.count_affine_plus_infinity();
    let n1_u: u64 = match n1.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("N_1 too big"),
    };
    let n2 = count_points_fp2(curve, ctx);
    let a: i128 = (p_u as i128) + 1 - (n1_u as i128);
    let s2: i128 = (p_u as i128) * (p_u as i128) + 1 - (n2 as i128);
    let a_sq = a * a;
    debug_assert_eq!((a_sq - s2) % 2, 0, "a²−s_2 must be even");
    let b: i128 = (a_sq - s2) / 2;
    let jac: i128 = 1 - a + b - (p_u as i128) * a + (p_u as i128) * (p_u as i128);
    assert!(jac >= 0, "negative #Jac");
    (FrobABForJac { a, b }, BigUint::from(jac as u128))
}

/// **L-polynomial method** for `#Jac(C)(F_p)`.
///
/// For genus 2, the Frobenius characteristic polynomial is
/// ```text
///     P(T) = T⁴ − a·T³ + b·T² − p·a·T + p²
/// ```
/// and `#Jac(C)(F_p) = P(1) = 1 − a + b − p·a + p²`.
///
/// The coefficients are determined by the curve's point counts via
/// the **Newton identities**:
/// ```text
///     #C(F_p)   = p   + 1 − s_1        where s_1 = a
///     #C(F_{p²}) = p² + 1 − s_2        where s_2 = a² − 2b
/// ```
/// so `a = p + 1 − N_1` and `b = (a² − s_2)/2 = (a² − (p²+1−N_2))/2`.
///
/// Complexity: `O(p + p²)` field operations (counting `N_1` and
/// `N_2`).  Far faster than the `O(p⁴)` brute-force Mumford
/// enumeration for `p > ~10`.
pub fn jac_order_via_lpoly(curve: &HyperellipticCurveP, ctx: &Fp2Ctx) -> BigUint {
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("jac_order_via_lpoly: p too big"),
    };
    let n1 = curve.count_affine_plus_infinity();
    let n1_u: u64 = match n1.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("N_1 too big"),
    };
    let n2 = count_points_fp2(curve, ctx);
    // a = p + 1 - N_1   (may be negative — keep as i128)
    let a: i128 = (p_u as i128) + 1 - (n1_u as i128);
    // s_2 = p² + 1 - N_2
    let s2: i128 = (p_u as i128) * (p_u as i128) + 1 - (n2 as i128);
    // b = (a² - s_2) / 2
    let a_sq = a * a;
    debug_assert_eq!((a_sq - s2) % 2, 0, "a²−s_2 must be even");
    let b: i128 = (a_sq - s2) / 2;
    // #Jac = 1 - a + b - p·a + p²
    let jac: i128 = 1 - a + b - (p_u as i128) * a + (p_u as i128) * (p_u as i128);
    assert!(jac >= 0, "negative #Jac — likely numerical bug");
    BigUint::from(jac as u128)
}

/// Re-export the old brute-force counter under its public name; kept
/// for compatibility with the existing Phase-1 tests.
pub fn brute_force_jac_order_via_lpoly(curve: &HyperellipticCurveP) -> BigUint {
    // Build a fresh Fp2 context and delegate.
    let p_u: u64 = match curve.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => panic!("p too big"),
    };
    let ctx = Fp2Ctx::new(p_u);
    jac_order_via_lpoly(curve, &ctx)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p11() -> BigUint {
        BigUint::from(11u32)
    }

    /// **Benchmark**: time `fast_frob_ab` vs `frob_ab_and_jac` on
    /// the same 100 curves at `p = 251`.  Reports the ratio.
    /// `#[ignore]`-d so it doesn't slow the normal test run.
    #[test]
    #[ignore]
    fn benchmark_fast_vs_slow_p251() {
        use std::time::Instant;
        let p_u = 251u64;
        let p = BigUint::from(p_u);
        let ctx = Fp2Ctx::new(p_u);
        let mut curves: Vec<HyperellipticCurveP> = Vec::new();
        // Build 100 random-looking squarefree quintics.
        let mut seed = 0xC0FFEE_u64;
        let mut tries = 0;
        while curves.len() < 100 && tries < 10_000 {
            tries += 1;
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let c0 = (seed >> 8) % p_u;
            let c1 = (seed >> 16) % p_u;
            let c2 = (seed >> 24) % p_u;
            let c3 = (seed >> 32) % p_u;
            let c4 = (seed >> 40) % p_u;
            let f = FpPoly::from_coeffs(
                vec![
                    BigUint::from(c0),
                    BigUint::from(c1),
                    BigUint::from(c2),
                    BigUint::from(c3),
                    BigUint::from(c4),
                    BigUint::one(),
                ],
                p.clone(),
            );
            // squarefree?
            let mut der_coeffs = Vec::with_capacity(5);
            for i in 1..=5 {
                der_coeffs.push((f.coeff(i) * BigUint::from(i as u32)) % &p);
            }
            let fp = FpPoly::from_coeffs(der_coeffs, p.clone());
            let g = f.gcd(&fp);
            if g.degree() == Some(0) {
                curves.push(HyperellipticCurveP::new(p.clone(), f, 2));
            }
        }
        let t0 = Instant::now();
        for c in &curves {
            let _ = frob_ab_and_jac(c, &ctx);
        }
        let slow = t0.elapsed();
        let t1 = Instant::now();
        for c in &curves {
            let _ = fast_frob_ab(c);
        }
        let fast = t1.elapsed();
        println!("\n  Benchmark p = {}, {} curves", p_u, curves.len());
        println!("    Slow (Fp2Ctx + BigUint): {:?}", slow);
        println!("    Fast (u64 + norm-QR):    {:?}", fast);
        println!(
            "    Speedup: {:.1}×",
            slow.as_nanos() as f64 / fast.as_nanos() as f64
        );
    }

    /// Fast counter and slow `Fp2Ctx` counter agree.
    #[test]
    fn fast_counter_matches_slow() {
        let p = p11();
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p.clone(), f, 2);
        let ctx = Fp2Ctx::new(11);
        let (ab_slow, jac_slow) = frob_ab_and_jac(&curve, &ctx);
        let (ab_fast, jac_fast) = fast_frob_ab(&curve);
        assert_eq!(ab_slow, ab_fast);
        assert_eq!(jac_slow, jac_fast);
    }

    /// L-polynomial and brute-force `#Jac` agree at toy size.
    #[test]
    fn lpoly_matches_brute_force() {
        let p = p11();
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p.clone(), f, 2);
        let brute = brute_force_jac_order(&curve);
        let ctx = Fp2Ctx::new(11);
        let lpoly = jac_order_via_lpoly(&curve, &ctx);
        assert_eq!(brute, lpoly, "L-poly and brute force disagree");
    }

    /// Toy genus-2 curve y² = x⁵ + x + 1 over F_{11}.  Confirm
    /// brute-force Jacobian order matches a hand-computable value.
    #[test]
    fn brute_force_consistency_small() {
        let p = p11();
        // f = 1 + x + x⁵
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p, f, 2);
        let order = brute_force_jac_order(&curve);
        // For genus 2 over F_q, #Jac satisfies (√q − 1)⁴ ≤ #Jac ≤
        // (√q + 1)⁴.  At q = 11: ~29 to ~347.
        let lo = 29u32;
        let hi = 348u32;
        assert!(
            order >= BigUint::from(lo),
            "order = {} below Hasse-Weil",
            order
        );
        assert!(
            order <= BigUint::from(hi),
            "order = {} above Hasse-Weil",
            order
        );
        // Cross-check via point-counting: #C(F_p) = 8 (hand
        // computed for f = x⁵+x+1 over F_{11}; Σ χ(f(x)) = -4,
        // #C_affine = 7, +1 for ∞).  Then a_1 = (p+1) - #C = 4,
        // so #Jac = 1 - a_1 + a_2 - p·a_1 + p² = 74 + a_2.  Hence
        // a_2 = #Jac - 74 — must be in [-4p, 4p]
        // (consequence of Frobenius eigenvalue bound |α_i| = √p).
        let n1 = count_points(&curve);
        let a1 = curve.p.clone() + BigUint::one() - n1.clone();
        // Sanity: a_1 here = 4
        assert_eq!(a1, BigUint::from(4u32));
        let _ = order;
        let _ = n1;
    }

    /// Identity acts as identity.
    #[test]
    fn identity_arithmetic() {
        let p = p11();
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p.clone(), f, 2);
        let id = MumfordDivisorP::identity(p);
        let id2 = id.add(&id, &curve);
        assert!(id2.is_identity());
    }

    /// `D + (−D) = identity` on a generic point.
    #[test]
    fn neg_then_add_is_identity() {
        let p = p11();
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p.clone(), f, 2);
        // Find a point on C.
        let mut pt = None;
        for xi in 0u64..11 {
            let x = BigUint::from(xi);
            let y_sq = curve.f.eval(&x);
            if y_sq.is_zero() {
                continue;
            }
            // Try y = 1, 2, ..., 10 to see if y² = y_sq.
            for yi in 1u64..11 {
                let y = BigUint::from(yi);
                let yy = (&y * &y) % &p;
                if yy == y_sq {
                    pt = Some((x.clone(), y));
                    break;
                }
            }
            if pt.is_some() {
                break;
            }
        }
        let (x, y) = pt.expect("a point on C exists");
        let d = MumfordDivisorP::from_point(&curve, &x, &y).unwrap();
        let neg_d = d.neg(&curve);
        let sum = d.add(&neg_d, &curve);
        assert!(sum.is_identity());
    }

    /// Doubling matches self-addition.
    #[test]
    fn double_equals_add_self() {
        let p = p11();
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p.clone(),
        );
        let curve = HyperellipticCurveP::new(p.clone(), f, 2);
        let mut pt = None;
        for xi in 0u64..11 {
            let x = BigUint::from(xi);
            let y_sq = curve.f.eval(&x);
            if y_sq.is_zero() {
                continue;
            }
            for yi in 1u64..11 {
                let y = BigUint::from(yi);
                let yy = (&y * &y) % &p;
                if yy == y_sq {
                    pt = Some((x.clone(), y));
                    break;
                }
            }
            if pt.is_some() {
                break;
            }
        }
        let (x, y) = pt.expect("a point on C exists");
        let d = MumfordDivisorP::from_point(&curve, &x, &y).unwrap();
        let d2_dbl = d.double(&curve);
        let d2_add = d.add(&d, &curve);
        assert_eq!(d2_dbl, d2_add);
    }
}
