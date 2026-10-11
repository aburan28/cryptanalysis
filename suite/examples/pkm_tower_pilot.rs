//! **Design-validation pilot for the PKM tower oracle.**
//!
//! `research/notes/index-calculus/RESEARCH_PKM_TOWER_ORACLE.md` designs an
//! algebraic decomposition oracle for prime-field curves on
//! Petit–Kosters–Messeng tower factor bases, and pre-registers (§5.2) the one
//! measurement that decides whether to build it: how the F4 solving degree
//! of a tower system grows with the number of tower unknowns `N = m·t`.
//! This example runs a small subset of those cells with the repository's
//! degree-bounded F4 (`f4_fp`), with the §5.3 controls that fit a pilot:
//!
//! - `tower`: PKM's system, i.e. `S₃` (or the `S₃` chain at `m ≥ 3`) plus
//!   the tower equations, raw presentation;
//! - `ladder`: the same system plus `g − 1` random quadrics that vanish at
//!   the planted solution (the generator-count ladder, instrument power);
//! - `naive`: the same `V`, membership as one univariate `x^{2^t} = g^{2^t}`
//!   (Kummer only);
//! - `null`: `S₃`'s monomial support with random coefficients and a
//!   planted zero, under the same tower.
//!
//! Every tower, every Vélu map and every planted decomposition is checked
//! before anything is measured, so a construction bug stops the run instead
//! of reading as a degree.
//!
//! It is a stage diagnostic of the solver axis (`AGENTS.md` §2): it prices
//! no pipeline, reports no `S`, and decides nothing on its own. Stage A of
//! the note decides, on its full ladder.
//!
//! `--engine tower` runs the same systems on the sparse tower engine
//! `f4_fp_tower` instead (note §11): the tower equations become its
//! rewriting rules, the other equations its input in normal form (the
//! `reduced` presentation), and the naive control, which has no tower, is
//! skipped. `--max-nnz` stops a system whose matrices grow past a size, and
//! `--trace` prints its step trace.
//!
//! The committed runs, their exact flags and the scripts that tabulate and
//! cross-check them are in `research/pkm_tower_pilot_20260924/` (the pilot,
//! `f4_fp`) and `research/pkm_tower_round2_20260925/` (round 2,
//! `f4_fp_tower`).
//!
//! ```bash
//! cargo run --release --example pkm_tower_pilot -- --out pilot.jsonl
//! cargo run --release --example pkm_tower_pilot -- --kinds kummer --max-t 6 --budget 30
//! # What F4 knows at degree 4 on one N = 16 system: its basis elements of
//! # degree at most 3 (`--cap` bounds the degree, `--dump` prints the basis).
//! cargo run --release --example pkm_tower_pilot -- --kinds kummer --m 2 --controls tower \
//!     --t-min 8 --max-t 8 --planted 0 --random 1 --cap 4 --dump 3 --ladder-t none
//! # The same system on the tower engine, with its step trace.
//! cargo run --release --example pkm_tower_pilot -- --engine tower --kinds kummer --m 2 \
//!     --controls tower --t-min 8 --max-t 8 --planted 0 --random 1 --ladder-t none --trace
//! ```

use std::collections::BTreeMap;
use std::fs::File;
use std::io::Write;
use std::time::{Duration, Instant};

use cryptanalysis_suite::cryptanalysis::f4_fp::{self, F4Options, F4Report, Ordering, Poly};
use cryptanalysis_suite::cryptanalysis::f4_fp_tower::{
    self, RPoly, SquareRule, TowerF4Options, TowerRing,
};
use cryptanalysis_suite::cryptanalysis::ic_boundary::{
    CountedGroup, GroupOps, PrimeCurve, PrimePoint,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::{json, Value};

// ── Field arithmetic ───────────────────────────────────────────────

fn mulm(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn addm(a: u64, b: u64, p: u64) -> u64 {
    (a + b) % p
}

fn subm(a: u64, b: u64, p: u64) -> u64 {
    (a + p - b % p) % p
}

fn powm(mut a: u64, mut e: u64, p: u64) -> u64 {
    let mut r = 1u64;
    a %= p;
    while e > 0 {
        if e & 1 == 1 {
            r = mulm(r, a, p);
        }
        a = mulm(a, a, p);
        e >>= 1;
    }
    r
}

fn invm(a: u64, p: u64) -> u64 {
    assert!(!a.is_multiple_of(p), "inverse of zero");
    powm(a, p - 2, p)
}

// ── Polynomials while building a system ────────────────────────────

/// A polynomial over `F_p` in `n` variables, as a map from exponent
/// vectors to non-zero coefficients.
#[derive(Clone, Debug)]
struct Pol {
    n: usize,
    terms: BTreeMap<Vec<u32>, u64>,
}

impl Pol {
    fn zero(n: usize) -> Self {
        Pol {
            n,
            terms: BTreeMap::new(),
        }
    }

    fn constant(n: usize, c: u64, p: u64) -> Self {
        let mut f = Pol::zero(n);
        if !c.is_multiple_of(p) {
            f.terms.insert(vec![0; n], c % p);
        }
        f
    }

    fn var(n: usize, i: usize) -> Self {
        let mut e = vec![0; n];
        e[i] = 1;
        let mut f = Pol::zero(n);
        f.terms.insert(e, 1);
        f
    }

    fn add(&self, o: &Pol, p: u64) -> Pol {
        let mut f = self.clone();
        for (e, c) in &o.terms {
            let v = f.terms.entry(e.clone()).or_insert(0);
            *v = addm(*v, *c, p);
        }
        f.terms.retain(|_, c| *c != 0);
        f
    }

    fn scale(&self, k: u64, p: u64) -> Pol {
        let mut f = Pol::zero(self.n);
        for (e, c) in &self.terms {
            let v = mulm(*c, k, p);
            if v != 0 {
                f.terms.insert(e.clone(), v);
            }
        }
        f
    }

    fn sub(&self, o: &Pol, p: u64) -> Pol {
        self.add(&o.scale(p - 1, p), p)
    }

    fn mul(&self, o: &Pol, p: u64) -> Pol {
        let mut f = Pol::zero(self.n);
        for (e1, c1) in &self.terms {
            for (e2, c2) in &o.terms {
                let e: Vec<u32> = e1.iter().zip(e2).map(|(a, b)| a + b).collect();
                let v = f.terms.entry(e).or_insert(0);
                *v = addm(*v, mulm(*c1, *c2, p), p);
            }
        }
        f.terms.retain(|_, c| *c != 0);
        f
    }

    fn eval(&self, x: &[u64], p: u64) -> u64 {
        let mut acc = 0u64;
        for (e, c) in &self.terms {
            let mut t = *c;
            for (i, k) in e.iter().enumerate() {
                if *k > 0 {
                    t = mulm(t, powm(x[i], *k as u64, p), p);
                }
            }
            acc = addm(acc, t, p);
        }
        acc
    }

    fn degree(&self) -> u32 {
        self.terms
            .keys()
            .map(|e| e.iter().sum::<u32>())
            .max()
            .unwrap_or(0)
    }

    fn to_poly(&self, p: u64) -> Poly {
        let terms: Vec<(Vec<u32>, u64)> = self.terms.iter().map(|(e, c)| (e.clone(), *c)).collect();
        f4_fp::normalise(&terms, p, Ordering::Grevlex)
    }
}

/// Semaev's third summation polynomial for `y² = x³ + ax + b`, on three
/// polynomial arguments:
/// `(X1 − X2)²X3² − 2((X1 + X2)(X1X2 + a) + 2b)X3 + (X1X2 − a)² − 4b(X1 + X2)`.
fn s3(x1: &Pol, x2: &Pol, x3: &Pol, a: u64, b: u64, p: u64) -> Pol {
    let n = x1.n;
    let d = x1.sub(x2, p);
    let t1 = d.mul(&d, p).mul(x3, p).mul(x3, p);
    let s = x1.add(x2, p);
    let pr = x1.mul(x2, p);
    let inner = s
        .mul(&pr.add(&Pol::constant(n, a, p), p), p)
        .add(&Pol::constant(n, mulm(2, b, p), p), p);
    let t2 = inner.mul(x3, p).scale(p - 2, p);
    let q = pr.sub(&Pol::constant(n, a, p), p);
    let t3 = q.mul(&q, p).sub(&s.scale(mulm(4, b, p), p), p);
    t1.add(&t2, p).add(&t3, p)
}

// ── Towers ─────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    Kummer,
    Dickson,
    Isogeny,
}

impl Kind {
    fn name(self) -> &'static str {
        match self {
            Kind::Kummer => "kummer",
            Kind::Dickson => "dickson",
            Kind::Isogeny => "isogeny",
        }
    }
}

/// One level of a tower: how `y_{j+1}` (or the final constant) follows
/// from `y_j`.
#[derive(Clone, Copy, Debug)]
enum Step {
    /// `y_{j+1} = y_j²` (Kummer).
    Square,
    /// `y_{j+1} = y_j² − 2` (Dickson `D_2`).
    Dickson,
    /// `y_{j+1} = y_j + τ/(y_j − ξ)`, the x-map of a 2-isogeny with
    /// kernel `(ξ, 0)`.
    Velu { xi: u64, tau: u64 },
}

struct Tower {
    kind: Kind,
    t: usize,
    /// The factor-base abscissa set, `2^t` distinct elements of `F_p`.
    v: Vec<u64>,
    /// `x = scale · y_0` (Kummer: the coset representative `g`).
    scale: u64,
    steps: Vec<Step>,
    /// The value the last step must reach.
    c: u64,
    info: Value,
}

impl Tower {
    fn apply(&self, j: usize, y: u64, p: u64) -> u64 {
        match self.steps[j] {
            Step::Square => mulm(y, y, p),
            Step::Dickson => subm(mulm(y, y, p), 2, p),
            Step::Velu { xi, tau } => addm(y, mulm(tau, invm(subm(y, xi, p), p), p), p),
        }
    }

    /// `y_0 … y_{t−1}` for an abscissa of `V`.
    fn values(&self, x: u64, p: u64) -> Vec<u64> {
        let mut y = vec![0u64; self.t];
        y[0] = mulm(x, invm(self.scale, p), p);
        for j in 0..self.t - 1 {
            y[j + 1] = self.apply(j, y[j], p);
        }
        y
    }

    /// The `t` equations of one block whose variables start at `base`.
    fn equations(&self, n: usize, base: usize, p: u64) -> Vec<Pol> {
        (0..self.t)
            .map(|j| {
                let yj = Pol::var(n, base + j);
                let next = if j + 1 < self.t {
                    Pol::var(n, base + j + 1)
                } else {
                    Pol::constant(n, self.c, p)
                };
                let sq = yj.mul(&yj, p);
                match self.steps[j] {
                    Step::Square => next.sub(&sq, p),
                    Step::Dickson => next.sub(&sq.sub(&Pol::constant(n, 2, p), p), p),
                    Step::Velu { xi, tau } => {
                        let lhs = next.mul(&yj.sub(&Pol::constant(n, xi, p), p), p);
                        let rhs = sq
                            .sub(&yj.scale(xi, p), p)
                            .add(&Pol::constant(n, tau, p), p);
                        lhs.sub(&rhs, p)
                    }
                }
            })
            .collect()
    }

    /// The tower equations of one block (variables from `base`) as the
    /// square rules of [`f4_fp_tower`]: each equation solved for `y_j²`.
    fn square_rules(&self, base: usize, p: u64) -> Vec<SquareRule> {
        (0..self.t)
            .map(|j| {
                let top = j + 1 == self.t;
                let next = (!top).then_some((base + j + 1) as u8);
                match (self.steps[j], top) {
                    // y_{j+1} = y_j²; on top, y_j² = c
                    (Step::Square, false) => SquareRule {
                        next,
                        a: 0,
                        b: 1,
                        c: 0,
                        d: 0,
                    },
                    (Step::Square, true) => SquareRule {
                        next,
                        a: 0,
                        b: 0,
                        c: 0,
                        d: self.c % p,
                    },
                    // y_{j+1} = y_j² − 2; on top, y_j² = c + 2
                    (Step::Dickson, false) => SquareRule {
                        next,
                        a: 0,
                        b: 1,
                        c: 0,
                        d: 2 % p,
                    },
                    (Step::Dickson, true) => SquareRule {
                        next,
                        a: 0,
                        b: 0,
                        c: 0,
                        d: addm(self.c, 2, p),
                    },
                    // y_{j+1}(y_j − ξ) = y_j² − ξ·y_j + τ, so
                    // y_j² = y_j·y_{j+1} − ξ·y_{j+1} + ξ·y_j − τ
                    (Step::Velu { xi, tau }, false) => SquareRule {
                        next,
                        a: 1,
                        b: subm(0, xi, p),
                        c: xi,
                        d: subm(0, tau, p),
                    },
                    // c·(y_j − ξ) = y_j² − ξ·y_j + τ, so
                    // y_j² = (c + ξ)·y_j − (c·ξ + τ)
                    (Step::Velu { xi, tau }, true) => SquareRule {
                        next,
                        a: 0,
                        b: 0,
                        c: addm(self.c, xi, p),
                        d: subm(0, addm(mulm(self.c, xi, p), tau, p), p),
                    },
                }
            })
            .collect()
    }

    /// Every element of `V` satisfies the tower, `|V| = 2^t` and the
    /// elements are distinct.  Panics otherwise: a wrong tower would make
    /// every degree below meaningless.
    fn check(&self, p: u64) {
        let mut sorted = self.v.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), 1 << self.t, "{:?}: V has repeats", self.kind);
        let n = self.t;
        let eqs = self.equations(n, 0, p);
        for &x in &self.v {
            let y = self.values(x, p);
            for (j, e) in eqs.iter().enumerate() {
                assert_eq!(
                    e.eval(&y, p),
                    0,
                    "{:?}: level {j} fails at x = {x}",
                    self.kind
                );
            }
        }
    }
}

/// An element of exact order `2^t` in `F_p^*`.
fn root_of_unity(p: u64, t: usize, rng: &mut StdRng) -> u64 {
    assert!(
        (p - 1).is_multiple_of(1u64 << t),
        "2^{t} does not divide p − 1"
    );
    loop {
        let h = rng.gen_range(2..p);
        if powm(h, (p - 1) / 2, p) == p - 1 {
            return powm(h, (p - 1) >> t, p);
        }
    }
}

fn kummer(p: u64, t: usize, rng: &mut StdRng) -> Tower {
    let zeta = root_of_unity(p, t, rng);
    let g = rng.gen_range(2..p);
    let v: Vec<u64> = (0..1u64 << t)
        .map(|k| mulm(g, powm(zeta, k, p), p))
        .collect();
    Tower {
        kind: Kind::Kummer,
        t,
        v,
        scale: g,
        steps: vec![Step::Square; t],
        c: 1,
        info: json!({"g": g, "zeta": zeta}),
    }
}

fn dickson(p: u64, t: usize, rng: &mut StdRng) -> Tower {
    let zeta = root_of_unity(p, t, rng);
    loop {
        let u = rng.gen_range(2..p);
        if powm(u, 1u64 << (t + 1), p) == 1 {
            continue;
        }
        let v: Vec<u64> = (0..1u64 << t)
            .map(|k| {
                let w = mulm(u, powm(zeta, k, p), p);
                addm(w, invm(w, p), p)
            })
            .collect();
        let mut s = v.clone();
        s.sort_unstable();
        s.dedup();
        if s.len() != 1 << t {
            continue;
        }
        let ut = powm(u, 1u64 << t, p);
        return Tower {
            kind: Kind::Dickson,
            t,
            v,
            scale: 1,
            steps: vec![Step::Dickson; t],
            c: addm(ut, invm(ut, p), p),
            info: json!({"u": u, "zeta": zeta}),
        };
    }
}

fn random_point(curve: &PrimeCurve, rng: &mut StdRng) -> PrimePoint {
    loop {
        let x = rng.gen_range(0..curve.p);
        let r = curve.rhs(x);
        if r == 0 {
            continue;
        }
        if let Some(y) = curve.sqrt(r) {
            let y = if rng.gen::<bool>() { y } else { curve.p - y };
            return PrimePoint::affine(x, y);
        }
    }
}

/// The 2-isogeny with kernel `(ξ, 0)`, on a point (Vélu).
fn velu_map(pt: PrimePoint, xi: u64, tau: u64, p: u64) -> PrimePoint {
    if pt.infinity || pt.x == xi {
        return PrimePoint::INFINITY;
    }
    let d = invm(subm(pt.x, xi, p), p);
    let x = addm(pt.x, mulm(tau, d, p), p);
    let y = mulm(pt.y, subm(1, mulm(tau, mulm(d, d, p), p), p), p);
    PrimePoint::affine(x, y)
}

fn nonsingular(a: u64, b: u64, p: u64) -> bool {
    let d = addm(
        mulm(4, mulm(mulm(a, a, p), a, p), p),
        mulm(27, mulm(b, b, p), p),
        p,
    );
    d != 0
}

/// A tower of 2-isogenies on an auxiliary curve `E'` with a rational
/// point `Q` of order `2^t`; `V = x(R' + ⟨Q⟩)`.  The search for `E'` is
/// the per-curve precomputation the oracle's base charges; here it is
/// only reported.
fn isogeny(p: u64, t: usize, rng: &mut StdRng) -> Tower {
    let two_t = 1u64 << t;
    let mut ops = GroupOps::default();
    let mut curves_tried = 0u64;
    loop {
        curves_tried += 1;
        let a = rng.gen_range(0..p);
        let b = rng.gen_range(1..p);
        if !nonsingular(a, b, p) {
            continue;
        }
        let e = PrimeCurve { p, a, b };
        let n = e.point_count();
        if !n.is_multiple_of(two_t) {
            continue;
        }
        // Q of exact order 2^t.
        let mut q = None;
        for _ in 0..16 {
            let cand = e.mul(&mut ops, random_point(&e, rng), n / two_t);
            let half = e.mul(&mut ops, cand, two_t / 2);
            if !half.infinity && e.mul(&mut ops, cand, two_t).infinity {
                q = Some(cand);
                break;
            }
        }
        let Some(q) = q else { continue };
        let multiples: Vec<PrimePoint> = (0..two_t).map(|k| e.mul(&mut ops, q, k)).collect();
        // R' with 2R' outside <Q>, so R' + <Q> and its negative are disjoint.
        let r0 = loop {
            let r = random_point(&e, rng);
            let r2 = e.double(&mut ops, r);
            if !multiples.contains(&r2) {
                break r;
            }
        };
        let v: Vec<u64> = multiples
            .iter()
            .map(|&m| e.add(&mut ops, r0, m))
            .filter(|pt| !pt.infinity)
            .map(|pt| pt.x)
            .collect();
        let mut s = v.clone();
        s.sort_unstable();
        s.dedup();
        if s.len() != two_t as usize {
            continue;
        }
        // The chain: kernel of step j is [2^{t−1−j}] Q_j on E'_j.
        let (mut aj, mut bj) = (a, b);
        let (mut qj, mut rj) = (q, r0);
        let mut steps = Vec::with_capacity(t);
        for j in 0..t {
            let cj = PrimeCurve { p, a: aj, b: bj };
            let kj = cj.mul(&mut ops, qj, 1u64 << (t - 1 - j));
            assert!(
                !kj.infinity && kj.y == 0,
                "step {j}: kernel point is not 2-torsion"
            );
            let xi = kj.x;
            let tau = addm(mulm(3, mulm(xi, xi, p), p), aj, p);
            steps.push(Step::Velu { xi, tau });
            qj = velu_map(qj, xi, tau, p);
            rj = velu_map(rj, xi, tau, p);
            aj = subm(aj, mulm(5, tau, p), p);
            bj = subm(bj, mulm(7, mulm(xi, tau, p), p), p);
            let next = PrimeCurve { p, a: aj, b: bj };
            assert!(
                next.is_on_curve(qj),
                "step {j}: Vélu image of Q is off the codomain"
            );
            assert!(
                next.is_on_curve(rj),
                "step {j}: Vélu image of R' is off the codomain"
            );
        }
        // V itself, since it cannot be rebuilt from two numbers: the
        // exhaustive cross-check (`verify.py`) needs it.
        let info = json!({"aux_a": a, "aux_b": b, "aux_order": n, "aux_curves_tried": curves_tried, "v": &v});
        return Tower {
            kind: Kind::Isogeny,
            t,
            v,
            scale: 1,
            steps,
            c: rj.x,
            info,
        };
    }
}

fn build_tower(kind: Kind, p: u64, t: usize, rng: &mut StdRng) -> Tower {
    let tower = match kind {
        Kind::Kummer => kummer(p, t, rng),
        Kind::Dickson => dickson(p, t, rng),
        Kind::Isogeny => isogeny(p, t, rng),
    };
    tower.check(p);
    tower
}

// ── Targets ────────────────────────────────────────────────────────

/// A target and, when planted, the full solution of its system.
struct Target {
    planted: bool,
    x_r: u64,
    /// Values of every variable at the planted solution.
    solution: Option<Vec<u64>>,
    /// The planted abscissae, for the naive control.
    xs: Vec<u64>,
}

/// Plant `R = P_1 + … + P_m` over distinct base abscissae with random
/// signs; `None` when the partial sums hit the identity.
fn plant(
    curve: &PrimeCurve,
    tower: &Tower,
    m: usize,
    on: &[u64],
    rng: &mut StdRng,
) -> Option<Target> {
    let p = curve.p;
    let mut ops = GroupOps::default();
    let mut pick: Vec<u64> = Vec::with_capacity(m);
    while pick.len() < m {
        let x = on[rng.gen_range(0..on.len())];
        if !pick.contains(&x) {
            pick.push(x);
        }
    }
    let pts: Vec<PrimePoint> = pick
        .iter()
        .map(|&x| {
            let y = curve.sqrt(curve.rhs(x)).expect("abscissa on the curve");
            PrimePoint::affine(x, if rng.gen::<bool>() { y } else { p - y })
        })
        .collect();
    let mut acc = pts[0];
    let mut partial = Vec::new();
    for pt in &pts[1..] {
        acc = curve.add(&mut ops, acc, *pt);
        if acc.infinity {
            return None;
        }
        partial.push(acc.x);
    }
    let x_r = acc.x;
    let t = tower.t;
    let mut sol = vec![0u64; m * t + (m - 2)];
    for (i, &x) in pick.iter().enumerate() {
        sol[i * t..(i + 1) * t].copy_from_slice(&tower.values(x, p));
    }
    // The chain's free unknowns are the partial-sum abscissae x(P_1 + … + P_{k+1}).
    for k in 0..m - 2 {
        sol[m * t + k] = partial[k];
    }
    Some(Target {
        planted: true,
        x_r,
        solution: Some(sol),
        xs: pick,
    })
}

fn random_target(curve: &PrimeCurve, rng: &mut StdRng) -> Target {
    let x_r = random_point(curve, rng).x;
    Target {
        planted: false,
        x_r,
        solution: None,
        xs: Vec::new(),
    }
}

// ── Systems ────────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Control {
    Tower,
    Ladder,
    Naive,
    Null,
}

impl Control {
    fn name(self) -> &'static str {
        match self {
            Control::Tower => "tower",
            Control::Ladder => "ladder",
            Control::Naive => "naive",
            Control::Null => "null",
        }
    }
}

/// The summation part: `S₃(x_1, x_2, x_R)` at `m = 2`; for `m ≥ 3` the
/// chain `S₃(x_1, x_2, u_1)`, `S₃(u_k, x_{k+2}, u_{k+1})`,
/// `S₃(u_{m−2}, x_m, x_R)`, whose free unknowns `u_k` are the abscissae of
/// the partial sums.
fn summation(tower: &Tower, curve: &PrimeCurve, m: usize, n: usize, x_r: u64) -> Vec<Pol> {
    let p = curve.p;
    let (a, b) = (curve.a, curve.b);
    let x = |i: usize| Pol::var(n, i * tower.t).scale(tower.scale, p);
    let xr = Pol::constant(n, x_r, p);
    if m == 2 {
        return vec![s3(&x(0), &x(1), &xr, a, b, p)];
    }
    let u = |k: usize| Pol::var(n, m * tower.t + k);
    let mut eqs = vec![s3(&x(0), &x(1), &u(0), a, b, p)];
    for k in 1..m - 2 {
        eqs.push(s3(&u(k - 1), &x(k + 1), &u(k), a, b, p));
    }
    eqs.push(s3(&u(m - 3), &x(m - 1), &xr, a, b, p));
    eqs
}

/// A random polynomial of degree at most two in `n` variables that
/// vanishes at `at`.
fn random_quadric(n: usize, at: &[u64], p: u64, rng: &mut StdRng) -> Pol {
    let mut f = Pol::zero(n);
    for i in 0..n {
        for j in i..n {
            let mut e = vec![0u32; n];
            e[i] += 1;
            e[j] += 1;
            f.terms.insert(e, rng.gen_range(1..p));
        }
        let mut e = vec![0u32; n];
        e[i] = 1;
        f.terms.insert(e, rng.gen_range(1..p));
    }
    let c = f.eval(at, p);
    f.sub(&Pol::constant(n, c, p), p)
}

/// The system for one (control, target), with its number of variables
/// and the planted solution in that system's variables.
fn system(
    control: Control,
    tower: &Tower,
    curve: &PrimeCurve,
    m: usize,
    target: &Target,
    g: usize,
    rng: &mut StdRng,
) -> (Vec<Pol>, usize, Option<Vec<u64>>, std::ops::Range<usize>) {
    let p = curve.p;
    let t = tower.t;
    if control == Control::Naive {
        // Two unknowns x_1, x_2 and one univariate membership each.
        assert_eq!(m, 2);
        let n = 2;
        let k = 1u64 << t;
        let member = |i: usize| {
            let xi = Pol::var(n, i);
            let mut pw = Pol::constant(n, 1, p);
            for _ in 0..k {
                pw = pw.mul(&xi, p);
            }
            pw.sub(&Pol::constant(n, powm(tower.scale, k, p), p), p)
        };
        let s = s3(
            &Pol::var(n, 0),
            &Pol::var(n, 1),
            &Pol::constant(n, target.x_r, p),
            curve.a,
            curve.b,
            p,
        );
        let sol = target.planted.then(|| target.xs.clone());
        return (vec![s, member(0), member(1)], n, sol, 0..0);
    }
    let n = m * t + (m - 2);
    let mut eqs = summation(tower, curve, m, n, target.x_r);
    if control == Control::Null {
        // S₃'s support, random coefficients, planted zero.
        assert_eq!(m, 2);
        let mut f = Pol::zero(n);
        for e in eqs[0].terms.keys() {
            f.terms.insert(e.clone(), rng.gen_range(1..p));
        }
        if let Some(sol) = &target.solution {
            let c = f.eval(sol, p);
            f = f.sub(&Pol::constant(n, c, p), p);
        }
        eqs[0] = f;
    }
    let towers_from = eqs.len();
    for i in 0..m {
        eqs.extend(tower.equations(n, i * t, p));
    }
    let towers = towers_from..eqs.len();
    if control == Control::Ladder {
        let sol = target
            .solution
            .as_ref()
            .expect("the ladder runs on planted targets");
        for _ in 1..g {
            eqs.push(random_quadric(n, sol, p, rng));
        }
    }
    (eqs, n, target.solution.clone(), towers)
}

// ── Measuring ──────────────────────────────────────────────────────

struct Measured {
    report: F4Report,
    planted_ok: Option<bool>,
    zero_dim: bool,
    linear: usize,
}

fn measure(
    eqs: &[Pol],
    n: usize,
    p: u64,
    sol: Option<&[u64]>,
    max_degree: u32,
    budget: Duration,
    stop_below: Option<usize>,
) -> Measured {
    if let Some(s) = sol {
        for (k, e) in eqs.iter().enumerate() {
            assert_eq!(
                e.eval(s, p),
                0,
                "equation {k} does not vanish at the planted solution"
            );
        }
    }
    let input: Vec<Poly> = eqs
        .iter()
        .map(|e| e.to_poly(p))
        .filter(|f| !f.is_empty())
        .collect();
    // Optionally stop once at most `stop_below` candidate points remain: the
    // steps after that only certify the basis, and on planted systems at
    // large N it is they, not the solve, that exhaust memory.
    let mut opts = F4Options::new(Ordering::Grevlex, max_degree).with_budget(budget);
    if let Some(b) = stop_below {
        opts = opts.stopping_below(b);
    }
    let report = f4_fp::f4(&input, n, p, &opts);
    let planted_ok =
        sol.map(|s| !report.inconsistent && report.basis.iter().all(|f| f4_fp::eval(f, s, p) == 0));
    let pure = |k: usize| {
        report.basis.iter().any(|f| {
            f.first()
                .map(|(e, _)| e.iter().enumerate().all(|(i, &x)| (i == k) == (x > 0)))
                .unwrap_or(false)
        })
    };
    let zero_dim = report.inconsistent || (0..n).all(pure);
    let linear = report
        .basis
        .iter()
        .filter(|f| {
            f.first()
                .map(|(e, _)| e.iter().sum::<u32>() == 1)
                .unwrap_or(false)
        })
        .count();
    Measured {
        report,
        planted_ok,
        zero_dim,
        linear,
    }
}

/// What one run reports, in the fields every row carries; `extra` holds
/// the engine's own fields and is merged into the row.
struct Outcome {
    solving_degree_max: u32,
    last_productive_degree: u32,
    degree_reached: u32,
    max_cols_to_solution: usize,
    steps_to_solution: usize,
    inconsistent: bool,
    zero_dim: bool,
    linear: usize,
    basis_len: usize,
    steps: usize,
    max_rows: usize,
    max_cols: usize,
    ms: f64,
    timed_out: bool,
    pairs_above_bound: usize,
    staircase_at_stop: Option<usize>,
    planted_ok: Option<bool>,
    extra: Value,
}

impl Outcome {
    fn from_f4(r: &Measured) -> Self {
        Outcome {
            solving_degree_max: r.report.solving_degree_max,
            last_productive_degree: r.report.solving_degree,
            degree_reached: r.report.degree_reached,
            max_cols_to_solution: r.report.max_cols_to_solution,
            steps_to_solution: r.report.steps_to_solution,
            inconsistent: r.report.inconsistent,
            zero_dim: r.zero_dim,
            linear: r.linear,
            basis_len: r.report.basis.len(),
            steps: r.report.steps,
            max_rows: r.report.max_rows,
            max_cols: r.report.max_cols,
            ms: r.report.ms,
            timed_out: r.report.timed_out,
            pairs_above_bound: r.report.pairs_above_bound,
            staircase_at_stop: r.report.staircase_at_stop,
            planted_ok: r.planted_ok,
            extra: json!({"engine": "f4_fp"}),
        }
    }
}

/// The tower quotient ring of an `m`-summand system: `m` blocks of the
/// tower's rules, then the chain's `m − 2` free unknowns.
fn tower_ring(tower: &Tower, m: usize, p: u64) -> TowerRing {
    let mut rules = Vec::with_capacity(m * tower.t);
    for i in 0..m {
        rules.extend(tower.square_rules(i * tower.t, p));
    }
    TowerRing {
        p,
        rules,
        n_free: m - 2,
    }
}

fn raw_terms(e: &Pol) -> Vec<(Vec<u32>, u64)> {
    e.terms.iter().map(|(k, v)| (k.clone(), *v)).collect()
}

/// Run `f4_fp_tower` on a system: the tower equations become the ring's
/// rewriting, and the other equations its input in normal form.
fn measure_tower(
    eqs: &[Pol],
    towers: std::ops::Range<usize>,
    ring: &TowerRing,
    sol: Option<&[u64]>,
    max_degree: u32,
    budget: Duration,
    stop_below: Option<usize>,
    max_nnz: Option<u64>,
    trace: bool,
) -> (Outcome, Vec<RPoly>) {
    let p = ring.p;
    if let Some(s) = sol {
        for (k, e) in eqs.iter().enumerate() {
            assert_eq!(
                e.eval(s, p),
                0,
                "equation {k} does not vanish at the planted solution"
            );
        }
    }
    for k in towers.clone() {
        assert!(
            ring.from_raw(&raw_terms(&eqs[k])).is_empty(),
            "tower equation {k} is not zero in the ring: the square rules are wrong"
        );
    }
    let input: Vec<RPoly> = eqs
        .iter()
        .enumerate()
        .filter(|(k, _)| !towers.contains(k))
        .map(|(_, e)| ring.from_raw(&raw_terms(e)))
        .filter(|f| !f.is_empty())
        .collect();
    let ring_degrees: Vec<u32> = input.iter().map(RPoly::degree).collect();
    let mut opts = TowerF4Options::new(max_degree).with_budget(budget);
    if let Some(b) = stop_below {
        opts = opts.stopping_below(b);
    }
    if let Some(c) = max_nnz {
        opts = opts.with_max_nnz(c);
    }
    let r = f4_fp_tower::f4_tower(&input, ring, &opts);
    if trace {
        for (k, st) in r.trace.iter().enumerate() {
            eprintln!(
                "tower step {}: degree {}, {} critical + {} tower pairs, {} S-rows + {} reducers + {} promoted x {} cols, nnz {}, residue {} x {}, fresh {} (lowest degree {}), basis {}, pairs left {}, {:.1} ms (rows {:.0}, A {:.0}, B {:.0}, update {:.0})",
                k + 1,
                st.degree,
                st.critical_pairs,
                st.tower_pairs,
                st.s_rows,
                st.reducer_rows,
                st.promoted_rows,
                st.cols,
                st.nnz,
                st.residual_rows,
                st.residual_cols,
                st.fresh,
                st.fresh_min_degree,
                st.basis_active,
                st.pairs_left,
                st.ms,
                st.ms_rows,
                st.ms_reduce,
                st.ms_echelon,
                st.ms_update
            );
        }
    }
    let planted_ok = sol.map(|s| !r.inconsistent && r.basis.iter().all(|f| ring.eval(f, s) == 0));
    let lms: Vec<u128> = r.basis.iter().filter_map(RPoly::lm).collect();
    let pure = |k: usize| {
        lms.iter().any(|&m| {
            let f = f4_fp_tower::free_of(m);
            f4_fp_tower::mask_of(m) == 0
                && (0..f4_fp_tower::MAX_FREE).all(|i| (i == k) == (f[i] > 0))
        })
    };
    let zero_dim = r.inconsistent || (0..ring.n_free).all(pure);
    let linear = lms
        .iter()
        .filter(|&&m| f4_fp_tower::degree_of(m) == 1)
        .count();
    let out = Outcome {
        solving_degree_max: r.solving_degree_max,
        last_productive_degree: r.last_productive_degree,
        degree_reached: r.degree_reached,
        max_cols_to_solution: r.max_cols_to_solution,
        steps_to_solution: r.steps_to_solution,
        inconsistent: r.inconsistent,
        zero_dim,
        linear,
        basis_len: r.basis.len(),
        steps: r.steps,
        max_rows: r.max_rows,
        max_cols: r.max_cols,
        ms: r.ms,
        // A run stopped for size did not finish either: its degree is a
        // lower bound, like a timeout's.
        timed_out: r.timed_out || r.oversize,
        pairs_above_bound: r.pairs_above_bound,
        staircase_at_stop: r.staircase_at_stop,
        planted_ok,
        extra: json!({
            "engine": "f4_fp_tower",
            "input_ring_degrees": ring_degrees,
            "muladds": r.muladds,
            "max_nnz": r.max_nnz,
            "max_residual_rows": r.max_residual_rows,
            "oversize": r.oversize,
            "critical_pairs_reduced": r.critical_pairs_reduced,
            "tower_pairs_reduced": r.tower_pairs_reduced,
            "pairs_product_skipped": r.pairs_product_skipped,
            "pairs_chain_skipped": r.pairs_chain_skipped,
            "reducer_rows": r.reducer_rows,
        }),
    };
    (out, r.basis)
}

// ── Driver ─────────────────────────────────────────────────────────

struct Args {
    p: u64,
    kinds: Vec<Kind>,
    ms: Vec<usize>,
    controls: Vec<Control>,
    t_min: usize,
    max_t: usize,
    max_t_m3: usize,
    max_t_m4: usize,
    planted: usize,
    /// Above this `t`, cells run refutations only: a planted system keeps
    /// processing pairs that reduce to zero long after it is solved, and at
    /// large `N` that tail, not the solve, exhausts memory.
    planted_max_t: usize,
    random: usize,
    budget: u64,
    seed: u64,
    ladder_ts: Vec<usize>,
    ladder_gs: Vec<usize>,
    out: Option<String>,
    /// Stop F4 once at most this many candidate points remain (off by
    /// default; every committed run was made without it).
    stop_below: Option<usize>,
    /// Diagnostic: F4's degree bound for every system, in place of
    /// `n + d + 6`. With `--dump`, shows what F4 knows at a given degree.
    cap: Option<u32>,
    /// Diagnostic: print every basis element of degree at most this, with
    /// tower variables named `y<summand>_<level>`.
    dump: Option<u32>,
    /// The engine: `f4_fp` on the raw system (the default, and every
    /// committed pilot row), or `f4_fp_tower` on the tower quotient ring.
    engine: Engine,
    /// `f4_fp_tower` only: stop before a matrix with more non-zeros.
    max_nnz: Option<u64>,
    /// `f4_fp_tower` only: print one line per F4 step.
    trace: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Engine {
    F4,
    Tower,
}

/// Rows as they are measured: every row reaches `--out` and is flushed
/// before the next system is built, so a run that exhausts memory on a
/// large cell keeps every cell before it.
struct Sink {
    rows: Vec<Value>,
    file: Option<File>,
}

impl Sink {
    fn push(&mut self, row: Value) {
        if let Some(f) = self.file.as_mut() {
            writeln!(f, "{row}").expect("write --out");
            f.flush().expect("flush --out");
        }
        self.rows.push(row);
    }
}

fn parse_args() -> Args {
    let mut a = Args {
        p: 786_433, // 3·2^18 + 1, so 2^t | p − 1 for every t ≤ 18
        kinds: vec![Kind::Kummer, Kind::Dickson, Kind::Isogeny],
        ms: vec![2, 3],
        controls: vec![Control::Tower, Control::Null, Control::Naive],
        t_min: 1,
        max_t: 10,
        max_t_m3: 5,
        max_t_m4: 3,
        planted: 3,
        planted_max_t: usize::MAX,
        random: 3,
        budget: 60,
        seed: 0x504B_4D54,
        ladder_ts: vec![4, 6],
        ladder_gs: vec![1, 2, 4, 8],
        out: None,
        stop_below: None,
        cap: None,
        dump: None,
        engine: Engine::F4,
        max_nnz: None,
        trace: false,
    };
    let args: Vec<String> = std::env::args().skip(1).collect();
    let list = |s: &str| -> Vec<usize> {
        if s == "none" {
            return Vec::new();
        }
        s.split(',').map(|x| x.parse().expect("a number")).collect()
    };
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--trace" {
            a.trace = true;
            i += 1;
            continue;
        }
        let v = args.get(i + 1).cloned().unwrap_or_default();
        match args[i].as_str() {
            "--p" => a.p = v.parse().expect("--p"),
            "--kinds" => {
                a.kinds = v
                    .split(',')
                    .map(|k| match k {
                        "kummer" => Kind::Kummer,
                        "dickson" => Kind::Dickson,
                        "isogeny" => Kind::Isogeny,
                        other => panic!("unknown kind `{other}`"),
                    })
                    .collect()
            }
            "--m" => a.ms = list(&v),
            "--controls" => {
                a.controls = v
                    .split(',')
                    .map(|c| match c {
                        "tower" => Control::Tower,
                        "null" => Control::Null,
                        "naive" => Control::Naive,
                        other => panic!("unknown control `{other}` (the ladder has its own flags)"),
                    })
                    .collect()
            }
            "--t-min" => a.t_min = v.parse().expect("--t-min"),
            "--max-t" => a.max_t = v.parse().expect("--max-t"),
            "--max-t-m3" => a.max_t_m3 = v.parse().expect("--max-t-m3"),
            "--max-t-m4" => a.max_t_m4 = v.parse().expect("--max-t-m4"),
            "--planted" => a.planted = v.parse().expect("--planted"),
            "--planted-max-t" => a.planted_max_t = v.parse().expect("--planted-max-t"),
            "--random" => a.random = v.parse().expect("--random"),
            "--budget" => a.budget = v.parse().expect("--budget"),
            "--seed" => a.seed = v.parse().expect("--seed"),
            "--ladder-t" => a.ladder_ts = list(&v),
            "--ladder-g" => a.ladder_gs = list(&v),
            "--out" => a.out = Some(v),
            "--stop-below" => a.stop_below = Some(v.parse().expect("--stop-below")),
            "--cap" => a.cap = Some(v.parse().expect("--cap")),
            "--engine" => {
                a.engine = match v.as_str() {
                    "f4" | "f4_fp" => Engine::F4,
                    "tower" | "f4_fp_tower" => Engine::Tower,
                    other => panic!("unknown engine `{other}`"),
                }
            }
            "--max-nnz" => a.max_nnz = Some(v.parse().expect("--max-nnz")),
            "--dump" => a.dump = Some(v.parse().expect("--dump")),
            other => panic!("unknown flag `{other}`"),
        }
        i += 2;
    }
    a
}

/// A target curve over `F_p` on which at least `need` abscissae of `V`
/// carry points.
fn target_curve(p: u64, tower: &Tower, need: usize, rng: &mut StdRng) -> (PrimeCurve, Vec<u64>) {
    loop {
        let a = rng.gen_range(0..p);
        let b = rng.gen_range(1..p);
        if !nonsingular(a, b, p) {
            continue;
        }
        let curve = PrimeCurve { p, a, b };
        let on: Vec<u64> = tower
            .v
            .iter()
            .copied()
            .filter(|&x| curve.legendre(curve.rhs(x)) == 1)
            .collect();
        if on.len() >= need {
            return (curve, on);
        }
    }
}

struct Cell {
    kind: Kind,
    m: usize,
    control: Control,
    t: usize,
    g: usize,
}

fn run_cell(cell: &Cell, a: &Args, sink: &mut Sink) -> bool {
    let p = a.p;
    let cell_seed = a.seed
        ^ ((cell.kind as u64) << 40)
        ^ ((cell.m as u64) << 32)
        ^ ((cell.t as u64) << 16)
        ^ (cell.g as u64);
    let mut rng = StdRng::seed_from_u64(cell_seed);
    let tower = build_tower(cell.kind, p, cell.t, &mut rng);
    let (curve, on) = target_curve(p, &tower, cell.m.max(2), &mut rng);
    let mut targets = Vec::new();
    let planted = if cell.t > a.planted_max_t && cell.control != Control::Ladder {
        0
    } else {
        a.planted
    };
    while targets.len() < planted {
        if let Some(tg) = plant(&curve, &tower, cell.m, &on, &mut rng) {
            targets.push(tg);
        }
    }
    if cell.control != Control::Ladder {
        for _ in 0..a.random {
            targets.push(random_target(&curve, &mut rng));
        }
    }
    let mut any_finished = false;
    for (k, target) in targets.iter().enumerate() {
        let (eqs, n, sol, towers) = system(
            cell.control,
            &tower,
            &curve,
            cell.m,
            target,
            cell.g,
            &mut rng,
        );
        if a.engine == Engine::Tower && cell.control == Control::Naive {
            // The naive control has no tower to rewrite by.
            continue;
        }
        let d_in: Vec<u32> = eqs.iter().map(Pol::degree).collect();
        let d_max = d_in.iter().copied().max().unwrap_or(1);
        let max_degree = match (a.cap, cell.control) {
            (Some(cap), _) => cap,
            (None, Control::Naive) => 2 * d_max + 8,
            (None, _) => n as u32 + d_max + 6,
        };
        let started = Instant::now();
        let (r, basis) = match a.engine {
            Engine::F4 => {
                let m = measure(
                    &eqs,
                    n,
                    p,
                    sol.as_deref(),
                    max_degree,
                    Duration::from_secs(a.budget),
                    a.stop_below,
                );
                let out = Outcome::from_f4(&m);
                (out, Dumpable::Raw(m.report.basis))
            }
            Engine::Tower => {
                let ring = tower_ring(&tower, cell.m, p);
                let (out, basis) = measure_tower(
                    &eqs,
                    towers,
                    &ring,
                    sol.as_deref(),
                    max_degree,
                    Duration::from_secs(a.budget),
                    a.stop_below,
                    a.max_nnz,
                    a.trace,
                );
                (out, Dumpable::Ring(basis))
            }
        };
        let wall = started.elapsed().as_secs_f64();
        if !r.timed_out {
            any_finished = true;
        }
        let mut row = json!({
            "kind": cell.kind.name(),
            "m": cell.m,
            "control": cell.control.name(),
            "t": cell.t,
            "N": cell.m * cell.t,
            "g": cell.g,
            "n_vars": n,
            "n_equations": eqs.len(),
            "input_degrees": d_in,
            "target": if target.planted { "planted" } else { "random" },
            "target_index": k,
            "x_r": target.x_r,
            "p": p,
            "curve": {"a": curve.a, "b": curve.b},
            "tower": tower.info,
            "max_degree_bound": max_degree,
            "solving_degree_max": r.solving_degree_max,
            "last_productive_degree": r.last_productive_degree,
            "degree_reached": r.degree_reached,
            "max_cols_to_solution": r.max_cols_to_solution,
            "steps_to_solution": r.steps_to_solution,
            "inconsistent": r.inconsistent,
            "zero_dim": r.zero_dim,
            "linear_basis_elements": r.linear,
            "basis_len": r.basis_len,
            "steps": r.steps,
            "max_rows": r.max_rows,
            "max_cols": r.max_cols,
            "ms": r.ms,
            "wall_s": wall,
            "timed_out": r.timed_out,
            "pairs_above_bound": r.pairs_above_bound,
            "staircase_at_stop": r.staircase_at_stop,
            "planted_ok": r.planted_ok,
        });
        if let (Some(obj), Some(extra)) = (row.as_object_mut(), r.extra.as_object()) {
            for (k, v) in extra {
                obj.insert(k.clone(), v.clone());
            }
        }
        eprintln!(
            "{:8} m={} {:6} t={:2} N={:2} g={:2} {:7} Dmax={:3} reached={:3} cols_to_sol={:7} cols={:7} {:8.1} ms{}{}",
            cell.kind.name(),
            cell.m,
            cell.control.name(),
            cell.t,
            cell.m * cell.t,
            cell.g,
            if target.planted { "planted" } else { "random" },
            r.solving_degree_max,
            r.degree_reached,
            r.max_cols_to_solution,
            r.max_cols,
            r.ms,
            if r.timed_out { "  TIMEOUT" } else { "" },
            if r.planted_ok == Some(false) {
                "  PLANTED-VIOLATION"
            } else {
                ""
            },
        );
        if let Some(k) = a.dump {
            match &basis {
                Dumpable::Raw(b) => dump_basis(b, cell, k),
                Dumpable::Ring(b) => dump_ring_basis(b, cell, k),
            }
        }
        sink.push(row);
    }
    any_finished
}

/// A basis to print with `--dump`, from either engine.
enum Dumpable {
    Raw(Vec<Poly>),
    Ring(Vec<RPoly>),
}

/// `dump_basis` for a basis in the tower ring: the monomials are masks of
/// tower variables and free exponents.
fn dump_ring_basis(basis: &[RPoly], cell: &Cell, k: u32) {
    let as_raw: Vec<Poly> = basis
        .iter()
        .map(|f| {
            f.monos
                .iter()
                .zip(&f.coefs)
                .map(|(&m, &c)| {
                    let n_t = cell.m * cell.t;
                    let mut e = vec![0u32; n_t + cell.m.saturating_sub(2)];
                    let mask = f4_fp_tower::mask_of(m);
                    for (j, x) in e.iter_mut().enumerate().take(n_t) {
                        *x = ((mask >> j) & 1) as u32;
                    }
                    let fr = f4_fp_tower::free_of(m);
                    for k2 in 0..cell.m.saturating_sub(2) {
                        e[n_t + k2] = u32::from(fr[k2]);
                    }
                    (e, u64::from(c))
                })
                .collect()
        })
        .collect();
    dump_basis(&as_raw, cell, k);
}

/// Print the basis elements of degree at most `k`, low degree first, with
/// tower variables named `y<summand>_<level>` and the chain unknowns
/// `u<k>`.
fn dump_basis(basis: &[Poly], cell: &Cell, k: u32) {
    let name = |v: usize| -> String {
        if cell.control == Control::Naive {
            format!("x{v}")
        } else if v >= cell.m * cell.t {
            format!("u{}", v - cell.m * cell.t)
        } else {
            format!("y{}_{}", v / cell.t, v % cell.t)
        }
    };
    let degree = |f: &Poly| {
        f.iter()
            .map(|(e, _)| e.iter().sum::<u32>())
            .max()
            .unwrap_or(0)
    };
    let mut low: Vec<&Poly> = basis.iter().filter(|f| degree(f) <= k).collect();
    low.sort_by_key(|f| degree(f));
    for f in low {
        let terms: Vec<String> = f
            .iter()
            .map(|(e, c)| {
                let mon: Vec<String> = e
                    .iter()
                    .enumerate()
                    .filter(|&(_, &x)| x > 0)
                    .map(|(v, &x)| {
                        if x == 1 {
                            name(v)
                        } else {
                            format!("{}^{x}", name(v))
                        }
                    })
                    .collect();
                if mon.is_empty() {
                    c.to_string()
                } else {
                    format!("{c}·{}", mon.join("·"))
                }
            })
            .collect();
        eprintln!("  [deg {}] {}", degree(f), terms.join(" + "));
    }
}

fn main() {
    let a = parse_args();
    let started = Instant::now();
    let mut sink = Sink {
        rows: Vec::new(),
        file: a
            .out
            .as_ref()
            .map(|path| File::create(path).expect("create --out")),
    };
    // The tower systems and their naive and null controls, t upward until
    // a whole cell times out.
    for &kind in &a.kinds {
        for &m in &a.ms {
            let max_t = match m {
                2 => a.max_t,
                3 => a.max_t_m3,
                _ => a.max_t_m4,
            };
            // The null and naive controls are written for m = 2, and the
            // naive membership for the Kummer coset only.
            let controls: Vec<Control> = a
                .controls
                .iter()
                .copied()
                .filter(|c| match c {
                    Control::Tower => true,
                    Control::Null => m == 2,
                    Control::Naive => m == 2 && kind == Kind::Kummer,
                    Control::Ladder => false,
                })
                .collect();
            // m ≥ 3 needs m distinct base abscissae, so |V| = 2^t ≥ 4.
            let t_min = if m >= 3 { a.t_min.max(2) } else { a.t_min };
            for control in controls {
                for t in t_min..=max_t {
                    let cell = Cell {
                        kind,
                        m,
                        control,
                        t,
                        g: 1,
                    };
                    if !run_cell(&cell, &a, &mut sink) {
                        eprintln!(
                            "-- {} m={m} {}: every run at t = {t} timed out; stopping",
                            kind.name(),
                            control.name()
                        );
                        break;
                    }
                }
            }
        }
    }
    // The generator-count ladder, on planted targets.
    for &kind in &a.kinds {
        for &t in &a.ladder_ts {
            for &g in &a.ladder_gs {
                let cell = Cell {
                    kind,
                    m: 2,
                    control: Control::Ladder,
                    t,
                    g,
                };
                run_cell(&cell, &a, &mut sink);
            }
        }
    }
    let rows = &sink.rows;
    let summary = json!({
        "p": a.p,
        "budget_seconds": a.budget,
        "seed": a.seed,
        "planted_per_cell": a.planted,
        "random_per_cell": a.random,
        "wall_seconds": started.elapsed().as_secs_f64(),
        "rows": rows.len(),
        "planted_violations": rows.iter().filter(|r| r["planted_ok"] == json!(false)).count(),
    });
    eprintln!("{summary}");
    if let Some(f) = sink.file.as_mut() {
        writeln!(f, "{}", json!({ "summary": summary })).expect("write --out");
    }
}
