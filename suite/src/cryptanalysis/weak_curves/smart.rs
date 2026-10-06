//! Smart's attack on anomalous curves (`#E(F_p) = p`), and a CM
//! generator for anomalous curves of any size.
//!
//! # The attack (Smart 1999; Satoh–Araki 1998; Semaev 1998)
//!
//! Let `E/F_p` have exactly `p` points, `P` a generator and `Q = d·P`.
//! Choose any lift `Ê/Z_p` of `E` and lifts `P̂, Q̂ ∈ Ê(Z_p)`.  Because
//! `[p]` kills `E(F_p)`, the points `[p]P̂` and `[p]Q̂` reduce to the
//! identity: they lie in the kernel of reduction `Ê₁(Q_p)`, which the
//! formal logarithm maps isomorphically onto `pZ_p`.  Reduction is a
//! homomorphism, so `Q̂ − d·P̂ ∈ Ê₁` and
//!
//! ```text
//! [p]Q̂ − d·[p]P̂ = [p](Q̂ − dP̂) ∈ [p]Ê₁ = Ê₂,
//! ```
//!
//! i.e. the two points agree to `p²`-adic precision after scaling by
//! `d`.  With `ψ(R) = log_Ê(R)/p mod p`,
//! `d ≡ ψ([p]Q̂)/ψ([p]P̂) (mod p)`.  For a short Weierstrass model the
//! formal logarithm is `z + (2a/5)z⁵ + …` in the parameter
//! `z = −x/y`, so modulo `p²` it is just `z` once `v_p(z) ≥ 1` and
//! `p ≥ 5` — the whole attack is one scalar multiplication by `p` in
//! `E(Z/p²Z)` per point.
//!
//! The computation needs precision `p²` only.  It is carried out in
//! homogeneous projective coordinates `(X:Y:Z)` over `Z/p²Z`, which
//! never divide, so the final point — whose affine coordinates have
//! negative valuation — is represented exactly with `Y` a unit and
//! `z = −X/Y`.  In the double-and-add chain for `[p]P̂` every
//! intermediate multiple `jP̂` (`0 < j < p`) reduces to a non-identity,
//! non-2-torsion point, and the two summands of an addition are
//! congruent modulo `p` (up to sign) only in the final addition, where
//! the chord formula is still exact.
//!
//! **Degenerate lifts.** If `ψ([p]P̂) ≡ 0 (mod p)` the lift is useless —
//! this is what happens for the canonical lift, where `[p]` maps
//! `Ê(Z_p)` into `Ê₂` (Smart's paper discusses the case; the fix is the
//! random lift).  This implementation lifts the curve *randomly*: `a`
//! and the coordinates of `P` get random multiples of `p` added and `b`
//! is solved for so that `P̂` lies on the lifted curve; `Q̂` is then a
//! Hensel lift.  A degenerate lift occurs with probability about `1/p`
//! and is retried with fresh randomness; the answer is always checked
//! by scalar multiplication.
//!
//! # Generating anomalous curves by CM
//!
//! For `D ∈ {11, 19, 43, 67, 163}` the order `O_{−D}` has class number
//! one and a single rational `j`-invariant.  If `4p = 1 + D·v²` then a
//! curve over `F_p` with that `j` has trace `±1`, i.e. order `p` or
//! `p + 2`; one of it and its quadratic twist is anomalous.  Picking
//! `v` of the right size until `p` is prime takes a few hundred tries
//! at 256 bits.  [`anomalous_curve_cm`] does this and certifies the
//! choice by checking `[p]R = O` for a point `R ≠ O` (which forces
//! `#E = p` since the only other candidate, `p + 2`, is coprime to `p`).
//!
//! References: N. P. Smart, *The discrete logarithm problem on elliptic
//! curves of trace one*, J. Cryptology 12 (1999); T. Satoh and K. Araki,
//! *Fermat quotients and the polynomial time discrete log algorithm for
//! anomalous elliptic curves*, Comment. Math. Univ. St. Pauli 47
//! (1998); I. A. Semaev, *Evaluation of discrete logarithms in a group
//! of p-torsion points of an elliptic curve in characteristic p*,
//! Math. Comp. 67 (1998); J. H. Silverman, *The Arithmetic of Elliptic
//! Curves*, ch. IV and VII; A. Atkin and F. Morain, *Elliptic curves and
//! primality proving*, Math. Comp. 61 (1993) for CM construction.

use super::arith::{is_probable_prime, legendre, sub_mod, AffinePoint, Ec};
use super::WeakCurveError;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::Rng;
use serde::Serialize;
use std::time::Instant;

/// Options for [`smart_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct SmartOptions {
    /// Random lifts to try before giving up (a lift fails with
    /// probability about `1/p`).
    pub max_lifts: usize,
    /// RNG seed for the random lifts.
    pub seed: u64,
}

impl Default for SmartOptions {
    fn default() -> Self {
        SmartOptions {
            max_lifts: 16,
            seed: 0x005a_4a27,
        }
    }
}

/// Result of [`smart_attack`].
#[derive(Clone, Debug, Serialize)]
pub struct SmartOutcome {
    /// Recovered `d` with `Q = d·G`, verified by scalar multiplication.
    #[serde(serialize_with = "super::ser::big")]
    pub scalar: BigUint,
    /// Bit length of `p`.
    pub p_bits: u64,
    /// Lifts tried (including the successful one).
    pub lifts_tried: usize,
    /// Lifts rejected as degenerate (`ψ([p]P̂) ≡ 0`) or failing
    /// verification.
    pub degenerate_lifts: usize,
    /// Wall-clock milliseconds.
    pub elapsed_ms: f64,
}

// ── Homogeneous projective arithmetic over Z/p²Z ─────────────────────────

#[derive(Clone, Debug)]
struct P2 {
    x: BigUint,
    y: BigUint,
    z: BigUint,
}

struct Ring {
    m: BigUint,
}

impl Ring {
    fn mul(&self, a: &BigUint, b: &BigUint) -> BigUint {
        (a * b) % &self.m
    }
    fn sub(&self, a: &BigUint, b: &BigUint) -> BigUint {
        sub_mod(a, b, &self.m)
    }
    fn small(&self, c: u32, a: &BigUint) -> BigUint {
        (a * c) % &self.m
    }

    /// Doubling (Cohen–Miyaji–Ono 1998, `dbl-1998-cmo-2`).
    fn double(&self, a4: &BigUint, pt: &P2) -> P2 {
        let (x, y, z) = (&pt.x, &pt.y, &pt.z);
        let w = (self.mul(a4, &self.mul(z, z)) + self.small(3, &self.mul(x, x))) % &self.m;
        let s = self.mul(y, z);
        let b = self.mul(&self.mul(x, y), &s);
        let h = self.sub(&self.mul(&w, &w), &self.small(8, &b));
        let x3 = self.small(2, &self.mul(&h, &s));
        let y3 = self.sub(
            &self.mul(&w, &self.sub(&self.small(4, &b), &h)),
            &self.small(8, &self.mul(&self.mul(y, y), &self.mul(&s, &s))),
        );
        let z3 = self.small(8, &self.mul(&s, &self.mul(&s, &s)));
        P2 {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Addition (Cohen–Miyaji–Ono 1998, `add-1998-cmo-2`).
    fn add(&self, p1: &P2, p2: &P2) -> P2 {
        let u = self.sub(&self.mul(&p2.y, &p1.z), &self.mul(&p1.y, &p2.z));
        let v = self.sub(&self.mul(&p2.x, &p1.z), &self.mul(&p1.x, &p2.z));
        let z1z2 = self.mul(&p1.z, &p2.z);
        let v2 = self.mul(&v, &v);
        let v3 = self.mul(&v2, &v);
        let v2x1z2 = self.mul(&v2, &self.mul(&p1.x, &p2.z));
        let a = self.sub(
            &self.sub(&self.mul(&self.mul(&u, &u), &z1z2), &v3),
            &self.small(2, &v2x1z2),
        );
        let x3 = self.mul(&v, &a);
        let y3 = self.sub(
            &self.mul(&u, &self.sub(&v2x1z2, &a)),
            &self.mul(&v3, &self.mul(&p1.y, &p2.z)),
        );
        let z3 = self.mul(&v3, &z1z2);
        P2 {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// `[k]P` by right-to-left double-and-add (see the module docs for
    /// why no exceptional case arises when `k = p`).
    fn mul_scalar(&self, a4: &BigUint, pt: &P2, k: &BigUint) -> Option<P2> {
        let mut acc: Option<P2> = None;
        let mut addend = pt.clone();
        let top = k.bits();
        for i in 0..top {
            if k.bit(i) {
                acc = Some(match acc {
                    None => addend.clone(),
                    Some(r) => self.add(&r, &addend),
                });
            }
            if i + 1 < top {
                addend = self.double(a4, &addend);
            }
        }
        acc
    }
}

/// `ψ([p]R̂) = (−X/Y)/p mod p` for the projective `[p]R̂`, or `None` if
/// the lift is degenerate.
fn psi(ring: &Ring, p: &BigUint, a4: &BigUint, r: &P2) -> Option<BigUint> {
    let pr = ring.mul_scalar(a4, r, p)?;
    let y_mod_p = &pr.y % p;
    if y_mod_p.is_zero() || !(&pr.z % p).is_zero() || !(&pr.x % p).is_zero() {
        return None; // not in the formal group: order is not p
    }
    let y_inv = pr.y.modinv(&ring.m)?;
    let t = ring.sub(&BigUint::zero(), &ring.mul(&pr.x, &y_inv));
    let u = (t / p) % p;
    if u.is_zero() {
        None
    } else {
        Some(u)
    }
}

/// One random lift.  `Ok(Some(d))` on a non-degenerate lift (the caller
/// verifies), `Ok(None)` on a degenerate one.
fn smart_one_lift(
    ec: &Ec,
    g: (&BigUint, &BigUint),
    q: (&BigUint, &BigUint),
    rng: &mut StdRng,
) -> Result<Option<BigUint>, WeakCurveError> {
    let p = &ec.p;
    let m = p * p;
    let ring = Ring { m: m.clone() };
    let lift = |v: &BigUint, rng: &mut StdRng| (v + p * rng.gen_biguint_below(p)) % &m;
    // Random lift of a, and of G's coordinates; solve for b̂.
    let a_hat = lift(&ec.a, rng);
    let xg = lift(g.0, rng);
    let yg = lift(g.1, rng);
    let rhs_no_b = |x: &BigUint| (ring.mul(&ring.mul(x, x), x) + ring.mul(&a_hat, x)) % &m;
    let b_hat = ring.sub(&ring.mul(&yg, &yg), &rhs_no_b(&xg));
    debug_assert_eq!(&b_hat % p, ec.b);
    // Hensel-lift Q: keep a random x̂, one Newton step on ŷ.
    let xq = lift(q.0, rng);
    let rhs_q = (rhs_no_b(&xq) + &b_hat) % &m;
    let yq0 = q.1 % p;
    let two_y_inv = ((&yq0 << 1u32) % p)
        .modinv(p)
        .ok_or_else(|| WeakCurveError::InvalidInput("Q has y = 0 (2-torsion)".into()))?;
    // ŷ = y − (y² − rhs)/(2y); the correction is a multiple of p, so the
    // inverse of 2y mod p suffices.
    let f = ring.sub(&ring.mul(&yq0, &yq0), &rhs_q);
    let corr = ((&f / p) * &two_y_inv) % p * p;
    let yq = ring.sub(&yq0, &corr);
    debug_assert_eq!(ring.mul(&yq, &yq), rhs_q);
    let one = BigUint::one();
    let gp = P2 {
        x: xg,
        y: yg,
        z: one.clone(),
    };
    let qp = P2 {
        x: xq,
        y: yq,
        z: one,
    };
    let Some(psi_g) = psi(&ring, p, &a_hat, &gp) else {
        return Ok(None);
    };
    let psi_q = match psi(&ring, p, &a_hat, &qp) {
        Some(v) => v,
        // ψ([p]Q̂) ≡ 0 means d ≡ 0 — but Q ≠ O here, so this lift is bad.
        None => return Ok(None),
    };
    let inv = psi_g.modinv(p).expect("ψ(P) is a unit");
    Ok(Some((psi_q * inv) % p))
}

/// Core of Smart's attack over the local curve type; the result is
/// verified with the local arithmetic.  Returns `(d, lifts tried,
/// degenerate lifts)`.
pub(crate) fn smart_core(
    ec: &Ec,
    g: &AffinePoint,
    q: &AffinePoint,
    opts: &SmartOptions,
) -> Result<(BigUint, usize, usize), WeakCurveError> {
    let p = &ec.p;
    if p < &BigUint::from(5u32) || !is_probable_prime(p) {
        return Err(WeakCurveError::InvalidInput(
            "Smart's attack needs a prime p ≥ 5".into(),
        ));
    }
    if ec.discriminant().is_zero() {
        return Err(WeakCurveError::NotApplicable(
            "curve is singular; use the singular-curve attack".into(),
        ));
    }
    if !ec.is_on_curve(g) || !ec.is_on_curve(q) {
        return Err(WeakCurveError::InvalidInput(
            "point not on the curve".into(),
        ));
    }
    let AffinePoint::Affine(gx, gy) = g else {
        return Err(WeakCurveError::InvalidInput("G is the identity".into()));
    };
    if ec.mul(g, p) != AffinePoint::Infinity {
        return Err(WeakCurveError::NotApplicable(
            "ord(G) ≠ p: the curve is not anomalous".into(),
        ));
    }
    let (qx, qy) = match q {
        AffinePoint::Infinity => return Ok((BigUint::zero(), 0, 0)),
        AffinePoint::Affine(x, y) => (x, y),
    };
    let mut rng = super::arith::seeded_rng(opts.seed);
    let mut degenerate = 0usize;
    for attempt in 1..=opts.max_lifts.max(1) {
        match smart_one_lift(ec, (gx, gy), (qx, qy), &mut rng)? {
            Some(d) if ec.mul(g, &d) == *q => return Ok((d, attempt, degenerate)),
            _ => degenerate += 1,
        }
    }
    Err(WeakCurveError::SolverFailed(format!(
        "all {} random lifts were degenerate or failed verification",
        opts.max_lifts
    )))
}

/// **Smart's attack**: recover `d` with `Q = d·G` on an anomalous curve
/// (`ord(G) = p`, hence `#E(F_p) = p`).  Polynomial time: two scalar
/// multiplications by `p` over `Z/p²Z` per lift.  The scalar is verified
/// with the crate's [`Point::scalar_mul`] before it is returned.
pub fn smart_attack(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    opts: &SmartOptions,
) -> Result<SmartOutcome, WeakCurveError> {
    let t0 = Instant::now();
    let ec = Ec::from_params(curve);
    let (d, lifts, degenerate) = smart_core(&ec, &ec.import(g), &ec.import(q), opts)?;
    if g.scalar_mul(&d, &curve.a_fe()) != *q {
        return Err(WeakCurveError::VerificationFailed);
    }
    Ok(SmartOutcome {
        scalar: d,
        p_bits: curve.p.bits(),
        lifts_tried: lifts,
        degenerate_lifts: degenerate,
        elapsed_ms: t0.elapsed().as_secs_f64() * 1e3,
    })
}

// ── CM construction of anomalous curves ──────────────────────────────────

/// The class-number-one discriminants `−D` with `D ≡ 3 (mod 4)`, `D > 3`,
/// and their `j`-invariants.
pub const CLASS_NUMBER_ONE_J: [(u32, i64); 5] = [
    (11, -32_768),
    (19, -884_736),
    (43, -884_736_000),
    (67, -147_197_952_000),
    (163, -262_537_412_640_768_000),
];

/// An anomalous curve `y² = x³ + a·x + b` over `F_p` with `#E(F_p) = p`,
/// and a generator.
#[derive(Clone, Debug, Serialize)]
pub struct AnomalousCurve {
    /// `D` in the CM discriminant `−D`.
    pub discriminant: u32,
    /// Field prime, `4p = 1 + D·v²`.
    #[serde(serialize_with = "super::ser::big")]
    pub p: BigUint,
    /// Coefficient `a`.
    #[serde(serialize_with = "super::ser::big")]
    pub a: BigUint,
    /// Coefficient `b`.
    #[serde(serialize_with = "super::ser::big")]
    pub b: BigUint,
    /// Generator x-coordinate.
    #[serde(serialize_with = "super::ser::big")]
    pub gx: BigUint,
    /// Generator y-coordinate.
    #[serde(serialize_with = "super::ser::big")]
    pub gy: BigUint,
}

impl AnomalousCurve {
    /// As crate curve parameters (`n = p`, `h = 1`).
    pub fn to_curve_params(&self) -> CurveParams {
        CurveParams {
            name: "cm-anomalous",
            p: self.p.clone(),
            a: self.a.clone(),
            b: self.b.clone(),
            gx: self.gx.clone(),
            gy: self.gy.clone(),
            n: self.p.clone(),
            h: 1,
        }
    }
}

/// Construct an anomalous curve over a `bits`-bit prime by the CM
/// method with discriminant `−d`, `d ∈ {11, 19, 43, 67, 163}`.
pub fn anomalous_curve_cm<R: Rng + ?Sized>(
    bits: u64,
    d: u32,
    rng: &mut R,
) -> Result<AnomalousCurve, WeakCurveError> {
    let j = CLASS_NUMBER_ONE_J
        .iter()
        .find(|(dd, _)| *dd == d)
        .map(|(_, j)| *j)
        .ok_or_else(|| {
            WeakCurveError::InvalidInput(format!(
                "D = −{d} is not a supported class-number-one discriminant"
            ))
        })?;
    if bits < 16 {
        return Err(WeakCurveError::InvalidInput(
            "use at least 16 bits (smaller anomalous curves: brute-force search)".into(),
        ));
    }
    let dd = BigUint::from(d);
    // p ∈ [2^{bits−1}, 2^bits)  ⇔  D·v² ∈ [2^{bits+1} − 1, 2^{bits+2} − 1).
    let v_lo = (BigUint::one() << (bits + 1)) / &dd;
    let v_lo = v_lo.sqrt() + 1u32;
    let v_hi = ((BigUint::one() << (bits + 2)) - 1u32) / &dd;
    let v_hi = v_hi.sqrt();
    if v_lo >= v_hi {
        return Err(WeakCurveError::InvalidInput("bit size too small".into()));
    }
    for _ in 0..200_000 {
        let mut v = rng.gen_biguint_range(&v_lo, &v_hi);
        if v.is_even() {
            v += 1u32;
        }
        let four_p = &dd * &v * &v + 1u32;
        let p = &four_p >> 2u32;
        if p.bits() != bits || !is_probable_prime(&p) {
            continue;
        }
        let j_mod = sub_mod(
            &BigUint::zero(),
            &(BigUint::from(j.unsigned_abs()) % &p),
            &p,
        );
        let k = sub_mod(&(BigUint::from(1728u32) % &p), &j_mod, &p);
        if j_mod.is_zero() || k.is_zero() {
            continue;
        }
        let k_inv = k.modinv(&p).expect("unit");
        let a = (&j_mod * 3u32 % &p) * &k_inv % &p;
        let b = (&j_mod * 2u32 % &p) * &k_inv % &p;
        let ec = Ec::new(&p, &a, &b);
        if ec.discriminant().is_zero() {
            continue;
        }
        let candidates = {
            // Quadratic twist by a non-residue c: (a c², b c³).
            let mut c = BigUint::from(2u32);
            while legendre(&c, &p) != -1 {
                c += 1u32;
            }
            let c2 = &c * &c % &p;
            let c3 = &c2 * &c % &p;
            [ec.clone(), Ec::new(&p, &(&a * &c2), &(&b * &c3))]
        };
        for cand in candidates {
            let r = cand.random_point(rng);
            if cand.mul(&r, &p) == AffinePoint::Infinity {
                // #E ∈ {p, p+2} and a non-identity point is killed by p.
                let AffinePoint::Affine(gx, gy) = r else {
                    continue;
                };
                return Ok(AnomalousCurve {
                    discriminant: d,
                    p: p.clone(),
                    a: cand.a.clone(),
                    b: cand.b.clone(),
                    gx,
                    gy,
                });
            }
        }
    }
    Err(WeakCurveError::SolverFailed(
        "no CM prime found in the search budget".into(),
    ))
}

#[cfg(test)]
mod tests {
    use super::super::arith::seeded_rng;
    use super::*;
    use crate::cryptanalysis::canonical_lift::find_anomalous_curve;

    fn curve_from(ec: &Ec, g: &AffinePoint) -> CurveParams {
        let AffinePoint::Affine(gx, gy) = g else {
            panic!("identity");
        };
        CurveParams {
            name: "test-anomalous",
            p: ec.p.clone(),
            a: ec.a.clone(),
            b: ec.b.clone(),
            gx: gx.clone(),
            gy: gy.clone(),
            n: ec.p.clone(),
            h: 1,
        }
    }

    /// Every scalar on small brute-forced anomalous curves.
    #[test]
    fn smart_small_anomalous_all_scalars() {
        let mut rng = seeded_rng(11);
        for p in [11u64, 23, 43, 53] {
            let (a, b) = find_anomalous_curve(p).expect("anomalous curve exists");
            let ec = Ec::new(&BigUint::from(p), &BigUint::from(a), &BigUint::from(b));
            let g = ec.random_point(&mut rng);
            let curve = curve_from(&ec, &g);
            let gpt = curve.generator();
            for d in 0..p {
                let d = BigUint::from(d);
                let q = gpt.scalar_mul(&d, &curve.a_fe());
                let out = smart_attack(&curve, &gpt, &q, &SmartOptions::default())
                    .unwrap_or_else(|e| panic!("p={p} d={d}: {e}"));
                assert_eq!(out.scalar, d, "p = {p}");
            }
        }
    }

    /// 256-bit anomalous curves built by CM for several discriminants.
    #[test]
    fn smart_256_bit_cm_curves() {
        let mut rng = seeded_rng(256);
        for d in [11u32, 43, 163] {
            let ac = anomalous_curve_cm(256, d, &mut rng).unwrap();
            assert_eq!(ac.p.bits(), 256);
            let curve = ac.to_curve_params();
            let g = curve.generator();
            assert!(curve.is_on_curve(&g));
            let a = curve.a_fe();
            assert_eq!(g.scalar_mul(&curve.p, &a), Point::Infinity);
            let secret = rng.gen_biguint_below(&curve.p);
            let q = g.scalar_mul(&secret, &a);
            let out = smart_attack(&curve, &g, &q, &SmartOptions::default()).unwrap();
            assert_eq!(out.scalar, secret);
        }
    }

    #[test]
    fn smart_rejects_non_anomalous() {
        // y² = x³ + 2 over F_211 with a point of order 199.
        let curve = CurveParams {
            name: "non-anomalous",
            p: BigUint::from(211u32),
            a: BigUint::zero(),
            b: BigUint::from(2u32),
            gx: BigUint::from(4u32),
            gy: BigUint::from(53u32),
            n: BigUint::from(199u32),
            h: 1,
        };
        let g = curve.generator();
        let err = smart_attack(&curve, &g, &g, &SmartOptions::default()).unwrap_err();
        assert!(matches!(err, WeakCurveError::NotApplicable(_)));
    }
}
