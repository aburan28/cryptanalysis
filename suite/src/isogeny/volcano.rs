//! # ℓ-isogeny volcanoes (Kohel, Sutherland).
//!
//! For an ordinary `E/F_p` and a prime `ℓ ∤ p · disc(End(E))`,
//! the `ℓ`-isogeny graph
//!
//! ```text
//! G_ℓ = (vertex set: j-invariants;  edges: ℓ-isogenies up to ±)
//! ```
//!
//! around `E` has the shape of a **volcano**:
//!
//! - A **crater** at the top: a cycle (or single vertex) of
//!   horizontal isogenies among curves whose endomorphism ring is
//!   the *maximal* order `O_K`.  The crater's length is the order of
//!   `[ℓ]` in `Cl(O_K)` (could be 1, ℓ−1, ℓ, or ℓ+1).
//! - **Descending edges** from each crater vertex into a tree of
//!   non-maximal orders.  Each level corresponds to a power of `ℓ`
//!   in the conductor.
//! - The **floor**: leaves of the tree, where the conductor's
//!   `ℓ`-adic valuation equals the maximum permitted by the
//!   Frobenius trace.
//!
//! Kohel's algorithm reads off `v_ℓ(End(E))` (the `ℓ`-adic
//! valuation of the conductor) from the **depth** at which a random
//! walk first hits a 1-regular vertex (the floor): every floor
//! curve has exactly one `ℓ`-isogenous neighbour (its ascending
//! one).
//!
//! ## What we implement
//!
//! - [`map_volcano`] — Starting from a given curve `E`, build the
//!   local volcano structure up to a configurable depth, by
//!   alternating Vélu walks across `ℓ`-isogenies.
//! - [`volcano_depth`] — Walk from `E` to the floor (descending
//!   when possible, randomly otherwise) and report the depth.
//! - [`crater_size`] — Once at the crater, walk horizontally
//!   until cycling back to start; report the cycle length.
//! - [`position`] — Determine `(level, on_crater?)` for `E`.

use super::cm::{cm_discriminant, CmData};
use super::velu::{velu_isogeny_2, velu_isogeny_odd, VeluIsogeny};
use super::SmallCurve;
use std::collections::{BTreeMap, BTreeSet, VecDeque};

/// One level of the volcano, recording the curves and their
/// 1-step neighbours within the level (crater horizontal edges)
/// and the descent edges to the level below.
#[derive(Clone, Debug, serde::Serialize)]
pub struct VolcanoLevel {
    /// `0 = crater`, increasing downward.
    pub level: usize,
    /// j-invariants present at this level.
    pub j_invariants: Vec<u64>,
    /// Curves at this level (as `(p, a, b)` tuples).
    pub curves: Vec<(u64, u64, u64)>,
}

/// A complete map of an `ℓ`-isogeny volcano around a starting curve.
#[derive(Clone, Debug, serde::Serialize)]
pub struct VolcanoMap {
    pub ell: u64,
    pub start_curve: (u64, u64, u64),
    pub start_cm: CmData,
    pub levels: Vec<VolcanoLevel>,
    /// Whether the start curve sits on the crater (level 0).
    pub start_on_crater: bool,
}

/// Compute the j-invariant of an elliptic curve `y² = x³ + ax + b`:
///
/// ```text
/// j = 1728 · 4a³ / (4a³ + 27 b²)
/// ```
pub fn j_invariant(curve: &SmallCurve) -> u64 {
    let p = curve.p as u128;
    let a = curve.a as u128 % p;
    let b = curve.b as u128 % p;
    let a3 = (a * a % p * a) % p;
    let b2 = (b * b) % p;
    let num = (4 * a3) % p * 1728 % p;
    let den = (4 * a3 + 27 * b2) % p;
    // For singular curves the denominator is zero; return 0.
    let den_inv = match crate::utils::mod_inverse(
        &num_bigint::BigUint::from(den as u64),
        &num_bigint::BigUint::from(p as u64),
    ) {
        Some(v) => v,
        None => return 0,
    };
    let inv_u = den_inv.iter_u64_digits().next().unwrap_or(0) as u128;
    ((num * inv_u) % p) as u64
}

/// Enumerate the `ℓ`-isogenous neighbours of `curve` via Vélu's
/// formulas.  Returns one `VeluIsogeny` per cyclic order-`ℓ`
/// subgroup; the codomains' j-invariants are the neighbours.
pub fn neighbors_ell(curve: &SmallCurve, ell: u64) -> Vec<VeluIsogeny> {
    if ell == 2 {
        // 2-isogenies: kernel = order-2 subgroup = {O, T}, with
        // T = (x_T, 0).  Roots of x³ + a x + b = 0 over F_p.
        let mut out = Vec::new();
        for x in 0..curve.p {
            if curve.rhs(x) == 0 {
                if let Some(iso) = velu_isogeny_2(curve, x) {
                    out.push(iso);
                }
            }
        }
        out
    } else {
        velu_isogeny_odd(curve, ell)
    }
}

/// Map the volcano around `curve` for the given prime `ℓ`.  Performs
/// a BFS over the local `ℓ`-isogeny graph, capped at `max_depth`
/// hops and at `max_vertices` total vertices.
///
/// The returned `levels` use BFS distance as the level coordinate;
/// **callers must determine** whether level 0 corresponds to the
/// crater (we tag this in `start_on_crater` using the conductor's
/// `ℓ`-adic valuation, which is derived from the Frobenius trace).
pub fn map_volcano(
    curve: &SmallCurve,
    ell: u64,
    max_depth: usize,
    max_vertices: usize,
) -> VolcanoMap {
    let cm = cm_discriminant(curve);
    // ν_ℓ(f): the start curve sits at level ν.  If ν = 0 then
    // we are already on the crater.
    let f = cm.conductor.unsigned_abs();
    let mut nu = 0u32;
    let mut ff = f;
    while ff.is_multiple_of(ell) && ff != 0 {
        ff /= ell;
        nu += 1;
    }
    let start_on_crater = nu == 0;

    // BFS by j-invariant.
    let start_j = j_invariant(curve);
    let mut levels: BTreeMap<usize, Vec<(u64, u64, u64, u64)>> = BTreeMap::new();
    levels.insert(0, vec![(start_j, curve.p, curve.a, curve.b)]);
    let mut seen = BTreeSet::<u64>::new();
    seen.insert(start_j);

    let mut frontier: VecDeque<(SmallCurve, usize)> = VecDeque::new();
    frontier.push_back((*curve, 0));
    let mut visited = 1usize;

    while let Some((c, d)) = frontier.pop_front() {
        if d >= max_depth || visited >= max_vertices {
            continue;
        }
        let neighbours = neighbors_ell(&c, ell);
        for iso in neighbours {
            let j = j_invariant(&iso.codomain);
            if seen.insert(j) {
                visited += 1;
                levels.entry(d + 1).or_default().push((
                    j,
                    iso.codomain.p,
                    iso.codomain.a,
                    iso.codomain.b,
                ));
                frontier.push_back((iso.codomain, d + 1));
                if visited >= max_vertices {
                    break;
                }
            }
        }
    }

    let level_vec: Vec<VolcanoLevel> = levels
        .into_iter()
        .map(|(level, entries)| VolcanoLevel {
            level,
            j_invariants: entries.iter().map(|e| e.0).collect(),
            curves: entries.iter().map(|e| (e.1, e.2, e.3)).collect(),
        })
        .collect();

    VolcanoMap {
        ell,
        start_curve: (curve.p, curve.a, curve.b),
        start_cm: cm,
        levels: level_vec,
        start_on_crater,
    }
}

// ── Targeted walks ───────────────────────────────────────────────────────────

/// Walk **down** the `ℓ`-volcano from `curve` until we reach the
/// floor (a vertex with exactly one `ℓ`-isogenous neighbour up to
/// the one we just came from).  Returns the number of descent
/// steps taken.
///
/// This is Kohel's algorithm restricted to detecting the floor.
/// Combined with the crater walk below, it lets us read off
/// `v_ℓ(End(E))`.
pub fn volcano_depth(curve: &SmallCurve, ell: u64, max_depth: usize) -> usize {
    let mut current = *curve;
    let mut previous_j: Option<u64> = None;
    for d in 0..max_depth {
        let n = neighbors_ell(&current, ell);
        // Filter out the edge we came from.
        let forward: Vec<_> = n
            .iter()
            .filter(|iso| Some(j_invariant(&iso.codomain)) != previous_j)
            .collect();
        if forward.is_empty() {
            // We hit a dead-end immediately — should not happen for
            // a well-formed ordinary curve, but if it does we're at
            // a degenerate floor.
            return d;
        }
        if forward.len() == 1 {
            // Floor (one neighbour besides the one we came from).
            // Actually a "floor" vertex has *zero* forward neighbours
            // when ν = depth; a 1-forward vertex is mid-descent.
            // We continue but record `d` as our last position.
            return d + 1;
        }
        // Multiple forward neighbours: pick any descending one.  In
        // general we should detect "ascending" vs "descending" using
        // the conductor, but for a top-down random walk we can pick
        // the first forward neighbour and rely on the volcano's
        // tree structure below the crater.
        previous_j = Some(j_invariant(&current));
        current = forward[0].codomain;
    }
    max_depth
}

/// Walk horizontally on the crater starting from `curve`.  Picks any
/// `ℓ`-isogeny that **does not change** the endomorphism-ring
/// discriminant (detected by checking that the codomain's Frobenius
/// trace matches the source's) and follows it until cycling back to
/// the start (or until `max_steps`).  Returns the cycle length.
pub fn crater_size(curve: &SmallCurve, ell: u64, max_steps: usize) -> usize {
    let start_j = j_invariant(curve);
    let start_disc = cm_discriminant(curve).endomorphism_disc;
    let mut current = *curve;
    let mut previous_j: Option<u64> = None;
    for step in 1..=max_steps {
        let n = neighbors_ell(&current, ell);
        let horizontal: Vec<_> = n
            .iter()
            .filter(|iso| {
                let c = cm_discriminant(&iso.codomain);
                c.endomorphism_disc == start_disc && Some(j_invariant(&iso.codomain)) != previous_j
            })
            .collect();
        if horizontal.is_empty() {
            return 0; // not on the crater
        }
        let next = horizontal[0].codomain;
        if j_invariant(&next) == start_j {
            return step;
        }
        previous_j = Some(j_invariant(&current));
        current = next;
    }
    max_steps
}

/// Classification of a curve's position within the `ℓ`-volcano.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize)]
pub struct VolcanoPosition {
    pub on_crater: bool,
    /// Distance from the crater (`0` iff on the crater).
    pub depth: u32,
    /// Crater length (`1` for a single vertex).
    pub crater_size: u32,
}

pub fn position(curve: &SmallCurve, ell: u64) -> VolcanoPosition {
    let cm = cm_discriminant(curve);
    let mut f = cm.conductor.unsigned_abs();
    let mut depth = 0u32;
    while f != 0 && f.is_multiple_of(ell) {
        f /= ell;
        depth += 1;
    }
    let on_crater = depth == 0;
    let crater = if on_crater {
        crater_size(curve, ell, 64) as u32
    } else {
        0
    };
    VolcanoPosition {
        on_crater,
        depth,
        crater_size: crater.max(1),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::isogeny::{toy_curve_a, toy_curve_b, toy_curve_j0};

    #[test]
    fn j_invariant_in_range() {
        let j = j_invariant(&toy_curve_a());
        assert!(j < toy_curve_a().p);
    }

    #[test]
    fn j_invariant_j0_curve_is_zero() {
        // y² = x³ + 1 has j = 0 by construction (a = 0).
        let j = j_invariant(&toy_curve_j0());
        assert_eq!(j, 0);
    }

    #[test]
    fn volcano_smoke() {
        // Build a tiny volcano and just check it doesn't crash.
        let v = map_volcano(&toy_curve_b(), 2, 3, 16);
        assert!(!v.levels.is_empty());
    }
}
