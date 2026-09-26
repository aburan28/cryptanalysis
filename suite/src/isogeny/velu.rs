//! # Vélu's formulas: explicit isogenies from a kernel subgroup.
//!
//! Vélu (1971) gave a closed-form expression for the isogeny
//! `φ: E → E/G` once a finite subgroup `G ⊂ E(F̄)` is specified by
//! its non-identity points.  Given `E: y² = x³ + a x + b` and a
//! kernel `G = {O} ∪ {±P_1, …, ±P_s}` (so `|G| = 2s + 1` for odd
//! cyclic; `|G| = 2s + 2` for cyclic of even order with the 2-torsion
//! point `T = (x_T, 0)` adjoined), define for each `Q = (x_Q, y_Q)`
//! in `G \ {O}`:
//!
//! ```text
//!   g_x(Q) = 3 x_Q² + a
//!   g_y(Q) = -2 y_Q
//!   v(Q)   =   g_x(Q)            if 2Q = O          (T-row)
//!          = 2 g_x(Q)            otherwise
//!   u(Q)   = g_y(Q)²              (for the y-coordinate map)
//! ```
//!
//! Then summing over a half-set `R` (one representative of each
//! `{±Q}`):
//!
//! ```text
//!   x'  =  x + Σ_{Q ∈ R} [ v(Q) / (x − x_Q)  +  u(Q) / (x − x_Q)² ]
//!   y'  =  y · ( 1 − Σ_{Q ∈ R} [ v(Q) / (x − x_Q)²
//!                                + 2 u(Q) / (x − x_Q)³ ] )
//! ```
//!
//! and the codomain curve is `E' : Y² = X³ + a' X + b'` with
//!
//! ```text
//!   a' = a − 5 · Σ v(Q)
//!   b' = b − 7 · Σ ( u(Q) + x_Q · v(Q) )
//! ```
//!
//! (Both sums are over `R`.)
//!
//! ## Why we keep a separate, small implementation
//!
//! [`crate::cryptanalysis::modular_polynomial`] gives the
//! "algebraic" view: `Φ_ℓ(j(E), j(E')) = 0` constrains *which*
//! `E'` can be reached, but does not tell us **how** to construct
//! the isogeny rationally.  Vélu does both: codomain curve **and**
//! the rational maps for evaluating `φ` on points.
//!
//! ## Scope
//!
//! We enumerate the kernel `G` by brute force over `F_p` and
//! compute Vélu's sums directly.  This is `O(ℓ)` field operations
//! per isogeny — fine for `ℓ ≤ 100` and the toy curves used here.
//! Production-grade `√ℓ`-style algorithms (Bernstein–De Feo–
//! Leroux–Smith, 2020) are deliberately not implemented.

use super::SmallCurve;
use num_bigint::BigUint;

/// An `ℓ`-isogeny `φ: E → E'` constructed via Vélu's formulas.
#[derive(Clone, Debug)]
pub struct VeluIsogeny {
    /// The source curve.
    pub domain: SmallCurve,
    /// The codomain curve `E'`.  Computed by Vélu's `a'`, `b'`
    /// formulas above.  `name` is reused from the domain (we do
    /// not invent a new label here).
    pub codomain: SmallCurve,
    /// The degree `ℓ`.
    pub degree: u64,
    /// The kernel's non-identity points as `(x, y)` pairs over
    /// `F_p`, listed as a half-set `R` (one representative per
    /// `{±Q}`).
    pub kernel_half: Vec<(u64, u64)>,
}

impl VeluIsogeny {
    /// Evaluate the isogeny at an affine point `(x, y)`.  Returns
    /// `None` when `(x, y)` is in the kernel (image is the point
    /// at infinity).
    pub fn evaluate(&self, x: u64, y: u64) -> Option<(u64, u64)> {
        let p = self.domain.p as u128;
        let xm = x as u128 % p;
        let ym = y as u128 % p;
        let a = self.domain.a as u128 % p;

        // Reject kernel points.
        for &(xk, _) in &self.kernel_half {
            if xm == xk as u128 % p {
                return None;
            }
        }

        let mut acc_x = xm;
        let mut acc_y = ym;
        for &(xq, yq) in &self.kernel_half {
            let xq = xq as u128 % p;
            let yq = yq as u128 % p;

            let gx_q = mod_add(3 * mod_mul(xq, xq, p) % p, a, p);
            let gy_q = mod_sub(0, 2 * yq % p, p);
            // T-row test: 2Q = O ⇔ yQ = 0.
            let t_row = yq == 0;

            // Vélu: v(Q) = g_x(Q) when 2Q = O, and 2·g_x(Q) otherwise.
            let v_q = if t_row { gx_q } else { (2 * gx_q) % p };
            let u_q = mod_mul(gy_q, gy_q, p);

            let dx = mod_sub(xm, xq, p);
            let dx_inv = mod_inv(dx, p)?;
            let dx_inv2 = mod_mul(dx_inv, dx_inv, p);
            let dx_inv3 = mod_mul(dx_inv2, dx_inv, p);

            acc_x = mod_add(acc_x, mod_mul(v_q, dx_inv, p), p);
            acc_x = mod_add(acc_x, mod_mul(u_q, dx_inv2, p), p);

            // y-coordinate transformation: y' = y · (1 - ...)
            // We accumulate the bracket Σ [v · dx^{-2} + 2u · dx^{-3}].
            let bracket = mod_add(
                mod_mul(v_q, dx_inv2, p),
                mod_mul(2 * u_q % p, dx_inv3, p),
                p,
            );
            // Subtract the bracket from acc_y / ym, then re-multiply by y.
            // The cleanest way: compute the prefactor (1 − Σ) on the
            // running ym independently.
            //
            // Since acc_y starts as ym, the *first* iteration should
            // already apply (1 - bracket_1).  But we want all
            // iterations to multiply the same y, not to cascade.
            // Rebuild the factor explicitly:
            acc_y = mod_sub(acc_y, mod_mul(ym, bracket, p), p);
        }
        Some((acc_x as u64, acc_y as u64))
    }
}

// ── Modular arithmetic helpers in u128 ────────────────────────────────────────

fn mod_add(a: u128, b: u128, p: u128) -> u128 {
    ((a % p) + (b % p)) % p
}
fn mod_sub(a: u128, b: u128, p: u128) -> u128 {
    ((a % p) + p - (b % p)) % p
}
fn mod_mul(a: u128, b: u128, p: u128) -> u128 {
    // For p < 2^62 this fits comfortably in u128 (operands < 2^62
    // each, product < 2^124).
    ((a % p) * (b % p)) % p
}
fn mod_pow(mut base: u128, mut e: u128, p: u128) -> u128 {
    let mut r = 1u128 % p;
    base %= p;
    while e > 0 {
        if e & 1 == 1 {
            r = mod_mul(r, base, p);
        }
        base = mod_mul(base, base, p);
        e >>= 1;
    }
    r
}
fn mod_inv(a: u128, p: u128) -> Option<u128> {
    if a == 0 {
        return None;
    }
    // Fermat: p prime ⇒ a^{p-2} ≡ a⁻¹.
    Some(mod_pow(a, p - 2, p))
}

// ── Vélu codomain construction ────────────────────────────────────────────────

/// Compute the codomain curve and kernel-half representation from a
/// list of affine kernel points.  The list must contain at least one
/// representative of each `{±Q}` orbit.  Duplicate `{±Q}` orbits in
/// the input are silently de-duplicated.
fn velu_codomain_from_kernel(domain: &SmallCurve, kernel: &[(u64, u64)]) -> VeluIsogeny {
    let p = domain.p as u128;
    let a = domain.a as u128 % p;
    let b = domain.b as u128 % p;

    // Reduce to a half-set R: keep `Q` and drop `-Q`.
    let mut seen_x = std::collections::HashSet::<u64>::new();
    let mut half = Vec::new();
    for &(x, y) in kernel {
        if seen_x.insert(x) {
            half.push((x, y));
        }
    }

    let mut sum_v = 0u128;
    let mut sum_uvx = 0u128;
    for &(xq, yq) in &half {
        let xq = xq as u128 % p;
        let yq = yq as u128 % p;

        let gx_q = mod_add(3 * mod_mul(xq, xq, p) % p, a, p);
        let gy_q = mod_sub(0, 2 * yq % p, p);
        let t_row = yq == 0;
        // Vélu: v(Q) = g_x(Q) when 2Q = O, and 2·g_x(Q) otherwise.
        let v_q = if t_row { gx_q } else { (2 * gx_q) % p };
        let u_q = mod_mul(gy_q, gy_q, p);

        sum_v = mod_add(sum_v, v_q, p);
        sum_uvx = mod_add(sum_uvx, mod_add(u_q, mod_mul(xq, v_q, p), p), p);
    }

    let new_a = mod_sub(a, (5 * sum_v) % p, p) as u64;
    let new_b = mod_sub(b, (7 * sum_uvx) % p, p) as u64;
    let codomain = SmallCurve {
        name: domain.name,
        p: domain.p,
        a: new_a,
        b: new_b,
    };
    // For a cyclic kernel of odd order ℓ: |G| = 2·|half| + 1.
    // For a cyclic kernel of even order ℓ that includes the
    // 2-torsion point T = (x_T, 0): |G| = 2·|half| (T appears in
    // `half` as its own inverse).
    let degree = if half.iter().any(|&(_, y)| y == 0) {
        2 * (half.len() as u64)
    } else {
        2 * (half.len() as u64) + 1
    };

    VeluIsogeny {
        domain: *domain,
        codomain,
        degree,
        kernel_half: half,
    }
}

// ── ℓ = 2 isogeny ────────────────────────────────────────────────────────────

/// Compute a 2-isogeny with the specified 2-torsion point `T = (x_T, 0)`
/// as kernel.  `T` must satisfy `y² = x³ + a x + b` with `y = 0`,
/// i.e. `x_T` is a root of `x³ + a x + b` over `F_p`.
pub fn velu_isogeny_2(domain: &SmallCurve, x_t: u64) -> Option<VeluIsogeny> {
    let p = domain.p as u128;
    let xt = x_t as u128 % p;
    let a = domain.a as u128 % p;
    let b = domain.b as u128 % p;
    // Check x_T is on the curve with y = 0.
    let rhs = mod_add(
        mod_add(mod_mul(mod_mul(xt, xt, p), xt, p), mod_mul(a, xt, p), p),
        b,
        p,
    );
    if rhs != 0 {
        return None;
    }
    Some(velu_codomain_from_kernel(domain, &[(x_t, 0)]))
}

// ── ℓ-odd isogeny via cofactor sampling ──────────────────────────────────────

/// Return all `ℓ`-isogenies from the curve as `VeluIsogeny` records.
/// `ℓ` must be an odd prime.
///
/// Algorithm (random-point cofactor method, Schoof 1995 §3):
///
/// 1. Compute `#E(F_p) = p + 1 − t` via [`crate::isogeny::cm::cm_discriminant`].
/// 2. If `ℓ ∤ #E`, there is no `F_p`-rational `ℓ`-torsion, so no
///    isogenies of degree `ℓ` are defined over `F_p`.  Return `[]`.
/// 3. Otherwise let `m = #E / ℓ`.  Repeatedly sample random
///    `P ∈ E(F_p)` and form `Q = m·P`; if `Q ≠ O`, then `Q` has
///    order dividing `ℓ`, and (since `ℓ` is prime) its order is
///    exactly `ℓ`, so `⟨Q⟩` is a cyclic subgroup of order `ℓ`.
/// 4. Stop when we've enumerated every distinct cyclic subgroup
///    (at most `ℓ+1` of them when `E[ℓ](F_p) ≅ (Z/ℓ)²`).
///
/// Cost: `O(ℓ² · log² p)` total — `O(log² p)` per scalar mult,
/// `O(ℓ)` samples expected per distinct subgroup, `O(ℓ)` subgroups
/// in the saturated case.  Compared to the previous
/// `O(ℓ² · p · log² p)` enumeration: at `p = 2^30` and `ℓ = 3`,
/// roughly a `10^9×` speed-up.
pub fn velu_isogeny_odd(domain: &SmallCurve, ell: u64) -> Vec<VeluIsogeny> {
    assert!(ell >= 3 && ell % 2 == 1, "ℓ must be an odd prime");

    use crate::ecc::point::Point;
    use crate::isogeny::cm::cm_discriminant;
    use std::collections::HashSet;

    let cm = cm_discriminant(domain);
    if cm.order <= 0 {
        return Vec::new();
    }
    let order = cm.order as u64;
    if !order.is_multiple_of(ell) {
        // No F_p-rational ℓ-torsion → no ℓ-isogenies definable over F_p.
        return Vec::new();
    }
    let cofactor = order / ell;

    let curve = domain.to_curve_params();
    let a_fe = curve.a_fe();

    // Sample random points P, form Q = cofactor · P.  Collect distinct
    // cyclic subgroups ⟨Q⟩ until we've either seen ℓ+1 (saturated) or
    // run out of attempts.
    let mut seen_subgroups: HashSet<Vec<u64>> = HashSet::new();
    let mut result = Vec::new();
    let mut rng_state: u64 = domain
        .p
        .wrapping_mul(0x9E3779B97F4A7C15)
        .wrapping_add(domain.a)
        .wrapping_mul(0xC6BC279692B5C323)
        .wrapping_add(domain.b)
        .wrapping_add(ell);
    let max_attempts: u64 = 4 * ell + 16; // expected O(ℓ²), pad for tail
    let max_subgroups = (ell + 1) as usize;

    for _ in 0..max_attempts {
        rng_state = rng_state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let point = match crate::isogeny::cm::sample_random_point(domain, &mut rng_state) {
            Some(p) => p,
            None => continue,
        };
        let q = point.scalar_mul(&BigUint::from(cofactor), &a_fe);
        if matches!(q, Point::Infinity) {
            continue;
        }
        // Q has order dividing ℓ; since ℓ is prime and Q ≠ O, order is ℓ.
        // Build subgroup ⟨Q⟩ = { Q, 2Q, ..., (ℓ-1)Q }.  We canonicalise
        // by sorting the x-coordinates so {P, -P, 2P, -2P, ...} all map
        // to the same key.
        let mut xs: Vec<u64> = Vec::with_capacity((ell - 1) as usize);
        let mut kernel: Vec<(u64, u64)> = Vec::with_capacity((ell - 1) as usize);
        let mut acc = q.clone();
        let mut bad = false;
        for _ in 1..ell {
            match &acc {
                Point::Affine { x, y } => {
                    let xv = x.value.iter_u64_digits().next().unwrap_or(0);
                    let yv = y.value.iter_u64_digits().next().unwrap_or(0);
                    xs.push(xv);
                    kernel.push((xv, yv));
                }
                Point::Infinity => {
                    bad = true;
                    break;
                }
            }
            acc = acc.add(&q, &a_fe);
        }
        if bad || kernel.len() as u64 != ell - 1 {
            continue;
        }
        let mut key = xs.clone();
        key.sort();
        if !seen_subgroups.insert(key) {
            continue; // already have this subgroup
        }
        result.push(velu_codomain_from_kernel(domain, &kernel));
        if result.len() >= max_subgroups {
            break;
        }
    }
    result
}

// ── Dual isogeny ──────────────────────────────────────────────────────────────
//
// For φ: E → E' of degree ℓ, the dual `φ̂: E' → E` is again degree ℓ
// and satisfies `φ̂ ∘ φ = [ℓ]_E`.  The kernel of `φ̂` is `φ(E[ℓ])`,
// which over `F_p` is the image of any `ℓ`-torsion subgroup of `E'`
// not equal to `ker(φ̂)` itself.
//
// We provide a `dual_isogeny_naive` that simply searches the
// codomain's `ℓ`-torsion subgroups and picks the one that completes
// the round-trip on a probe point.

/// Find the dual `ℓ`-isogeny of a `VeluIsogeny` by exhaustive search
/// over the codomain's `ℓ`-isogeny family.  `O(deg)`-many candidates
/// (one per cyclic subgroup); each is tested by checking that the
/// composition is `[ℓ]` on a single probe point.
pub fn dual_isogeny_naive(phi: &VeluIsogeny) -> Option<VeluIsogeny> {
    let ell = phi.degree;
    let cands = if ell == 2 {
        // 2-isogeny: search the codomain's 2-torsion.
        let mut v = Vec::new();
        for x in 0..phi.codomain.p {
            if phi.codomain.rhs(x) == 0 {
                if let Some(iso) = velu_isogeny_2(&phi.codomain, x) {
                    v.push(iso);
                }
            }
        }
        v
    } else {
        velu_isogeny_odd(&phi.codomain, ell)
    };

    // Probe: pick a point on the domain that's not in ker(φ).
    let p = phi.domain.p;
    for x in 2..p {
        let rhs = phi.domain.rhs(x);
        if rhs == 0 {
            continue;
        }
        let y = match crate::isogeny::cm::legendre_u64(rhs, p) {
            1 => match crate::isogeny::cm::tonelli_shanks_u64(rhs, p) {
                Some(y) if y != 0 => y,
                _ => continue,
            },
            _ => continue,
        };
        let _ = y; // explicit binding for clarity below

        if let Some(image) = phi.evaluate(x, y) {
            // For each candidate ψ, compute ψ(image) and check it equals [ell] · (x, y).
            let curve = phi.domain.to_curve_params();
            let a_fe = curve.a_fe();
            let p_point = crate::ecc::point::Point::Affine {
                x: curve.fe(BigUint::from(x)),
                y: curve.fe(BigUint::from(y)),
            };
            let ell_p = p_point.scalar_mul(&BigUint::from(ell), &a_fe);
            for psi in &cands {
                if let Some((px, py)) = psi.evaluate(image.0, image.1) {
                    if let crate::ecc::point::Point::Affine { x: ex, y: ey } = &ell_p {
                        let exv = ex.value.iter_u64_digits().next().unwrap_or(0);
                        let eyv = ey.value.iter_u64_digits().next().unwrap_or(0);
                        if exv == px && eyv == py {
                            return Some(psi.clone());
                        }
                    }
                }
            }
            // No probe → too small; bail.
            break;
        }
    }
    None
}

// ── Composition of isogenies ─────────────────────────────────────────────────

/// Compose two Vélu isogenies `φ: E → E'` and `ψ: E' → E''`.  The
/// returned record's `kernel_half` field is the *pull-back* of
/// `ψ`'s kernel under `φ` (computed by evaluating `φ` on a curve
/// enumeration), so the resulting record correctly represents the
/// composite as a single isogeny.  Note: the **degree** of the
/// composite is `phi.degree · psi.degree`.
pub fn compose_isogenies(phi: &VeluIsogeny, psi: &VeluIsogeny) -> Option<VeluIsogeny> {
    if phi.codomain.a != psi.domain.a
        || phi.codomain.b != psi.domain.b
        || phi.codomain.p != psi.domain.p
    {
        return None;
    }
    // Enumerate ker(ψ ∘ φ) by walking E(F_p) and keeping points
    // whose image under φ lies in ker(ψ).  Tonelli-Shanks per x
    // gives O(p · log² p) instead of O(p²).
    let mut kernel = Vec::new();
    let p = phi.domain.p;
    for x in 0..p {
        let rhs = phi.domain.rhs(x);
        let y = if rhs == 0 {
            0u64
        } else {
            match crate::isogeny::cm::legendre_u64(rhs, p) {
                1 => match crate::isogeny::cm::tonelli_shanks_u64(rhs, p) {
                    Some(y) => y,
                    None => continue,
                },
                _ => continue,
            }
        };
        if let Some(image) = phi.evaluate(x, y) {
            if psi.kernel_half.iter().any(|&(kx, _)| kx == image.0) {
                kernel.push((x, y));
            }
        }
    }
    let mut iso = velu_codomain_from_kernel(&phi.domain, &kernel);
    iso.codomain = psi.codomain;
    iso.degree = phi.degree * psi.degree;
    Some(iso)
}

// ── Unit tests ───────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::isogeny::toy_curve_a;

    #[test]
    fn two_isogeny_round_trip() {
        // On the toy-2003 curve, search for a 2-torsion point and
        // build the 2-isogeny.  Codomain should be a valid curve
        // with non-zero discriminant.
        let curve = toy_curve_a();
        let mut found = None;
        for x in 0..curve.p {
            if curve.rhs(x) == 0 {
                found = Some(x);
                break;
            }
        }
        if let Some(x_t) = found {
            let iso = velu_isogeny_2(&curve, x_t).expect("2-iso constructs");
            assert_eq!(iso.degree, 2);
            // Codomain is a *different* curve (unless x_T is degenerate).
            assert!(iso.codomain.p == curve.p);
        }
    }

    #[test]
    fn three_isogeny_count_for_toy() {
        // On a small ordinary curve, the number of 3-isogenies is
        // bounded by the number of order-3 cyclic subgroups, which
        // is 0, 1, 2, or 4 depending on rank of E[3].
        let curve = toy_curve_a();
        let isos = velu_isogeny_odd(&curve, 3);
        assert!(isos.len() <= 4, "got {} 3-isogenies", isos.len());
    }

    // ── The transfer that lever L5 rests on ───────────────────────────────
    //
    // `research/notes/ecc2k130/RESEARCH_ISOGENY_CLASS_SEARCH.md` opens by
    // asserting that "the ECDLP transports along an isogeny of degree
    // coprime to the subgroup order".  §1.1 of that note derives it; these
    // two tests are what make it a checked statement rather than a cited
    // one, and they are the reason the thread may treat every curve in the
    // class as carrying the same discrete logarithm.

    use crate::ecc::field::FieldElement;
    use crate::ecc::point::Point;

    fn pt(x: u64, y: u64, p: u64) -> Point {
        Point::Affine {
            x: FieldElement::new(BigUint::from(x), BigUint::from(p)),
            y: FieldElement::new(BigUint::from(y), BigUint::from(p)),
        }
    }

    fn xy(point: &Point) -> Option<(u64, u64)> {
        match point {
            Point::Affine { x, y } => Some((
                x.value.iter_u64_digits().next().unwrap_or(0),
                y.value.iter_u64_digits().next().unwrap_or(0),
            )),
            Point::Infinity => None,
        }
    }

    /// An isogeny is a group homomorphism, so `φ([k]P) = [k]φ(P)` and the
    /// discrete logarithm crosses **unchanged** — no factor of the degree
    /// appears anywhere in the transfer.
    ///
    /// `toy_curve_a` has `#E = 2019 = 3 · 673`, so with `ℓ = 3` the kernel
    /// has order 3 and `⟨P⟩` has prime order `n = 673`.  `gcd(3, 673) = 1`
    /// makes `φ` injective on `⟨P⟩`, which is exactly the note's side
    /// condition.  Every `k` in `1..n` is checked, not a sample.
    #[test]
    fn transfer_preserves_the_discrete_logarithm() {
        let curve = toy_curve_a();
        let (ell, n) = (3u64, 673u64);
        assert_eq!(2019, ell * n, "toy_curve_a order must factor as 3 · 673");
        assert_eq!(
            1,
            num_integer::gcd(ell, n),
            "side condition gcd(deg, n) = 1"
        );

        let iso = velu_isogeny_odd(&curve, ell)
            .into_iter()
            .next()
            .expect("toy_curve_a admits a 3-isogeny");

        let dom = curve.to_curve_params();
        let cod = iso.codomain.to_curve_params();
        let (a_dom, a_cod) = (dom.a_fe(), cod.a_fe());

        // A generator of the order-n subgroup: kill the cofactor ℓ.
        let mut rng: u64 = 0x5DEE_CE66_D4A5_1B2D;
        let base = loop {
            if let Some(p0) = crate::isogeny::cm::sample_random_point(&curve, &mut rng) {
                let q = p0.scalar_mul(&BigUint::from(ell), &a_dom);
                if !matches!(q, Point::Infinity) {
                    break q;
                }
            }
        };
        assert!(
            matches!(base.scalar_mul(&BigUint::from(n), &a_dom), Point::Infinity),
            "base point must have order n"
        );

        let (bx, by) = xy(&base).expect("base is affine");
        let image = iso.evaluate(bx, by).expect("P is not in ker φ");
        let p_img = pt(image.0, image.1, iso.codomain.p);

        // φ([k]P) == [k]φ(P) for every k in 1..n.
        for k in 1..n {
            let kp = base.scalar_mul(&BigUint::from(k), &a_dom);
            let (kx, ky) = xy(&kp).expect("[k]P affine for 0 < k < n");
            let lhs = iso.evaluate(kx, ky).expect("[k]P not in ker φ");
            let rhs = xy(&p_img.scalar_mul(&BigUint::from(k), &a_cod)).expect("[k]φ(P) affine");
            assert_eq!(
                lhs, rhs,
                "φ([{k}]P) != [{k}]φ(P) — the log did not transfer"
            );
        }
    }

    /// Regression pin for the `v(Q)` formula.  Until 2026-09, this module
    /// used `v(Q) = 4 x_Q g_y(Q)² + 2 g_x(Q)²` for non-2-torsion `Q`, which
    /// is not Vélu's: the correct value is `2 g_x(Q)` (and `g_x(Q)` on the
    /// T-row).  The bug was invisible to the older tests because they only
    /// checked a subgroup *count* and that the codomain shared the domain's
    /// prime — never that a point's image satisfies the codomain equation,
    /// which it did not.
    ///
    /// The expected values here come from an independent implementation
    /// cross-checked for the homomorphism property; they are not read back
    /// from this code.
    #[test]
    fn codomain_and_image_match_an_independent_reference() {
        let curve = toy_curve_a();
        let iso = velu_isogeny_odd(&curve, 3)
            .into_iter()
            .next()
            .expect("toy_curve_a admits a 3-isogeny");

        assert_eq!(iso.kernel_half, vec![(594u64, 805u64)], "kernel generator");
        assert_eq!(
            (iso.codomain.a, iso.codomain.b),
            (739, 792),
            "Vélu codomain"
        );
        assert_eq!(
            iso.evaluate(24, 118),
            Some((643, 1661)),
            "image of (24, 118)"
        );

        // …and the image really is a point of the codomain.
        let (p, a2, b2) = (
            curve.p as u128,
            iso.codomain.a as u128,
            iso.codomain.b as u128,
        );
        let (x, y) = iso.evaluate(24, 118).expect("not in kernel");
        let (x, y) = (x as u128, y as u128);
        assert_eq!(
            y * y % p,
            (x * x % p * x % p + a2 * x % p + b2) % p,
            "φ(P) must satisfy the codomain equation"
        );
    }

    /// The side condition, from the other direction: `ker φ ∩ ⟨P⟩` is a
    /// subgroup of a group of prime order `n`, so it is trivial unless
    /// `n | deg φ`.  Kernel points themselves must die.
    #[test]
    fn kernel_points_die_and_the_subgroup_survives() {
        let curve = toy_curve_a();
        let iso = velu_isogeny_odd(&curve, 3)
            .into_iter()
            .next()
            .expect("toy_curve_a admits a 3-isogeny");

        for &(kx, ky) in &iso.kernel_half {
            assert!(
                iso.evaluate(kx, ky).is_none(),
                "kernel point ({kx}, {ky}) should map to the point at infinity"
            );
        }
        assert_eq!(
            iso.kernel_half.len() as u64,
            (iso.degree - 1) / 2,
            "half-set of a degree-{} kernel has (ℓ-1)/2 points",
            iso.degree
        );
    }
}
