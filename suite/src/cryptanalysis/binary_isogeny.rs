//! # Step 1 of the GHS / Hess Weil-descent pipeline: isogeny walk.
//!
//! Given a target binary elliptic curve `E / F_{2^N}` whose direct GHS
//! magic number is too small (typically `m = 1`, useless), we walk the
//! `l`-isogeny graph until we find an isogenous curve `E'` whose magic
//! number is `2 ≤ m' ≤ ~6` — small enough that the descended
//! hyperelliptic curve has tractable genus.  This is the move that
//! takes c2pnb176w1 from "structurally interesting but uncrackable
//! direct-GHS" to "crackable via Hess's generalisation."
//!
//! ## What this module does
//!
//! 1. [`j_invariant`] — `j(E) = 1/b` for ordinary binary curves in the
//!    `y² + xy = x³ + a x² + b` form (a one-line standard formula).
//! 2. [`phi_l_mod2_in_x`] — substitute `Y = j(E)` into the integer
//!    modular polynomial `Φ_l(X, Y)`, reduce the coefficients mod 2,
//!    and lift back into `F_{2^N}[X]`.  The roots are the `j`-invariants
//!    of `l`-isogenous curves.
//! 3. [`find_roots_in_f2m`] — Cantor-Zassenhaus / equal-degree-factoring
//!    over `F_{2^N}` extracts those `j'` values.
//! 4. [`l_isogenous_neighbours`] — packages the above: from one curve,
//!    returns every `l`-isogenous codomain (up to twist).
//! 5. [`walk_to_magic`] — BFS the small-`l` isogeny graph looking for
//!    a curve whose magic number hits a configurable target.
//!
//! ## What this module does *not* do
//!
//! - Compute the **explicit isogeny morphism** φ: E → E'.  The walk
//!   tracks `j`-invariants only; reconstructing φ as a rational map
//!   in `(x, y)` requires Vélu's formulae adapted to characteristic 2,
//!   which is a separate (non-trivial) implementation.  Without φ we
//!   cannot lift a `DLP` on `E'` back to `E` via the standard
//!   isogeny-pushforward; see [`crate::cryptanalysis::ghs_full_attack`]
//!   for the workarounds we use in the end-to-end demo.

use crate::binary_ecc::{F2mElement, F2mPoly, IrreduciblePoly};
use crate::cryptanalysis::ec_trapdoor::{magic_number_full, FieldTower};
use crate::cryptanalysis::ghs_descent::ECurve;
use crate::cryptanalysis::modular_polynomial::{phi_2, phi_3, ModularPolynomial};
use num_bigint::BigInt;
use num_traits::{Signed, Zero};
use std::collections::{HashMap, HashSet, VecDeque};

// ── j-invariant ─────────────────────────────────────────────────────

/// `j(E)` for an ordinary binary curve `E: y² + xy = x³ + ax² + b`.
///
/// Standard formula in characteristic 2: with `c₄ = 1`, `Δ = b`, we have
/// `j(E) = c₄³ / Δ = 1 / b`.  `b = 0` would be a supersingular curve,
/// which we never deal with here (the GHS trapdoor assumes ordinary `b`).
pub fn j_invariant(curve: &ECurve) -> F2mElement {
    assert!(
        !curve.b.is_zero(),
        "supersingular curve (b = 0) — j undefined"
    );
    curve
        .b
        .flt_inverse(&curve.irr)
        .expect("b ≠ 0 implies invertible")
}

// ── Φ_l(X, j) over F_{2^m} ─────────────────────────────────────────

/// Look up `Φ_l(X, Y)` from the integer table.  We currently ship
/// `l ∈ {2, 3}`; the table can be extended with the entries already
/// computed in [`crate::cryptanalysis::modular_polynomial`].
fn modular_polynomial_lookup(l: u32) -> Option<ModularPolynomial> {
    match l {
        2 => Some(phi_2()),
        3 => Some(phi_3()),
        _ => None,
    }
}

/// Reduce `(i, j) ↦ ModularPolynomial` integer coefficients modulo 2.
/// `Φ_l(X, Y)` is stored "upper-triangularly" — the table only lists one
/// of `(i, j)` and `(j, i)` since the polynomial is symmetric.  We
/// reconstitute both halves here.
fn phi_l_coeffs_mod2(phi: &ModularPolynomial) -> HashMap<(u32, u32), u8> {
    let mut out = HashMap::new();
    for ((i, j), c) in &phi.coeffs {
        let bit = (c.abs() % BigInt::from(2u8)).is_zero();
        let bit_u8 = if bit { 0u8 } else { 1u8 };
        if bit_u8 == 0 {
            continue;
        }
        // Symmetric: both (i, j) and (j, i) get the coefficient.
        out.insert((*i, *j), 1);
        if i != j {
            out.insert((*j, *i), 1);
        }
    }
    out
}

/// Build `Φ_l(X, Y = j) ∈ F_{2^m}[X]` from the integer-coefficient
/// modular polynomial.  Each retained term contributes `Y^j` powers,
/// evaluated at the field element `j_val`.
pub fn phi_l_mod2_in_x(l: u32, j_val: &F2mElement, m: u32, irr: &IrreduciblePoly) -> F2mPoly {
    let phi = modular_polynomial_lookup(l)
        .unwrap_or_else(|| panic!("Φ_{} not in table; only l ∈ {{2, 3}} supported", l));
    let coeffs_bits = phi_l_coeffs_mod2(&phi);

    // Group by X-degree.  For each degree i, accumulate Σ_j j_val^j over
    // (i, j) entries with bit = 1.
    let mut by_x_deg: HashMap<u32, F2mElement> = HashMap::new();

    // Precompute powers of `j_val`.
    let max_deg = phi.total_degree();
    let mut j_powers = Vec::with_capacity((max_deg + 1) as usize);
    let mut cur = F2mElement::one(m);
    for _ in 0..=max_deg {
        j_powers.push(cur.clone());
        cur = cur.mul(j_val, irr);
    }

    for (i, jdeg) in coeffs_bits.keys() {
        let term = j_powers[*jdeg as usize].clone();
        let entry = by_x_deg.entry(*i).or_insert_with(|| F2mElement::zero(m));
        *entry = entry.add(&term);
    }

    // Pack into F2mPoly.
    let mut coeffs = vec![F2mElement::zero(m); (max_deg + 1) as usize];
    for (xdeg, c) in by_x_deg {
        coeffs[xdeg as usize] = c;
    }
    let mut p = F2mPoly::from_coeffs(coeffs, m);
    p.trim();
    p
}

// ── Root finding in F_{2^m}[X] ─────────────────────────────────────

/// Find every root of `poly` in `F_{2^m}`.  Strategy:
///
/// 1. Compute `gcd(poly(X), X^{2^m} - X)` to isolate the F_{2^m}-rational
///    factor (Cantor-Zassenhaus pre-step).
/// 2. Equal-degree factor the result into linear pieces by repeatedly
///    splitting via random `(X + r)` polynomials' GCDs.
///
/// For low-degree input (`l = 2` gives degree `≤ 3`; `l = 3` gives
/// degree `≤ 4`), the simpler exhaustive search over `F_{2^m}` is also
/// viable when `m ≤ 16`.  We do both: fast path for small `m`, generic
/// otherwise.
pub fn find_roots_in_f2m(poly: &F2mPoly, m: u32, irr: &IrreduciblePoly) -> Vec<F2mElement> {
    let mut roots = Vec::new();
    if poly.is_zero() {
        return roots;
    }
    let deg = poly.degree().unwrap_or(0);
    if deg == 0 {
        return roots;
    }

    // Small-field fast path: just try every element.
    if m <= 16 {
        for v in 0u64..(1u64 << m) {
            let bits: Vec<u32> = (0..m).filter(|i| (v >> i) & 1 == 1).collect();
            let elt = F2mElement::from_bit_positions(&bits, m);
            if poly.eval(&elt, irr).is_zero() {
                roots.push(elt);
            }
        }
        return roots;
    }

    // Generic: CZ-style.  First, restrict to the F_{2^m}-rational part
    // by computing g(X) = gcd(poly(X), X^{2^m} − X).  X^{2^m} − X in
    // char 2 is X^{2^m} + X.
    let rational_factor = restrict_to_rational(poly, m, irr);
    if rational_factor.is_zero() {
        return roots;
    }
    let rdeg = rational_factor.degree().unwrap_or(0);
    if rdeg == 0 {
        return roots;
    }
    // Linear-factor extraction by trial.  For our purposes degrees are
    // tiny (≤ 4), so randomised CZ is overkill — just trial division
    // by all `(X + α)` for `α ∈ F_{2^m}` once we know `rdeg` roots exist.
    // But m may be large here, so we use proper CZ via random splitting.
    cz_split(&rational_factor, m, irr, &mut roots);
    roots
}

/// `gcd(poly, X^{2^m} − X)` in `F_{2^m}[X]`.  This is the F_{2^m}-rational
/// factor of `poly`.  Computed via repeated squaring modulo `poly` to
/// build `X^{2^m} mod poly` without ever materialising the full
/// `X^{2^m} − X` polynomial.
fn restrict_to_rational(poly: &F2mPoly, m: u32, irr: &IrreduciblePoly) -> F2mPoly {
    // h(X) = X mod poly, then square m times.
    let mut h = F2mPoly::x(poly.m);
    let _ = m; // m below is the field's m parameter — we use bit-length m for the squaring count
    let field_m = poly.m;
    // We need to square (mod poly) the absolute Frobenius `X ↦ X^2`
    // exactly `field_m` times so that `h = X^{2^{field_m}} mod poly`,
    // which is what we want for finding F_{2^{field_m}}-rational roots.
    for _ in 0..field_m {
        h = h.mul(&h, irr).rem(poly, irr);
    }
    // h = X^{2^m} mod poly.  Subtract X (= add in char 2).
    let x = F2mPoly::x(field_m);
    let diff = h.add(&x);
    poly.gcd(&diff, irr)
}

/// Equal-degree factor a separable polynomial whose every irreducible
/// factor has degree 1 over `F_{2^m}`, extracting roots.
fn cz_split(poly: &F2mPoly, m: u32, irr: &IrreduciblePoly, roots: &mut Vec<F2mElement>) {
    let deg = poly.degree().unwrap_or(0);
    if deg == 0 {
        return;
    }
    if deg == 1 {
        // poly = X + c, root = c.
        let c = poly.coeff(0);
        roots.push(c);
        return;
    }
    // Try to split with random b ∈ F_{2^m}.  In char 2, the splitting
    // technique uses gcd(poly, Tr(b·X) + tr_offset).  We use a simple
    // trace-form that works for separable poly over F_{2^m}:
    //   g(X) = T(X) = X + X^2 + X^4 + ... + X^{2^{m-1}}
    // is the absolute trace from F_{2^m} to F_2.  For random shift `c`,
    // gcd(poly, T(c·X)) typically splits poly into two non-trivial
    // halves.

    // For our use case (deg ≤ ~5) the cleanest is: enumerate by
    // dividing out linear factors one at a time using a random shift.
    // We retry with different shifts until a non-trivial split.
    for attempt in 0..32u32 {
        let mut bits = Vec::new();
        let bound = m.min(20);
        for k in 0..bound {
            if (attempt.wrapping_mul(0x9E3779B1).rotate_left(k) >> 1) & 1 == 1 {
                bits.push(k);
            }
        }
        if bits.is_empty() {
            bits.push(0);
        }
        let c = F2mElement::from_bit_positions(&bits, m);
        if c.is_zero() {
            continue;
        }
        // Build trace polynomial T(c·X) = c·X + (c·X)^2 + ... + (c·X)^{2^{m-1}} mod poly.
        let mut acc = F2mPoly::x(m).scalar_mul(&c, irr).rem(poly, irr);
        let mut sum = acc.clone();
        for _ in 1..m {
            acc = acc.mul(&acc, irr).rem(poly, irr);
            sum = sum.add(&acc);
        }
        let g = poly.gcd(&sum, irr);
        let g_deg = g.degree().unwrap_or(0);
        if g_deg > 0 && g_deg < deg {
            // Split.  Recurse on both halves.
            let (other, _) = poly.divrem(&g, irr);
            cz_split(&g, m, irr, roots);
            cz_split(&other, m, irr, roots);
            return;
        }
    }
    // Fallback: shouldn't reach here for separable input.
}

// ── Neighbour enumeration ───────────────────────────────────────────

/// Reconstruct a "canonical" binary curve from a target `j`-invariant.
/// Returns `E': y² + xy = x³ + a' · x² + (1/j')` with `a' = 0`.  Any
/// curve with this `j` is isomorphic to this one over the algebraic
/// closure, possibly through a quadratic twist; for magic-number
/// purposes both choices of `a' ∈ {0, 1}` should be tried.
pub fn curve_from_j(j: &F2mElement, m: u32, irr: &IrreduciblePoly, a_choice: u8) -> Option<ECurve> {
    if j.is_zero() {
        // j = 0 corresponds to supersingular curves in char 2 — out of
        // scope for the GHS attack.
        return None;
    }
    let b = j.flt_inverse(irr)?;
    let a = if a_choice == 0 {
        F2mElement::zero(m)
    } else {
        F2mElement::one(m)
    };
    Some(ECurve::new(m, irr.clone(), a, b))
}

/// All `l`-isogenous curve representatives reachable from `curve`.
/// Returns one canonical curve per neighbour `j'`-invariant; the caller
/// is responsible for trying twists (different `a`) as needed.
pub fn l_isogenous_neighbours(curve: &ECurve, l: u32) -> Vec<ECurve> {
    let j = j_invariant(curve);
    let phi_poly = phi_l_mod2_in_x(l, &j, curve.m, &curve.irr);
    let roots = find_roots_in_f2m(&phi_poly, curve.m, &curve.irr);
    let mut out = Vec::new();
    for r in &roots {
        for a_choice in [0u8, 1u8] {
            if let Some(e_prime) = curve_from_j(r, curve.m, &curve.irr, a_choice) {
                out.push(e_prime);
            }
        }
    }
    out
}

// ── Walk for target magic number ────────────────────────────────────

/// Result of an isogeny walk.
#[derive(Clone, Debug)]
pub struct WalkResult {
    /// Final curve `E'` reached.
    pub curve: ECurve,
    /// Magic number achieved.
    pub magic: u32,
    /// `j`-invariants visited along the walk, in order.
    pub path: Vec<F2mElement>,
}

/// Options for [`walk_to_magic`].
#[derive(Clone, Debug)]
pub struct WalkOptions {
    /// Isogeny degrees to consider at each step.  Default `[2, 3]`.
    pub degrees: Vec<u32>,
    /// Maximum number of `j`-invariants to visit before giving up.
    pub max_visited: usize,
    /// Target magic number — the walk stops as soon as `m' ≥ target`.
    pub target_magic: u32,
}

impl Default for WalkOptions {
    fn default() -> Self {
        WalkOptions {
            degrees: vec![2, 3],
            max_visited: 256,
            target_magic: 2,
        }
    }
}

/// BFS the small-`l` isogeny graph from `start`.  At each visited
/// curve, compute its magic number with respect to the given field
/// tower; stop and return as soon as we reach `target_magic` or above.
///
/// We track visited `j`-invariants to avoid cycles.  This is the
/// "macroscopic" Hess-attack search loop.
pub fn walk_to_magic(start: &ECurve, tower: &FieldTower, opts: &WalkOptions) -> Option<WalkResult> {
    let start_magic = magic_number_full(tower, &start.a, &start.b);
    if start_magic >= opts.target_magic {
        return Some(WalkResult {
            curve: start.clone(),
            magic: start_magic,
            path: vec![j_invariant(start)],
        });
    }

    let mut visited: HashSet<Vec<u64>> = HashSet::new();
    let mut queue: VecDeque<(ECurve, Vec<F2mElement>)> = VecDeque::new();
    let start_j = j_invariant(start);
    visited.insert(start_j.raw_bits().to_vec());
    queue.push_back((start.clone(), vec![start_j]));

    while let Some((cur, path)) = queue.pop_front() {
        if visited.len() > opts.max_visited {
            return None;
        }
        for &l in &opts.degrees {
            for nb in l_isogenous_neighbours(&cur, l) {
                let nb_j = j_invariant(&nb);
                let key = nb_j.raw_bits().to_vec();
                if !visited.insert(key) {
                    continue;
                }
                let nb_magic = magic_number_full(tower, &nb.a, &nb.b);
                let mut path2 = path.clone();
                path2.push(nb_j.clone());
                if nb_magic >= opts.target_magic {
                    return Some(WalkResult {
                        curve: nb,
                        magic: nb_magic,
                        path: path2,
                    });
                }
                queue.push_back((nb, path2));
            }
        }
    }
    None
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;

    /// `j(E) · b = 1` for ordinary curves.
    #[test]
    fn j_inverts_b() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        // Random nonzero b.
        let b = F2mElement::from_bit_positions(&[0, 2, 3], m);
        let a = F2mElement::one(m);
        let curve = ECurve::new(m, irr.clone(), a, b.clone());
        let j = j_invariant(&curve);
        let prod = j.mul(&b, &irr);
        assert_eq!(prod, F2mElement::one(m));
    }

    /// Round-trip: build E from j(E), recover same j.
    #[test]
    fn j_round_trip() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let j_target = F2mElement::from_bit_positions(&[1, 4], m);
        let e_prime = curve_from_j(&j_target, m, &irr, 0).expect("nonzero j");
        let j_recovered = j_invariant(&e_prime);
        assert_eq!(j_recovered, j_target);
    }

    /// Φ_2(X, j) over F_{2^m} has at most 3 roots (it's a cubic in X).
    #[test]
    fn phi_2_is_cubic() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let j = F2mElement::from_bit_positions(&[0, 3, 5], m);
        let phi = phi_l_mod2_in_x(2, &j, m, &irr);
        assert!(phi.degree().unwrap_or(0) <= 3);
    }

    /// Root finder on a known-factored polynomial: `(X − 1)(X − ω)` with
    /// `ω ∈ F_{2^m}` random.
    #[test]
    fn root_finder_basic() {
        let irr = IrreduciblePoly::deg_8();
        let m = 8;
        let r0 = F2mElement::one(m);
        let r1 = F2mElement::from_bit_positions(&[2, 5], m);
        // Poly = (X + r0)(X + r1) = X² + (r0 + r1) X + r0·r1.
        let c0 = r0.mul(&r1, &irr);
        let c1 = r0.add(&r1);
        let poly = F2mPoly::from_coeffs(vec![c0, c1, F2mElement::one(m)], m);
        let mut roots = find_roots_in_f2m(&poly, m, &irr);
        roots.sort_by_key(|r| r.to_biguint());
        let mut expected = vec![r0.clone(), r1.clone()];
        expected.sort_by_key(|r| r.to_biguint());
        assert_eq!(roots, expected);
    }

    /// Sanity: starting from a curve with magic = 1 over F_{2^6} =
    /// F_{(2^3)²}, the walk should either find a curve with higher
    /// magic OR exhaust without finding one (depending on the isogeny
    /// class structure).  We assert the walk terminates without panic.
    #[test]
    fn walk_terminates() {
        let irr = IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        };
        let m = 6;
        let big_n = 6;
        let n = 3;
        let l = 2;
        let tower = FieldTower::new(big_n, n, l, irr.clone());
        // Pick b in F_4 = F_{2^l}: any element fixed by Frobenius x ↦ x^4.
        let b = F2mElement::one(m);
        let a = F2mElement::one(m);
        let start = ECurve::new(m, irr.clone(), a, b);
        let opts = WalkOptions {
            degrees: vec![2, 3],
            max_visited: 32,
            target_magic: 2,
        };
        // We don't assert success — the F_2^6 isogeny graph is small
        // and may not contain a magic-2 neighbour.  Just check the
        // walk machinery runs cleanly.
        let _result = walk_to_magic(&start, &tower, &opts);
    }
}
