//! Sieves that actually run.
//!
//! Everything else in this module predicts what lattice reduction would cost.
//! This file *does* it, in the dimensions where doing it is possible, so the
//! predictions are anchored to something measured.
//!
//! Three sieves, in the order they were invented:
//!
//! * [`gauss_sieve`] — Micciancio–Voulgaris (2010). Maintain a list of pairwise
//!   Gauss-reduced vectors; each new sample is reduced against the list and
//!   then reduces the list in turn. Memory `2^{0.2075d}`, and the
//!   implementation is short enough to be obviously correct.
//! * [`nv_sieve`] — Nguyen–Vidick (2008). Start with many vectors of norm `≤ R`,
//!   subtract nearby "centres" to get a list of norm `≤ γR`, repeat. The
//!   original sieve, and the one whose analysis is cleanest.
//! * [`bucketed_sieve`] — a near-neighbour-search sieve in the shape of
//!   Becker–Ducas–Gama–Laarhoven (2016). Rather than comparing every pair,
//!   bucket by random spherical projections and compare only within buckets.
//!   This is where the `2^{0.292d}` exponent comes from — the point of the
//!   implementation is to make the pair-count saving *visible*, which
//!   [`bucketed_sieve`]'s statistics report.
//!
//! Plus [`progressive_bkz`], which runs increasing block sizes over a basis and
//! returns the measured profile, so the predictions in [`super::cost`] can be
//! checked against a real reduction rather than only against each other.
//!
//! # What these cannot do
//!
//! They cannot attack ML-KEM. The dimensions that matter are 500–2000 and
//! these run in 40–60. That gap is the whole reason the estimators exist. What
//! the sieves *can* do is confirm the shape of the cost — list size growing
//! like `2^{0.2075d}`, bucketing saving a polynomial-in-`N` factor of pair
//! comparisons — and provide a real SVP oracle for the research-scale attacks
//! elsewhere in this crate.
//!
//! Every function here is deterministic given its seed.

use num_bigint::BigInt;
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};

/// An integer lattice vector.
pub type Vect = Vec<i64>;

/// Squared Euclidean norm. `i128` because a dimension-60 vector with entries of
/// a few thousand overflows `i64` when squared and summed.
pub fn norm2(v: &[i64]) -> i128 {
    v.iter().map(|&x| (x as i128) * (x as i128)).sum()
}

/// Inner product, in `i128` for the same reason.
pub fn dot(a: &[i64], b: &[i64]) -> i128 {
    a.iter()
        .zip(b)
        .map(|(&x, &y)| (x as i128) * (y as i128))
        .sum()
}

fn is_zero(v: &[i64]) -> bool {
    v.iter().all(|&x| x == 0)
}

/// What a sieve did, as opposed to what it found.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SieveStats {
    /// Peak number of vectors held.
    pub peak_list: usize,
    /// Zero vectors produced — the signal that the list has saturated.
    pub collisions: usize,
    /// Pairwise reduction attempts, i.e. inner products computed. This is the
    /// number the bucketing is supposed to bring down.
    pub pair_ops: u64,
    /// Fresh lattice vectors sampled.
    pub samples: usize,
    /// Rounds, for the sieves that have them.
    pub rounds: usize,
    /// Outer-loop iterations the Gauss sieve made.
    pub iterations: u64,
    /// Whether a cap stopped the sieve rather than its own termination
    /// condition. A capped result is still a lattice vector — just not
    /// necessarily the shortest one — so callers that care must check this.
    pub capped: bool,
}

/// A sieve's answer.
///
/// `list` is the sieve's final database, not just the winner. That matters
/// beyond bookkeeping: the dual attack ([`super::dual`]) consumes *many* short
/// vectors rather than one, and the whole reason sieving displaced enumeration
/// in dual attacks is that one sieve call hands you `2^{0.2075d}` of them. A
/// sieve API that returned only the shortest vector would hide that.
#[derive(Clone, Debug, PartialEq)]
pub struct SieveResult {
    pub shortest: Vect,
    pub norm2: i128,
    /// The final database, shortest first.
    pub list: Vec<Vect>,
    pub stats: SieveStats,
}

/// Knobs. The defaults suit dimensions up to about 50 on a laptop.
#[derive(Clone, Copy, Debug)]
pub struct SieveConfig {
    /// Stop after this many zero vectors in a row of bad luck.
    pub max_collisions: usize,
    /// Hard cap on the list, so a bad parameter choice cannot exhaust memory.
    pub max_list: usize,
    /// Hard cap on samples.
    pub max_samples: usize,
    /// Coefficient range for the lattice-vector sampler.
    pub sample_range: i64,
    /// Hard cap on the Gauss sieve's outer loop.
    ///
    /// The sieve's own termination argument is sound — every reduction strictly
    /// shortens a vector, and norms are bounded below — but "terminates" is not
    /// "terminates soon", and a research tool that can wedge is not usable. The
    /// cap converts a wedge into a `capped` result the caller can see.
    pub max_iterations: u64,
    /// Hard cap on the sampler's retry loop, for the same reason.
    pub max_sample_retries: u32,
    pub seed: u64,
}

impl Default for SieveConfig {
    fn default() -> Self {
        SieveConfig {
            max_collisions: 200,
            max_list: 20_000,
            max_samples: 200_000,
            sample_range: 3,
            max_iterations: 2_000_000,
            max_sample_retries: 4096,
            seed: 0x5175_6172_6b73_1234,
        }
    }
}

/// Gauss-reduce `v` against `w`: subtract the multiple of `w` closest to `v`'s
/// projection, if that shortens `v`.
///
/// Returns true if `v` changed. The condition `2|⟨v,w⟩| > ⟨w,w⟩` is exactly
/// "the rounded quotient is nonzero".
pub fn gauss_reduce(v: &mut [i64], w: &[i64]) -> bool {
    let ww = norm2(w);
    if ww == 0 {
        return false;
    }
    let vw = dot(v, w);
    if 2 * vw.abs() <= ww {
        return false;
    }
    // Round-half-away quotient of vw by ww.
    let q = if vw >= 0 {
        (2 * vw + ww) / (2 * ww)
    } else {
        -((-2 * vw + ww) / (2 * ww))
    };
    if q == 0 {
        return false;
    }
    for (vi, &wi) in v.iter_mut().zip(w) {
        *vi -= (q as i64) * wi;
    }
    true
}

/// A sampler of lattice vectors: small random integer combinations of the
/// basis, then greedily size-reduced against the basis itself.
///
/// Not Klein's sampler — which would give a provably Gaussian distribution —
/// but adequate in the dimensions this file runs in, and deterministic.
pub struct LatticeSampler<'a> {
    basis: &'a [Vect],
    rng: SmallRng,
    range: i64,
    max_retries: u32,
}

impl<'a> LatticeSampler<'a> {
    pub fn new(basis: &'a [Vect], seed: u64, range: i64) -> Self {
        LatticeSampler {
            basis,
            rng: SmallRng::seed_from_u64(seed),
            range: range.max(1),
            max_retries: 4096,
        }
    }

    /// Cap the retry loop, so a basis whose small combinations all collapse to
    /// zero cannot wedge the sampler.
    pub fn with_max_retries(mut self, n: u32) -> Self {
        self.max_retries = n.max(1);
        self
    }

    /// One fresh nonzero lattice vector.
    ///
    /// Builds a small random combination of the basis and then size-reduces it
    /// against the basis. The reduction is what makes the sample useful — an
    /// unreduced combination is far longer than the lattice's short vectors —
    /// but it can also collapse the sample to zero, which happens whenever the
    /// combination lands on a small multiple of a basis vector.
    ///
    /// Retrying on a collapse is the obvious response and it is wrong: for some
    /// reduced bases *most* small combinations collapse, and the retry loop
    /// then dominates the sieve's runtime or fails to terminate at all. So the
    /// unreduced combination is kept, and returned when the reduction destroys
    /// it. That is still a lattice vector, just a longer one, and the sieve's
    /// own reduction pass will deal with it.
    pub fn sample(&mut self) -> Vect {
        let dim = self.basis[0].len();
        for _ in 0..self.max_retries {
            let mut raw = vec![0i64; dim];
            for b in self.basis {
                let c = self.rng.gen_range(-self.range..=self.range);
                if c == 0 {
                    continue;
                }
                for (vi, &bi) in raw.iter_mut().zip(b) {
                    *vi += c * bi;
                }
            }
            if is_zero(&raw) {
                continue;
            }
            let mut v = raw.clone();
            for _ in 0..2 {
                for b in self.basis {
                    gauss_reduce(&mut v, b);
                }
            }
            return if is_zero(&v) { raw } else { v };
        }
        self.basis
            .iter()
            .filter(|v| !is_zero(v))
            .min_by_key(|v| norm2(v))
            .cloned()
            .unwrap_or_else(|| vec![0; dim])
    }
}

/// The Gauss sieve (Micciancio–Voulgaris 2010).
///
/// Invariant: every pair in the list is Gauss-reduced, so no two list vectors
/// can shorten each other. The shortest list entry at termination is, with the
/// usual heuristic, the shortest lattice vector.
pub fn gauss_sieve(basis: &[Vect], cfg: &SieveConfig) -> SieveResult {
    let mut list: Vec<Vect> = Vec::new();
    let mut stack: Vec<Vect> = Vec::new();
    let mut sampler = LatticeSampler::new(basis, cfg.seed, cfg.sample_range)
        .with_max_retries(cfg.max_sample_retries);
    let mut stats = SieveStats::default();

    while stats.collisions < cfg.max_collisions
        && list.len() < cfg.max_list
        && stats.samples < cfg.max_samples
    {
        if stats.iterations >= cfg.max_iterations {
            stats.capped = true;
            break;
        }
        stats.iterations += 1;
        let mut v = match stack.pop() {
            Some(v) => v,
            None => {
                stats.samples += 1;
                sampler.sample()
            }
        };

        // Reduce v against the list until it stops changing.
        let mut changed = true;
        while changed && !is_zero(&v) {
            changed = false;
            for w in &list {
                stats.pair_ops += 1;
                if gauss_reduce(&mut v, w) {
                    changed = true;
                }
            }
        }
        if is_zero(&v) {
            stats.collisions += 1;
            continue;
        }

        // Now reduce the list against v; anything that shortens goes back on
        // the stack, because it may now reduce others.
        let mut keep: Vec<Vect> = Vec::with_capacity(list.len());
        for mut w in list.drain(..) {
            stats.pair_ops += 1;
            if gauss_reduce(&mut w, &v) {
                if !is_zero(&w) {
                    stack.push(w);
                }
            } else {
                keep.push(w);
            }
        }
        list = keep;
        list.push(v);
        stats.peak_list = stats.peak_list.max(list.len());
    }

    finish(list, basis, stats)
}

/// Assemble a result from a sieve's database.
///
/// The input basis is always folded into the candidate set. Its rows are
/// lattice vectors like any others, a real attacker has them for free, and a
/// sieve that happened not to improve on them should report *their* best rather
/// than something longer.
fn finish(mut list: Vec<Vect>, basis: &[Vect], stats: SieveStats) -> SieveResult {
    list.retain(|v| !is_zero(v));
    let mut candidates = list.clone();
    candidates.extend(basis.iter().filter(|v| !is_zero(v)).cloned());
    let best = candidates
        .into_iter()
        .min_by_key(|v| norm2(v))
        .unwrap_or_else(|| vec![0; basis[0].len()]);
    list.sort_by_key(|v| norm2(v));
    SieveResult {
        norm2: norm2(&best),
        shortest: best,
        list,
        stats,
    }
}

/// The Nguyen–Vidick sieve.
///
/// Sample `n_start` lattice vectors, then repeatedly: walk the list, and for
/// each vector either find an existing "centre" within `gamma·R` of it and
/// replace it by the difference, or promote it to a centre. Each round shrinks
/// the radius by `gamma`.
///
/// `gamma` must be in `(0.5, 1)`; 0.95 is the usual choice and what
/// `Default` uses.
pub fn nv_sieve(basis: &[Vect], n_start: usize, gamma: f64, cfg: &SieveConfig) -> SieveResult {
    assert!(gamma > 0.5 && gamma < 1.0, "gamma must lie in (0.5, 1)");
    let mut sampler = LatticeSampler::new(basis, cfg.seed, cfg.sample_range)
        .with_max_retries(cfg.max_sample_retries);
    let mut stats = SieveStats::default();
    let mut list: Vec<Vect> = (0..n_start)
        .map(|_| {
            stats.samples += 1;
            sampler.sample()
        })
        .collect();
    stats.peak_list = list.len();

    let mut radius2 = list.iter().map(|v| norm2(v)).max().unwrap_or(0) as f64;
    let mut best: Option<Vect> = list
        .iter()
        .filter(|v| !is_zero(v))
        .min_by_key(|v| norm2(v))
        .cloned();

    for _ in 0..64 {
        stats.rounds += 1;
        let target2 = radius2 * gamma * gamma;
        let mut centres: Vec<Vect> = Vec::new();
        let mut next: Vec<Vect> = Vec::new();
        for v in list.drain(..) {
            if is_zero(&v) {
                stats.collisions += 1;
                continue;
            }
            if (norm2(&v) as f64) <= target2 {
                next.push(v);
                continue;
            }
            let mut placed = false;
            for c in &centres {
                stats.pair_ops += 1;
                let mut d: Vect = v.iter().zip(c).map(|(&a, &b)| a - b).collect();
                if is_zero(&d) {
                    stats.collisions += 1;
                    placed = true;
                    break;
                }
                if (norm2(&d) as f64) <= target2 {
                    // Keep the shorter of v-c and v+c.
                    let s: Vect = v.iter().zip(c).map(|(&a, &b)| a + b).collect();
                    if !is_zero(&s) && norm2(&s) < norm2(&d) {
                        d = s;
                    }
                    next.push(d);
                    placed = true;
                    break;
                }
            }
            if !placed {
                centres.push(v);
            }
        }
        for v in &next {
            if !is_zero(v) && best.as_ref().map(|b| norm2(v) < norm2(b)).unwrap_or(true) {
                best = Some(v.clone());
            }
        }
        for v in &centres {
            if !is_zero(v) && best.as_ref().map(|b| norm2(v) < norm2(b)).unwrap_or(true) {
                best = Some(v.clone());
            }
        }
        if next.len() < 2 {
            break;
        }
        list = next;
        stats.peak_list = stats.peak_list.max(list.len() + centres.len());
        radius2 = target2;
        if radius2 < 1.0 {
            break;
        }
    }

    let mut db = list;
    if let Some(b) = &best {
        db.push(b.clone());
    }
    finish(db, basis, stats)
}

/// Statistics specific to the bucketed sieve, so the saving is quotable.
#[derive(Clone, Debug, PartialEq)]
pub struct BucketedResult {
    pub result: SieveResult,
    /// Pair comparisons the bucketed pass performed.
    pub bucketed_pairs: u64,
    /// Pair comparisons an all-pairs pass over the same list would have
    /// performed: `N(N-1)/2`.
    pub all_pairs: u64,
    /// Number of buckets used.
    pub buckets: usize,
}

impl BucketedResult {
    /// The saving, as a ratio of all-pairs to bucketed. Above 1 means the
    /// bucketing paid off.
    pub fn speedup(&self) -> f64 {
        if self.bucketed_pairs == 0 {
            return f64::INFINITY;
        }
        self.all_pairs as f64 / self.bucketed_pairs as f64
    }
}

/// A bucketed near-neighbour sieve, in the shape of BDGL16.
///
/// Draw `buckets` random directions. Assign each list vector to the bucket
/// whose direction it correlates with most strongly (and to the antipode, since
/// `±v` are the same lattice point for reduction purposes). Only vectors
/// sharing a bucket are compared.
///
/// The asymptotic claim behind `2^{0.292d}` is that with the right bucket
/// structure the pair count drops from `N²` to `N^{1+o(1)}`, and the
/// [`BucketedResult::speedup`] this returns is the finite-dimension shadow of
/// that. It is *not* BDGL's random-product-code structure, which is what makes
/// the exponent provable; it is the simplest bucketing that exhibits the
/// saving.
pub fn bucketed_sieve(
    basis: &[Vect],
    n_start: usize,
    buckets: usize,
    rounds: usize,
    cfg: &SieveConfig,
) -> BucketedResult {
    let dim = basis[0].len();
    let mut rng = SmallRng::seed_from_u64(cfg.seed ^ 0xB0CC_E7ED);
    let mut sampler = LatticeSampler::new(basis, cfg.seed, cfg.sample_range)
        .with_max_retries(cfg.max_sample_retries);
    let mut stats = SieveStats::default();
    let mut list: Vec<Vect> = (0..n_start)
        .map(|_| {
            stats.samples += 1;
            sampler.sample()
        })
        .collect();
    stats.peak_list = list.len();

    let mut bucketed_pairs = 0u64;
    let mut all_pairs = 0u64;

    for _ in 0..rounds {
        stats.rounds += 1;
        let n = list.len();
        all_pairs += (n as u64) * (n as u64).saturating_sub(1) / 2;

        // Random bucket directions, as random ±1 vectors: cheap to correlate
        // against and spherically symmetric enough in these dimensions.
        let dirs: Vec<Vec<i64>> = (0..buckets.max(1))
            .map(|_| {
                (0..dim)
                    .map(|_| if rng.gen::<bool>() { 1i64 } else { -1 })
                    .collect()
            })
            .collect();

        let mut assigned: Vec<Vec<usize>> = vec![Vec::new(); dirs.len()];
        for (i, v) in list.iter().enumerate() {
            let mut best = (0usize, i128::MIN);
            for (j, d) in dirs.iter().enumerate() {
                let c = dot(v, d).abs();
                if c > best.1 {
                    best = (j, c);
                }
            }
            assigned[best.0].push(i);
        }

        let mut next = list.clone();
        for bucket in &assigned {
            for (bi, &i) in bucket.iter().enumerate() {
                for &j in &bucket[bi + 1..] {
                    bucketed_pairs += 1;
                    let (a, b) = (next[i].clone(), next[j].clone());
                    let mut d: Vect = a.iter().zip(&b).map(|(&x, &y)| x - y).collect();
                    let s: Vect = a.iter().zip(&b).map(|(&x, &y)| x + y).collect();
                    if !is_zero(&s) && (is_zero(&d) || norm2(&s) < norm2(&d)) {
                        d = s;
                    }
                    if is_zero(&d) {
                        stats.collisions += 1;
                        continue;
                    }
                    if norm2(&d) < norm2(&next[i]) {
                        next[i] = d;
                    }
                }
            }
        }
        list = next;
        list.retain(|v| !is_zero(v));
        if list.len() < 2 {
            break;
        }
        stats.peak_list = stats.peak_list.max(list.len());
    }

    BucketedResult {
        result: finish(list, basis, stats),
        bucketed_pairs,
        all_pairs,
        buckets: buckets.max(1),
    }
}

// ── Reduction and profiles ───────────────────────────────────────────────────

/// Convert an `i64` basis to the `BigInt` form [`crate::cryptanalysis::lattice`]
/// wants.
pub fn to_bigint_basis(basis: &[Vect]) -> Vec<Vec<BigInt>> {
    basis
        .iter()
        .map(|r| r.iter().map(|&x| BigInt::from(x)).collect())
        .collect()
}

/// Convert back, saturating anything that no longer fits — which reduction
/// never produces, since it only shortens.
pub fn from_bigint_basis(basis: &[Vec<BigInt>]) -> Vec<Vect> {
    use num_traits::ToPrimitive;
    basis
        .iter()
        .map(|r| r.iter().map(|x| x.to_i64().unwrap_or(i64::MAX)).collect())
        .collect()
}

/// Run LLL, then BKZ at increasing block sizes, and report the measured
/// Gram–Schmidt profile after each stage.
///
/// Progressive block sizes are how every real implementation is run: reducing
/// at β directly from an unreduced basis is far slower than walking up to it.
///
/// Returns `(reduced_basis, stages)` where each stage is
/// `(beta, log2 ‖b*_0‖, log2 volume)`.
/// One stage of [`progressive_bkz`]: the block size, `log2 ‖b*_0‖` measured
/// afterwards, and `log2` of the lattice volume (which must not move).
pub type BkzStage = (usize, f64, f64);

pub fn progressive_bkz(
    basis: &[Vect],
    beta_max: usize,
    delta: f64,
) -> Result<(Vec<Vect>, Vec<BkzStage>), &'static str> {
    use crate::cryptanalysis::lattice::{bkz_reduce, lll_reduce};
    let mut b = to_bigint_basis(basis);
    lll_reduce(&mut b, delta)?;
    let mut stages = Vec::new();
    let cur = from_bigint_basis(&b);
    stages.push((2usize, measured_head_log2(&cur), measured_log2_volume(&cur)));
    let mut beta = 4usize;
    while beta <= beta_max {
        bkz_reduce(&mut b, beta, delta)?;
        let cur = from_bigint_basis(&b);
        stages.push((beta, measured_head_log2(&cur), measured_log2_volume(&cur)));
        beta += 2;
    }
    Ok((from_bigint_basis(&b), stages))
}

/// `log2` of the shortest basis vector's length.
pub fn measured_head_log2(basis: &[Vect]) -> f64 {
    let m = basis
        .iter()
        .filter(|v| !is_zero(v))
        .map(|v| norm2(v))
        .min()
        .unwrap_or(1);
    (m as f64).sqrt().log2()
}

/// `log2` of the lattice volume, by Gram–Schmidt on `f64`.
///
/// Fine in the dimensions this file runs in; the `BigInt` path in
/// [`crate::cryptanalysis::lattice`] is there for when it is not.
pub fn measured_log2_volume(basis: &[Vect]) -> f64 {
    let n = basis.len();
    let dim = basis[0].len();
    let mut b: Vec<Vec<f64>> = basis
        .iter()
        .map(|r| r.iter().map(|&x| x as f64).collect())
        .collect();
    let mut log2_vol = 0.0;
    for i in 0..n {
        for j in 0..i {
            let bj: Vec<f64> = b[j].clone();
            let nj: f64 = bj.iter().map(|x| x * x).sum();
            if nj <= 0.0 {
                continue;
            }
            let ip: f64 = b[i].iter().zip(&bj).map(|(x, y)| x * y).sum();
            let mu = ip / nj;
            for k in 0..dim {
                b[i][k] -= mu * bj[k];
            }
        }
        let ni: f64 = b[i].iter().map(|x| x * x).sum();
        if ni > 0.0 {
            log2_vol += 0.5 * ni.log2();
        }
    }
    log2_vol
}

/// A random q-ary lattice in the Goldstein–Mayer model: the standard source of
/// "random lattice" test instances.
///
/// Basis rows: `(q, 0, …, 0)`, then `(a_i, 0, …, 1, …, 0)` for random `a_i`.
/// Volume `q`, dimension `dim`.
pub fn random_qary_lattice(dim: usize, q: i64, seed: u64) -> Vec<Vect> {
    let mut rng = SmallRng::seed_from_u64(seed);
    let mut rows = Vec::with_capacity(dim);
    let mut first = vec![0i64; dim];
    first[0] = q;
    rows.push(first);
    for i in 1..dim {
        let mut r = vec![0i64; dim];
        r[0] = rng.gen_range(0..q);
        r[i] = 1;
        rows.push(r);
    }
    rows
}

/// Exhaustive search over small coefficient vectors, for checking a sieve's
/// answer in dimensions where exhaustion is affordable.
///
/// Searches `Σ c_i b_i` for `c ∈ [-range, range]^dim`, skipping zero. Returns
/// the shortest. Exponential in `dim`, so keep `dim·log(2 range+1)` under 20 or
/// so.
pub fn brute_force_shortest(basis: &[Vect], range: i64) -> Vect {
    let n = basis.len();
    let dim = basis[0].len();
    let span = (2 * range + 1) as u64;
    let total = span
        .checked_pow(n as u32)
        .expect("brute force range too large");
    let mut best: Option<Vect> = None;
    for code in 1..total {
        let mut c = code;
        let mut v = vec![0i64; dim];
        let mut all_zero = true;
        for b in basis {
            let digit = (c % span) as i64 - range;
            c /= span;
            if digit != 0 {
                all_zero = false;
                for (vi, &bi) in v.iter_mut().zip(b) {
                    *vi += digit * bi;
                }
            }
        }
        if all_zero || is_zero(&v) {
            continue;
        }
        if best.as_ref().map(|b| norm2(&v) < norm2(b)).unwrap_or(true) {
            best = Some(v);
        }
    }
    best.unwrap_or_else(|| vec![0; dim])
}

/// One row of a sieve scaling measurement.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ScalingRow {
    pub dim: usize,
    pub peak_list: usize,
    pub pair_ops: u64,
    pub samples: usize,
}

/// Measure the Gauss sieve across a range of dimensions.
///
/// The asymptotic prediction is `peak_list ≈ 2^{0.2075 d}`. Do not expect to
/// see that here: at `d = 40` the `o(d)` term dominates and the measured list
/// is far from `2^{8.3}`. What the measurement *does* show is monotone
/// exponential-shaped growth, which is the honest thing a dimension-40
/// experiment can say about a dimension-800 claim.
pub fn measure_gauss_scaling(dims: &[usize], q: i64, cfg: &SieveConfig) -> Vec<ScalingRow> {
    dims.iter()
        .map(|&dim| {
            let basis = random_qary_lattice(dim, q, cfg.seed ^ dim as u64);
            let mut b = to_bigint_basis(&basis);
            let _ = crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99);
            let basis = from_bigint_basis(&b);
            let r = gauss_sieve(&basis, cfg);
            ScalingRow {
                dim,
                peak_list: r.stats.peak_list,
                pair_ops: r.stats.pair_ops,
                samples: r.stats.samples,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn small_cfg(seed: u64) -> SieveConfig {
        SieveConfig {
            max_collisions: 60,
            max_list: 3000,
            max_samples: 20_000,
            sample_range: 3,
            seed,
            ..Default::default()
        }
    }

    #[test]
    fn norm_and_dot_do_not_overflow_at_realistic_magnitudes() {
        let v = vec![1_000_000i64; 60];
        assert_eq!(norm2(&v), 60 * 1_000_000i128 * 1_000_000);
        assert_eq!(dot(&v, &v), norm2(&v));
        assert_eq!(dot(&[1, 2, 3], &[4, 5, 6]), 32);
    }

    #[test]
    fn gauss_reduce_shortens_or_does_nothing() {
        let w = vec![10i64, 0];
        let mut v = vec![97i64, 3];
        let before = norm2(&v);
        assert!(gauss_reduce(&mut v, &w));
        assert!(norm2(&v) < before);
        assert_eq!(v, vec![-3, 3]);
        // Already reduced: no change, and the report says so.
        let mut u = vec![3i64, 3];
        assert!(!gauss_reduce(&mut u, &w));
        assert_eq!(u, vec![3, 3]);
    }

    #[test]
    fn gauss_reduce_rounds_to_the_nearest_multiple() {
        let w = vec![4i64, 0];
        // 10 = 2·4 + 2: nearest multiple is 8 (q=2) or 12 (q=3); |10-8| = 2 = |10-12|.
        let mut v = vec![10i64, 0];
        gauss_reduce(&mut v, &w);
        assert!(norm2(&v) <= 4);
        // Negative side behaves symmetrically.
        let mut v = vec![-10i64, 0];
        gauss_reduce(&mut v, &w);
        assert!(norm2(&v) <= 4);
    }

    #[test]
    fn gauss_sieve_finds_the_shortest_vector_of_a_tiny_lattice() {
        // Dimension 4, small q: brute force is exhaustive here, so this is a
        // real correctness check and not a plausibility check.
        for seed in 0..6u64 {
            let basis = random_qary_lattice(4, 31, seed);
            let mut b = to_bigint_basis(&basis);
            crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
            let basis = from_bigint_basis(&b);
            let sieved = gauss_sieve(&basis, &small_cfg(seed));
            let brute = brute_force_shortest(&basis, 4);
            assert_eq!(
                sieved.norm2,
                norm2(&brute),
                "seed {seed}: sieve {:?} (|v|² = {}), brute {:?} (|v|² = {})",
                sieved.shortest,
                sieved.norm2,
                brute,
                norm2(&brute)
            );
        }
    }

    #[test]
    fn gauss_sieve_matches_lll_or_beats_it_in_dimension_ten() {
        for seed in 0..4u64 {
            let basis = random_qary_lattice(10, 1021, seed);
            let mut b = to_bigint_basis(&basis);
            crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
            let reduced = from_bigint_basis(&b);
            let lll_best = reduced.iter().map(|v| norm2(v)).min().unwrap();
            let sieved = gauss_sieve(&reduced, &small_cfg(seed));
            assert!(
                sieved.norm2 <= lll_best,
                "seed {seed}: sieve {} worse than LLL {}",
                sieved.norm2,
                lll_best
            );
        }
    }

    #[test]
    fn gauss_sieve_output_is_pairwise_reduced() {
        // The invariant the algorithm exists to maintain: no list vector can
        // shorten any other. Checked directly on the returned database, which
        // is why the API returns it.
        let basis = random_qary_lattice(8, 257, 11);
        let mut b = to_bigint_basis(&basis);
        crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
        let basis = from_bigint_basis(&b);
        let r = gauss_sieve(&basis, &small_cfg(11));
        assert!(r.list.len() > 4, "list too small to be meaningful");
        for (i, v) in r.list.iter().enumerate() {
            for w in r.list.iter().skip(i + 1) {
                let mut v2 = v.clone();
                assert!(
                    !gauss_reduce(&mut v2, w),
                    "pair not Gauss-reduced: {v:?} against {w:?}"
                );
            }
        }
        // The list is returned shortest-first, and its head is the answer.
        assert_eq!(norm2(&r.list[0]), r.norm2.min(norm2(&r.list[0])));
    }

    #[test]
    fn nv_sieve_agrees_with_gauss_on_small_lattices() {
        for seed in 0..4u64 {
            let basis = random_qary_lattice(6, 127, seed);
            let mut b = to_bigint_basis(&basis);
            crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
            let basis = from_bigint_basis(&b);
            let g = gauss_sieve(&basis, &small_cfg(seed));
            let nv = nv_sieve(&basis, 400, 0.95, &small_cfg(seed));
            // NV is a heuristic with a fixed sample budget: it may not match
            // the Gauss sieve exactly, but it must not be far off, and it must
            // beat the reduced basis.
            let lll_best = basis.iter().map(|v| norm2(v)).min().unwrap();
            assert!(nv.norm2 <= lll_best, "seed {seed}");
            assert!(
                (nv.norm2 as f64) <= 4.0 * g.norm2 as f64,
                "seed {seed}: NV {} vs Gauss {}",
                nv.norm2,
                g.norm2
            );
        }
    }

    #[test]
    #[should_panic(expected = "gamma must lie in (0.5, 1)")]
    fn nv_sieve_rejects_a_gamma_that_cannot_converge() {
        let basis = random_qary_lattice(4, 31, 0);
        nv_sieve(&basis, 10, 1.5, &SieveConfig::default());
    }

    #[test]
    fn bucketing_cuts_the_pair_count() {
        // The measurable shadow of the 0.292 exponent: with buckets, far fewer
        // pairs are touched than all-pairs would need.
        let basis = random_qary_lattice(20, 1021, 7);
        let mut b = to_bigint_basis(&basis);
        crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
        let basis = from_bigint_basis(&b);
        let r = bucketed_sieve(&basis, 600, 40, 4, &small_cfg(7));
        assert!(r.all_pairs > 0);
        assert!(
            r.speedup() > 3.0,
            "bucketing saved only {:.2}× ({} vs {} pairs)",
            r.speedup(),
            r.bucketed_pairs,
            r.all_pairs
        );
        // …and it still finds something short.
        let lll_best = basis.iter().map(|v| norm2(v)).min().unwrap();
        assert!(r.result.norm2 <= lll_best);
    }

    #[test]
    fn more_buckets_means_fewer_pairs() {
        let basis = random_qary_lattice(16, 1021, 3);
        let few = bucketed_sieve(&basis, 400, 8, 2, &small_cfg(3));
        let many = bucketed_sieve(&basis, 400, 64, 2, &small_cfg(3));
        assert!(
            many.bucketed_pairs < few.bucketed_pairs,
            "{} vs {}",
            many.bucketed_pairs,
            few.bucketed_pairs
        );
        assert!(many.speedup() > few.speedup());
    }

    #[test]
    fn progressive_bkz_shortens_the_head_monotonically() {
        let basis = random_qary_lattice(24, 4099, 5);
        let (_reduced, stages) = progressive_bkz(&basis, 12, 0.99).unwrap();
        assert!(stages.len() >= 3);
        for w in stages.windows(2) {
            assert!(
                w[1].1 <= w[0].1 + 1e-9,
                "head grew from β={} ({}) to β={} ({})",
                w[0].0,
                w[0].1,
                w[1].0,
                w[1].1
            );
        }
        // Volume is a lattice invariant: reduction must not change it.
        let v0 = stages[0].2;
        for s in &stages {
            assert!((s.2 - v0).abs() < 0.5, "volume moved: {} vs {v0}", s.2);
        }
    }

    #[test]
    fn measured_volume_matches_the_qary_construction() {
        // A q-ary lattice with one row (q, 0, …) and unit rows elsewhere has
        // volume exactly q.
        for (dim, q) in [(6usize, 101i64), (10, 1021), (14, 4099)] {
            let basis = random_qary_lattice(dim, q, 1);
            let got = measured_log2_volume(&basis);
            assert!(
                (got - (q as f64).log2()).abs() < 1e-6,
                "dim {dim}: {got} vs {}",
                (q as f64).log2()
            );
        }
    }

    #[test]
    fn reduction_preserves_volume_through_the_bigint_round_trip() {
        let basis = random_qary_lattice(12, 1021, 9);
        let before = measured_log2_volume(&basis);
        let mut b = to_bigint_basis(&basis);
        crate::cryptanalysis::lattice::lll_reduce(&mut b, 0.99).unwrap();
        let after = measured_log2_volume(&from_bigint_basis(&b));
        assert!((before - after).abs() < 1e-6);
    }

    #[test]
    fn brute_force_finds_the_obvious_answer() {
        // Basis {(5,0),(0,7)}: shortest is (5,0).
        let basis = vec![vec![5i64, 0], vec![0i64, 7]];
        let v = brute_force_shortest(&basis, 2);
        assert_eq!(norm2(&v), 25);
    }

    #[test]
    fn sampler_is_deterministic_in_its_seed() {
        let basis = random_qary_lattice(8, 257, 1);
        let a: Vec<Vect> = {
            let mut s = LatticeSampler::new(&basis, 42, 3);
            (0..10).map(|_| s.sample()).collect()
        };
        let b: Vec<Vect> = {
            let mut s = LatticeSampler::new(&basis, 42, 3);
            (0..10).map(|_| s.sample()).collect()
        };
        assert_eq!(a, b);
        let c: Vec<Vect> = {
            let mut s = LatticeSampler::new(&basis, 43, 3);
            (0..10).map(|_| s.sample()).collect()
        };
        assert_ne!(a, c);
    }

    #[test]
    fn samples_are_lattice_points() {
        // Every sample must lie in the lattice: for the q-ary construction that
        // means the first coordinate is congruent to the rest's contribution.
        let (dim, q) = (8usize, 257i64);
        let basis = random_qary_lattice(dim, q, 4);
        let mut s = LatticeSampler::new(&basis, 5, 3);
        for _ in 0..40 {
            let v = s.sample();
            let expect: i64 = (1..dim).map(|i| v[i] * basis[i][0]).sum::<i64>();
            assert_eq!((v[0] - expect).rem_euclid(q), 0);
        }
    }

    #[test]
    fn gauss_sieve_scaling_grows_with_dimension() {
        // Dimensions small enough to run in a unit test. The claim is only
        // monotonicity — see the function's doc comment for why the asymptotic
        // constant is not visible here.
        let cfg = SieveConfig {
            max_collisions: 25,
            max_list: 4000,
            max_samples: 8000,
            ..small_cfg(2)
        };
        let rows = measure_gauss_scaling(&[10, 14, 18], 4099, &cfg);
        assert_eq!(rows.len(), 3);
        for w in rows.windows(2) {
            assert!(
                w[1].peak_list >= w[0].peak_list,
                "list shrank from dim {} ({}) to dim {} ({})",
                w[0].dim,
                w[0].peak_list,
                w[1].dim,
                w[1].peak_list
            );
        }
        assert!(rows.iter().all(|r| r.pair_ops > 0));
    }
}
