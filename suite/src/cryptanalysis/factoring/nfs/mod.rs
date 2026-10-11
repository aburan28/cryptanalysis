//! **The Number Field Sieve** for integer factorisation — a shared core
//! with two front ends, [`gnfs`] (general numbers, base-m polynomials)
//! and [`snfs`] (numbers of the form `c·rᵉ + s`).
//!
//! # The algorithm
//!
//! Pick `f ∈ ℤ[x]` irreducible of degree `d` and `m` with `f(m) ≡ 0
//! (mod n)`; let `α` be a root of `f` and `K = ℚ(α)`.  The ring map
//! `φ: ℤ[α] → ℤ/n`, `α ↦ m` sends `a − bα` to `a − bm`.  Find a set `S`
//! of coprime pairs `(a, b)` such that
//!
//! ```text
//! ∏_S (a − b·m) = y²  in ℤ        and        ∏_S (a − b·α) = γ²  in K,
//! ```
//!
//! then `φ(γ)² ≡ y² (mod n)`, and `gcd(φ(γ) − y, n)` splits `n` with
//! probability ≥ 1/2.  The stages:
//!
//! 1. **Polynomial selection** — [`polysel`] (base-m) or [`snfs`].
//! 2. **Factor bases** — primes `p ≤ B_r` (rational) and degree-one prime
//!    ideals `(p, r)`, `f(r) ≡ 0 (mod p)`, `p ≤ B_a` (algebraic);
//!    [`sieve::FactorBases`].
//! 3. **Sieving** — [`sieve`]: line sieving over `b = 1, 2, …`,
//!    `|a| < A` (with `A/b` near the polynomial's skewness), log
//!    approximations, exact verification, one large prime per side.
//! 4. **Matrix** — one column per rational prime, per prime ideal, per
//!    large prime, for the sign of `a − bm`, for **quadratic characters**
//!    `χ_q(a − bα) = ((a − b s)/q)` at ~48 primes `q > B_a` with
//!    `f(s) ≡ 0 (mod q)` (Adleman: these make "exponent vector even"
//!    imply "square in `K`" with high probability, covering units, the
//!    class group and the index `[O_K : ℤ[α]]`), and — when `f` is not
//!    monic — a **parity** column so that `|S|` is even.  Filtering and
//!    GF(2) elimination: [`linalg`].
//! 5. **Square roots** — rational: `y = ∏ p^{e_p/2} mod n` from the
//!    recorded factorisations; algebraic: [`sqrt`], exact product +
//!    Newton lifting from an inert prime, verified `δ² = Γ` exactly.
//!
//! **Non-monic `f`.**  With `c = lead(f)` everything is done for the
//! monic `F(y) = c^{d−1} f(y/c)` with root `β = cα` and `M = c·m`:
//! `∏ (c·a − b·β) = c^{|S|} γ²` is a square when `|S|` is even, and
//! `φ(F'(β)·√…) ≡ F'(M)·c^{|S|/2}·y`.
//!
//! # Complexity and scale
//!
//! Heuristic `L_n[1/3, (64/9)^{1/3} ≈ 1.923]` (GNFS) and
//! `L_n[1/3, (32/9)^{1/3} ≈ 1.526]` (SNFS).  The asymptotic advantage over
//! the QS (`L_n[1/2, 1]`) only pays off around 100 digits **with**
//! lattice sieving and good polynomials; with the line siever and base-m
//! polynomials here, the QS in [`super::qs`](mod@super::qs) is faster at every size this
//! code can reach, and the NFS is provided because it is the algorithm
//! that matters at scale.  Measured sizes and timings are in the suite
//! README.  Not implemented: lattice sieving, Kleinjung polynomial
//! selection, root optimisation, double large primes, Block Lanczos,
//! Montgomery/Nguyen square root, free relations, clique removal.
//!
//! References: A. K. Lenstra and H. W. Lenstra Jr. (eds.), *The
//! development of the number field sieve*, LNM 1554 (1993) — in
//! particular Buhler, Lenstra and Pomerance, *Factoring integers with the
//! number field sieve*; M. Briggs, *An introduction to the general number
//! field sieve*, M.Sc. thesis, Virginia Tech (1998); R. Crandall and
//! C. Pomerance, *Prime Numbers: A Computational Perspective*, §6.2.

pub mod gnfs;
pub mod linalg;
pub mod poly;
pub mod polysel;
pub mod sieve;
pub mod snfs;
pub mod sqrt;

use crate::cryptanalysis::fx_hash::FxMap;
use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::{One, ToPrimitive, Zero};
use rayon::prelude::*;
use serde::Serialize;
use std::collections::HashMap;
use std::time::Instant;

use super::arith::{bigint_mod, decimal_digits, is_prime_u64, jacobi_u64, secs};
use super::{serde_big, Progress, ProgressFn};
use linalg::{filtered_excess, find_dependencies, parity_vector, singleton_survivors, LinalgStats};
use poly::{fp, IntPoly};
use sieve::{sieve_segment, FactorBases, Relation, SieveConfig};
use sqrt::SqrtStats;

/// Sieve and linear-algebra parameters shared by GNFS and SNFS.  `None`
/// fields are chosen from the (effective) size of the input.
#[derive(Clone, Debug, Serialize)]
pub struct NfsParams {
    /// Rational factor-base bound `B_r`.
    pub rational_bound: Option<u64>,
    /// Algebraic factor-base bound `B_a`.
    pub algebraic_bound: Option<u64>,
    /// Large-prime bound as a multiple of the factor-base bound (0 = none).
    pub large_prime_multiplier: u64,
    /// Sieve half-width `A` (`a ∈ [−A, A)`); default from the skewness.
    pub sieve_half_width: Option<u64>,
    /// Give up after this many lines `b`.
    pub max_b: Option<u64>,
    /// Bits subtracted from both sieve thresholds.
    pub threshold_slack_bits: f64,
    /// Number of quadratic characters.
    pub quadratic_characters: usize,
    /// Relations beyond the column count before sieving stops.
    pub surplus: usize,
    /// Dependencies requested from the linear algebra.
    pub max_dependencies: usize,
    /// Worker threads (1 = sequential).
    pub threads: usize,
}

impl Default for NfsParams {
    fn default() -> Self {
        NfsParams {
            rational_bound: None,
            algebraic_bound: None,
            large_prime_multiplier: 80,
            sieve_half_width: None,
            max_b: None,
            threshold_slack_bits: 4.0,
            quadratic_characters: 48,
            surplus: 32,
            max_dependencies: 32,
            threads: 1,
        }
    }
}

/// Outcome and statistics of an NFS run.
#[derive(Clone, Debug, Serialize)]
pub struct NfsReport {
    /// `"gnfs"` or `"snfs"`.
    pub method: &'static str,
    /// The number that was attacked.
    #[serde(with = "serde_big::biguint")]
    pub n: BigUint,
    /// Decimal digits of `n`.
    pub digits: usize,
    /// A proper factor, if found.
    #[serde(with = "serde_big::opt_biguint")]
    pub factor: Option<BigUint>,
    /// `n / factor`.
    #[serde(with = "serde_big::opt_biguint")]
    pub cofactor: Option<BigUint>,
    /// `factor · cofactor == n` was checked.
    pub verified: bool,
    /// Why no factor was returned, if none was.
    pub failure: Option<String>,
    /// A factor found during polynomial selection rather than by sieving.
    pub found_in_polyselect: bool,
    /// `f` as a string, e.g. `"x^3 + 2*x - 5"`.
    pub polynomial: String,
    /// Coefficients of `f`, lowest degree first.
    #[serde(with = "serde_big::vec_bigint")]
    pub coefficients: Vec<BigInt>,
    /// The common root `m`.
    #[serde(with = "serde_big::biguint")]
    pub m: BigUint,
    /// Degree of `f`.
    pub degree: usize,
    /// Skewness used for the sieve region.
    pub skewness: f64,
    /// Murphy α of `f`.
    pub alpha: f64,
    /// Inert prime used by the algebraic square root.
    pub inert_prime: u64,
    /// Rational factor-base bound.
    pub rational_bound: u64,
    /// Algebraic factor-base bound.
    pub algebraic_bound: u64,
    /// Rational factor-base size (primes).
    pub rational_fb_size: usize,
    /// Algebraic factor-base size (prime ideals).
    pub algebraic_fb_size: usize,
    /// Large-prime bound (both sides).
    pub large_prime_bound: u64,
    /// Quadratic characters used.
    pub quadratic_characters: usize,
    /// Sieve half-width `A`.
    pub sieve_half_width: u64,
    /// Largest line `b` sieved.
    pub lines_sieved: u64,
    /// Cells sieved in total.
    pub cells_sieved: u64,
    /// Survivors that were factored.
    pub candidates: u64,
    /// Relations with no large prime.
    pub full_relations: usize,
    /// Relations with one or two large primes.
    pub partial_relations: usize,
    /// Linear-algebra sizes.
    pub linalg: LinalgStats,
    /// Dependencies passed to the square-root stage.
    pub dependencies_tried: usize,
    /// Per-dependency square-root statistics.
    pub sqrt_attempts: Vec<SqrtStats>,
    /// Seconds in polynomial selection.
    pub polyselect_seconds: f64,
    /// Seconds in the sieve.
    pub sieve_seconds: f64,
    /// Seconds in filtering + linear algebra.
    pub linalg_seconds: f64,
    /// Seconds in the square roots.
    pub sqrt_seconds: f64,
    /// Total seconds.
    pub total_seconds: f64,
}

impl NfsReport {
    pub(crate) fn new(method: &'static str, n: &BigUint) -> Self {
        NfsReport {
            method,
            n: n.clone(),
            digits: decimal_digits(n),
            factor: None,
            cofactor: None,
            verified: false,
            failure: None,
            found_in_polyselect: false,
            polynomial: String::new(),
            coefficients: Vec::new(),
            m: BigUint::zero(),
            degree: 0,
            skewness: 1.0,
            alpha: 0.0,
            inert_prime: 0,
            rational_bound: 0,
            algebraic_bound: 0,
            rational_fb_size: 0,
            algebraic_fb_size: 0,
            large_prime_bound: 0,
            quadratic_characters: 0,
            sieve_half_width: 0,
            lines_sieved: 0,
            cells_sieved: 0,
            candidates: 0,
            full_relations: 0,
            partial_relations: 0,
            linalg: LinalgStats::default(),
            dependencies_tried: 0,
            sqrt_attempts: Vec::new(),
            polyselect_seconds: 0.0,
            sieve_seconds: 0.0,
            linalg_seconds: 0.0,
            sqrt_seconds: 0.0,
            total_seconds: 0.0,
        }
    }

    /// Record `g` as the factor if it is a proper divisor of `n`, verified
    /// by multiplication.
    pub(crate) fn accept(&mut self, g: BigUint) -> bool {
        if g.is_zero() || g.is_one() || g == self.n {
            return false;
        }
        let (q, r) = self.n.div_rem(&g);
        if !r.is_zero() || &g * &q != self.n {
            return false;
        }
        let (small, large) = if g <= q { (g, q) } else { (q, g) };
        self.factor = Some(small);
        self.cofactor = Some(large);
        self.verified = true;
        self.failure = None;
        true
    }
}

/// Default `(rational bound, algebraic bound, sieve area)` for an input of
/// `eff_digits` "GNFS-equivalent" digits.
pub(crate) fn default_bounds(eff_digits: usize) -> (u64, u64, f64) {
    // (digits, bound, area) — tuned on this implementation.
    const TABLE: [(f64, f64, f64); 8] = [
        (20.0, 2_000.0, 2e6),
        (30.0, 8_000.0, 2e7),
        (40.0, 30_000.0, 3e8),
        (45.0, 50_000.0, 1e9),
        (50.0, 80_000.0, 3e9),
        (55.0, 150_000.0, 1e10),
        (60.0, 260_000.0, 3e10),
        (70.0, 600_000.0, 3e11),
    ];
    let d = eff_digits as f64;
    let mut out = (TABLE[0].1, TABLE[0].2);
    if d >= TABLE[TABLE.len() - 1].0 {
        let t = TABLE[TABLE.len() - 1];
        out = (t.1, t.2);
    } else {
        for w in TABLE.windows(2) {
            if d >= w[0].0 && d <= w[1].0 {
                let f = (d - w[0].0) / (w[1].0 - w[0].0);
                out = (
                    w[0].1 * (w[1].1 / w[0].1).powf(f),
                    w[0].2 * (w[1].2 / w[0].2).powf(f),
                );
            }
        }
    }
    (out.0 as u64, out.0 as u64, out.1)
}

/// Column keys: `(0, 1)` sign, `(0, 2)` parity, `(1, i)` character `i`,
/// `(p, u64::MAX)` rational prime, `(p, r)` algebraic ideal.
fn prime_columns(rel: &Relation, keys: &mut FxMap<(u64, u64), u32>, with_parity: bool) -> Vec<u32> {
    let mut key = |k: (u64, u64)| {
        let next = keys.len() as u32;
        *keys.entry(k).or_insert(next)
    };
    let mut cols = Vec::with_capacity(rel.rat.len() + rel.alg.len() + 2);
    if rel.rat_negative {
        cols.push(key((0, 1)));
    }
    if with_parity {
        cols.push(key((0, 2)));
    }
    for &p in &rel.rat {
        cols.push(key((p, u64::MAX)));
    }
    for &(p, r) in &rel.alg {
        cols.push(key((p, r)));
    }
    cols
}

/// Quadratic characters: pairs `(q, s)` with `q` prime above `start`,
/// `f(s) ≡ 0`, `f'(s) ≢ 0 (mod q)`, `q ∤ lead(f)`.
fn quadratic_characters(f: &IntPoly, start: u64, count: usize) -> Vec<(u64, u64)> {
    let fd = f.derivative();
    let mut out = Vec::new();
    let mut q = start | 1;
    while out.len() < count && q < (1 << 40) {
        q += 2;
        if !is_prime_u64(q) || (f.lead() % q).is_zero() {
            continue;
        }
        let fq = f.mod_p(q);
        for s in fp::roots(&fq, q) {
            let d = fd.mod_p(q);
            let mut acc = 0u64;
            for &c in d.iter().rev() {
                acc = ((acc as u128 * s as u128 + c as u128) % q as u128) as u64;
            }
            if acc != 0 && out.len() < count {
                out.push((q, s));
            }
        }
    }
    out
}

/// Run the NFS core on a given polynomial.  `f(m) ≡ 0 (mod n)` is
/// checked; `f` must be irreducible with an inert prime (see [`sqrt`]).
/// `eff_digits` sets the default parameters; the default sieve half-width
/// is `width_factor · √(area · skew / 2)` — 1 for SNFS, 0.35 for base-m
/// GNFS polynomials, whose low lines `b` have much smaller rational norms
/// (measured ~30% faster at 40 and 50 digits than the balanced shape).
pub(crate) fn run_core(
    report: &mut NfsReport,
    f: &IntPoly,
    m: &BigUint,
    skew: f64,
    width_factor: f64,
    eff_digits: usize,
    params: &NfsParams,
    progress: ProgressFn,
) {
    let t0 = Instant::now();
    let n = report.n.clone();
    report.polynomial = f.to_string();
    report.coefficients = f.coeffs.clone();
    report.m = m.clone();
    report.degree = f.degree();
    report.skewness = skew;
    report.alpha = polysel::murphy_alpha(f, 200);
    let fm = bigint_mod(&f.eval(&BigInt::from(m.clone())), &n);
    if !fm.is_zero() {
        report.failure = Some("f(m) is not divisible by n".into());
        return;
    }
    if f.degree() < 2 {
        report.failure = Some("polynomial degree must be at least 2".into());
        return;
    }
    let Some(inert) = polysel::find_inert_prime(&f.monic_transform(), 1 << 20, 400) else {
        report.failure = Some(
            "no inert prime: f is reducible or its Galois group has no d-cycle \
             (unsupported by this square root)"
                .into(),
        );
        return;
    };
    report.inert_prime = inert;

    // Parameters.
    let (rb0, ab0, area) = default_bounds(eff_digits);
    let rb = params.rational_bound.unwrap_or(rb0).max(100);
    let ab = params.algebraic_bound.unwrap_or(ab0).max(100);
    let lp_mult = params.large_prime_multiplier;
    let rat_lp = if lp_mult == 0 {
        1
    } else {
        rb.saturating_mul(lp_mult).min(rb.saturating_mul(rb))
    };
    let alg_lp = if lp_mult == 0 {
        1
    } else {
        ab.saturating_mul(lp_mult).min(ab.saturating_mul(ab))
    };
    let a_half = params
        .sieve_half_width
        // The skew-balanced rectangle of the planned area, times the front
        // end's `width_factor` (see `run_core`).
        .unwrap_or_else(|| {
            (width_factor * (area * skew / 2.0).sqrt()).clamp(8192.0, (1u64 << 31) as f64) as u64
        })
        .max(1024);
    let max_b = params.max_b.unwrap_or(1 << 24);
    report.rational_bound = rb;
    report.algebraic_bound = ab;
    report.large_prime_bound = rat_lp.max(alg_lp);
    report.sieve_half_width = a_half;

    let fb = FactorBases::build(f, m, rb, ab);
    report.rational_fb_size = fb.rat.len();
    report.algebraic_fb_size = fb.alg.len() + fb.alg_projective.len();
    let chars = quadratic_characters(
        f,
        rat_lp.max(alg_lp).max(ab) + 1000,
        params.quadratic_characters,
    );
    report.quadratic_characters = chars.len();
    let with_parity = !f.lead().is_one();

    let cfg = SieveConfig {
        f,
        m: BigInt::from(m.clone()),
        m_f64: m.to_f64().unwrap_or(f64::MAX),
        fb: &fb,
        rat_lp,
        alg_lp,
        slack_bits: params.threshold_slack_bits,
        min_sieve_prime: 30,
    };
    let Ok(pool) = rayon::ThreadPoolBuilder::new()
        .num_threads(params.threads.max(1))
        .build()
    else {
        report.failure = Some("could not build the thread pool".into());
        return;
    };

    // Sieve in batches of (b, segment) work items.
    const SEG: i64 = 1 << 20;
    let mut rels: Vec<Relation> = Vec::new();
    // Prime-only column vectors, built as relations arrive.
    let mut keys: FxMap<(u64, u64), u32> = FxMap::default();
    let mut rows: Vec<Vec<u32>> = Vec::new();
    let mut b = 1u64;
    let mut seg_lo = -(a_half as i64);
    let batch = params.threads.max(1) * 4;
    let extra_cols = chars.len() + 2 + params.surplus;
    let mut next_check = (fb.rat.len() + fb.alg.len()) * 3 / 4;
    let ts = Instant::now();
    'sieve: loop {
        let mut items = Vec::with_capacity(batch);
        while items.len() < batch {
            if b > max_b {
                break;
            }
            let hi = (seg_lo + SEG).min(a_half as i64);
            items.push((b, seg_lo, hi));
            seg_lo = hi;
            if seg_lo >= a_half as i64 {
                b += 1;
                seg_lo = -(a_half as i64);
            }
        }
        if items.is_empty() {
            report.failure = Some(format!(
                "sieve exhausted at b = {max_b} with {} relations",
                rels.len()
            ));
            break;
        }
        let outs: Vec<_> = pool.install(|| {
            items
                .par_iter()
                .map(|&(b, lo, hi)| sieve_segment(&cfg, b, lo, hi))
                .collect()
        });
        report.lines_sieved = items.last().map(|x| x.0).unwrap_or(0);
        for o in outs {
            report.cells_sieved += o.cells;
            report.candidates += o.candidates;
            rels.extend(o.relations);
        }
        if let Some(cb) = progress {
            cb(&Progress {
                stage: "sieve",
                done: rels.len() as u64,
                target: next_check as u64,
                seconds: secs(t0),
            });
        }
        for r in &rels[rows.len()..] {
            rows.push(parity_vector(prime_columns(r, &mut keys, false)));
        }
        if rels.len() >= next_check {
            let (r, c) = filtered_excess(&rows);
            if r >= c + extra_cols {
                break 'sieve;
            }
            next_check = rels.len() + (rels.len() / 20).max(100);
        }
    }
    report.sieve_seconds = secs(ts);
    report.full_relations = rels.iter().filter(|r| r.large_primes(rb, ab) == 0).count();
    report.partial_relations = rels.len() - report.full_relations;
    if report.failure.is_some() {
        report.total_seconds = secs(t0);
        return;
    }

    // Matrix with characters.
    if let Some(cb) = progress {
        cb(&Progress {
            stage: "linalg",
            done: rels.len() as u64,
            target: 0,
            seconds: secs(t0),
        });
    }
    let tl = Instant::now();
    // Only relations that survive singleton removal can be in a
    // dependency; characters and the parity column are added to those.
    let alive = singleton_survivors(&rows);
    let mut final_rows = Vec::new();
    let mut row_rel = Vec::new();
    let mut ckeys: FxMap<(u64, u64), u32> = FxMap::default();
    'rel: for (i, r) in rels.iter().enumerate() {
        if !alive[i] {
            continue;
        }
        let mut cols = prime_columns(r, &mut ckeys, with_parity);
        for (ci, &(q, s)) in chars.iter().enumerate() {
            let v = (r.a as i128 - r.b as i128 * s as i128).rem_euclid(q as i128) as u64;
            match jacobi_u64(v, q) {
                0 => continue 'rel,
                -1 => {
                    let next = ckeys.len() as u32;
                    cols.push(*ckeys.entry((1, ci as u64)).or_insert(next));
                }
                _ => {}
            }
        }
        final_rows.push(parity_vector(cols));
        row_rel.push(i);
    }
    let (deps, mut stats) = find_dependencies(&final_rows, params.max_dependencies, params.surplus);
    stats.rows_in = rels.len();
    stats.cols_in = keys.len();
    report.linalg = stats;
    report.linalg_seconds = secs(tl);

    // Square roots.
    let tq = Instant::now();
    let fmonic = f.monic_transform();
    let c = f.lead().clone();
    let cmod = bigint_mod(&c, &n);
    let mm = &cmod * m % &n;
    let fprime_m = bigint_mod(&fmonic.derivative().eval(&BigInt::from(mm.clone())), &n);
    for (k, dep) in deps.iter().enumerate() {
        if let Some(cb) = progress {
            cb(&Progress {
                stage: "sqrt",
                done: k as u64,
                target: deps.len() as u64,
                seconds: secs(t0),
            });
        }
        report.dependencies_tried += 1;
        let sel: Vec<&Relation> = dep.iter().map(|&i| &rels[row_rel[i]]).collect();
        let mut st = SqrtStats {
            relations: sel.len(),
            ..Default::default()
        };
        // Rational square root from the recorded factorisations.
        let mut exps: HashMap<u64, u64> = HashMap::new();
        let mut neg = 0usize;
        for r in &sel {
            neg += r.rat_negative as usize;
            for &p in &r.rat {
                *exps.entry(p).or_insert(0) += 1;
            }
        }
        if neg % 2 == 1 || exps.values().any(|e| e % 2 == 1) || (with_parity && sel.len() % 2 == 1)
        {
            st.outcome = "rational side not a square (internal error)".into();
            report.sqrt_attempts.push(st);
            continue;
        }
        let mut y = BigUint::one();
        let mut word = 1u128;
        for (&p, &e) in &exps {
            for _ in 0..e / 2 {
                if word.leading_zeros() < 64 - p.leading_zeros() {
                    y = y * BigUint::from(word) % &n;
                    word = 1;
                }
                word *= p as u128;
            }
        }
        y = y * BigUint::from(word) % &n;
        let pairs: Vec<(i64, u64)> = sel.iter().map(|r| (r.a, r.b)).collect();
        let g = sqrt::gamma(&fmonic, &c, &pairs);
        let Some(delta) = sqrt::sqrt_gamma(&fmonic, &g, inert, &mut st) else {
            report.sqrt_attempts.push(st);
            continue;
        };
        let x = sqrt::eval_mod(&delta, &mm, &n);
        let cpow = cmod.modpow(&BigUint::from(sel.len() / 2), &n);
        let yy = &fprime_m * cpow % &n * y % &n;
        if &x * &x % &n != &yy * &yy % &n {
            st.outcome = "congruence check failed".into();
            report.sqrt_attempts.push(st);
            continue;
        }
        report.sqrt_attempts.push(st);
        let d1 = if x >= yy { &x - &yy } else { &yy - &x };
        if report.accept(d1.gcd(&n)) || report.accept((&x + &yy).gcd(&n)) {
            break;
        }
    }
    report.sqrt_seconds = secs(tq);
    if report.factor.is_none() {
        report.failure = Some(format!(
            "{} dependencies tried, none gave a proper factor",
            report.dependencies_tried
        ));
    }
    report.total_seconds = secs(t0);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn core_handles_non_monic_polynomial() {
        // Base-m with leading coefficient 7 (f(m) = n exactly): exercises
        // the monic transform, the parity column and c^{|S|/2} on the
        // rational side.
        let p: BigUint = "100000000000000003".parse().unwrap();
        let q: BigUint = "1000000000039".parse().unwrap();
        let n = &p * &q;
        let (f, m) = polysel::base_m(&n, 3, 7).unwrap();
        assert!(!f.lead().is_one());
        let mut report = NfsReport::new("gnfs", &n);
        let skew = polysel::skewness(&f);
        run_core(
            &mut report,
            &f,
            &m,
            skew,
            0.35,
            30,
            &NfsParams::default(),
            None,
        );
        assert!(report.verified, "{:?}", report.failure);
        assert_eq!(report.factor.unwrap() * report.cofactor.unwrap(), n);
    }

    #[test]
    fn default_bounds_grow_with_size() {
        let mut last = 0;
        for d in (20..=80).step_by(5) {
            let (r, a, area) = default_bounds(d);
            assert_eq!(r, a);
            assert!(r >= last && area > 0.0);
            last = r;
        }
    }

    #[test]
    fn wrong_root_is_rejected() {
        let n = BigUint::from(1_000_000_016_000_000_063u64); // 1000000007 · 1000000009
        let f = IntPoly::from_i64(&[2, 0, 0, 1]);
        let mut report = NfsReport::new("snfs", &n);
        run_core(
            &mut report,
            &f,
            &BigUint::from(12345u32),
            1.0,
            1.0,
            20,
            &NfsParams::default(),
            None,
        );
        assert!(report.factor.is_none());
        assert!(report.failure.unwrap().contains("f(m)"));
    }
}
