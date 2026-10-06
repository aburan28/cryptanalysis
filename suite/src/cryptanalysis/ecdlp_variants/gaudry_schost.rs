//! Gaudry–Schost ECDLP family (rows #6, #11, #15 of the
//! Galbraith–Wang–Zhang table).
//!
//! Gaudry–Schost (2004) is the low-memory, parallelisable counterpart
//! to baby-step/giant-step: instead of storing a `√n` table it runs
//! pseudo-random walks and detects a **tame/wild** collision at
//! *distinguished points* (DPs), like van Oorschot–Wiener rho but with
//! two colours of walker.  Expected `≈ 1.66√n` group operations.
//!
//! # State representation
//!
//! Every walker tracks a point together with a coefficient pair
//! `(u, v)` such that `R = uP + vQ`:
//!
//! - **tame** walkers start at `aP`, i.e. `(u, v) = (a, 0)`;
//! - **wild** walkers start at `Q + bP`, i.e. `(u, v) = (b, 1)`.
//!
//! An `r`-adding walk step `R ↦ R + s_{h(R)}P` adds a known constant
//! to `u`.  When a tame DP `(u₁, v₁)` and a wild DP `(u₂, v₂)` coincide
//! the points are equal, so `(u₁ − u₂)P = (v₂ − v₁)Q = (v₂−v₁)x·P` and
//!
//! ```text
//!     x = (u₁ − u₂) · (v₂ − v₁)⁻¹  (mod n).
//! ```
//!
//! The `(u, v)` form is what makes the **negation** variant (#11)
//! clean: folding `R` to its `±` representative just negates `(u, v)`,
//! and the same recovery formula still applies — no special-casing of
//! the unknown `x` in the wild walk.
//!
//! # The three variants
//!
//! - [`gaudry_schost`] (#6) — plain tame/wild DP collision search.
//! - [`gaudry_schost_negation`] (#11) — fold each step to the `±`
//!   representative (x-coordinate keyed DPs), halving the search
//!   space for a `≈ √2` speed-up.  Fruitless cycles are escaped by a
//!   per-walker step cap + fresh restart.
//! - [`gaudry_schost_montgomery`] (#15) — advance `B` walkers in
//!   lock-step and batch their per-step additions behind a single
//!   Montgomery-trick (`batch_invert`) inversion, so
//!   `field_inversions ≈ group_ops / B`.

use std::collections::HashMap;

use num_bigint::{BigUint, RandBigInt};
use num_traits::Zero;
use rand::rngs::StdRng;
use rand::SeedableRng;

use super::{key, sub_mod, xkey, DlpSolution, EcGroup};
use crate::ecc::point::Point;
use crate::utils::mod_inverse;

/// Tuning for the Gaudry–Schost walks.
#[derive(Clone, Debug)]
pub struct GaudrySchostOptions {
    /// A point is distinguished when the low `dp_bits` of its
    /// x-coordinate are zero (mean trail length `2^dp_bits`).  Keep it
    /// well below `½·log₂ n` so trails are short relative to `√n`.
    pub dp_bits: u8,
    /// Number of `r`-adding walk branches `R`.
    pub num_jumps: usize,
    /// Maximum walkers (restarts) before giving up.
    pub max_walkers: u64,
    /// Hard cap on steps per walker (escapes fruitless cycles / stuck
    /// walks); `0` ⇒ auto (`20·2^dp_bits`).
    pub max_steps_per_walker: u64,
    /// Lock-step block width for the Montgomery-trick variant (#15).
    pub block: usize,
    /// Deterministic RNG seed.
    pub seed: Option<u64>,
}

impl Default for GaudrySchostOptions {
    fn default() -> Self {
        Self {
            dp_bits: 4,
            num_jumps: 32,
            max_walkers: 1 << 22,
            max_steps_per_walker: 0,
            block: 32,
            seed: None,
        }
    }
}

/// Precomputed `r`-adding walk: branch points `s_k·P` and their known
/// scalars `s_k`.
struct Jumps {
    pts: Vec<Point>,
    scal: Vec<BigUint>,
}

impl Jumps {
    fn build(group: &EcGroup, r: usize, rng: &mut StdRng) -> Self {
        let n = group.order();
        let r = r.max(2);
        let mut pts = Vec::with_capacity(r);
        let mut scal = Vec::with_capacity(r);
        for _ in 0..r {
            // Non-zero branch scalars so every step actually moves.
            let mut s = rng.gen_biguint_below(n);
            if s.is_zero() {
                s = BigUint::from(1u32);
            }
            pts.push(group.mul_setup(&s));
            scal.push(s);
        }
        Self { pts, scal }
    }
    fn len(&self) -> usize {
        self.pts.len()
    }
}

/// Branch selector `h(R) ∈ [0, R)` from the x-coordinate's low byte.
fn branch(p: &Point, r: usize) -> usize {
    match p {
        Point::Affine { x, .. } => {
            let b = x.value.to_bytes_le();
            (*b.first().unwrap_or(&0) as usize) % r
        }
        Point::Infinity => 0,
    }
}

/// Distinguished-point test: low `dp_bits` of the x-coordinate zero.
fn is_dp(p: &Point, dp_mask: &BigUint) -> bool {
    match p {
        Point::Affine { x, .. } => (&x.value & dp_mask).is_zero(),
        Point::Infinity => false,
    }
}

/// Keep the `±` representative with `y ≤ (p−1)/2`.
fn needs_flip(p: &Point, field_p: &BigUint) -> bool {
    match p {
        Point::Affine { y, .. } => &(&y.value * 2u32) > field_p,
        Point::Infinity => false,
    }
}

/// One `r`-adding step, optionally folded to the `±` representative.
/// Returns `(R', u', v')` for `R = uP + vQ`.
fn step(
    group: &EcGroup,
    jumps: &Jumps,
    p: &Point,
    u: &BigUint,
    v: &BigUint,
    negate: bool,
) -> (Point, BigUint, BigUint) {
    let n = group.order();
    let idx = branch(p, jumps.len());
    let np = group.add(p, &jumps.pts[idx]);
    let nu = (u + &jumps.scal[idx]) % n;
    if negate && needs_flip(&np, &group.field_prime()) {
        let neg = group.neg(&np);
        (
            neg,
            sub_mod(&BigUint::zero(), &nu, n),
            sub_mod(&BigUint::zero(), v, n),
        )
    } else {
        (np, nu, v.clone())
    }
}

impl EcGroup {
    /// Field prime `p` (needed for the negation representative test).
    fn field_prime(&self) -> BigUint {
        self.p.clone()
    }
}

/// Fold a point to its `±` representative, carrying `(u, v)` along.
fn fold(
    group: &EcGroup,
    p: Point,
    u: BigUint,
    v: BigUint,
    negate: bool,
) -> (Point, BigUint, BigUint) {
    let n = group.order();
    if negate && needs_flip(&p, &group.field_prime()) {
        (
            group.neg(&p),
            sub_mod(&BigUint::zero(), &u, n),
            sub_mod(&BigUint::zero(), &v, n),
        )
    } else {
        (p, u, v)
    }
}

/// Recover `x` from a tame `(u_a, v_a)` and wild `(u_b, v_b)` meeting
/// at one point; `None` if the pair is degenerate or fails to verify.
fn recover(
    group: &EcGroup,
    q: &Point,
    a: (&BigUint, &BigUint),
    b: (&BigUint, &BigUint),
) -> Option<BigUint> {
    let n = group.order();
    let dv = sub_mod(b.1, a.1, n); // v_b − v_a
    if dv.is_zero() {
        return None;
    }
    let inv = mod_inverse(&dv, n)?;
    let du = sub_mod(a.0, b.0, n); // u_a − u_b
    let x = (du * inv) % n;
    if &group.mul_setup(&x) == q {
        Some(x)
    } else {
        None
    }
}

fn dp_mask(dp_bits: u8) -> BigUint {
    (BigUint::from(1u32) << dp_bits) - 1u32
}

fn trivial(q: &Point) -> Option<DlpSolution> {
    if matches!(q, Point::Infinity) {
        Some(DlpSolution {
            x: BigUint::zero(),
            group_ops: 0,
            field_inversions: 0,
            table_size: 0,
        })
    } else {
        None
    }
}

/// Shared driver for #6 (negate = false, exact DP key) and #11
/// (negate = true, x-coordinate DP key).
fn gaudry_schost_core(
    group: &EcGroup,
    q: &Point,
    opts: &GaudrySchostOptions,
    negate: bool,
) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let mut rng = StdRng::seed_from_u64(opts.seed.unwrap_or(0x6A53_C057_0F1E_1D2Eu64));
    let jumps = Jumps::build(group, opts.num_jumps, &mut rng);
    let mask = dp_mask(opts.dp_bits);
    let step_cap = if opts.max_steps_per_walker == 0 {
        20u64 << opts.dp_bits
    } else {
        opts.max_steps_per_walker
    };

    // Tame/wild DP tables keyed by point (or x-coordinate when folding).
    let mut tame: HashMap<Vec<u8>, (BigUint, BigUint)> = HashMap::new();
    let mut wild: HashMap<Vec<u8>, (BigUint, BigUint)> = HashMap::new();

    let dpkey = |p: &Point| -> Vec<u8> {
        if negate {
            xkey(p)
        } else {
            let (mut a, b) = key(p);
            a.push(0xFF);
            a.extend_from_slice(&b);
            a
        }
    };

    for w in 0..opts.max_walkers {
        let tame_walker = w % 2 == 0;
        // Random start in the chosen colour.
        let r0 = rng.gen_biguint_below(n);
        let (mut p, mut u, mut v) = if tame_walker {
            (group.mul_setup(&r0), r0.clone(), BigUint::zero())
        } else {
            (
                group.add_setup(q, &group.mul_setup(&r0)),
                r0.clone(),
                BigUint::from(1u32),
            )
        };
        if negate && needs_flip(&p, &group.field_prime()) {
            p = group.neg(&p);
            u = sub_mod(&BigUint::zero(), &u, n);
            v = sub_mod(&BigUint::zero(), &v, n);
        }

        let mut steps = 0u64;
        let mut last: Option<Point> = None;
        loop {
            if is_dp(&p, &mask) {
                let k = dpkey(&p);
                if tame_walker {
                    if let Some((ub, vb)) = wild.get(&k) {
                        if let Some(x) = recover(group, q, (&u, &v), (ub, vb)) {
                            return Ok(finish(group, x, tame.len() + wild.len()));
                        }
                    }
                    tame.entry(k).or_insert((u.clone(), v.clone()));
                } else {
                    if let Some((ua, va)) = tame.get(&k) {
                        if let Some(x) = recover(group, q, (ua, va), (&u, &v)) {
                            return Ok(finish(group, x, tame.len() + wild.len()));
                        }
                    }
                    wild.entry(k).or_insert((u.clone(), v.clone()));
                }
                break; // restart a fresh walker from a new colour/start
            }
            let (np, nu, nv) = step(group, &jumps, &p, &u, &v, negate);
            // Fruitless-cycle escape: under the negation map the walk
            // can fall into a 2-cycle `…→A→B→A→…`.  If the next point
            // is exactly where we were one step ago, break the symmetry
            // by *doubling* the current point instead.
            if negate && last.as_ref() == Some(&np) {
                let n = group.order();
                let dbl = group.dbl(&p);
                let (fp, fu, fv) = fold(group, dbl, (&u + &u) % n, (&v + &v) % n, true);
                last = Some(p.clone());
                p = fp;
                u = fu;
                v = fv;
            } else {
                last = Some(p.clone());
                p = np;
                u = nu;
                v = nv;
            }
            steps += 1;
            if steps > step_cap {
                break; // abandon a stuck / fruitless walker
            }
        }
    }
    Err("Gaudry–Schost: no tame/wild collision within walker budget")
}

fn finish(group: &EcGroup, x: BigUint, table_size: usize) -> DlpSolution {
    DlpSolution {
        x,
        group_ops: group.group_ops(),
        field_inversions: group.field_inversions(),
        table_size,
    }
}

/// **#6 — Gaudry–Schost.**  Tame/wild distinguished-point collision
/// search; low memory, `O(√n)` expected work.
pub fn gaudry_schost(
    group: &EcGroup,
    q: &Point,
    opts: &GaudrySchostOptions,
) -> Result<DlpSolution, &'static str> {
    gaudry_schost_core(group, q, opts, false)
}

/// **#11 — Gaudry–Schost with the negation map.**  Each step folds to
/// the `±` representative and DPs are keyed by x-coordinate, so the
/// effective search space is halved (`≈ √2` speed-up).  A per-walker
/// step cap escapes the fruitless 2-cycles the negation map can
/// induce.
pub fn gaudry_schost_negation(
    group: &EcGroup,
    q: &Point,
    opts: &GaudrySchostOptions,
) -> Result<DlpSolution, &'static str> {
    gaudry_schost_core(group, q, opts, true)
}

/// **#15 — Gaudry–Schost with Montgomery's trick.**  `B` walkers are
/// advanced in lock-step; every round performs one
/// [`batch_add`](EcGroup::batch_add), so the `B` affine additions of a
/// round share a single field inversion.  Result:
/// `field_inversions ≈ group_ops / B`, at the same `O(√n)` operation
/// count as #6.
pub fn gaudry_schost_montgomery(
    group: &EcGroup,
    q: &Point,
    opts: &GaudrySchostOptions,
) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let b = opts.block.max(1);
    let mut rng = StdRng::seed_from_u64(opts.seed.unwrap_or(0x15A2_77E5_0DB0_C0DEu64));
    let jumps = Jumps::build(group, opts.num_jumps, &mut rng);
    let mask = dp_mask(opts.dp_bits);
    let step_cap = if opts.max_steps_per_walker == 0 {
        20u64 << opts.dp_bits
    } else {
        opts.max_steps_per_walker
    };

    let mut tame: HashMap<Vec<u8>, (BigUint, BigUint)> = HashMap::new();
    let mut wild: HashMap<Vec<u8>, (BigUint, BigUint)> = HashMap::new();
    let dpkey = |p: &Point| -> Vec<u8> {
        let (mut a, c) = key(p);
        a.push(0xFF);
        a.extend_from_slice(&c);
        a
    };

    // Per-lane walker state.
    struct Lane {
        p: Point,
        u: BigUint,
        v: BigUint,
        tame: bool,
        steps: u64,
    }
    let spawn = |rng: &mut StdRng, tame: bool| -> Lane {
        let r0 = rng.gen_biguint_below(n);
        if tame {
            Lane {
                p: group.mul_setup(&r0),
                u: r0,
                v: BigUint::zero(),
                tame: true,
                steps: 0,
            }
        } else {
            Lane {
                p: group.add_setup(q, &group.mul_setup(&r0)),
                u: r0,
                v: BigUint::from(1u32),
                tame: false,
                steps: 0,
            }
        }
    };

    let mut lanes: Vec<Lane> = (0..b).map(|i| spawn(&mut rng, i % 2 == 0)).collect();
    let mut walkers_spawned = b as u64;

    let max_rounds = opts.max_walkers; // generous round budget
    for _round in 0..max_rounds {
        // Batch the B per-lane additions behind one inversion.
        let idxs: Vec<usize> = lanes.iter().map(|l| branch(&l.p, jumps.len())).collect();
        let pairs: Vec<(Point, Point)> = lanes
            .iter()
            .zip(&idxs)
            .map(|(l, &i)| (l.p.clone(), jumps.pts[i].clone()))
            .collect();
        let nexts = group.batch_add(&pairs);

        for r in 0..lanes.len() {
            lanes[r].p = nexts[r].clone();
            lanes[r].u = (&lanes[r].u + &jumps.scal[idxs[r]]) % n;
            lanes[r].steps += 1;

            if is_dp(&lanes[r].p, &mask) {
                let k = dpkey(&lanes[r].p);
                let (u, v) = (lanes[r].u.clone(), lanes[r].v.clone());
                if lanes[r].tame {
                    if let Some((ub, vb)) = wild.get(&k) {
                        if let Some(x) = recover(group, q, (&u, &v), (ub, vb)) {
                            return Ok(finish(group, x, tame.len() + wild.len()));
                        }
                    }
                    tame.entry(k).or_insert((u, v));
                } else {
                    if let Some((ua, va)) = tame.get(&k) {
                        if let Some(x) = recover(group, q, (ua, va), (&u, &v)) {
                            return Ok(finish(group, x, tame.len() + wild.len()));
                        }
                    }
                    wild.entry(k).or_insert((u, v));
                }
                let tame = lanes[r].tame;
                lanes[r] = spawn(&mut rng, tame);
                walkers_spawned += 1;
            } else if lanes[r].steps > step_cap {
                let tame = lanes[r].tame;
                lanes[r] = spawn(&mut rng, tame);
                walkers_spawned += 1;
            }
        }
        if walkers_spawned > opts.max_walkers {
            break;
        }
    }
    Err("Gaudry–Schost (Montgomery): no collision within budget")
}

#[cfg(test)]
mod tests {
    use super::super::{demo_group_mid, demo_group_small};
    use super::*;

    fn opts_small() -> GaudrySchostOptions {
        GaudrySchostOptions {
            dp_bits: 3,
            num_jumps: 24,
            seed: Some(0xA11CE),
            ..Default::default()
        }
    }

    #[test]
    fn gaudry_schost_recovers_small() {
        let g = demo_group_small();
        for &x in &[1u64, 2, 4242, 9999, 10038] {
            let q = g.mul_setup(&BigUint::from(x));
            let sol = gaudry_schost(&g, &q, &opts_small()).unwrap();
            assert_eq!(sol.x, BigUint::from(x), "plain GS x={x}");
        }
    }

    #[test]
    fn gaudry_schost_negation_recovers_small() {
        let g = demo_group_small();
        for &x in &[3u64, 555, 7777, 10000] {
            let q = g.mul_setup(&BigUint::from(x));
            let sol = gaudry_schost_negation(&g, &q, &opts_small()).unwrap();
            assert_eq!(sol.x, BigUint::from(x), "negation GS x={x}");
        }
    }

    #[test]
    fn gaudry_schost_montgomery_recovers_small() {
        let g = demo_group_small();
        let opts = GaudrySchostOptions {
            dp_bits: 3,
            num_jumps: 24,
            block: 16,
            seed: Some(0xB0B),
            ..Default::default()
        };
        for &x in &[9u64, 1234, 8888] {
            let q = g.mul_setup(&BigUint::from(x));
            let sol = gaudry_schost_montgomery(&g, &q, &opts).unwrap();
            assert_eq!(sol.x, BigUint::from(x), "Montgomery GS x={x}");
            // Batching keeps inversions well below the op count.
            assert!(
                sol.field_inversions * 4 < sol.group_ops,
                "inversions {} not ≪ ops {}",
                sol.field_inversions,
                sol.group_ops
            );
        }
    }

    #[test]
    fn gaudry_schost_zero_log() {
        let g = demo_group_small();
        let q = Point::Infinity;
        assert!(gaudry_schost(&g, &q, &opts_small()).unwrap().x.is_zero());
        assert!(gaudry_schost_negation(&g, &q, &opts_small())
            .unwrap()
            .x
            .is_zero());
    }

    #[test]
    fn gaudry_schost_mid_curve() {
        let g = demo_group_mid();
        let opts = GaudrySchostOptions {
            dp_bits: 4,
            num_jumps: 32,
            seed: Some(0xC0FFEE),
            ..Default::default()
        };
        let q = g.mul_setup(&BigUint::from(73_313u32));
        assert_eq!(
            gaudry_schost(&g, &q, &opts).unwrap().x,
            BigUint::from(73_313u32)
        );
        assert_eq!(
            gaudry_schost_negation(&g, &q, &opts).unwrap().x,
            BigUint::from(73_313u32)
        );
    }
}
