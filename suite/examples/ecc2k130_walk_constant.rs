//! **The iteration constant of an ECC2K-130 walk, measured.**
//!
//! Parallel rho on classes of `⟨σ, −1⟩` expects `c · √(πN/2)` iterations,
//! `N = (ℓ − 1)/2n` classes, where `c` is the walk's own constant: how far
//! it falls short of a random mapping (`c = 1`).  The campaign's planning
//! figure `2^60.9` is `√(πN/2) = 2^60.81` times `1.069`, the first-order
//! penalty `1/√(1 − 1/r)` of an `r = 8` branch walk — assumed, not
//! measured.  This measures `c` for the two iteration functions in
//! `ecc2k130/` (`ecc2k130/WALK-CONSTANT.md` has the method and the numbers):
//!
//! - `sigma`: `R ← R + σʲ(R)`, `j = 3 + b` — the shipping walk;
//! - `table`: `R ← R + ε σᵏ(T_h)`, `h = b` — the table walk
//!   (`ecc2k130/ITERATION-FUNCTION.md` §4), built as the device builds it: the
//!   walk carries the point itself, the step's tag `(h, k, ε)` names the
//!   addend, and the tag-history rule of `ecc2k130/include/tablewalk.h`
//!   advances `h` past a step that would undo the last one or close a
//!   4-cycle with the three before it.  Only the frame differs: here `k` and
//!   `ε` come from the canonical representative of the class (least rotation
//!   of the normal-basis `x`, least `y` of `±`), where the device derives them
//!   from a phase and a pivot bit.  Both frames satisfy `k(σR) = k(R) + 1` and
//!   `ε(−R) = 1 − ε(R)`, which is all the walk's class structure and the
//!   cycle rule use.
//! - `adding`: the table walk with hundreds of uniform branches, a control
//!   whose constant is `≈ 1`.
//!
//! and three ways of choosing the branch `b`, all class-invariant:
//!
//! - `native`: `(HW(x)/2) mod H`, the weight of `x` in a normal basis, as the
//!   device does.  Its distribution depends on the degree — `HW/2` has a
//!   standard deviation of `√n/4` — so at the small degrees this can run it
//!   is *not* ECC2K-130's.
//! - `uniform`: a hash of the class, uniform over `H`.
//! - `ecc2k130`: a hash of the class mapped onto the exact branch
//!   probabilities `(HW/2) mod H` has at `n = 131` (`HW` binomial, even).
//!
//! The count is the one a campaign pays for: `W` walks from random starts,
//! stepped in turn, until one of them lands on a class any of them has
//! visited — found exactly with a set of canonical keys, so no
//! distinguished points, no launch granularity and no tail.  The number of
//! distinct classes visited by then has mean `1 + Q(N)` for a random mapping
//! (every new point is a fresh uniform one until the first repeat), and `c`
//! is the measured mean over that.  Many walks rather than one, because a
//! single walk's rho length is set by the cycle of the component it lands
//! in and does not average; and a fresh mapping per trial (the hash salt,
//! the table) so that trials average over mappings as well as starts.
//!
//! **Fruitless cycles.**  An additive walk can return to a point it left a
//! few steps ago with no collision at all: steps whose addends cancel in
//! pairs.  The cycle rule removes the 2- and 4-step ones; longer ones remain,
//! and a walk that enters one never reaches a distinguished point.  Such a
//! return is not a collision and is not counted as one: every table step
//! compares the new point with the walk's last `RECENT` points, and a return
//! whose tags cancel in pairs is recorded by its length, and the walk
//! restarts from a fresh point.  Returns come in two formal kinds, counted
//! apart: tags that cancel in pairs (6 steps and up get past the rule), and
//! steps whose addends sum to zero through Frobenius itself — `τ² + τ + 2 = 0`
//! makes `σ^{k+2}T + σ^{k+1}T + σ^kT + σ^kT = O`, four steps and no pair.
//! The per-step rates are reported beside the leading-order predictions
//! `4(Σp²)³/(2n)³` and `24Σp⁴/(2n)³` (the number of patterns the rule lets
//! through, times the chance each determined tag comes up: a pair's second
//! tag matches its first with probability `Σp²/2n`, and a relation's four
//! steps all share one branch); what a trapped
//! walk costs a campaign is priced in the note, not here.  An exact return
//! that is not formal is a genuine collision and is scored as one.
//!
//! The normal basis here is `FrobeniusCanon`'s, not the device's type-II
//! optimal one, so `native` picks different branches for a given point than
//! the device would; `ecc2k130/src/walkconstant.cpp` runs the device's own
//! walks for comparison.
//!
//! Usage:
//! `cargo run --release --example ecc2k130_walk_constant -- --n 41 --walk sigma --dist ecc2k130 --trials 10000`
//! (`--walks W`, default 16; `--branches H`, `--seed S`, `--threads K`; one
//! JSON line on stdout).  `--rule v2` (the default) is the device's cycle rule
//! as extended in `WALK-CONSTANT.md` §11; `--rule v1` is the one before it,
//! which `matrix-v2` ran under.  The `*_predicted` fields are always rule
//! v1's leading-order counts, so a `v2` row reads as what the extension
//! removed.  `--merge N` instead runs N merge trials: two walks meet at one
//! point carrying different pasts, and the tool counts how often the rule
//! parts them within 16 steps (a lost collision under distinguished
//! points).  `--fixed-mapping` draws the mapping once, from the
//! seed, and runs every trial on it: the constant of *one* mapping, which is
//! what a campaign pays, where the default averages over mappings.  The
//! `native` σ walk has only one mapping per degree whatever the flag says.
use std::collections::HashSet;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{FastCurve, FastPoint, FrobeniusCanon};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use num_traits::ToPrimitive;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

#[derive(Clone, Copy, PartialEq, Debug)]
enum Walk {
    Sigma,
    Table,
    Adding,
}

#[derive(Clone, Copy, PartialEq, Debug)]
enum Dist {
    Native,
    Uniform,
    Ecc2k130,
}

/// How many of a walk's own recent points a step is compared with.
const RECENT: usize = 16;

/// Step tag `(h, k, ε)`: `h` in bits 0–15, `k` in 16–23, `ε` in bit 24, as
/// `tablewalk.h` packs them with wider fields.  Two tags name opposite
/// addends exactly when they differ in `ε` alone.
const TAG_EPS: u32 = 1 << 24;
const TAG_NONE: u32 = u32::MAX;

fn tag(h: usize, k: u32, eps: bool) -> u32 {
    h as u32 | (k << 16) | (u32::from(eps) << 24)
}

/// Which cycle rule the table walk applies (`--rule`): the device's, as
/// extended in `WALK-CONSTANT.md` §11, or the one before it.
#[derive(Clone, Copy, PartialEq, Debug)]
enum Rule {
    /// Refuse a step that undoes the last one, or that with the last one
    /// undoes the two before: the rule `matrix-v2` ran under.
    V1,
    /// Refuse a step that undoes any of the last four, or that closes a
    /// τ-relation with the last three: `eccTagFruitless` today.
    V2,
}

/// The tag `d` phases on from `t`, same branch and sign, `k` mod `n`.
fn advance_k(t: u32, d: u32, n: u32) -> u32 {
    let k = ((t >> 16) & 0xff) + d;
    let k = if k >= n { k - n } else { k };
    (t & !(0xff << 16)) | (k << 16)
}

/// `eccTauPartners`: with `r` the repeated tag, whether `{u, v}` sit at
/// `(k+1, ε), (k+2, ε)` or at `(k+1, −ε), (k+3, −ε)`.
fn tau_partners(r: u32, u: u32, v: u32, n: u32) -> bool {
    let (a1, a2) = (advance_k(r, 1, n), advance_k(r, 2, n));
    let (b1, b3) = (a1 ^ TAG_EPS, advance_k(r, 3, n) ^ TAG_EPS);
    (u == a1 && v == a2) || (u == a2 && v == a1) || (u == b1 && v == b3) || (u == b3 && v == b1)
}

/// `eccTauRelation`: four steps on one branch summing to `O` through
/// `τ² + τ + 2 = 0` or `τ³ + τ − 2 = 0`.
fn tau_relation(t: u32, t1: u32, t2: u32, t3: u32, n: u32) -> bool {
    if ((t ^ t1) | (t ^ t2) | (t ^ t3)) & 0xffff != 0 {
        return false;
    }
    if [t1, t2, t3].iter().any(|&u| (u >> 16) & 0xff >= n) {
        return false;
    }
    if t == t1 {
        tau_partners(t, t2, t3, n)
    } else if t == t2 {
        tau_partners(t, t1, t3, n)
    } else if t == t3 {
        tau_partners(t, t1, t2, n)
    } else if t1 == t2 {
        tau_partners(t1, t, t3, n)
    } else if t1 == t3 {
        tau_partners(t1, t, t2, n)
    } else if t2 == t3 {
        tau_partners(t2, t, t1, n)
    } else {
        false
    }
}

/// `eccTagFruitless` under `rule`.  `hist = [t1, t2, t3, t4]`, most recent
/// first.
fn fruitless(rule: Rule, t: u32, hist: &[u32; 4], n: u32) -> bool {
    match rule {
        Rule::V1 => {
            (t ^ hist[0]) == TAG_EPS || ((t ^ hist[1]) == TAG_EPS && (hist[0] ^ hist[2]) == TAG_EPS)
        }
        Rule::V2 => {
            hist.iter().any(|&u| (t ^ u) == TAG_EPS)
                || tau_relation(t, hist[0], hist[1], hist[2], n)
        }
    }
}

/// Whether steps with these tags return a walk to where it started, for
/// every table: per branch `h`, the signed sum of `τ^k` over its steps is 0
/// in `Z[τ]`, `τ² + τ + 2 = 0` (Frobenius on these curves, `σ² + σ + 2 = 0`).
/// Exponents are taken from the element after the largest cyclic gap in
/// `k mod n`, which is exact for any relation spanning less than `n`.
fn returns_formally(tags: &[u32], n: u32) -> bool {
    let mut branches: Vec<u32> = tags.iter().map(|t| t & 0xffff).collect();
    branches.sort_unstable();
    branches.dedup();
    branches.iter().all(|&h| {
        let mut ks: Vec<u32> = tags
            .iter()
            .filter(|t| *t & 0xffff == h)
            .map(|t| (t >> 16) & 0xff)
            .collect();
        ks.sort_unstable();
        ks.dedup();
        // Start just after the largest gap between consecutive k (cyclically).
        let base = (0..ks.len())
            .max_by_key(|&i| (ks[(i + 1) % ks.len()] + n - ks[i] - 1) % n)
            .map_or(0, |i| ks[(i + 1) % ks.len()]);
        let (mut a, mut b) = (0i64, 0i64);
        for &t in tags.iter().filter(|t| *t & 0xffff == h) {
            let d = (((t >> 16) & 0xff) + n - base) % n;
            // τ^d = x + yτ, from τ^{j+1} = −2y + (x − y)τ.
            let (mut x, mut y) = (1i64, 0i64);
            for _ in 0..d {
                (x, y) = (-2 * y, x - y);
            }
            let sign = if t & TAG_EPS != 0 { -1 } else { 1 };
            a += sign * x;
            b += sign * y;
        }
        a == 0 && b == 0
    })
}

/// Whether the tags cancel in pairs: every tag's opposite is there as often.
fn cancels(tags: &[u32]) -> bool {
    let mut left: Vec<u32> = tags.to_vec();
    while let Some(t) = left.pop() {
        match left.iter().position(|&u| u == t ^ TAG_EPS) {
            Some(i) => {
                left.swap_remove(i);
            }
            None => return false,
        }
    }
    true
}

fn splitmix(mut z: u64) -> u64 {
    z = z.wrapping_add(0x9e37_79b9_7f4a_7c15);
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

/// `P[(HW/2) mod h]` for `HW` binomial on `n` coordinates, conditioned even:
/// the branch distribution of the device's selection at degree `n`.
fn weight_branch_probabilities(n: u32, h: usize) -> Vec<f64> {
    // log C(n, k), summed in logs to stay finite at n = 131.
    let ln_c = |k: u32| -> f64 { (1..=k).map(|i| ((n - k + i) as f64 / i as f64).ln()).sum() };
    let mut p = vec![0.0; h];
    let mut total = 0.0;
    for k in (0..=n).step_by(2) {
        let w = ln_c(k).exp();
        p[(k as usize / 2) % h] += w;
        total += w;
    }
    p.iter().map(|x| x / total).collect()
}

/// Exact expected number of distinct points a random mapping on `n` points
/// visits from a random start before the first repeat: `1 + Q(n)`.
fn random_mapping_rho(n: f64) -> f64 {
    let (mut term, mut sum, mut k) = (1.0f64, 1.0f64, 1.0f64);
    while term > 1e-15 && k < n {
        term *= 1.0 - k / n;
        sum += term;
        k += 1.0;
    }
    sum
}

struct Setup {
    walk: Walk,
    dist: Dist,
    branches: usize,
    curve: FastCurve,
    canon: FrobeniusCanon,
    n: u32,
    ell: u64,
    generator: FastPoint,
    walks: usize,
    /// Cumulative `ecc2k130` branch probabilities, scaled to `u64`.
    cdf: Vec<u64>,
    /// Whether squaring rotates the normal coordinates left (else right).
    squaring_rotates_left: bool,
    /// The one mapping every trial uses, under `--fixed-mapping`.
    fixed: Option<Mapping>,
    /// The table walk's cycle rule.
    rule: Rule,
}

/// The part of a mapping a trial draws for itself.
struct Mapping {
    table: Vec<FastPoint>,
    salt: u64,
}

/// One walk: where it is, its last three tags, and its recent trail.
struct WalkState {
    p: FastPoint,
    hist: [u32; 4],
    recent: [(FastPoint, u32); RECENT],
    len: usize,
}

#[derive(Default, Clone)]
struct Tally {
    trials: u64,
    visited: f64,
    visited_sq: f64,
    branch_counts: Vec<u64>,
    even: u64,
    weighed: u64,
    cycle_rule: u64,
    restarts: u64,
    /// `fruitless[L]`: returns to the point `L` steps back whose tags cancel
    /// in pairs.
    fruitless: [u64; RECENT + 1],
    /// `relation[L]`: formal returns that are not pairwise — the steps of a
    /// branch sum to zero through `τ² + τ + 2 = 0`.
    relation: [u64; RECENT + 1],
    /// Exact short returns that are not formal (genuine collisions).
    short_returns: u64,
}

impl Tally {
    fn add(&mut self, t: &Tally) {
        self.trials += t.trials;
        self.visited += t.visited;
        self.visited_sq += t.visited_sq;
        self.even += t.even;
        self.weighed += t.weighed;
        self.cycle_rule += t.cycle_rule;
        self.restarts += t.restarts;
        self.short_returns += t.short_returns;
        for (x, y) in self.branch_counts.iter_mut().zip(&t.branch_counts) {
            *x += y;
        }
        for (x, y) in self.fruitless.iter_mut().zip(&t.fruitless) {
            *x += y;
        }
        for (x, y) in self.relation.iter_mut().zip(&t.relation) {
            *x += y;
        }
    }
}

impl Setup {
    fn rotl(&self, v: u64, r: u32) -> u64 {
        let n = self.n;
        let mask = (1u64 << n) - 1;
        let r = r % n;
        if r == 0 {
            v
        } else {
            ((v << r) | (v >> (n - r))) & mask
        }
    }

    /// The class key: least rotation of the normal coordinates of `x`.
    fn key(&self, p: &FastPoint) -> u64 {
        self.canon.canon(p.x)
    }

    fn branch(&self, m: &Mapping, p: &FastPoint, key: u64) -> usize {
        match self.dist {
            Dist::Native => {
                let hw = self.canon.coords(p.x).count_ones() as usize;
                (hw / 2) % self.branches
            }
            Dist::Uniform => (splitmix(key ^ m.salt) as usize) % self.branches,
            Dist::Ecc2k130 => {
                let u = splitmix(key ^ m.salt);
                self.cdf
                    .iter()
                    .position(|&c| u < c)
                    .unwrap_or(self.branches - 1)
            }
        }
    }

    /// The frame `(k, ε)` of a point: the canonical member of its class is
    /// `(−1)^ε σ^{−k}(p)` — the conjugate whose normal coordinates are the
    /// least rotation, and of `±` the one with the smaller `y` coordinates —
    /// so `k(σp) = k(p) + 1` and `ε(−p) = 1 − ε(p)`.
    fn frame(&self, p: &FastPoint) -> (u32, bool) {
        let c = self.canon.coords(p.x);
        let least = self.canon.canon(p.x);
        let r = (0..self.n)
            .find(|&r| self.rotl(c, r) == least)
            .expect("a rotation");
        // σ^j rotates the coordinates by j one way or the other.
        let j = if self.squaring_rotates_left {
            r
        } else {
            (self.n - r) % self.n
        };
        let q = self.curve.frobenius_k(*p, j);
        let neg = self.curve.neg(q);
        let eps = self.canon.coords(neg.y) < self.canon.coords(q.y);
        ((self.n - j) % self.n, eps)
    }

    /// The addend a tag names: `(−1)^ε σ^k(T_h)`.
    fn addend(&self, m: &Mapping, t: u32) -> FastPoint {
        let (h, k, eps) = ((t & 0xffff) as usize, (t >> 16) & 0xff, t & TAG_EPS != 0);
        let a = self.curve.frobenius_k(m.table[h], k);
        if eps {
            self.curve.neg(a)
        } else {
            a
        }
    }

    /// One table step from `w` on branch `b`: the tag after the cycle rule,
    /// pushed into the walk's history, and the point it leads to (the walk's
    /// own point is left for the caller to move).  Also whether the rule
    /// fired.
    fn table_step(&self, m: &Mapping, w: &mut WalkState, b: usize) -> (FastPoint, u32, bool) {
        let (k, eps) = self.frame(&w.p);
        let raw = tag(b, k, eps);
        let mut tg = raw;
        // The device's cycle rule: advance h past a fruitless step.
        for _ in 0..self.branches {
            if !fruitless(self.rule, tg, &w.hist, self.n) {
                break;
            }
            tg = tag(((tg & 0xffff) as usize + 1) % self.branches, k, eps);
        }
        w.hist = [tg, w.hist[0], w.hist[1], w.hist[2]];
        (self.curve.add(w.p, self.addend(m, tg)), tg, tg != raw)
    }

    fn mapping(&self, rng: &mut StdRng) -> Mapping {
        let table = match self.walk {
            Walk::Sigma => Vec::new(),
            Walk::Table | Walk::Adding => (0..self.branches)
                .map(|_| {
                    self.curve
                        .mul_u64(self.generator, rng.gen_range(1..self.ell))
                })
                .collect(),
        };
        Mapping {
            table,
            salt: rng.gen(),
        }
    }

    fn start(&self, rng: &mut StdRng) -> WalkState {
        let p = self
            .curve
            .mul_u64(self.generator, rng.gen_range(1..self.ell));
        WalkState {
            p,
            hist: [TAG_NONE; 4],
            recent: [(p, TAG_NONE); RECENT],
            len: 0,
        }
    }
}

/// One trial: a mapping, `W` walks from random starts stepped in turn,
/// stopped at the first class visited twice that is not a fruitless return.
fn trial(s: &Setup, rng: &mut StdRng, t: &mut Tally) {
    let drawn;
    let m = match &s.fixed {
        Some(m) => m,
        None => {
            drawn = s.mapping(rng);
            &drawn
        }
    };
    let mut seen: HashSet<u64> = HashSet::new();
    let mut walks: Vec<WalkState> = Vec::with_capacity(s.walks);
    for _ in 0..s.walks {
        let w = s.start(rng);
        if !seen.insert(s.key(&w.p)) {
            // Two starts in one class: a collision before any step.
            t.trials += 1;
            let v = seen.len() as f64;
            t.visited += v;
            t.visited_sq += v * v;
            return;
        }
        walks.push(w);
    }
    'run: loop {
        for w in walks.iter_mut() {
            let key = s.key(&w.p);
            if t.weighed < 1 << 20 {
                let hw = s.canon.coords(w.p.x).count_ones();
                t.even += u64::from(hw & 1 == 0);
                t.weighed += 1;
            }
            let b = s.branch(m, &w.p, key);
            t.branch_counts[b] += 1;
            let next = if s.walk == Walk::Sigma {
                s.curve.add(w.p, s.curve.frobenius_k(w.p, 3 + b as u32))
            } else {
                let (next, tg, fired) = s.table_step(m, w, b);
                t.cycle_rule += u64::from(fired);
                // A return to one of the walk's own recent points whose tags
                // cancel is a fruitless cycle, not a collision.
                let slot = w.len % RECENT;
                w.recent[slot] = (w.p, tg);
                w.len += 1;
                let mut formal_len = 0;
                for l in 1..=RECENT.min(w.len) {
                    let (q, _) = w.recent[(w.len - l) % RECENT];
                    if q == next {
                        let tags: Vec<u32> =
                            (1..=l).map(|i| w.recent[(w.len - i) % RECENT].1).collect();
                        if cancels(&tags) {
                            t.fruitless[l] += 1;
                            formal_len = l;
                        } else if returns_formally(&tags, s.n) {
                            t.relation[l] += 1;
                            formal_len = l;
                        } else {
                            t.short_returns += 1;
                        }
                        break;
                    }
                }
                if formal_len > 0 {
                    *w = s.start(rng);
                    if !seen.insert(s.key(&w.p)) {
                        break 'run;
                    }
                    continue;
                }
                next
            };
            if next.infinity {
                // O has no class; a probability-1/ℓ event, reported.
                t.restarts += 1;
                return;
            }
            w.p = next;
            if !seen.insert(s.key(&w.p)) {
                break 'run;
            }
        }
    }
    let v = seen.len() as f64;
    t.trials += 1;
    t.visited += v;
    t.visited_sq += v * v;
}

/// How often two walks that meet at one point part again.
#[derive(Default, Clone)]
struct MergeTally {
    trials: u64,
    /// `parted[i]`: pairs whose points first differ after step `i + 1`.
    parted: [u64; MERGE_STEPS],
    branch_counts: Vec<u64>,
}

/// Steps after a merge in which a parting is looked for: the rule reads four
/// tags back, so after four steps both walks carry the same history.
const MERGE_STEPS: usize = 16;

/// One merge: two walks, each eight steps into its own trail, are put on the
/// same point with their own histories -- as when one trail lands on
/// another -- and stepped together.  If the rule decides differently for
/// their different pasts they part, and the collision is lost to
/// distinguished points.
fn merge_trial(s: &Setup, rng: &mut StdRng, t: &mut MergeTally) {
    let drawn;
    let m = match &s.fixed {
        Some(m) => m,
        None => {
            drawn = s.mapping(rng);
            &drawn
        }
    };
    let (mut a, mut b) = (s.start(rng), s.start(rng));
    for w in [&mut a, &mut b] {
        for _ in 0..8 {
            let key = s.key(&w.p);
            let br = s.branch(m, &w.p, key);
            let (next, _, _) = s.table_step(m, w, br);
            if next.infinity {
                return;
            }
            w.p = next;
        }
    }
    b.p = a.p;
    for i in 0..MERGE_STEPS {
        let key = s.key(&a.p);
        let br = s.branch(m, &a.p, key);
        t.branch_counts[br] += 1;
        let (na, _, _) = s.table_step(m, &mut a, br);
        let (nb, _, _) = s.table_step(m, &mut b, br);
        if na != nb {
            t.parted[i] += 1;
            t.trials += 1;
            return;
        }
        if na.infinity {
            return;
        }
        a.p = na;
        b.p = nb;
    }
    t.trials += 1;
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let get = |name: &str| -> Option<String> {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1).cloned())
    };
    let n: u32 = get("--n").map_or(41, |v| v.parse().expect("--n"));
    let walk = match get("--walk").as_deref().unwrap_or("sigma") {
        "sigma" => Walk::Sigma,
        "table" => Walk::Table,
        "adding" => Walk::Adding,
        w => panic!("unknown walk {w}"),
    };
    let dist = match get("--dist").as_deref().unwrap_or("ecc2k130") {
        "native" => Dist::Native,
        "uniform" => Dist::Uniform,
        "ecc2k130" => Dist::Ecc2k130,
        d => panic!("unknown dist {d}"),
    };
    let branches: usize = get("--branches").map_or(
        match walk {
            Walk::Sigma => 8,
            Walk::Table => 8,
            Walk::Adding => 256,
        },
        |v| v.parse().expect("--branches"),
    );
    assert!(
        walk != Walk::Sigma || branches == 8,
        "the sigma walk has eight branches"
    );
    assert!(branches <= 1 << 16, "at most 2^16 branches");
    let trials: u64 = get("--trials").map_or(1000, |v| v.parse().expect("--trials"));
    let seed: u64 = get("--seed").map_or(1, |v| v.parse().expect("--seed"));
    let walks: usize = get("--walks").map_or(16, |v| v.parse().expect("--walks"));
    let threads: usize = get("--threads").map_or_else(
        || std::thread::available_parallelism().map_or(1, |p| p.get()),
        |v| v.parse().expect("--threads"),
    );

    let kc = KoblitzCurve::new(0, n).expect("a Koblitz curve with a = 0 at this degree");
    let ell = kc
        .subgroup_order
        .to_u64()
        .expect("a subgroup order below 2^64");
    let curve = FastCurve::new(&kc.curve).expect("a single-word field");
    let canon = FrobeniusCanon::new(&curve.field, n).expect("a normal element");
    let generator = curve.lift(kc.generator());
    // Which way squaring turns the coordinates, found once.
    let probe = generator.x;
    let squaring_rotates_left = {
        let c = canon.coords(probe);
        let c2 = canon.coords(curve.field.sqr(probe));
        let mask = (1u64 << n) - 1;
        c2 == ((c << 1) | (c >> (n - 1))) & mask
    };
    let p131 = weight_branch_probabilities(131, branches);
    let mut cdf = Vec::with_capacity(branches);
    let mut acc = 0.0;
    for &p in &p131 {
        acc += p;
        cdf.push(if acc >= 1.0 {
            u64::MAX
        } else {
            (acc * 2f64.powi(64)) as u64
        });
    }
    let fixed_mapping = args.iter().any(|a| a == "--fixed-mapping");
    let rule = match get("--rule").as_deref().unwrap_or("v2") {
        "v1" => Rule::V1,
        "v2" => Rule::V2,
        r => panic!("unknown rule {r}"),
    };
    let mut setup = Setup {
        walk,
        dist,
        branches,
        curve,
        canon,
        n,
        ell,
        generator,
        walks,
        cdf,
        squaring_rotates_left,
        fixed: None,
        rule,
    };
    if fixed_mapping {
        let mut rng = StdRng::seed_from_u64(splitmix(seed ^ 0x6d61_7070_696e_6721));
        setup.fixed = Some(setup.mapping(&mut rng));
    }

    let merge: u64 = get("--merge").map_or(0, |v| v.parse().expect("--merge"));
    if merge > 0 {
        assert!(
            walk != Walk::Sigma,
            "the sigma walk has no history to part on"
        );
        let next = AtomicU64::new(0);
        let total = Mutex::new(MergeTally {
            branch_counts: vec![0; branches],
            ..MergeTally::default()
        });
        std::thread::scope(|scope| {
            for tid in 0..threads {
                let (setup, next, total) = (&setup, &next, &total);
                scope.spawn(move || {
                    let mut t = MergeTally {
                        branch_counts: vec![0; setup.branches],
                        ..MergeTally::default()
                    };
                    let mut rng =
                        StdRng::seed_from_u64(splitmix(seed.wrapping_mul(1_000_003) + tid as u64));
                    while next.fetch_add(1, Ordering::Relaxed) < merge {
                        merge_trial(setup, &mut rng, &mut t);
                    }
                    let mut g = total.lock().unwrap();
                    g.trials += t.trials;
                    for (x, y) in g.parted.iter_mut().zip(&t.parted) {
                        *x += y;
                    }
                    for (x, y) in g.branch_counts.iter_mut().zip(&t.branch_counts) {
                        *x += y;
                    }
                });
            }
        });
        let t = total.into_inner().unwrap();
        let steps: u64 = t.branch_counts.iter().sum();
        let s2: f64 = t
            .branch_counts
            .iter()
            .map(|&c| (c as f64 / steps as f64).powi(2))
            .sum();
        let q = s2 / (2.0 * n as f64);
        let parted: u64 = t.parted.iter().sum();
        let rate = parted as f64 / t.trials as f64;
        let se = (rate * (1.0 - rate) / t.trials as f64).sqrt();
        // Leading order: a parting needs the tag at the meeting point, or one
        // of the next three, to negate a tag from one walk's past and not the
        // other's: 2 * (4 + 3 + 2 + 1) q under rule v2, 2 q under v1.
        let predicted = match rule {
            Rule::V1 => 2.0 * q,
            Rule::V2 => 20.0 * q,
        };
        let rule_name = format!("{rule:?}").to_lowercase();
        let dist_name = format!("{dist:?}").to_lowercase();
        let by_step = t
            .parted
            .iter()
            .map(|x| x.to_string())
            .collect::<Vec<_>>()
            .join(",");
        eprintln!(
            "n = {n}, table walk (rule {rule_name}), H = {branches}, {dist_name} branches: {} merges, \
             {parted} parted ({rate:.3e} ± {se:.1e}; predicted {predicted:.3e} from q = Σp²/2n = {q:.3e}); \
             by step [{by_step}]",
            t.trials
        );
        println!(
            "{{\"n\":{n},\"walk\":\"table\",\"branches\":{branches},\"dist\":\"{dist_name}\",\"rule\":\"{rule_name}\",\
             \"seed\":{seed},\"merges\":{},\"parted\":{parted},\"parted_rate\":{rate:.6e},\"parted_se\":{se:.6e},\
             \"parted_by_step\":[{by_step}],\"sum_p2\":{s2:.6},\"predicted\":{predicted:.6e},\
             \"emulation\":\"device-rule\"}}",
            t.trials
        );
        return;
    }

    let next_trial = AtomicU64::new(0);
    let total = Mutex::new(Tally {
        branch_counts: vec![0; branches],
        ..Tally::default()
    });
    std::thread::scope(|scope| {
        for tid in 0..threads {
            let (setup, next_trial, total) = (&setup, &next_trial, &total);
            scope.spawn(move || {
                let mut t = Tally {
                    branch_counts: vec![0; setup.branches],
                    ..Tally::default()
                };
                let mut rng =
                    StdRng::seed_from_u64(splitmix(seed.wrapping_mul(1_000_003) + tid as u64));
                while next_trial.fetch_add(1, Ordering::Relaxed) < trials {
                    trial(setup, &mut rng, &mut t);
                }
                total.lock().unwrap().add(&t);
            });
        }
    });
    let t = total.into_inner().unwrap();

    let classes = (ell - 1) as f64 / (2.0 * n as f64);
    let expected = random_mapping_rho(classes);
    let mean = t.visited / t.trials as f64;
    let var = t.visited_sq / t.trials as f64 - mean * mean;
    let se = (var / t.trials as f64).sqrt();
    let steps: u64 = t.branch_counts.iter().sum();
    let s2: f64 = t
        .branch_counts
        .iter()
        .map(|&c| (c as f64 / steps as f64).powi(2))
        .sum();
    let c = mean / expected;
    let c_se = se / expected;
    // First-order models (WALK-CONSTANT.md §2): a walk injective on each
    // branch pays 1/√(1 − Σp²); the table walk's same-branch class
    // collisions are suppressed only when the frames agree, 1/2n of them.
    let injective = 1.0 / (1.0 - s2).sqrt();
    let class_frame = 1.0 / (1.0 - s2 / (2.0 * n as f64)).sqrt();
    let model = if walk == Walk::Sigma {
        injective
    } else {
        class_frame
    };
    // Leading order (WALK-CONSTANT.md §5): 4 pairwise 6-step patterns pass
    // the rule, three branches each drawn twice, (Σp²/2n)³; and 24 4-step
    // τ-relations, one branch drawn four times, Σp⁴/(2n)³.
    let s4: f64 = t
        .branch_counts
        .iter()
        .map(|&c| (c as f64 / steps as f64).powi(4))
        .sum();
    let two_n = 2.0 * n as f64;
    let pairwise_predicted = 4.0 * (s2 / two_n).powi(3);
    let relation_predicted = 24.0 * s4 / two_n.powi(3);
    let per_step = |counts: &[u64]| counts.iter().sum::<u64>() as f64 / steps.max(1) as f64;
    let by_length = |counts: &[u64]| {
        counts
            .iter()
            .enumerate()
            .filter(|&(_, &x)| x > 0)
            .map(|(l, x)| format!("\"{l}\":{x}"))
            .collect::<Vec<_>>()
            .join(",")
    };
    let (fruitless_rate, relation_rate) = (per_step(&t.fruitless), per_step(&t.relation));
    let (fruitless_json, relation_json) = (by_length(&t.fruitless), by_length(&t.relation));
    let walk_name = format!("{walk:?}").to_lowercase();
    let rule_name = format!("{rule:?}").to_lowercase();
    let dist_name = format!("{dist:?}").to_lowercase();
    eprintln!(
        "n = {n}, {walk_name} walk (rule {rule_name}), H = {branches}, {dist_name} branches{}, W = {walks}: {} trials, \
         mean {mean:.1} classes visited (random mapping {expected:.1}), \
         c = {c:.4} ± {c_se:.4}; Σp² = {s2:.5}, model {model:.4}, c / model = {:.4}; \
         cycle rule {} times in {steps} steps; fruitless: pairwise {fruitless_rate:.3e}/step \
         (predicted {pairwise_predicted:.3e}) by length {{{fruitless_json}}}, τ-relation \
         {relation_rate:.3e}/step (predicted {relation_predicted:.3e}) by length {{{relation_json}}}; \
         short returns {}; restarts {}",
        if fixed_mapping { " (one mapping)" } else { "" },
        t.trials,
        c / model,
        t.cycle_rule,
        t.short_returns,
        t.restarts,
    );
    println!(
        "{{\"n\":{n},\"walk\":\"{walk_name}\",\"branches\":{branches},\"dist\":\"{dist_name}\",\"walks\":{walks},\
         \"trials\":{},\"seed\":{seed},\"classes\":{classes:.1},\"random_mapping_rho\":{expected:.4},\
         \"mean_visited\":{mean:.4},\"se_visited\":{se:.4},\"c\":{c:.6},\"c_se\":{c_se:.6},\
         \"sum_p2\":{s2:.6},\"sum_p4\":{s4:.6},\"injective_model\":{injective:.6},\"class_frame_model\":{class_frame:.6},\
         \"even_weight_fraction\":{:.6},\"cycle_rule\":{},\"restarts\":{},\"steps\":{steps},\
         \"fruitless\":{{{fruitless_json}}},\"fruitless_per_step\":{fruitless_rate:.6e},\
         \"fruitless_predicted\":{pairwise_predicted:.6e},\"relation\":{{{relation_json}}},\
         \"relation_per_step\":{relation_rate:.6e},\"relation_predicted\":{relation_predicted:.6e},\
         \"short_returns\":{},\"fixed_mapping\":{fixed_mapping},\
         \"emulation\":\"device-rule\",\"rule\":\"{rule_name}\"}}",
        t.trials,
        t.even as f64 / t.weighed.max(1) as f64,
        t.cycle_rule,
        t.restarts,
        t.short_returns,
    );
}
