//! # Coordinate quotients: invariants of any finite group of point maps, by
//! orbit sums — the second search space of `research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md`.
//!
//! The first search ([`crate::cryptanalysis::coordinate_search`]) handled
//! coordinates of a single point and proved that, up to a Möbius frame, the
//! only pairwise symmetry such a coordinate can see is translation by
//! rational 2-torsion.  Two things were left open: the *joint* invariants of
//! the whole group `E[2](K) ≅ (Z/2)²` when it is rational, and coordinates
//! on *tuples* of points, where translation by 4-torsion (which does not act
//! on the `x`-line at all) can act.  Both need invariants of a group that is
//! no longer a single involution, and deriving them by hand for every group
//! is exactly the kind of work an algorithm should do.
//!
//! ## What this does
//!
//! 1. **Group closure.**  A generating set of point maps `P ↦ α(P) + T`
//!    (negation, automorphisms, translations by rational torsion points) is
//!    closed into a finite group `G`.
//! 2. **Relation subgroup, by experiment.**  `Γ ⊆ G^{m+1}` is the set of
//!    tuples `(γ_0, …, γ_m)` with `Σ γ_i(P_i) = O` whenever `Σ P_i = O`,
//!    decided on random relation tuples.  No theory about which torsion
//!    orders may act on which points is assumed; for 2-torsion this recovers
//!    "even weight", for 4-torsion "weights summing to `0 mod 4`", for
//!    automorphisms "all equal".
//! 3. **Invariants by orbit sets.**  For a seed function `f` of the tuple —
//!    a per-point coordinate `u(P_i)`, a pair coordinate `u(P_i ± P_j)`, the
//!    product or sum of the `u_i` — the values `{f(γ·P) : γ ∈ Γ}` form a
//!    set, and its elementary symmetric functions are `Γ`-invariant.  Sets
//!    rather than multisets, because over `F_2` a multiset with even
//!    multiplicities has vanishing symmetric functions.  Constants and
//!    duplicates are dropped.
//! 4. **Minimal-degree relation.**  Interpolate the polynomial relation
//!    among the invariants at total degree `1, 2, …` and stop at the first
//!    degree where one exists; verify it on fresh relations.
//! 5. **Collapse, exactly.**  On a small curve every relation tuple is
//!    enumerated and hashed by its invariant vector; the collapse factor is
//!    tuples per vector.  It is never below `|Γ|`; equality means the
//!    invariants separate the `Γ`-orbits, more means a symmetry the group
//!    does not account for.
//!
//! ## Honest scope
//!
//! Toy curves (`#E ≲ 10³` for exact collapse at `m = 3`), groups of order a
//! few hundred, seeds chosen by the caller.  This finds the invariant system
//! a group gives and measures it; it does not prove there is no better one.

use std::collections::{HashMap, HashSet};

use super::coordinate_search::{
    detect_symmetries, kernel, linearising_frame, relation_tuple, Auto, Curve, FrameKind, Gf,
    Mobius, Pt, Rng64, Scope, SymmetryKind, INF,
};

/// Exponent vectors over `nv` variables with total degree exactly `d`.
fn monomials_of_total_degree(nv: usize, d: u32) -> Vec<Vec<u32>> {
    fn rec(nv: usize, d: u32, prefix: &mut Vec<u32>, out: &mut Vec<Vec<u32>>) {
        if prefix.len() == nv - 1 {
            prefix.push(d);
            out.push(prefix.clone());
            prefix.pop();
            return;
        }
        for k in 0..=d {
            prefix.push(k);
            rec(nv, d - k, prefix, out);
            prefix.pop();
        }
    }
    if nv == 0 {
        return vec![];
    }
    let mut out = Vec::new();
    rec(nv, d, &mut Vec::new(), &mut out);
    out
}

/// Exponent vectors with total degree at most `d`.
pub fn monomials_up_to_total_degree(nv: usize, d: u32) -> Vec<Vec<u32>> {
    (0..=d)
        .flat_map(|k| monomials_of_total_degree(nv, k))
        .collect()
}

/// At most this many symmetric functions per seed, and this many
/// invariants in total, so the monomial count stays sane.
pub const MAX_E_PER_SEED: usize = 4;
pub const MAX_INVARIANTS: usize = 14;

// ── Charts: a Möbius frame on the `x`- or the `y`-line ─────────────

/// Which coordinate line a frame lives on.  Every point map that commutes
/// with the order-3 automorphism of a `j = 0` curve descends to the
/// `y`-line (the quotient by that automorphism), which is where rational
/// 3-torsion translations become Möbius maps.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Line {
    X,
    Y,
    /// `x²`: the quotient of the `x`-line by the order-4 automorphism
    /// `(x, y) ↦ (−x, iy)` of `y² = x³ + ax` (`i ∈ F_q`).
    X2,
    /// `x(P) + x(P + T)` for a 2-torsion point `T`: the `x`-line of the
    /// 2-isogenous curve `E/⟨T⟩` (Vélu, up to an affine change), where a
    /// 4-torsion point `Q` with `2Q = T` becomes 2-torsion and its
    /// translation a Möbius involution.
    Iso2(Pt),
    /// `x(P) + x(P + T) + x(P − T)` for a 3-torsion point `T`: the
    /// `x`-line of `E/⟨T⟩`, where a 2-torsion translation stays a Möbius
    /// involution and the two together give the 6-torsion.
    Iso3(Pt),
}

/// A coordinate on the curve: a Möbius frame applied to `x(P)` or `y(P)`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Chart {
    pub line: Line,
    pub mob: Mobius,
}

impl Chart {
    pub fn x(mob: Mobius) -> Self {
        Chart { line: Line::X, mob }
    }
    pub fn y(mob: Mobius) -> Self {
        Chart { line: Line::Y, mob }
    }
    pub fn on(line: Line, mob: Mobius) -> Self {
        Chart { line, mob }
    }
    /// The underlying coordinate before the frame, `INF` at a pole.
    pub fn base_value(line: Line, curve: &Curve, p: Pt) -> u64 {
        let f = &curve.f;
        match line {
            Line::X => p.x(),
            Line::Y => p.y(),
            Line::X2 => {
                let x = p.x();
                if x == INF {
                    INF
                } else {
                    f.mul(x, x)
                }
            }
            Line::Iso2(t) => {
                let (a, b) = (p.x(), curve.add(p, t).x());
                if a == INF || b == INF {
                    INF
                } else {
                    f.add(a, b)
                }
            }
            Line::Iso3(t) => {
                let (a, b, c) = (p.x(), curve.add(p, t).x(), curve.sub(p, t).x());
                if a == INF || b == INF || c == INF {
                    INF
                } else {
                    f.add(f.add(a, b), c)
                }
            }
        }
    }
    /// The chart value at `P`, `INF` at a pole.
    pub fn apply_on(&self, curve: &Curve, p: Pt) -> u64 {
        self.mob
            .apply(&curve.f, Chart::base_value(self.line, curve, p))
    }
    /// The chart value at `P` for the `x`- and `y`-lines (the lines that
    /// need no curve arithmetic); use [`Chart::apply_on`] in general.
    pub fn apply(&self, f: &Gf, p: Pt) -> u64 {
        let t = match self.line {
            Line::X => p.x(),
            Line::Y => p.y(),
            Line::X2 => {
                let x = p.x();
                if x == INF {
                    INF
                } else {
                    f.mul(x, x)
                }
            }
            Line::Iso2(_) | Line::Iso3(_) => {
                panic!("Chart::apply on an isogeny line needs the curve: use apply_on")
            }
        };
        self.mob.apply(f, t)
    }
    pub fn describe(&self, f: &Gf) -> String {
        let inner = self.mob.describe(f);
        match self.line {
            Line::X => inner.replace('t', "x"),
            Line::Y => inner.replace('t', "y"),
            Line::X2 => inner.replace('t', "x²"),
            Line::Iso2(_) => inner.replace('t', "x′"),
            Line::Iso3(_) => inner.replace('t', "x″"),
        }
    }
}

/// The Möbius map a point map induces on a line, if it induces one:
/// fitted on three points, verified on all.
pub fn descended_map(curve: &Curve, pts: &[Pt], line: Line, g: &PointMap) -> Option<Mobius> {
    let f = &curve.f;
    let val = |p: Pt| Chart::base_value(line, curve, p);
    let mut pairs: Vec<(u64, u64)> = Vec::new();
    let mut seen = HashSet::new();
    for &p in pts {
        let (t, s) = (val(p), val(g.apply(curve, p)));
        if t != INF && s != INF && seen.insert(t) {
            pairs.push((t, s));
        }
        if pairs.len() == 3 {
            break;
        }
    }
    let m = Mobius::fit(f, &pairs)?;
    let ok = pts.iter().all(|&p| {
        let (t, s) = (val(p), val(g.apply(curve, p)));
        // poles of the base coordinate carry no information
        t == INF || s == INF || m.apply(f, t) == s
    });
    ok.then_some(m)
}

/// A chart on `line` in which `g` (an involution on that line) is
/// linearised — `t ↦ −t` in odd characteristic, `t ↦ t + 1` in
/// characteristic 2 — when its fixed points are rational; otherwise the
/// plain line.  `None` if `g` is not a Möbius map on the line at all.
pub fn linearised_chart(
    curve: &Curve,
    pts: &[Pt],
    line: Line,
    g: &PointMap,
) -> Option<(Chart, FrameKind, Mobius)> {
    let m = descended_map(curve, pts, line, g)?;
    let fr = linearising_frame(&curve.f, &m);
    Some((Chart::on(line, fr.mob), fr.kind, m))
}

impl From<Mobius> for Chart {
    fn from(mob: Mobius) -> Self {
        Chart::x(mob)
    }
}

// ── Point maps and their group ─────────────────────────────────────

/// `P ↦ auto(P) + t`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PointMap {
    pub auto: Auto,
    pub t: Pt,
}

impl PointMap {
    pub fn identity() -> Self {
        PointMap {
            auto: Auto::Scale(1),
            t: Pt::Inf,
        }
    }
    pub fn translate(t: Pt) -> Self {
        PointMap {
            auto: Auto::Scale(1),
            t,
        }
    }
    pub fn negate() -> Self {
        PointMap {
            auto: Auto::Neg,
            t: Pt::Inf,
        }
    }
    pub fn apply(&self, curve: &Curve, p: Pt) -> Pt {
        curve.add(curve.apply_auto(self.auto, p), self.t)
    }
    /// `self ∘ other`.
    pub fn compose(&self, curve: &Curve, other: &PointMap) -> PointMap {
        // self(other(P)) = α₁(α₂(P) + T₂) + T₁ = (α₁α₂)(P) + α₁(T₂) + T₁
        let auto = compose_auto(curve, self.auto, other.auto);
        let t = curve.add(curve.apply_auto(self.auto, other.t), self.t);
        PointMap { auto, t }
    }
    pub fn describe(&self, f: &Gf) -> String {
        let a = match self.auto {
            Auto::Scale(1) => String::new(),
            Auto::Neg => "−".to_string(),
            Auto::Scale(u) => format!("[u={}]", f.show(u)),
        };
        let t = match self.t {
            Pt::Inf => String::new(),
            Pt::Aff(x, y) => format!("+({}, {})", f.show(x), f.show(y)),
        };
        if a.is_empty() && t.is_empty() {
            "id".to_string()
        } else {
            format!("{a}P{t}")
        }
    }
}

/// In odd characteristic negation is the scaling by `−1`; use one name for
/// it so group closure does not count the same map twice.
/// `(x, y) ↦ (u²x, u³y)` is an automorphism only of a curve with
/// `a₁ = a₃ = 0`; there, in odd characteristic, negation is `Scale(−1)`.
fn short_form(curve: &Curve) -> bool {
    curve.a1 == 0 && curve.a3 == 0
}

fn canonical_auto(curve: &Curve, a: Auto) -> Auto {
    match a {
        Auto::Neg if curve.f.p != 2 && short_form(curve) => Auto::Scale(curve.f.neg(1)),
        Auto::Scale(u) if curve.f.p == 2 && u != 1 => Auto::Neg,
        Auto::Scale(u) if curve.f.p != 2 && !short_form(curve) && u == curve.f.neg(1) => Auto::Neg,
        other => other,
    }
}

fn compose_auto(curve: &Curve, a: Auto, b: Auto) -> Auto {
    let f = &curve.f;
    let (a, b) = (canonical_auto(curve, a), canonical_auto(curve, b));
    match (a, b) {
        (Auto::Scale(1), x) | (x, Auto::Scale(1)) => x,
        (Auto::Neg, Auto::Neg) => Auto::Scale(1),
        (Auto::Scale(u), Auto::Scale(v)) => Auto::Scale(f.mul(u, v)),
        (Auto::Neg, Auto::Scale(u)) | (Auto::Scale(u), Auto::Neg) => {
            if f.p == 2 || !short_form(curve) {
                // only ±1 exist here, and Scale(u) with u ≠ 1 is not one
                Auto::Neg
            } else {
                Auto::Scale(f.neg(u))
            }
        }
    }
}

/// Close `generators` into a group, up to `cap` elements.
pub fn group_closure(curve: &Curve, generators: &[PointMap], cap: usize) -> Option<Vec<PointMap>> {
    let generators: Vec<PointMap> = generators
        .iter()
        .map(|g| PointMap {
            auto: canonical_auto(curve, g.auto),
            t: g.t,
        })
        .collect();
    let generators = &generators[..];
    let mut elems: Vec<PointMap> = vec![PointMap::identity()];
    let mut seen: HashSet<PointMap> = elems.iter().copied().collect();
    let mut frontier = elems.clone();
    while let Some(g) = frontier.pop() {
        for h in generators {
            let k = h.compose(curve, &g);
            if seen.insert(k) {
                elems.push(k);
                frontier.push(k);
                if elems.len() > cap {
                    return None;
                }
            }
        }
    }
    Some(elems)
}

/// The rational points of order dividing `k`.
pub fn torsion_points(curve: &Curve, pts: &[Pt], k: u64) -> Vec<Pt> {
    pts.iter()
        .copied()
        .filter(|&p| curve.mul(p, k) == Pt::Inf)
        .collect()
}

/// The relation-preserving subgroup `Γ ⊆ G^{m+1}`, found by testing every
/// tuple of group elements on `samples` random relation tuples.
pub fn relation_subgroup(
    curve: &Curve,
    pts: &[Pt],
    group: &[PointMap],
    m: usize,
    samples: usize,
    rng: &mut Rng64,
) -> Vec<Vec<PointMap>> {
    let tuples: Vec<Vec<Pt>> = (0..samples)
        .map(|_| relation_tuple(curve, pts, m, rng))
        .collect();
    let n = m + 1;
    let g = group.len();
    let total = g.pow(n as u32);
    let mut out = Vec::new();
    for code in 0..total {
        let mut idx = Vec::with_capacity(n);
        let mut c = code;
        for _ in 0..n {
            idx.push(c % g);
            c /= g;
        }
        let gamma: Vec<PointMap> = idx.iter().map(|&i| group[i]).collect();
        let ok = tuples.iter().all(|t| {
            let sum = t
                .iter()
                .zip(&gamma)
                .fold(Pt::Inf, |acc, (&p, gm)| curve.add(acc, gm.apply(curve, p)));
            sum == Pt::Inf
        });
        if ok {
            out.push(gamma);
        }
    }
    out
}

// ── Seeds and invariants ───────────────────────────────────────────

/// A function of the relation tuple used to seed invariants.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Seed {
    /// `u(P_i)`.
    Point(usize),
    /// `u(P_i + P_j)`.
    PairSum(usize, usize),
    /// `u(P_i − P_j)`.
    PairDiff(usize, usize),
    /// `Π_i u(P_i)`.
    Product,
    /// `Σ_i u(P_i)`.
    Sum,
}

impl Seed {
    /// Degree of the seed as a function of the per-point coordinates `u_i`
    /// (`None` for pair seeds, which are algebraic rather than polynomial
    /// in the `u_i`).
    pub fn intrinsic_degree(&self, m: usize) -> Option<u32> {
        match self {
            Seed::Point(_) => Some(1),
            Seed::PairSum(..) | Seed::PairDiff(..) => None,
            Seed::Product => Some(m as u32 + 1),
            Seed::Sum => Some(1),
        }
    }
    pub fn name(&self) -> String {
        match self {
            Seed::Point(i) => format!("u{}", i + 1),
            Seed::PairSum(i, j) => format!("u({}+{})", i + 1, j + 1),
            Seed::PairDiff(i, j) => format!("u({}−{})", i + 1, j + 1),
            Seed::Product => "Πu".to_string(),
            Seed::Sum => "Σu".to_string(),
        }
    }
    /// Value on a tuple, `None` at a pole.
    pub fn eval(&self, curve: &Curve, chart: &Chart, tuple: &[Pt]) -> Option<u64> {
        let f = &curve.f;
        let u = |p: Pt| -> Option<u64> {
            let v = chart.apply_on(curve, p);
            (v != INF).then_some(v)
        };
        match self {
            Seed::Point(i) => u(tuple[*i]),
            Seed::PairSum(i, j) => u(curve.add(tuple[*i], tuple[*j])),
            Seed::PairDiff(i, j) => u(curve.sub(tuple[*i], tuple[*j])),
            Seed::Product => tuple
                .iter()
                .try_fold(1u64, |acc, &p| Some(f.mul(acc, u(p)?))),
            Seed::Sum => tuple
                .iter()
                .try_fold(0u64, |acc, &p| Some(f.add(acc, u(p)?))),
        }
    }
}

/// One invariant: the `k`-th elementary symmetric function of the orbit set
/// of a seed.
#[derive(Clone, Debug)]
pub struct Invariant {
    pub seed: Seed,
    pub orbit_size: usize,
    pub k: usize,
}

impl Invariant {
    /// Degree in the `u_i`: `k` times the seed's, when the seed is
    /// polynomial in them.
    pub fn intrinsic_degree(&self, m: usize) -> Option<u32> {
        self.seed.intrinsic_degree(m).map(|d| d * self.k as u32)
    }
    pub fn name(&self) -> String {
        if self.orbit_size == 1 {
            self.seed.name()
        } else {
            format!("e{}[{}]", self.k, self.seed.name())
        }
    }
}

fn elementary_symmetric(f: &Gf, xs: &[u64]) -> Vec<u64> {
    let m = xs.len();
    let mut e = vec![0u64; m + 1];
    e[0] = 1;
    for &x in xs {
        for k in (1..=m).rev() {
            e[k] = f.add(e[k], f.mul(x, e[k - 1]));
        }
    }
    e[1..].to_vec()
}

/// The orbit set of `seed` under `gamma` on `tuple`: distinct values, or
/// `None` if any is a pole.
fn orbit_set(
    curve: &Curve,
    chart: &Chart,
    gamma: &[Vec<PointMap>],
    seed: &Seed,
    tuple: &[Pt],
) -> Option<Vec<u64>> {
    let mut vals: Vec<u64> = Vec::new();
    for g in gamma {
        let moved: Vec<Pt> = tuple
            .iter()
            .zip(g)
            .map(|(&p, gm)| gm.apply(curve, p))
            .collect();
        vals.push(seed.eval(curve, chart, &moved)?);
    }
    vals.sort_unstable();
    vals.dedup();
    Some(vals)
}

/// A quotient coordinate system: the group, its relation subgroup, the
/// frame, and the invariants selected from the seeds.
#[derive(Clone, Debug)]
pub struct QuotientSystem {
    pub group: Vec<PointMap>,
    pub gamma: Vec<Vec<PointMap>>,
    pub chart: Chart,
    pub seeds: Vec<Seed>,
    pub invariants: Vec<Invariant>,
    pub m: usize,
    /// Every map `Γ` applies at some coordinate acts on the `u`-line as
    /// `u ↦ a·u + b`; only then are orbit-set symmetric functions of `u_i`
    /// polynomial in `u_i`, and only then is a weighted degree meaningful.
    pub affine_on_u: bool,
}

/// Memo of orbit-set symmetric functions of per-point seeds: the orbit set
/// of `u(P_i)` under `Γ` depends only on `P_i` and on the projection of `Γ`
/// to coordinate `i`, so it is computed once per point.
#[derive(Default)]
pub struct EvalCache {
    point: HashMap<(usize, Pt), Option<Vec<u64>>>,
}

impl QuotientSystem {
    /// The distinct maps `Γ` applies at coordinate `i`.
    fn projection(&self, i: usize) -> Vec<PointMap> {
        let mut v: Vec<PointMap> = self.gamma.iter().map(|g| g[i]).collect();
        v.sort_by_key(|pm| format!("{pm:?}"));
        v.dedup();
        v
    }

    /// Weighted total degree of a relation: each invariant counted with
    /// its intrinsic degree in the `u_i`; `None` if any variable involved
    /// is algebraic in them.
    pub fn weighted_degree(&self, rel: &QuotientRelation) -> Option<u32> {
        if !self.affine_on_u {
            return None;
        }
        let ds: Vec<Option<u32>> = self
            .invariants
            .iter()
            .map(|i| i.intrinsic_degree(self.m))
            .collect();
        let mut best = 0;
        for (e, _) in &rel.terms {
            let mut d = 0;
            for (i, &k) in e.iter().enumerate() {
                if k > 0 {
                    d += k * ds[i]?;
                }
            }
            best = best.max(d);
        }
        Some(best)
    }

    /// Evaluate every invariant on a tuple; `None` if any seed hits a pole
    /// or an orbit set is smaller than its generic size (a degenerate tuple).
    pub fn evaluate(&self, curve: &Curve, tuple: &[Pt], cache: &mut EvalCache) -> Option<Vec<u64>> {
        let f = &curve.f;
        let mut per_seed: HashMap<String, Vec<u64>> = HashMap::new();
        let mut out = Vec::with_capacity(self.invariants.len());
        for inv in &self.invariants {
            let key = inv.seed.name();
            if !per_seed.contains_key(&key) {
                let es = match inv.seed {
                    Seed::Point(i) => {
                        let entry = cache.point.entry((i, tuple[i])).or_insert_with(|| {
                            let proj = self.projection(i);
                            let mut vals: Vec<u64> = Vec::new();
                            for g in &proj {
                                let v = self.chart.apply_on(curve, g.apply(curve, tuple[i]));
                                if v == INF {
                                    return None;
                                }
                                vals.push(v);
                            }
                            vals.sort_unstable();
                            vals.dedup();
                            Some(
                                elementary_symmetric(f, &vals)
                                    .into_iter()
                                    .chain([vals.len() as u64])
                                    .collect(),
                            )
                        });
                        let e = entry.clone()?;
                        // last entry carries the orbit size
                        let size = *e.last().unwrap() as usize;
                        if size != inv.orbit_size {
                            return None;
                        }
                        e[..e.len() - 1].to_vec()
                    }
                    _ => {
                        let set = orbit_set(curve, &self.chart, &self.gamma, &inv.seed, tuple)?;
                        if set.len() != inv.orbit_size {
                            return None;
                        }
                        elementary_symmetric(f, &set)
                    }
                };
                per_seed.insert(key.clone(), es);
            }
            out.push(per_seed[&key][inv.k - 1]);
        }
        Some(out)
    }
}

/// Build the quotient system: close the group, find `Γ`, form the orbit-set
/// invariants of the seeds, drop constants and duplicates.
pub fn build_quotient_system(
    curve: &Curve,
    pts: &[Pt],
    generators: &[PointMap],
    chart: impl Into<Chart>,
    seeds: &[Seed],
    m: usize,
    rng: &mut Rng64,
) -> Option<QuotientSystem> {
    let chart: Chart = chart.into();
    let group = group_closure(curve, generators, 512)?;
    let gamma = relation_subgroup(curve, pts, &group, m, 12, rng);
    if gamma.is_empty() {
        return None;
    }
    // Generic orbit sizes and value vectors on probe tuples.
    let probes: Vec<Vec<Pt>> = (0..24)
        .map(|_| relation_tuple(curve, pts, m, rng))
        .collect();
    let f = &curve.f;
    let mut invariants: Vec<Invariant> = Vec::new();
    let mut seen_vectors: Vec<Vec<u64>> = Vec::new();
    for seed in seeds {
        let sets: Vec<Vec<u64>> = probes
            .iter()
            .filter_map(|t| orbit_set(curve, &chart, &gamma, seed, t))
            .collect();
        if sets.len() < 8 {
            continue;
        }
        let size = sets.iter().map(|s| s.len()).max().unwrap();
        let generic: Vec<&Vec<u64>> = sets.iter().filter(|s| s.len() == size).collect();
        for k in 1..=size.min(MAX_E_PER_SEED) {
            if invariants.len() >= MAX_INVARIANTS {
                break;
            }
            let vector: Vec<u64> = generic
                .iter()
                .map(|s| elementary_symmetric(f, s)[k - 1])
                .collect();
            if vector.iter().all(|&v| v == vector[0]) {
                continue; // constant
            }
            if seen_vectors
                .iter()
                .any(|v| v.len() == vector.len() && *v == vector)
            {
                continue; // duplicate of an earlier invariant
            }
            seen_vectors.push(vector);
            invariants.push(Invariant {
                seed: seed.clone(),
                orbit_size: size,
                k,
            });
        }
    }
    if invariants.is_empty() {
        return None;
    }
    let affine_on_u = group
        .iter()
        .all(|g| map_is_affine_on_u(curve, pts, &chart, g));
    Some(QuotientSystem {
        group,
        gamma,
        chart,
        seeds: seeds.to_vec(),
        invariants,
        m,
        affine_on_u,
    })
}

/// Does `u(γP) = a·u(P) + b` for constants `a, b`, on every point?
fn map_is_affine_on_u(curve: &Curve, pts: &[Pt], chart: &Chart, g: &PointMap) -> bool {
    let f = &curve.f;
    let pairs: Vec<(u64, u64)> = pts
        .iter()
        .filter_map(|&p| {
            let a = chart.apply_on(curve, p);
            let b = chart.apply_on(curve, g.apply(curve, p));
            (a != INF && b != INF).then_some((a, b))
        })
        .collect();
    // fit a, b from two pairs with distinct u
    let Some((u0, v0)) = pairs.first().copied() else {
        return false;
    };
    let Some((u1, v1)) = pairs.iter().copied().find(|(u, _)| *u != u0) else {
        return false;
    };
    let a = f.div(f.sub(v1, v0), f.sub(u1, u0));
    let b = f.sub(v0, f.mul(a, u0));
    pairs.iter().all(|&(u, v)| f.add(f.mul(a, u), b) == v)
}

// ── Interpolation at minimal total degree ──────────────────────────

/// The relation among the invariants, as exponent vectors and coefficients.
#[derive(Clone, Debug)]
pub struct QuotientRelation {
    pub var_names: Vec<String>,
    pub terms: Vec<(Vec<u32>, u64)>,
    pub total_degree: u32,
    pub kernel_dim: usize,
    pub verified_on: usize,
}

impl QuotientRelation {
    pub fn eval(&self, f: &Gf, vals: &[u64]) -> u64 {
        let mut acc = 0;
        for (e, c) in &self.terms {
            let mut t = *c;
            for (i, &k) in e.iter().enumerate() {
                if k > 0 {
                    t = f.mul(t, f.pow(vals[i], k as u64));
                }
            }
            acc = f.add(acc, t);
        }
        acc
    }
    pub fn degrees(&self) -> Vec<u32> {
        let n = self.var_names.len();
        (0..n)
            .map(|i| self.terms.iter().map(|(e, _)| e[i]).max().unwrap_or(0))
            .collect()
    }
    pub fn render(&self, f: &Gf, max_terms: usize) -> String {
        let mut parts = Vec::new();
        for (e, c) in self.terms.iter().take(max_terms) {
            let mut mono = String::new();
            for (i, &k) in e.iter().enumerate() {
                if k == 1 {
                    mono.push_str(&format!("·{}", self.var_names[i]));
                } else if k > 1 {
                    mono.push_str(&format!("·{}^{}", self.var_names[i], k));
                }
            }
            let coef = if *c == 1 && !mono.is_empty() {
                String::new()
            } else {
                f.show(*c)
            };
            parts.push(format!("{coef}{mono}").trim_start_matches('·').to_string());
        }
        let mut s = parts.join(" + ");
        if self.terms.len() > max_terms {
            s.push_str(&format!(" + … ({} more)", self.terms.len() - max_terms));
        }
        s
    }
}

/// Rank of each monomial under the order (total degree, exponent of the
/// last variable, …, exponent of the first), highest rank = pivot
/// preference.  Later variables are the tuple seeds (`Σu`, `Πu`), so an
/// identity such as `s² + s = Σw` pivots on `s²` and reduction strips
/// exactly the identity's part from a relation, leaving the sparse form.
fn pivot_rank(monos: &[Vec<u32>]) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..monos.len()).collect();
    idx.sort_by(|&a, &b| {
        let ka: (u32, Vec<u32>) = (
            monos[a].iter().sum(),
            monos[a].iter().rev().copied().collect(),
        );
        let kb: (u32, Vec<u32>) = (
            monos[b].iter().sum(),
            monos[b].iter().rev().copied().collect(),
        );
        ka.cmp(&kb)
    });
    let mut rank = vec![0usize; monos.len()];
    for (r, &i) in idx.iter().enumerate() {
        rank[i] = r;
    }
    rank
}

/// Reduce `v` against the echelon basis `basis` (each with a distinct
/// pivot column), returning the residual.
fn reduce_against(f: &Gf, mut v: Vec<u64>, basis: &[(usize, Vec<u64>)]) -> Vec<u64> {
    for (lead, b) in basis {
        if v[*lead] != 0 {
            let c = v[*lead];
            for (x, y) in v.iter_mut().zip(b) {
                *x = f.sub(*x, f.mul(c, *y));
            }
        }
    }
    v
}

/// Turn a kernel basis into one with distinct pivot columns (each vector
/// scaled to pivot coefficient 1), pivoting on the highest-ranked monomial.
fn echelon(f: &Gf, vecs: &[Vec<u64>], rank: &[usize]) -> Vec<(usize, Vec<u64>)> {
    let mut basis: Vec<(usize, Vec<u64>)> = Vec::new();
    for v in vecs {
        let r = reduce_against(f, v.clone(), &basis);
        let lead = (0..r.len()).filter(|&i| r[i] != 0).max_by_key(|&i| rank[i]);
        if let Some(lead) = lead {
            let inv = f.inv(r[lead]);
            let scaled: Vec<u64> = r.iter().map(|&c| f.mul(c, inv)).collect();
            basis.push((lead, scaled));
        }
    }
    basis
}

/// A generic tuple of `m + 1` affine points — no relation among them.
fn generic_tuple(pts: &[Pt], m: usize, rng: &mut Rng64) -> Vec<Pt> {
    (0..=m)
        .map(|_| pts[rng.below(pts.len() as u64) as usize])
        .collect()
}

/// Interpolate the minimal-total-degree relation among the invariants, up
/// to `max_total_degree` and `max_monomials`.
///
/// At each degree two kernels are computed: polynomials vanishing on
/// relation tuples, and polynomials vanishing on *all* tuples (identities
/// among the invariants, such as `s² + s = Σw`).  A summation relation is a
/// vector of the first kernel outside the span of the second; the first
/// degree where one exists is reported, with the sparsest representative.
pub fn interpolate_quotient(
    curve: &Curve,
    pts: &[Pt],
    qs: &QuotientSystem,
    max_total_degree: u32,
    max_monomials: usize,
    rng: &mut Rng64,
) -> Result<QuotientRelation, String> {
    interpolate_quotient_boxed(curve, pts, qs, max_total_degree, max_monomials, None, rng)
}

/// [`interpolate_quotient`] with a per-variable degree cap on top of the
/// total degree: `caps = (point, tuple)` bounds the exponent of every
/// invariant seeded by a single point, and of every other invariant.  The
/// total degree still grows one step at a time, so the relation found is
/// still of minimal total degree within the box; the box only keeps the
/// monomial count down where the relation is known to be of bounded
/// degree in each point (as summation relations are).
pub fn interpolate_quotient_boxed(
    curve: &Curve,
    pts: &[Pt],
    qs: &QuotientSystem,
    max_total_degree: u32,
    max_monomials: usize,
    caps: Option<(u32, u32)>,
    rng: &mut Rng64,
) -> Result<QuotientRelation, String> {
    let f = &curve.f;
    let nv = qs.invariants.len();
    let names: Vec<String> = qs.invariants.iter().map(|i| i.name()).collect();
    let var_caps: Vec<u32> = qs
        .invariants
        .iter()
        .map(|inv| match (caps, &inv.seed) {
            (None, _) => u32::MAX,
            (Some((p, _)), Seed::Point(_)) => p,
            (Some((_, t)), _) => t,
        })
        .collect();
    let mut rel_samples: Vec<Vec<u64>> = Vec::new();
    let mut all_samples: Vec<Vec<u64>> = Vec::new();
    let mut cache = EvalCache::default();
    let mut identities_seen = Vec::new();
    let mut last_len = 0usize;
    // Experiment overrides: `QUOTIENT_START_DEGREE` skips the lower total
    // degrees (one kernel computation on the full box instead of one per
    // degree; the relation found is then the sparsest in the box, not of
    // minimal total degree), `QUOTIENT_MAX_MONOMIALS` raises the cap.
    let env_u32 = |k: &str| std::env::var(k).ok().and_then(|v| v.parse::<u32>().ok());
    let start = env_u32("QUOTIENT_START_DEGREE").unwrap_or(1).max(1);
    let max_monomials = env_u32("QUOTIENT_MAX_MONOMIALS")
        .map(|m| m as usize)
        .unwrap_or(max_monomials);
    for d in start..=max_total_degree {
        let monos: Vec<Vec<u32>> = monomials_up_to_total_degree(nv, d)
            .into_iter()
            .filter(|e| e.iter().zip(&var_caps).all(|(k, c)| k <= c))
            .collect();
        if monos.len() == last_len {
            // the box is saturated: nothing new at this total degree
            identities_seen.push(0usize);
            continue;
        }
        last_len = monos.len();
        if monos.len() > max_monomials {
            return Err(format!(
                "no relation up to total degree {}; degree {d} needs {} monomials (cap {max_monomials}); identities per degree {:?}",
                d - 1,
                monos.len(),
                identities_seen
            ));
        }
        let need = monos.len() + monos.len() / 4 + 40;
        let mut attempts = 0;
        while rel_samples.len() < need || all_samples.len() < need {
            attempts += 1;
            if attempts > 60 * need + 400 {
                return Err("could not sample enough generic tuples".to_string());
            }
            if rel_samples.len() < need {
                if let Some(v) =
                    qs.evaluate(curve, &relation_tuple(curve, pts, qs.m, rng), &mut cache)
                {
                    rel_samples.push(v);
                }
            }
            if all_samples.len() < need {
                if let Some(v) = qs.evaluate(curve, &generic_tuple(pts, qs.m, rng), &mut cache) {
                    all_samples.push(v);
                }
            }
        }
        let rows = |samples: &[Vec<u64>]| -> Vec<Vec<u64>> {
            samples
                .iter()
                .map(|vals| {
                    monos
                        .iter()
                        .map(|e| {
                            let mut t = 1;
                            for (i, &k) in e.iter().enumerate() {
                                if k > 0 {
                                    t = f.mul(t, f.pow(vals[i], k as u64));
                                }
                            }
                            t
                        })
                        .collect()
                })
                .collect()
        };
        let k_rel = kernel(f, rows(&rel_samples), monos.len());
        if k_rel.is_empty() {
            identities_seen.push(0usize);
            continue;
        }
        let k_all = kernel(f, rows(&all_samples), monos.len());
        identities_seen.push(k_all.len());
        let ident_basis = echelon(f, &k_all, &pivot_rank(&monos));
        let mut candidates: Vec<Vec<u64>> = k_rel
            .iter()
            .map(|v| reduce_against(f, v.clone(), &ident_basis))
            .filter(|v| v.iter().any(|&c| c != 0))
            .collect();
        if candidates.is_empty() {
            continue;
        }
        candidates.sort_by_key(|v| v.iter().filter(|&&c| c != 0).count());
        let v = &candidates[0];
        let mut terms: Vec<(Vec<u32>, u64)> = monos
            .iter()
            .zip(v)
            .filter(|(_, &c)| c != 0)
            .map(|(e, &c)| (e.clone(), c))
            .collect();
        let lead = terms.last().map(|t| t.1).unwrap_or(1);
        let inv = f.inv(lead);
        for (_, c) in terms.iter_mut() {
            *c = f.mul(*c, inv);
        }
        let rel = QuotientRelation {
            var_names: names,
            terms,
            total_degree: d,
            kernel_dim: k_rel.len() - k_all.len(),
            verified_on: 0,
        };
        let mut verified = 0;
        let mut tries = 0;
        while verified < 200 && tries < 4000 {
            tries += 1;
            if let Some(vals) =
                qs.evaluate(curve, &relation_tuple(curve, pts, qs.m, rng), &mut cache)
            {
                if rel.eval(f, &vals) != 0 {
                    return Err(format!(
                        "degree-{d} candidate failed on a fresh relation (kernel dims {} / {})",
                        k_rel.len(),
                        k_all.len()
                    ));
                }
                verified += 1;
            }
        }
        let mut fp = 0;
        let mut tested = 0;
        while tested < 200 {
            if let Some(vals) = qs.evaluate(curve, &generic_tuple(pts, qs.m, rng), &mut cache) {
                tested += 1;
                if rel.eval(f, &vals) == 0 {
                    fp += 1;
                }
            }
        }
        if fp * 2 > tested {
            return Err(format!(
                "degree-{d} candidate vanishes on {fp}/{tested} generic tuples: an identity slipped through"
            ));
        }
        return Ok(QuotientRelation {
            verified_on: verified,
            ..rel
        });
    }
    Err(format!(
        "no relation up to total degree {max_total_degree}; identities per degree {identities_seen:?}"
    ))
}

// ── Exact collapse ─────────────────────────────────────────────────

/// Enumerate every relation tuple on the curve and count how many share
/// each invariant vector.  Returns `(tuples counted, distinct vectors,
/// collapse)`; `None` if the enumeration would exceed `max_tuples`.
pub fn exact_collapse(
    curve: &Curve,
    pts: &[Pt],
    qs: &QuotientSystem,
    max_tuples: usize,
) -> Option<(usize, usize, f64)> {
    let m = qs.m;
    let total = pts.len().checked_pow(m as u32)?;
    if total > max_tuples {
        return None;
    }
    let mut counts: HashMap<Vec<u64>, usize> = HashMap::new();
    let mut counted = 0usize;
    let mut cache = EvalCache::default();
    let mut idx = vec![0usize; m];
    loop {
        let mut tuple: Vec<Pt> = idx.iter().map(|&i| pts[i]).collect();
        let sum = tuple.iter().fold(Pt::Inf, |acc, &p| curve.add(acc, p));
        let last = curve.neg(sum);
        if last != Pt::Inf {
            tuple.push(last);
            if let Some(v) = qs.evaluate(curve, &tuple, &mut cache) {
                *counts.entry(v).or_insert(0) += 1;
                counted += 1;
            }
        }
        let mut i = 0;
        loop {
            if i == m {
                break;
            }
            idx[i] += 1;
            if idx[i] < pts.len() {
                break;
            }
            idx[i] = 0;
            i += 1;
        }
        if i == m {
            break;
        }
    }
    if counts.is_empty() {
        return None;
    }
    Some((counted, counts.len(), counted as f64 / counts.len() as f64))
}

// ── Driver ─────────────────────────────────────────────────────────

/// Everything measured about one quotient system.
#[derive(Clone, Debug)]
pub struct QuotientReport {
    pub label: String,
    pub group_order: usize,
    pub gamma_order: usize,
    pub invariants: Vec<String>,
    pub relation: Result<QuotientRelation, String>,
    /// Total degree of the relation with each invariant weighted by its
    /// degree in the `u_i` (the number to compare with a Semaev degree).
    pub weighted_degree: Option<u32>,
    pub collapse: Option<(usize, usize, f64)>,
}

/// Run one candidate: generators, frame, seeds.
pub fn run_quotient(
    curve: &Curve,
    pts: &[Pt],
    label: &str,
    generators: &[PointMap],
    chart: impl Into<Chart>,
    seeds: &[Seed],
    m: usize,
    max_total_degree: u32,
    max_tuples: usize,
    rng: &mut Rng64,
) -> Option<QuotientReport> {
    run_quotient_boxed(
        curve,
        pts,
        label,
        generators,
        chart,
        seeds,
        m,
        max_total_degree,
        None,
        max_tuples,
        rng,
    )
}

/// [`run_quotient`] with the per-variable degree caps of
/// [`interpolate_quotient_boxed`].
#[allow(clippy::too_many_arguments)]
pub fn run_quotient_boxed(
    curve: &Curve,
    pts: &[Pt],
    label: &str,
    generators: &[PointMap],
    chart: impl Into<Chart>,
    seeds: &[Seed],
    m: usize,
    max_total_degree: u32,
    caps: Option<(u32, u32)>,
    max_tuples: usize,
    rng: &mut Rng64,
) -> Option<QuotientReport> {
    let qs = build_quotient_system(curve, pts, generators, chart.into(), seeds, m, rng)?;
    let relation = interpolate_quotient_boxed(curve, pts, &qs, max_total_degree, 3000, caps, rng);
    let weighted_degree = relation.as_ref().ok().and_then(|r| qs.weighted_degree(r));
    let collapse = exact_collapse(curve, pts, &qs, max_tuples);
    Some(QuotientReport {
        label: label.to_string(),
        group_order: qs.group.len(),
        gamma_order: qs.gamma.len(),
        invariants: qs.invariants.iter().map(|i| i.name()).collect(),
        relation,
        weighted_degree,
        collapse,
    })
}

/// The frame that linearises the 2-torsion of the curve, if any, else `x`.
pub fn two_torsion_frame(curve: &Curve, pts: &[Pt], rng: &mut Rng64) -> Mobius {
    for s in detect_symmetries(curve, pts, rng) {
        if let (SymmetryKind::TwoTorsion(_), Some(g), Scope::Pairwise) =
            (&s.kind, s.mobius, s.scope)
        {
            let fr = linearising_frame(&curve.f, &g);
            if fr.kind != FrameKind::Trace {
                return fr.mob;
            }
        }
    }
    Mobius::identity()
}

pub fn format_quotient(f: &Gf, r: &QuotientReport) -> String {
    let mut s = String::new();
    s.push_str(&format!(
        "   [{}]  |G| = {}, |Γ| = {}, invariants: {}\n",
        r.label,
        r.group_order,
        r.gamma_order,
        r.invariants.join(", ")
    ));
    match &r.relation {
        Ok(rel) => s.push_str(&format!(
            "      relation: total degree {} (weighted in u: {}), degrees {:?}, {} terms, kernel dim {}, verified on {}\n      {}\n",
            rel.total_degree,
            r.weighted_degree.map(|d| d.to_string()).unwrap_or_else(|| "algebraic".into()),
            rel.degrees(),
            rel.terms.len(),
            rel.kernel_dim,
            rel.verified_on,
            rel.render(f, 24)
        )),
        Err(e) => s.push_str(&format!("      relation: {e}\n")),
    }
    match r.collapse {
        Some((tuples, vectors, c)) => s.push_str(&format!(
            "      collapse: {c:.1} tuples per vector ({tuples} relation tuples, {vectors} vectors); |Γ| = {}{}\n",
            r.gamma_order,
            if (c - r.gamma_order as f64).abs() < 0.5 {
                " — separates Γ-orbits exactly"
            } else if c > r.gamma_order as f64 {
                " — above |Γ|: the invariants merge distinct Γ-orbits (incomplete), or G misses a symmetry"
            } else {
                " — below |Γ|: degenerate tuples with smaller fibres"
            }
        )),
        None => s.push_str("      collapse: not enumerated (curve too large)\n"),
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::coordinate_search::MobiusKind;

    fn seeds_points(m: usize) -> Vec<Seed> {
        let mut v: Vec<Seed> = (0..=m).map(Seed::Point).collect();
        v.push(Seed::Sum);
        v
    }

    #[test]
    fn two_torsion_quotient_reproduces_the_first_search() {
        // K_1/F_2^7, m = 2: Γ = even-weight T₂ translations × global sign,
        // |Γ| = 2·4 = 8; invariants w_i and s; relation w₁w₂w_R + Σw + s.
        let k = Curve::koblitz(1, 7);
        let pts = k.affine_points();
        let mut rng = Rng64::new(3);
        let t2 = torsion_points(&k, &pts, 2);
        assert_eq!(t2.len(), 1);
        let frame = two_torsion_frame(&k, &pts, &mut rng);
        let gens = vec![PointMap::translate(t2[0]), PointMap::negate()];
        let r = run_quotient(
            &k,
            &pts,
            "T2",
            &gens,
            frame,
            &seeds_points(2),
            2,
            3,
            4_000_000,
            &mut rng,
        )
        .unwrap();
        assert_eq!(r.group_order, 4);
        assert_eq!(r.gamma_order, 8);
        let rel = r.relation.unwrap();
        assert_eq!(rel.total_degree, 3);
        assert_eq!(rel.terms.len(), 5, "{}", rel.render(&k.f, 10));
        assert_eq!(r.weighted_degree, Some(6));
        let (_, _, c) = r.collapse.unwrap();
        assert!((c - 8.0).abs() < 0.3, "collapse {c}");
        // Adding the product seed gives invariants of degree 3 and 6 in
        // the u_i.  A relation of lower total degree may appear among them,
        // but never of lower degree in the u_i than the 5-term one (6).
        let mut with_product = seeds_points(2);
        with_product.push(Seed::Product);
        let r2 = run_quotient(
            &k,
            &pts,
            "T2+Π",
            &gens,
            frame,
            &with_product,
            2,
            3,
            4_000_000,
            &mut rng,
        )
        .unwrap();
        let rel2 = r2.relation.unwrap();
        assert!(rel2.total_degree <= 3, "{}", rel2.render(&k.f, 12));
        assert!(rel2.verified_on >= 100);
        assert!(r2.weighted_degree.unwrap() >= 6);
        assert!((r2.collapse.unwrap().2 - 8.0).abs() < 0.3);
    }

    #[test]
    fn koblitz_k0_has_rational_four_torsion_and_it_acts_on_relations() {
        let k = Curve::koblitz(0, 7);
        let pts = k.affine_points();
        let mut rng = Rng64::new(5);
        let t4: Vec<Pt> = torsion_points(&k, &pts, 4)
            .into_iter()
            .filter(|&p| k.mul(p, 2) != Pt::Inf)
            .collect();
        assert_eq!(t4.len(), 2, "two points of exact order 4");
        let g = group_closure(&k, &[PointMap::translate(t4[0]), PointMap::negate()], 64).unwrap();
        assert_eq!(g.len(), 8);
        let gamma = relation_subgroup(&k, &pts, &g, 2, 12, &mut rng);
        // weights summing to 0 mod 4 (16 of 64) × global sign
        assert_eq!(gamma.len(), 32);
    }

    #[test]
    fn klein_four_on_a_prime_curve_separates_128_orbits() {
        // y² = x³ − x over F_101: full rational 2-torsion.  m = 2:
        // Γ = {(T_i) : ΣT_i = 0} × ±, |Γ| = 16·2 = 32.
        let c = Curve::short_weierstrass(Gf::prime(101), 100, 0, "y²=x³−x");
        let pts = c.affine_points();
        let mut rng = Rng64::new(9);
        let t2 = torsion_points(&c, &pts, 2);
        assert_eq!(t2.len(), 3);
        let frame = two_torsion_frame(&c, &pts, &mut rng);
        let gens: Vec<PointMap> = t2
            .iter()
            .map(|&t| PointMap::translate(t))
            .chain([PointMap::negate()])
            .collect();
        let r = run_quotient(
            &c,
            &pts,
            "E[2]",
            &gens,
            frame,
            &seeds_points(2),
            2,
            4,
            4_000_000,
            &mut rng,
        )
        .unwrap();
        assert_eq!(r.group_order, 8);
        assert_eq!(r.gamma_order, 32);
        let rel = r.relation.unwrap();
        assert!(rel.verified_on >= 100);
        let (_, _, col) = r.collapse.unwrap();
        assert!((col - 32.0).abs() < 0.5, "collapse {col}");
    }

    #[test]
    fn three_torsion_is_velu_on_the_x_line_and_mobius_on_the_y_line() {
        // y² = x³ + 2 over F_1009 (p ≡ 1 mod 3): T = (0, √2) has order 3.
        let f = Gf::prime(1009);
        let b = 2;
        let t = f.sqrt(b).unwrap();
        let c = Curve::short_weierstrass(f.clone(), 0, b, "j=0");
        let t3 = Pt::Aff(0, t);
        assert_eq!(c.mul(t3, 3), Pt::Inf);
        let pts = c.affine_points();
        let mut rng = Rng64::new(5);
        let gens = vec![PointMap::translate(t3), PointMap::negate()];
        // x-line: the only non-constant orbit invariant of x is Vélu's
        // e₁ = x + 4b/x², the x-coordinate on E/⟨T⟩.
        let qs = build_quotient_system(
            &c,
            &pts,
            &gens,
            Mobius::identity(),
            &[Seed::Point(0), Seed::Point(1), Seed::Point(2)],
            2,
            &mut rng,
        )
        .unwrap();
        assert_eq!(qs.group.len(), 6);
        assert_eq!(qs.gamma.len(), 18);
        assert_eq!(
            qs.invariants.len(),
            3,
            "e₂ and e₃ of the orbit are constant"
        );
        assert!(
            !qs.affine_on_u,
            "a 3-torsion translation is not Möbius on x"
        );
        let four_b = f.mul(f.add(f.add(1, 1), f.add(1, 1)), b);
        let mut cache = EvalCache::default();
        for _ in 0..20 {
            let tuple = relation_tuple(&c, &pts, 2, &mut rng);
            if tuple.iter().any(|p| p.x() == 0) {
                continue;
            }
            let vals = qs.evaluate(&c, &tuple, &mut cache).unwrap();
            for (v, p) in vals.iter().zip(&tuple) {
                let x = p.x();
                let velu = f.add(x, f.div(four_b, f.mul(x, x)));
                assert_eq!(*v, velu);
            }
        }
        // y-line: v = (y − s)/(y + s), s = √b·√−3, has τ_T as v ↦ ω^{±1} v
        // and −1 as v ↦ 1/v, so the quotient engine sees an affine map
        // and the invariant v³.
        let three = f.add(f.add(1, 1), 1);
        let s = f.mul(t, f.sqrt(f.neg(three)).unwrap());
        let chart = Chart::y(Mobius {
            a: 1,
            b: f.neg(s),
            c: 1,
            d: s,
        });
        let omega = (2..f.q).find(|&u| u != 1 && f.pow(u, 3) == 1).unwrap();
        for &p in &pts {
            let v = chart.apply(&f, p);
            let vt = chart.apply(&f, c.add(p, t3));
            if v == INF || vt == INF || v == 0 {
                continue;
            }
            assert!(vt == f.mul(omega, v) || vt == f.mul(f.mul(omega, omega), v));
            assert_eq!(chart.apply(&f, c.neg(p)), f.inv(v));
        }
        let qs = build_quotient_system(
            &c,
            &pts,
            &[PointMap::translate(t3)],
            chart,
            &[Seed::Point(0), Seed::Point(1), Seed::Point(2)],
            2,
            &mut rng,
        )
        .unwrap();
        assert!(qs.affine_on_u);
        assert_eq!(qs.gamma.len(), 9);
        assert_eq!(
            qs.invariants.iter().map(|i| i.name()).collect::<Vec<_>>(),
            ["e3[u1]", "e3[u2]", "e3[u3]"]
        );
        let tuple = relation_tuple(&c, &pts, 2, &mut rng);
        let vals = qs.evaluate(&c, &tuple, &mut EvalCache::default()).unwrap();
        for (v, p) in vals.iter().zip(&tuple) {
            let u = chart.apply(&f, *p);
            assert_eq!(*v, f.pow(u, 3));
        }
    }

    #[test]
    fn torsion_translations_become_mobius_maps_on_the_new_lines() {
        let f = Gf::prime(1009);
        // (a) j = 1728, a a non-square: τ_T is Möbius on x (x ↦ a/x) with
        // irrational fixed points, and Möbius on x² with rational ones.
        let a = (2..f.p).find(|&a| f.sqrt(a).is_none()).unwrap();
        let c = Curve::short_weierstrass(f.clone(), a, 0, "j=1728");
        let pts = c.affine_points();
        let tau = PointMap::translate(Pt::Aff(0, 0));
        let on_x = descended_map(&c, &pts, Line::X, &tau).unwrap();
        assert_eq!(on_x.kind(&f), MobiusKind::Inversion(a));
        let (_, kind_x, _) = linearised_chart(&c, &pts, Line::X, &tau).unwrap();
        assert_eq!(kind_x, FrameKind::Trace, "±√a irrational");
        let (chart, kind, m) = linearised_chart(&c, &pts, Line::X2, &tau).unwrap();
        assert_eq!(m.kind(&f), MobiusKind::Inversion(f.mul(a, a)));
        assert_eq!(kind, FrameKind::Sign);
        for &p in pts.iter().take(200) {
            let v = chart.apply_on(&c, p);
            let vt = chart.apply_on(&c, c.add(p, Pt::Aff(0, 0)));
            if v != INF && vt != INF {
                assert_eq!(vt, f.neg(v));
            }
        }
        // (b) rational 4-torsion: τ_{T₄} is not Möbius on x but is on the
        // 2-isogeny line, as an involution
        let b = 2u64;
        let c4 = Curve {
            a1: 1,
            a2: f.neg(b),
            a3: f.neg(b),
            a4: 0,
            a6: 0,
            label: "4-torsion".into(),
            f: f.clone(),
        };
        let pts = c4.affine_points();
        let t4 = Pt::Aff(0, 0);
        assert_eq!(c4.mul(t4, 4), Pt::Inf);
        let t2 = c4.mul(t4, 2);
        let tau4 = PointMap::translate(t4);
        assert!(descended_map(&c4, &pts, Line::X, &tau4).is_none());
        let m = descended_map(&c4, &pts, Line::Iso2(t2), &tau4).unwrap();
        assert_eq!(m.order(&f, 8), Some(2));
        // (c) 6-torsion on y² = x³ + 1: τ_{T₂} and ω are Möbius on the
        // 3-isogeny line, τ_{T₃} acts trivially there
        let cb = Curve::short_weierstrass(f.clone(), 0, 1, "j=0");
        let pts = cb.affine_points();
        let t3 = Pt::Aff(0, 1);
        let t2 = torsion_points(&cb, &pts, 2)[0];
        let line = Line::Iso3(t3);
        assert!(descended_map(&cb, &pts, Line::X, &PointMap::translate(t3)).is_none());
        let m2 = descended_map(&cb, &pts, line, &PointMap::translate(t2)).unwrap();
        assert_eq!(m2.order(&f, 8), Some(2));
        let m3 = descended_map(&cb, &pts, line, &PointMap::translate(t3)).unwrap();
        assert!(m3.is_identity(&f));
        let omega = (2..f.p).find(|&u| u != 1 && f.pow(u, 3) == 1).unwrap();
        let om = PointMap {
            auto: Auto::Scale(omega),
            t: Pt::Inf,
        };
        let mo = descended_map(&cb, &pts, line, &om).unwrap();
        assert!(matches!(mo.kind(&f), MobiusKind::Scaling(_)));
    }

    #[test]
    fn four_torsion_on_the_two_isogeny_line_gives_a_system() {
        let f = Gf::prime(1009);
        let b = 2u64;
        let c4 = Curve {
            a1: 1,
            a2: f.neg(b),
            a3: f.neg(b),
            a4: 0,
            a6: 0,
            label: "4-torsion".into(),
            f: f.clone(),
        };
        let pts = c4.affine_points();
        let t4 = Pt::Aff(0, 0);
        let t2 = c4.mul(t4, 2);
        let tau4 = PointMap::translate(t4);
        let (chart, kind, _) = linearised_chart(&c4, &pts, Line::Iso2(t2), &tau4).unwrap();
        assert_eq!(kind, FrameKind::Sign);
        let mut rng = Rng64::new(9);
        let group = group_closure(&c4, &[tau4, PointMap::negate()], 64).unwrap();
        assert_eq!(group.len(), 8);
        let gamma = relation_subgroup(&c4, &pts, &group, 2, 12, &mut rng);
        assert_eq!(gamma.len(), 32, "16 translation triples × global sign");
        let probes: Vec<Vec<Pt>> = (0..24)
            .map(|_| relation_tuple(&c4, &pts, 2, &mut rng))
            .collect();
        let ok = probes
            .iter()
            .filter(|t| orbit_set(&c4, &chart, &gamma, &Seed::Point(0), t).is_some())
            .count();
        assert!(ok >= 8, "only {ok} probe tuples have a full orbit set");
        let qs = build_quotient_system(
            &c4,
            &pts,
            &[tau4, PointMap::negate()],
            chart,
            &[
                Seed::Point(0),
                Seed::Point(1),
                Seed::Point(2),
                Seed::Product,
            ],
            2,
            &mut rng,
        );
        assert!(qs.is_some());
    }

    #[test]
    fn a_translation_descends_to_the_quotient_by_an_automorphism_iff_its_point_is_fixed() {
        // On E/⟨α⟩ the translation by Q is a Möbius map iff α(Q) = Q, i.e.
        // Q ∈ E[1 − α]: E[2] for α = −1 (the Klein group on x), the three
        // points {O, ±T₃} for α = ω on the y-line, {O, T₂} for α = i on the
        // x²-line.  So no line carries all of E[3].
        let f = Gf::prime(1009);
        // j = 0 with full rational E[3]: −4b a cube and −3b a square
        let cube = |a: u64| f.pow(a, (f.p - 1) / 3) == 1;
        let b = (1..f.p)
            .find(|&b| {
                f.sqrt(b).is_some()
                    && cube(f.neg(f.mul(4, b)))
                    && f.sqrt(f.neg(f.mul(3, b))).is_some()
            })
            .unwrap();
        let c = Curve::short_weierstrass(f.clone(), 0, b, "j=0");
        let pts = c.affine_points();
        let e3 = torsion_points(&c, &pts, 3);
        assert_eq!(e3.len(), 8, "full E[3] rational");
        let omega = (2..f.p).find(|&u| u != 1 && f.pow(u, 3) == 1).unwrap();
        let om = Auto::Scale(omega);
        let mut descend = 0;
        for &q in &e3 {
            let fixed = c.apply_auto(om, q) == q;
            let m = descended_map(&c, &pts, Line::Y, &PointMap::translate(q));
            assert_eq!(m.is_some(), fixed, "{q:?}");
            descend += usize::from(fixed);
        }
        assert_eq!(descend, 2, "only ±T₃ = (0, ±√b)");
        // j = 1728 with full rational E[2]: a a square (x² + a splits)
        let i = (2..f.p).find(|&u| f.mul(u, u) == f.neg(1)).unwrap();
        let a = (2..f.p).find(|&a| f.sqrt(f.neg(a)).is_some()).unwrap();
        let c = Curve::short_weierstrass(f.clone(), a, 0, "j=1728");
        let pts = c.affine_points();
        let e2 = torsion_points(&c, &pts, 2);
        assert_eq!(e2.len(), 3);
        let iota = Auto::Scale(i);
        let mut descend = 0;
        for &q in &e2 {
            let fixed = c.apply_auto(iota, q) == q;
            let m = descended_map(&c, &pts, Line::X2, &PointMap::translate(q));
            assert_eq!(m.is_some(), fixed, "{q:?}");
            descend += usize::from(fixed);
            // on the x-line (quotient by −1) every 2-torsion translation descends
            assert!(descended_map(&c, &pts, Line::X, &PointMap::translate(q)).is_some());
        }
        assert_eq!(descend, 1, "only T = (0, 0)");
    }
}
