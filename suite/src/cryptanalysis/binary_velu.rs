//! # Explicit isogenies of ordinary binary curves, and what they transport
//!
//! [`crate::cryptanalysis::koblitz_isogeny_cost`] measures the ECDLP across an
//! isogeny class by handing every member the same discrete logarithm `d`.
//! That is *what an isogeny does to the logarithm* — `φ: E → E'` of degree
//! coprime to `r` carries `Q = [d]P` to `φ(Q) = [d]φ(P)` — but it is not the
//! map.  This module computes the map, so the pullback is a computation
//! rather than an inference.
//!
//! ## The formulas, for `E: y² + xy = x³ + a₂x² + a₆`
//!
//! Vélu (1971) holds in every characteristic for a general Weierstrass
//! model.  Specialising `a₁ = 1`, `a₃ = a₄ = 0` and reducing mod 2 collapses
//! it dramatically.  For a kernel point `Q`:
//!
//! ```text
//!   g_Q^x = 3x_Q² + 2a₂x_Q + a₄ − a₁y_Q = x_Q² + y_Q
//!   g_Q^y = −2y_Q − a₁x_Q − a₃         = x_Q
//!   t_Q   = 2g_Q^x − a₁ g_Q^y          = x_Q
//!   u_Q   = (g_Q^y)²                   = x_Q²
//!   w_Q   = u_Q + t_Q x_Q = x_Q² + x_Q² = 0
//! ```
//!
//! so with `t = Σ_{Q ∈ S} x_Q` over a half-set `S` of the kernel (one point
//! per `±` pair) and `b₂ = a₁² + 4a₂ = 1`:
//!
//! ```text
//!   a₄' = a₄ − 5t      = t
//!   a₆' = a₆ − b₂t − 7w = a₆ + t
//! ```
//!
//! The codomain `y² + xy = x³ + a₂x² + tx + (a₆ + t)` is not in short form.
//! Substituting `y ↦ y + t` clears the `x` term — `(y+t)² + x(y+t) = y² + xy
//! + tx + t²` — and leaves
//!
//! ```text
//!   a₆' = a₆ + t + t²        ← [`velu_codomain`]
//! ```
//!
//! with `a₂` unchanged up to the `s² + s` freedom, hence unchanged in trace
//! class — which is the consistency check that isogenous curves share a
//! trace.
//!
//! **The abscissa map** is the part that would normally need the kernel's
//! roots.  It does not, because char 2 is kind.  Writing `h(x) = Π_{Q ∈ S}
//! (x + x_Q)` for the kernel polynomial of degree `d = (ℓ−1)/2`:
//!
//! ```text
//!   Σ 1/(x + x_Q)   = h'(x)/h(x)
//!   Σ x_Q/(x + x_Q) = d + x·h'/h                       (each term is 1 + x/(x+x_Q))
//!   Σ z_Q²          = (Σ z_Q)²                          (Frobenius is additive)
//! ```
//!
//! so with `A = (d mod 2) + x·h'(x)/h(x)`,
//!
//! ```text
//!   X = x + A + A²           ← [`velu_x_map`]
//! ```
//!
//! which is computable from `h`'s coefficients alone, over `F_{2^n}`, with no
//! extension field and no root-finding.
//!
//! ## Why this is believed
//!
//! The derivation above is checked against an **independent oracle** rather
//! than trusted: at `ℓ = 3` the codomain's `j' = 1/a₆'` must be a root of the
//! classical modular polynomial `Φ₃(X, j)`, which
//! [`crate::cryptanalysis::binary_isogeny`] tabulates.  Over `F_{2^8}` with
//! `a₆ = 1` the four `ψ₃` roots `{13, 81, 177, 236}` produce exactly the four
//! `Φ₃` roots, as a permutation, with every codomain order equal to `#E`.
//! `velu_matches_the_modular_polynomial_at_ell_3` pins that.
//!
//! ## Scope
//!
//! Only the abscissa map is computed.  That is enough to transport a DLP
//! instance — `φ(P)` is determined up to sign by `x(φ(P))`, and a sign on
//! `φ(Q)` flips the recovered logarithm to `−d`, which
//! [`transport_instance`] reports rather than hides.  A full `(X, Y)` map
//! would need Vélu's `y`-formula and is not needed here.

use std::collections::{BTreeSet, HashMap};

use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, F2mPoly, IrreduciblePoly};
use crate::cryptanalysis::ic_boundary::{
    binary_point_count, ArtinSchreier, BinaryGroup, CountedGroup, GroupOps,
};
use crate::cryptanalysis::koblitz_fast::{FastCurve, FastPoint};
use crate::cryptanalysis::semaev_decomp::Gf2;

// ── field helpers ───────────────────────────────────────────────────

/// `v` as an element of `F_{2^n}` in the polynomial basis.
pub fn elt(v: u64, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..n).filter(|i| (v >> i) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

/// The integer whose bits are the coordinates of `e`.
pub fn to_u64(e: &F2mElement) -> u64 {
    e.to_biguint().to_u64_digits().first().copied().unwrap_or(0)
}

// ── Part A: division polynomials ────────────────────────────────────

/// **The `m`-division polynomial** `ψ_m ∈ F_{2^n}[x]` of
/// `E: y² + xy = x³ + a₂x² + a₆`.
///
/// In char 2 with `a₁ = 1`, `a₃ = 0` the usual `y`-dependence disappears:
/// `ψ₂ = 2y + a₁x + a₃ = x`, a polynomial in `x` alone, so every `ψ_m` is.
/// The `b`-invariants collapse to `b₂ = 1`, `b₄ = b₆ = 0`, `b₈ = a₆`, giving
///
/// ```text
///   ψ₁ = 1,  ψ₂ = x,  ψ₃ = x⁴ + x³ + a₆,  ψ₄ = x⁶ + a₆x²
/// ```
///
/// and thereafter the standard recurrences, which hold in any
/// characteristic:
///
/// ```text
///   ψ_{2m+1} = ψ_{m+2}ψ_m³ + ψ_{m−1}ψ_{m+1}³
///   ψ_{2m}·ψ₂ = ψ_m(ψ_{m+2}ψ_{m−1}² + ψ_{m−2}ψ_{m+1}²)
/// ```
///
/// For odd `ℓ`, `deg ψ_ℓ = (ℓ² − 1)/2`, and its roots are the abscissae of
/// the `ℓ`-torsion — `(ℓ+1)` subgroups of order `ℓ`, each contributing
/// `(ℓ−1)/2` of them.
pub fn division_polynomial(a6: &F2mElement, m: u32, n: u32, irr: &IrreduciblePoly) -> F2mPoly {
    let zero = F2mElement::zero(n);
    let one = F2mElement::one(n);
    let p0 = F2mPoly::zero(n);
    let p1 = F2mPoly::from_coeffs(vec![one.clone()], n);
    let psi2 = F2mPoly::from_coeffs(vec![zero.clone(), one.clone()], n);
    // ψ₃ = x⁴ + x³ + a₆
    let psi3 = F2mPoly::from_coeffs(
        vec![
            a6.clone(),
            zero.clone(),
            zero.clone(),
            one.clone(),
            one.clone(),
        ],
        n,
    );
    // ψ₄ = ψ₂·(x⁵ + a₆x) = x⁶ + a₆x²
    let psi4 = F2mPoly::from_coeffs(
        vec![
            zero.clone(),
            zero.clone(),
            a6.clone(),
            zero.clone(),
            zero.clone(),
            zero.clone(),
            one.clone(),
        ],
        n,
    );

    match m {
        0 => return p0,
        1 => return p1,
        2 => return psi2,
        3 => return psi3,
        4 => return psi4,
        _ => {}
    }

    let mut cache: HashMap<u32, F2mPoly> = HashMap::new();
    cache.insert(0, p0);
    cache.insert(1, p1);
    cache.insert(2, psi2);
    cache.insert(3, psi3);
    cache.insert(4, psi4);
    psi_rec(m, n, irr, &mut cache)
}

fn psi_rec(m: u32, n: u32, irr: &IrreduciblePoly, cache: &mut HashMap<u32, F2mPoly>) -> F2mPoly {
    if let Some(p) = cache.get(&m) {
        return p.clone();
    }
    let out = if m % 2 == 1 {
        let k = (m - 1) / 2; // m = 2k+1
        let a = psi_rec(k + 2, n, irr, cache);
        let b = psi_rec(k, n, irr, cache);
        let c = psi_rec(k.wrapping_sub(1), n, irr, cache);
        let d = psi_rec(k + 1, n, irr, cache);
        let b3 = b.mul(&b, irr).mul(&b, irr);
        let d3 = d.mul(&d, irr).mul(&d, irr);
        a.mul(&b3, irr).add(&c.mul(&d3, irr))
    } else {
        let k = m / 2; // m = 2k
        let a = psi_rec(k + 2, n, irr, cache);
        let b = psi_rec(k - 1, n, irr, cache);
        let c = psi_rec(k - 2, n, irr, cache);
        let d = psi_rec(k + 1, n, irr, cache);
        let e = psi_rec(k, n, irr, cache);
        let b2 = b.mul(&b, irr);
        let d2 = d.mul(&d, irr);
        let inner = a.mul(&b2, irr).add(&c.mul(&d2, irr));
        let num = e.mul(&inner, irr);
        // divide by ψ₂ = x
        let psi2 = F2mPoly::from_coeffs(vec![F2mElement::zero(n), F2mElement::one(n)], n);
        let (q, r) = num.divrem(&psi2, irr);
        debug_assert!(r.is_zero(), "ψ₂ must divide the even-index numerator");
        q
    };
    cache.insert(m, out.clone());
    out
}

// ── Part B: Vélu ────────────────────────────────────────────────────

/// An explicit isogeny, named by its kernel polynomial.
#[derive(Clone, Debug)]
pub struct BinaryIsogeny {
    /// Extension degree of the base field.
    pub n: u32,
    /// `a₂` of both curves — an isogeny preserves the trace, hence the
    /// family.
    pub a2: u8,
    /// `a₆` of the domain.
    pub a6: u64,
    /// `a₆` of the codomain, from [`velu_codomain`].
    pub a6_codomain: u64,
    /// Odd degree `ℓ`.
    pub ell: u64,
    /// Monic kernel polynomial, degree `(ℓ−1)/2`.
    pub kernel: F2mPoly,
    /// `t = Σ x_Q`, the trace of the kernel's abscissae.
    pub t: u64,
}

/// **The codomain's `a₆`.**  `a₆' = a₆ + t + t²` where `t` is the sum of the
/// kernel abscissae, i.e. the coefficient of `x^{d−1}` in the monic kernel
/// polynomial of degree `d`.
pub fn velu_codomain(
    a6: &F2mElement,
    kernel: &F2mPoly,
    n: u32,
    irr: &IrreduciblePoly,
) -> F2mElement {
    let d = kernel.degree().unwrap_or(0);
    let t = if d == 0 {
        F2mElement::zero(n)
    } else {
        kernel.coeff(d - 1)
    };
    a6.add(&t).add(&t.mul(&t, irr))
}

/// **The abscissa map** `X = x + A + A²`, `A = (d mod 2) + x·h'/h`.
///
/// Returns `None` when `h(x) = 0`, i.e. `x` is a kernel abscissa and the
/// point maps to the identity.
pub fn velu_x_map(
    x: &F2mElement,
    kernel: &F2mPoly,
    n: u32,
    irr: &IrreduciblePoly,
) -> Option<F2mElement> {
    let d = kernel.degree().unwrap_or(0);
    let hv = kernel.eval(x, irr);
    if hv.is_zero() {
        return None;
    }
    let hp = derivative(kernel, n);
    let hpv = hp.eval(x, irr);
    let mut a = x.mul(&hpv, irr).mul(&hv.flt_inverse(irr)?, irr);
    if d % 2 == 1 {
        a = a.add(&F2mElement::one(n));
    }
    Some(x.add(&a).add(&a.mul(&a, irr)))
}

/// Formal derivative in char 2: only odd-index coefficients survive.
pub fn derivative(p: &F2mPoly, n: u32) -> F2mPoly {
    let deg = match p.degree() {
        Some(d) => d,
        None => return F2mPoly::zero(n),
    };
    let mut coeffs = vec![F2mElement::zero(n); deg.max(1)];
    for i in 1..=deg {
        if i % 2 == 1 {
            coeffs[i - 1] = p.coeff(i);
        }
    }
    let mut out = F2mPoly::from_coeffs(coeffs, n);
    out.trim();
    out
}

// ── Part C: kernels from rational torsion ───────────────────────────

/// A curve with fast point arithmetic and its group order.
pub struct Curve {
    pub n: u32,
    pub irr: IrreduciblePoly,
    pub gf: Gf2,
    pub ash: ArtinSchreier,
    pub a2: u8,
    pub a6: u64,
    pub fast: FastCurve,
    pub order: u64,
}

impl Curve {
    pub fn new(n: u32, irr: &IrreduciblePoly, a2: u8, a6: u64) -> Option<Self> {
        let gf = Gf2::new(irr);
        let ash = ArtinSchreier::new(&gf);
        let order = binary_point_count(&gf, &ash, a2 as u64, a6);
        let curve = BinaryCurve {
            m: n,
            irreducible: irr.clone(),
            a: elt(a2 as u64, n),
            b: elt(a6, n),
            generator: BinaryPoint::Infinity,
            order: order.into(),
            cofactor: 1u64.into(),
        };
        let fast = FastCurve::new(&curve)?;
        Some(Curve {
            n,
            irr: irr.clone(),
            gf,
            ash,
            a2,
            a6,
            fast,
            order,
        })
    }

    /// Both points with abscissa `x`, or none.
    pub fn points_with_x(&self, x: u64) -> Vec<FastPoint> {
        let f = &self.fast.field;
        if x == 0 {
            return vec![FastPoint::affine(0, f.sqr_k(self.a6, self.n - 1))];
        }
        let inv = f.inv(x);
        let c = x ^ (self.a2 as u64) ^ f.mul(self.a6, f.sqr(inv));
        match self.ash.solve(c) {
            Some(u) => {
                let p = FastPoint::affine(x, f.mul(x, u));
                vec![p, self.fast.neg(p)]
            }
            None => Vec::new(),
        }
    }

    pub fn group(&self) -> BinaryGroup<'_> {
        BinaryGroup(&self.fast)
    }
}

/// **Enumerate the order-`ℓ` subgroups that live in `E(F_{2^n})`.**
///
/// When `ℓ² | #E` the full `ℓ`-torsion can be rational, and then all `ℓ+1`
/// subgroups are found here directly from points — no division polynomial,
/// no factorisation.  When only `ℓ ∥ #E` there is one rational subgroup.
/// When `ℓ ∤ #E` there are none, and the caller must go through
/// [`division_polynomial`] instead; [`kernels_via_rational_torsion`] says so
/// by returning an empty vector rather than by failing.
///
/// Returns each subgroup as its kernel polynomial.
pub fn kernels_via_rational_torsion(curve: &Curve, ell: u64, scan_limit: u64) -> Vec<F2mPoly> {
    if !curve.order.is_multiple_of(ell) {
        return Vec::new();
    }
    let group = curve.group();
    let mut ops = GroupOps::default();
    // The cofactor must strip EVERY power of `ell`, not one.  When the
    // `ell`-Sylow is `Z/ℓ × Z/ℓ` its exponent is `ℓ`, so `#E/ℓ` still
    // carries a factor `ℓ` and annihilates the whole `ell`-part —
    // `[#E/3]P = O` for every `P` at `n = 8`, where the 3-Sylow is
    // `Z/3 × Z/3`.  Removing the full `ℓ`-power lands in the Sylow instead.
    let mut cofactor = curve.order;
    while cofactor.is_multiple_of(ell) {
        cofactor /= ell;
    }

    // Collect points of order exactly ℓ by clearing the cofactor off a
    // scan of abscissae.  `scan_limit` bounds the scan; the ℓ-torsion is
    // dense enough that a small multiple of ℓ² suffices in practice, and
    // the caller checks the subgroup count it got back.
    let mut torsion: BTreeSet<u64> = BTreeSet::new();
    let limit = scan_limit.min(1u64 << curve.n);
    for x in 0..limit {
        let Some(&p) = curve.points_with_x(x).first() else {
            continue;
        };
        let mut q = group.mul(&mut ops, p, cofactor);
        if q.infinity {
            continue;
        }
        // Descend inside the Sylow to an element of order exactly `ell`.
        while !group.mul(&mut ops, q, ell).infinity {
            q = group.mul(&mut ops, q, ell);
            if q.infinity {
                break;
            }
        }
        if q.infinity {
            continue;
        }
        torsion.insert(q.pack());
    }

    // Group the ℓ-torsion into cyclic subgroups.
    let mut seen: BTreeSet<u64> = BTreeSet::new();
    let mut out = Vec::new();
    let packed: Vec<u64> = torsion.iter().copied().collect();
    for &key in &packed {
        if seen.contains(&key) {
            continue;
        }
        // Recover a point with this packed identity.
        let Some(p) = unpack(curve, key) else {
            continue;
        };
        // Walk ⟨p⟩, collecting abscissae one per ± pair.
        let mut xs: BTreeSet<u64> = BTreeSet::new();
        let mut cur = p;
        for _ in 1..ell {
            if cur.infinity {
                break;
            }
            seen.insert(cur.pack());
            xs.insert(cur.x);
            cur = group.add(&mut ops, cur, p);
        }
        if xs.len() as u64 != (ell - 1) / 2 {
            continue; // not a clean order-ℓ subgroup
        }
        out.push(kernel_polynomial(&xs, curve.n, &curve.irr));
    }
    out
}

fn unpack(curve: &Curve, packed: u64) -> Option<FastPoint> {
    if packed == 0 {
        return Some(FastPoint::INFINITY);
    }
    let x = (packed >> 1) - 1;
    let sign = packed & 1;
    let pts = curve.points_with_x(x);
    pts.into_iter().find(|p| (p.pack() & 1) == sign)
}

/// `h(x) = Π (x + x_i)` from a set of abscissae.
pub fn kernel_polynomial(xs: &BTreeSet<u64>, n: u32, irr: &IrreduciblePoly) -> F2mPoly {
    let mut h = F2mPoly::from_coeffs(vec![F2mElement::one(n)], n);
    for &x in xs {
        let lin = F2mPoly::from_coeffs(vec![elt(x, n), F2mElement::one(n)], n);
        h = h.mul(&lin, irr);
    }
    h
}

/// Build the isogeny a kernel polynomial defines.
pub fn isogeny_from_kernel(curve: &Curve, kernel: F2mPoly, ell: u64) -> BinaryIsogeny {
    let a6e = elt(curve.a6, curve.n);
    let a6p = velu_codomain(&a6e, &kernel, curve.n, &curve.irr);
    let d = kernel.degree().unwrap_or(0);
    let t = if d == 0 {
        0
    } else {
        to_u64(&kernel.coeff(d - 1))
    };
    BinaryIsogeny {
        n: curve.n,
        a2: curve.a2,
        a6: curve.a6,
        a6_codomain: to_u64(&a6p),
        ell,
        kernel,
        t,
    }
}

// ── Part D: transporting a DLP instance ─────────────────────────────

/// What an explicit isogeny did to one DLP instance.
#[derive(Clone, Debug)]
pub struct TransportReport {
    pub ell: u64,
    pub a6_domain: u64,
    pub a6_codomain: u64,
    /// `#E'`, which must equal `#E` for an isogeny.
    pub codomain_order: u64,
    pub order_preserved: bool,
    /// `x(φ(P))` and `x(φ(Q))`.
    pub x_phi_p: Option<u64>,
    pub x_phi_q: Option<u64>,
    /// Whether `[d]φ(P)` has abscissa `x(φ(Q))` — the transport, verified as
    /// a computation on the codomain.
    pub transported: bool,
    /// `φ(P)` has order `r` on the codomain, so the instance really did land
    /// in a subgroup of the right size.
    pub image_order_ok: bool,
}

/// **Transport `(P, Q = [d]P)` across `φ` and check it.**
///
/// Only abscissae are mapped, so `φ(P)` is determined up to sign.  A sign on
/// `φ(Q)` would flip the logarithm to `−d`; checking `x([d]φ(P)) = x(φ(Q))`
/// is insensitive to both signs at once, which is exactly the statement the
/// DLP needs — `Q` and `−Q` have logarithms `d` and `−d`, and an attacker
/// solving on `E'` recovers one of them.
pub fn transport_instance(
    domain: &Curve,
    iso: &BinaryIsogeny,
    p: FastPoint,
    q: FastPoint,
    d: u64,
    r: u64,
) -> Option<TransportReport> {
    let codomain = Curve::new(domain.n, &domain.irr, domain.a2, iso.a6_codomain)?;
    let order_preserved = codomain.order == domain.order;

    let xp =
        velu_x_map(&elt(p.x, domain.n), &iso.kernel, domain.n, &domain.irr).map(|e| to_u64(&e));
    let xq =
        velu_x_map(&elt(q.x, domain.n), &iso.kernel, domain.n, &domain.irr).map(|e| to_u64(&e));

    let mut transported = false;
    let mut image_order_ok = false;
    if let (Some(xp), Some(xq)) = (xp, xq) {
        if let Some(&pp) = codomain.points_with_x(xp).first() {
            let group = codomain.group();
            let mut ops = GroupOps::default();
            image_order_ok = group.mul(&mut ops, pp, r).infinity;
            let dp = group.mul(&mut ops, pp, d % r);
            transported = !dp.infinity && dp.x == xq;
        }
    }

    Some(TransportReport {
        ell: iso.ell,
        a6_domain: iso.a6,
        a6_codomain: iso.a6_codomain,
        codomain_order: codomain.order,
        order_preserved,
        x_phi_p: xp,
        x_phi_q: xq,
        transported,
        image_order_ok,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::binary_isogeny::{find_roots_in_f2m, phi_l_mod2_in_x};
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;

    fn field(n: u32) -> IrreduciblePoly {
        find_irreducible_sparse(n).expect("a sparse irreducible exists")
    }

    #[test]
    fn psi3_matches_its_closed_form_and_psi_recurrence_agrees() {
        let n = 8;
        let irr = field(n);
        let a6 = elt(1, n);
        let p3 = division_polynomial(&a6, 3, n, &irr);
        assert_eq!(p3.degree(), Some(4), "deg ψ₃ = (9−1)/2");
        let p5 = division_polynomial(&a6, 5, n, &irr);
        assert_eq!(p5.degree(), Some(12), "deg ψ₅ = (25−1)/2");
        let p7 = division_polynomial(&a6, 7, n, &irr);
        assert_eq!(p7.degree(), Some(24), "deg ψ₇ = (49−1)/2");
    }

    /// The load-bearing test: Vélu's codomain, derived here from scratch for
    /// char 2, against the classical modular polynomial the repository
    /// tabulates independently.
    #[test]
    fn velu_matches_the_modular_polynomial_at_ell_3() {
        let n = 8;
        let irr = field(n);
        let gf = Gf2::new(&irr);
        let a6v = 1u64;
        let a6 = elt(a6v, n);

        let psi3 = division_polynomial(&a6, 3, n, &irr);
        let roots = find_roots_in_f2m(&psi3, n, &irr);
        assert_eq!(roots.len(), 4, "E[3] is rational over F_2^8 here");

        let j = gf.inv(a6v);
        let phi = phi_l_mod2_in_x(3, &elt(j, n), n, &irr);
        let jroots: Vec<u64> = find_roots_in_f2m(&phi, n, &irr)
            .iter()
            .map(to_u64)
            .collect();
        assert_eq!(jroots.len(), 4);

        for root in &roots {
            // d = 1, so the kernel polynomial is the linear factor.
            let h = F2mPoly::from_coeffs(vec![root.clone(), F2mElement::one(n)], n);
            let a6p = velu_codomain(&a6, &h, n, &irr);
            let a6p_v = to_u64(&a6p);
            assert_ne!(a6p_v, 0, "codomain must be non-singular");
            let jp = gf.inv(a6p_v);
            assert!(
                jroots.contains(&jp),
                "j' = {jp} from Vélu is not a root of Φ₃(X, {j})"
            );
        }
    }

    #[test]
    fn the_codomain_is_isogenous_so_its_order_is_unchanged() {
        let n = 8;
        let irr = field(n);
        let a6v = 1u64;
        let domain = Curve::new(n, &irr, 0, a6v).expect("curve");
        let psi3 = division_polynomial(&elt(a6v, n), 3, n, &irr);
        for root in find_roots_in_f2m(&psi3, n, &irr) {
            let h = F2mPoly::from_coeffs(vec![root, F2mElement::one(n)], n);
            let iso = isogeny_from_kernel(&domain, h, 3);
            let codomain = Curve::new(n, &irr, 0, iso.a6_codomain).expect("codomain is a curve");
            assert_eq!(
                codomain.order, domain.order,
                "an isogeny preserves the number of points"
            );
        }
    }

    #[test]
    fn rational_torsion_finds_every_subgroup_the_division_polynomial_does() {
        let n = 8;
        let irr = field(n);
        let a6v = 1u64;
        let curve = Curve::new(n, &irr, 0, a6v).expect("curve");
        assert_eq!(curve.order % 3, 0, "3 | #E, so the torsion route applies");

        let from_points = kernels_via_rational_torsion(&curve, 3, 1 << n);
        let psi3 = division_polynomial(&elt(a6v, n), 3, n, &irr);
        let from_psi = find_roots_in_f2m(&psi3, n, &irr);

        let a: BTreeSet<u64> = from_points.iter().map(|h| to_u64(&h.coeff(0))).collect();
        let b: BTreeSet<u64> = from_psi.iter().map(to_u64).collect();
        assert_eq!(a, b, "both routes must name the same four subgroups");
    }

    #[test]
    fn the_x_map_sends_the_curve_into_its_codomain() {
        let n = 8;
        let irr = field(n);
        let a6v = 1u64;
        let domain = Curve::new(n, &irr, 0, a6v).expect("curve");
        let psi3 = division_polynomial(&elt(a6v, n), 3, n, &irr);
        let root = find_roots_in_f2m(&psi3, n, &irr)
            .into_iter()
            .next()
            .expect("a kernel");
        let h = F2mPoly::from_coeffs(vec![root, F2mElement::one(n)], n);
        let iso = isogeny_from_kernel(&domain, h, 3);
        let codomain = Curve::new(n, &irr, 0, iso.a6_codomain).expect("codomain");

        let mut mapped = 0;
        for x in 0..(1u64 << n) {
            if domain.points_with_x(x).is_empty() {
                continue;
            }
            let Some(xe) = velu_x_map(&elt(x, n), &iso.kernel, n, &irr) else {
                continue; // kernel abscissa, maps to O
            };
            assert!(
                !codomain.points_with_x(to_u64(&xe)).is_empty(),
                "φ({x}) = {} is not an abscissa on the codomain",
                to_u64(&xe)
            );
            mapped += 1;
        }
        assert!(mapped > 0, "something must have been mapped");
    }
}
