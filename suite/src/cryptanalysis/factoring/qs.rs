//! **Self-initialising quadratic sieve** (SIQS) with the single large
//! prime variation.
//!
//! # The method
//!
//! Find many `y` with `y² ≡ Q (mod n)` and `Q` smooth over a *factor
//! base* of primes `p` for which `n` is a square mod `p`; a subset whose
//! `Q`s multiply to a square `Y²` (found by GF(2) linear algebra on the
//! exponent parities) gives `X² ≡ Y² (mod n)` and, half the time,
//! `gcd(X − Y, n)` is a proper factor (Pomerance 1982).
//!
//! The sieve values come from polynomials `Q(x) = (a x + b)² − k n
//! = a · g(x)` with `g(x) = a x² + 2 b x + c`, `b² ≡ k n (mod a)`,
//! `c = (b² − k n)/a`, sieved over `x ∈ [−M, M)`.  Choosing
//! `a ≈ √(2kn)/M` keeps `|g(x)| ≲ M √(kn/2)` — the whole point of the
//! *multiple*-polynomial QS (Montgomery; Silverman 1987).  Here `a` is a
//! product of `s` factor-base primes `q_j`, which gives `2^{s−1}`
//! different `b` for one `a`; switching between them in Gray-code order
//! updates each sieve root with one modular addition — the
//! *self-initialising* QS (Alford–Pomerance; Contini's thesis 1997).
//!
//! The Knuth–Schroeppel multiplier `k` (squarefree, ≤ 73) is chosen to
//! maximise the expected contribution of small primes.  A relation is
//! kept if the unfactored cofactor after trial division is 1 (*full*)
//! or a single prime below `LP = large_prime_multiplier · p_max`
//! (*partial*); partials sharing a large prime become cycles in the
//! linear algebra, via singleton removal and structured elimination in
//! [`crate::cryptanalysis::factoring::nfs::linalg`] — the same GF(2)
//! engine the NFS uses.
//!
//! # Complexity and scale
//!
//! Heuristically `L_n[1/2, 1]`.  This implementation sieves with bytes of
//! rounded `log₂ p`, skips primes below 30 (compensated in the
//! threshold), and trial-divides survivors by checking each prime's two
//! roots.  Measured on one core: 40-digit semiprimes in ~0.3 s, 50 digits
//! in ~1 s, 60 digits in ~11 s (the README has the table).  YAFU and
//! msieve are several times faster still: they add bucket sieving for
//! large primes, resieving, SIMD, double/triple large primes and tuned
//! parameters.
//!
//! References: C. Pomerance, *Analysis and comparison of some integer
//! factoring algorithms* (1982); R. D. Silverman, *The multiple
//! polynomial quadratic sieve*, Math. Comp. 48 (1987); S. Contini,
//! *Factoring integers with the self-initializing quadratic sieve*,
//! M.Sc. thesis, U. Georgia (1997).

use num_bigint::{BigInt, BigUint, Sign};
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};
use rand::{rngs::SmallRng, Rng, SeedableRng};
use rayon::prelude::*;
use serde::Serialize;
use std::collections::{HashMap, HashSet};
use std::time::Instant;

use super::arith::{
    big_mod_u64, bigint_mod, bigint_mod_u64, inv_mod, is_probable_prime, isqrt_exact, legendre,
    mul_mod, primes_up_to, secs, sqrt_mod,
};
use super::nfs::linalg::{filtered_excess, find_dependencies, parity_vector, LinalgStats};
use super::{serde_big, Progress, ProgressFn};

/// Options for [`qs`].  `None` fields are chosen from the size of `n`.
#[derive(Clone, Debug, Serialize)]
pub struct QsParams {
    /// Number of primes in the factor base.
    pub factor_base_size: Option<usize>,
    /// Sieve interval half-width `M` (`x ∈ [−M, M)`).
    pub sieve_half_width: Option<u32>,
    /// Large-prime bound as a multiple of the largest factor-base prime
    /// (0 disables partial relations).
    pub large_prime_multiplier: u64,
    /// Bits subtracted from the sieve threshold on top of the large prime.
    pub threshold_slack_bits: u32,
    /// Knuth–Schroeppel multiplier; `None` chooses the best.
    pub multiplier: Option<u64>,
    /// Extra relations beyond the column count before stopping.
    pub surplus: usize,
    /// Dependencies to request from the linear algebra.
    pub max_dependencies: usize,
    /// Give up after this many `a` values (0 = unlimited).
    pub max_a_values: u64,
    /// Worker threads (1 = sequential).
    pub threads: usize,
    /// Seed for the choice of `a` values.
    pub seed: u64,
}

impl Default for QsParams {
    fn default() -> Self {
        QsParams {
            factor_base_size: None,
            sieve_half_width: None,
            large_prime_multiplier: 60,
            threshold_slack_bits: 4,
            multiplier: None,
            surplus: 64,
            max_dependencies: 64,
            max_a_values: 0,
            threads: 1,
            seed: 1,
        }
    }
}

/// Outcome and statistics of [`qs`].
#[derive(Clone, Debug, Serialize)]
pub struct QsReport {
    /// The number that was attacked.
    #[serde(with = "serde_big::biguint")]
    pub n: BigUint,
    /// Decimal digits of `n`.
    pub digits: usize,
    /// A non-trivial factor, if one was found.
    #[serde(with = "serde_big::opt_biguint")]
    pub factor: Option<BigUint>,
    /// `n / factor`.
    #[serde(with = "serde_big::opt_biguint")]
    pub cofactor: Option<BigUint>,
    /// `factor · cofactor == n` was checked.
    pub verified: bool,
    /// Why no factor was returned, if none was.
    pub failure: Option<String>,
    /// Knuth–Schroeppel multiplier used.
    pub multiplier: u64,
    /// Primes in the factor base.
    pub factor_base_size: usize,
    /// Largest factor-base prime.
    pub largest_prime: u64,
    /// Sieve half-width `M`.
    pub sieve_half_width: u32,
    /// Large-prime bound.
    pub large_prime_bound: u64,
    /// Primes per `a`.
    pub primes_per_a: usize,
    /// `a` values used.
    pub a_values: u64,
    /// Polynomials (`b` values) sieved.
    pub polynomials: u64,
    /// Sieve survivors that were trial-divided.
    pub candidates: u64,
    /// Full relations collected.
    pub full_relations: usize,
    /// Partial (one large prime) relations collected.
    pub partial_relations: usize,
    /// Linear-algebra sizes.
    pub linalg: LinalgStats,
    /// Dependencies tried in the square-root step.
    pub dependencies_tried: usize,
    /// Seconds in the sieve.
    pub sieve_seconds: f64,
    /// Seconds in linear algebra.
    pub linalg_seconds: f64,
    /// Seconds in the square-root / gcd step.
    pub sqrt_seconds: f64,
    /// Total seconds.
    pub total_seconds: f64,
}

/// One QS relation: `y² ≡ sign · ∏ primes (mod n)`.
#[derive(Clone, Debug)]
struct Relation {
    y: BigInt,
    negative: bool,
    /// Factor-base indices (with multiplicity).
    fb: Vec<u32>,
    /// Large prime, 1 if none.
    large: u64,
}

struct FactorBase {
    primes: Vec<u64>,
    /// `√(kn) mod p`.
    roots: Vec<u64>,
    logs: Vec<u8>,
    /// Primes dividing `k` (single root 0; trial-divided, not sieved).
    divides_k: Vec<bool>,
}

/// `(digits, factor-base size, M)` interpolation table.
const PARAM_TABLE: [(f64, f64, f64); 9] = [
    (20.0, 100.0, 16384.0),
    (30.0, 200.0, 32768.0),
    (40.0, 600.0, 65536.0),
    (45.0, 1000.0, 65536.0),
    (50.0, 1600.0, 65536.0),
    (55.0, 2400.0, 98304.0),
    (60.0, 3600.0, 131072.0),
    (70.0, 7500.0, 196608.0),
    (80.0, 15000.0, 262144.0),
];

fn table_params(digits: usize) -> (usize, u32) {
    let d = digits as f64;
    let t = &PARAM_TABLE;
    if d <= t[0].0 {
        return (t[0].1 as usize, t[0].2 as u32);
    }
    for w in t.windows(2) {
        if d <= w[1].0 {
            let f = (d - w[0].0) / (w[1].0 - w[0].0);
            let fb = w[0].1 + f * (w[1].1 - w[0].1);
            let m = w[0].2 + f * (w[1].2 - w[0].2);
            return (fb as usize, (m as u32).next_multiple_of(4096));
        }
    }
    let last = t[t.len() - 1];
    (last.1 as usize, last.2 as u32)
}

/// Knuth–Schroeppel: the squarefree `k ≤ 73` maximising the expected
/// log-contribution of small primes to `Q(x)` for `kn`.
fn choose_multiplier(n: &BigUint) -> u64 {
    let ks: [u64; 30] = [
        1, 2, 3, 5, 6, 7, 10, 11, 13, 14, 15, 17, 19, 21, 22, 23, 26, 29, 30, 31, 33, 34, 35, 37,
        38, 39, 41, 43, 47, 73,
    ];
    let primes = primes_up_to(2000);
    let mut best = (f64::MIN, 1u64);
    for &k in &ks {
        let kn = n * k;
        let mut score = -0.5 * (k as f64).ln();
        match big_mod_u64(&kn, 8) {
            1 => score += 2.0 * 2f64.ln(),
            5 => score += 2f64.ln(),
            3 | 7 => score += 0.5 * 2f64.ln(),
            _ => {}
        }
        for &p in primes.iter().skip(1) {
            let r = big_mod_u64(&kn, p);
            let lp = (p as f64).ln();
            if r == 0 {
                score += lp / p as f64;
            } else if legendre(r, p) == 1 {
                score += 2.0 * lp / (p - 1) as f64;
            }
        }
        if score > best.0 {
            best = (score, k);
        }
    }
    best.1
}

fn build_factor_base(kn: &BigUint, k: u64, size: usize) -> FactorBase {
    let mut fb = FactorBase {
        primes: vec![2],
        roots: vec![big_mod_u64(kn, 2)],
        logs: vec![1],
        divides_k: vec![k.is_multiple_of(2)],
    };
    let mut bound = (size as u64 * 30).max(1000);
    'outer: loop {
        for p in primes_up_to(bound).into_iter().skip(1) {
            if p <= *fb.primes.last().unwrap_or(&2) {
                continue;
            }
            let r = big_mod_u64(kn, p);
            let dk = k.is_multiple_of(p);
            if dk || legendre(r, p) == 1 {
                fb.primes.push(p);
                fb.roots
                    .push(if dk { 0 } else { sqrt_mod(r, p).unwrap_or(0) });
                fb.logs.push((p as f64).log2().round() as u8);
                fb.divides_k.push(dk);
                if fb.primes.len() >= size {
                    break 'outer;
                }
            }
        }
        bound *= 2;
    }
    fb
}

/// Per-`a` data shared by its `2^{s−1}` polynomials.
struct APoly {
    a: BigUint,
    /// Factor-base indices of the primes of `a`.
    q_idx: Vec<usize>,
    /// `B_j` with `b = Σ ±B_j`.
    bs: Vec<BigUint>,
}

/// Choose `a = ∏ q_j` close to `target` from the factor base.
fn choose_a(fb: &FactorBase, target: &BigUint, rng: &mut SmallRng, s: usize) -> Option<APoly> {
    let tf = target.to_f64()?;
    let n = fb.primes.len();
    // Candidate primes: odd, not dividing k, ≥ 50, around target^{1/s}.
    let want = tf.powf(1.0 / s as f64);
    let center = fb.primes.partition_point(|&p| (p as f64) < want);
    let lo = fb
        .primes
        .partition_point(|&p| p < 50)
        .max(center.saturating_sub(40));
    let hi = (center + 40).min(n - 1);
    if lo >= hi {
        return None;
    }
    let mut q_idx: Vec<usize> = Vec::with_capacity(s);
    let mut prod = BigUint::one();
    for _ in 0..s.saturating_sub(1) {
        let mut tries = 0;
        loop {
            let i = rng.gen_range(lo..=hi);
            if !q_idx.contains(&i) && !fb.divides_k[i] {
                q_idx.push(i);
                prod *= fb.primes[i];
                break;
            }
            tries += 1;
            if tries > 1000 {
                return None;
            }
        }
    }
    // Last prime: the one bringing the product closest to the target.
    let rest = tf / prod.to_f64()?;
    let start = fb.primes.partition_point(|&p| (p as f64) < rest);
    let mut best: Option<(f64, usize)> = None;
    for i in start.saturating_sub(8)..(start + 8).min(n) {
        if i == 0 || fb.primes[i] < 3 || q_idx.contains(&i) || fb.divides_k[i] {
            continue;
        }
        let err = ((fb.primes[i] as f64) / rest).ln().abs();
        if best.is_none_or(|(e, _)| err < e) {
            best = Some((err, i));
        }
    }
    let (_, last) = best?;
    q_idx.push(last);
    q_idx.sort_unstable();
    let a: BigUint = q_idx.iter().map(|&i| BigUint::from(fb.primes[i])).product();
    let mut bs = Vec::with_capacity(s);
    for &i in &q_idx {
        let q = fb.primes[i];
        let aq = &a / q;
        let aq_mod = big_mod_u64(&aq, q);
        let inv = inv_mod(aq_mod, q)?;
        let mut gamma = mul_mod(fb.roots[i], inv, q);
        if gamma > q / 2 {
            gamma = q - gamma;
        }
        bs.push(aq * gamma);
    }
    Some(APoly { a, q_idx, bs })
}

struct SieveCtx<'a> {
    kn: &'a BigUint,
    fb: &'a FactorBase,
    m: u32,
    lp_bound: u64,
    threshold: u8,
    min_sieve_prime: u64,
}

struct AOutcome {
    rels: Vec<Relation>,
    polys: u64,
    candidates: u64,
}

/// Sieve all `2^{s−1}` polynomials of one `a`.
fn sieve_a(ctx: &SieveCtx, ap: &APoly) -> AOutcome {
    let fb = ctx.fb;
    let nfb = fb.primes.len();
    let s = ap.bs.len();
    let m = ctx.m as i64;
    let len = 2 * ctx.m as usize;
    let mut out = AOutcome {
        rels: Vec::new(),
        polys: 0,
        candidates: 0,
    };
    let in_a: Vec<bool> = {
        let mut v = vec![false; nfb];
        for &i in &ap.q_idx {
            v[i] = true;
        }
        v
    };
    // b = B_0 + … + B_{s−1}; Gray code flips the signs of B_0 … B_{s−2}.
    let mut signs = vec![1i8; s];
    let mut b: BigInt = ap.bs.iter().map(|x| BigInt::from(x.clone())).sum();
    let mut ainv = vec![0u64; nfb];
    let mut bainv2 = vec![vec![0u64; nfb]; s];
    let mut soln1 = vec![0u64; nfb];
    let mut soln2 = vec![0u64; nfb];
    for i in 1..nfb {
        let p = fb.primes[i];
        if in_a[i] || fb.divides_k[i] {
            continue;
        }
        let ai = inv_mod(big_mod_u64(&ap.a, p), p).unwrap_or(0);
        ainv[i] = ai;
        for j in 0..s {
            bainv2[j][i] = mul_mod(2 * big_mod_u64(&ap.bs[j], p) % p, ai, p);
        }
        let bm = bigint_mod_u64(&b, p);
        let t = fb.roots[i];
        soln1[i] = mul_mod((t + p - bm) % p, ai, p);
        soln2[i] = mul_mod((2 * p - t - bm) % p, ai, p);
    }
    let a_big = BigInt::from(ap.a.clone());
    let kn_big = BigInt::from(ctx.kn.clone());
    let mut sieve = vec![0u8; len];
    let npolys = 1u64 << (s - 1);
    for poly in 0..npolys {
        if poly > 0 {
            let v = poly.trailing_zeros() as usize;
            // b ← b − 2·sign·B_v; roots move by +sign·2·B_v·a⁻¹.
            let sign = signs[v];
            let two_bv = BigInt::from(ap.bs[v].clone()) * 2;
            if sign > 0 {
                b -= &two_bv;
            } else {
                b += &two_bv;
            }
            signs[v] = -sign;
            for i in 1..nfb {
                let p = fb.primes[i];
                if ainv[i] == 0 {
                    continue;
                }
                let d = bainv2[v][i];
                if sign > 0 {
                    soln1[i] = (soln1[i] + d) % p;
                    soln2[i] = (soln2[i] + d) % p;
                } else {
                    soln1[i] = (soln1[i] + p - d) % p;
                    soln2[i] = (soln2[i] + p - d) % p;
                }
            }
        }
        out.polys += 1;
        // c = (b² − kn) / a.
        let c = (&b * &b - &kn_big) / &a_big;
        sieve.fill(0);
        for i in 1..nfb {
            let p = fb.primes[i];
            if p < ctx.min_sieve_prime || ainv[i] == 0 {
                continue;
            }
            let lg = fb.logs[i];
            let pu = p as usize;
            let mut j1 = ((soln1[i] + ctx.m as u64 % p) % p) as usize;
            let mut j2 = ((soln2[i] + ctx.m as u64 % p) % p) as usize;
            if j1 == j2 {
                while j1 < len {
                    sieve[j1] = sieve[j1].wrapping_add(lg);
                    j1 += pu;
                }
                continue;
            }
            if j1 > j2 {
                std::mem::swap(&mut j1, &mut j2);
            }
            // Walk both progressions together.
            while j2 < len {
                sieve[j1] = sieve[j1].wrapping_add(lg);
                sieve[j2] = sieve[j2].wrapping_add(lg);
                j1 += pu;
                j2 += pu;
            }
            if j1 < len {
                sieve[j1] = sieve[j1].wrapping_add(lg);
            }
        }
        for (idx, &v) in sieve.iter().enumerate() {
            if v < ctx.threshold {
                continue;
            }
            out.candidates += 1;
            let x = idx as i64 - m;
            if let Some(rel) = trial_divide(ctx, ap, &in_a, &b, &c, x, &soln1, &soln2) {
                out.rels.push(rel);
            }
        }
    }
    out
}

/// Trial-divide `g(x) = a x² + 2 b x + c`; relation for `a · g(x)`.
fn trial_divide(
    ctx: &SieveCtx,
    ap: &APoly,
    in_a: &[bool],
    b: &BigInt,
    c: &BigInt,
    x: i64,
    soln1: &[u64],
    soln2: &[u64],
) -> Option<Relation> {
    let fb = ctx.fb;
    let xb = BigInt::from(x);
    let a = BigInt::from(ap.a.clone());
    let g: BigInt = (&a * &xb + b * 2) * &xb + c;
    if g.is_zero() {
        return None;
    }
    let negative = g.sign() == Sign::Minus;
    let mut v = g.magnitude().clone();
    let mut fbi: Vec<u32> = ap.q_idx.iter().map(|&i| i as u32).collect();
    let tz = v.trailing_zeros().unwrap_or(0);
    if tz > 0 {
        v >>= tz;
        fbi.extend(std::iter::repeat_n(0u32, tz as usize));
    }
    for i in 1..fb.primes.len() {
        let p = fb.primes[i];
        let divides = if in_a[i] || fb.divides_k[i] {
            big_mod_u64(&v, p) == 0
        } else {
            let xm = x.rem_euclid(p as i64) as u64;
            xm == soln1[i] || xm == soln2[i]
        };
        if !divides {
            continue;
        }
        loop {
            let (q, r) = v.div_rem(&BigUint::from(p));
            if !r.is_zero() {
                break;
            }
            v = q;
            fbi.push(i as u32);
        }
    }
    let large = if v.is_one() {
        1
    } else {
        match v.to_u64() {
            Some(l) if l <= ctx.lp_bound => l,
            _ => return None,
        }
    };
    let y = a * xb + b;
    Some(Relation {
        y,
        negative,
        fb: fbi,
        large,
    })
}

/// Column vectors for the relations: `0` = sign, `1 + i` = factor-base
/// prime `i`, then one column per large prime.
fn relation_rows(rels: &[Relation], nfb: usize) -> Vec<Vec<u32>> {
    let mut lp_cols: HashMap<u64, u32> = HashMap::new();
    rels.iter()
        .map(|r| {
            let mut cols: Vec<u32> = r.fb.iter().map(|&i| i + 1).collect();
            if r.negative {
                cols.push(0);
            }
            if r.large > 1 {
                let next = (nfb + 1 + lp_cols.len()) as u32;
                cols.push(*lp_cols.entry(r.large).or_insert(next));
            }
            parity_vector(cols)
        })
        .collect()
}

fn failure_report(n: &BigUint, msg: &str) -> QsReport {
    QsReport {
        n: n.clone(),
        digits: n.to_str_radix(10).len(),
        factor: None,
        cofactor: None,
        verified: false,
        failure: Some(msg.to_string()),
        multiplier: 1,
        factor_base_size: 0,
        largest_prime: 0,
        sieve_half_width: 0,
        large_prime_bound: 0,
        primes_per_a: 0,
        a_values: 0,
        polynomials: 0,
        candidates: 0,
        full_relations: 0,
        partial_relations: 0,
        linalg: LinalgStats::default(),
        dependencies_tried: 0,
        sieve_seconds: 0.0,
        linalg_seconds: 0.0,
        sqrt_seconds: 0.0,
        total_seconds: 0.0,
    }
}

/// Set `factor`/`cofactor` if `g` is a proper divisor of `n`, verified by
/// multiplication.
fn accept(report: &mut QsReport, g: BigUint) -> bool {
    let n = &report.n;
    if g.is_one() || &g == n || g.is_zero() {
        return false;
    }
    let (q, r) = n.div_rem(&g);
    if r.is_zero() && &(&g * &q) == n {
        report.factor = Some(g.min(q.clone()));
        report.cofactor = Some(report.n.clone() / report.factor.as_ref().expect("set"));
        report.verified = true;
        true
    } else {
        false
    }
}

/// Factor `n` with the self-initialising quadratic sieve.  Returns one
/// verified proper factor (not a full factorisation).  `n` must be an odd
/// composite that is not a perfect power; trivial cases (even, perfect
/// square, small prime factor) are answered directly.
pub fn qs(n: &BigUint, params: &QsParams, progress: ProgressFn) -> QsReport {
    let t0 = Instant::now();
    let mut report = failure_report(n, "not started");
    report.failure = None;
    if n < &BigUint::from(4u32) || is_probable_prime(n) {
        report.failure = Some("n is < 4 or prime".into());
        return report;
    }
    // Trivial splits the sieve cannot handle.
    for p in primes_up_to(1000) {
        if big_mod_u64(n, p) == 0 {
            accept(&mut report, BigUint::from(p));
            report.total_seconds = secs(t0);
            return report;
        }
    }
    let (r, exact) = isqrt_exact(n);
    if exact {
        accept(&mut report, r);
        report.total_seconds = secs(t0);
        return report;
    }
    let digits = report.digits;
    let (fb_size, m) = table_params(digits);
    let fb_size = params.factor_base_size.unwrap_or(fb_size).max(30);
    let m = params.sieve_half_width.unwrap_or(m).max(1024);
    let k = params.multiplier.unwrap_or_else(|| choose_multiplier(n));
    let kn = n * k;
    let fb = build_factor_base(&kn, k, fb_size);
    for &p in &fb.primes {
        if big_mod_u64(n, p) == 0 {
            accept(&mut report, BigUint::from(p));
            report.total_seconds = secs(t0);
            return report;
        }
    }
    let pmax = *fb.primes.last().expect("non-empty");
    let lp_bound = if params.large_prime_multiplier == 0 {
        1
    } else {
        (pmax * params.large_prime_multiplier).min(pmax.saturating_mul(pmax))
    };
    // log2 of the typical |g(x)| ≈ M √(kn/2) / something; subtract the
    // large-prime allowance and the skipped small primes.
    let log_g = (m as f64).log2() + kn.bits() as f64 / 2.0 - 0.5;
    let lp_bits = if lp_bound > 1 {
        (lp_bound as f64).log2()
    } else {
        0.0
    };
    let threshold = (log_g - lp_bits - params.threshold_slack_bits as f64).clamp(10.0, 250.0) as u8;
    // a ≈ √(2kn)/M.
    let target_a = (&kn * 2u32).sqrt() / m;
    let ta = target_a.to_f64().unwrap_or(f64::MAX);
    let s = if ta < 2000.0 {
        1
    } else {
        let mut best = 2usize;
        let mut best_err = f64::MAX;
        for s in 2..=20usize {
            let q = ta.powf(1.0 / s as f64);
            let err = (q.ln() - 2000f64.min(pmax as f64 / 2.0).ln()).abs();
            if err < best_err {
                best_err = err;
                best = s;
            }
        }
        best
    };
    report.multiplier = k;
    report.factor_base_size = fb.primes.len();
    report.largest_prime = pmax;
    report.sieve_half_width = m;
    report.large_prime_bound = lp_bound;
    report.primes_per_a = s;

    let ctx = SieveCtx {
        kn: &kn,
        fb: &fb,
        m,
        lp_bound,
        threshold,
        min_sieve_prime: 30,
    };
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(params.threads.max(1))
        .build();
    let Ok(pool) = pool else {
        report.failure = Some("could not build the thread pool".into());
        return report;
    };
    let mut rng = SmallRng::seed_from_u64(params.seed);
    let mut used_a: HashSet<BigUint> = HashSet::new();
    let mut rels: Vec<Relation> = Vec::new();
    let mut seen_y: HashSet<BigInt> = HashSet::new();
    let batch = params.threads.max(1) * 4;
    let mut next_check = fb.primes.len();
    let mut failures = 0u32;
    loop {
        // Draw a batch of fresh a values.
        let mut aps = Vec::with_capacity(batch);
        while aps.len() < batch {
            match choose_a(&fb, &target_a, &mut rng, s) {
                Some(ap) if used_a.insert(ap.a.clone()) => {
                    failures = 0;
                    aps.push(ap)
                }
                _ => {
                    failures += 1;
                    if failures > 10_000 {
                        break;
                    }
                }
            }
        }
        if aps.is_empty() {
            report.failure = Some("ran out of distinct a values".into());
            break;
        }
        let outs: Vec<AOutcome> =
            pool.install(|| aps.par_iter().map(|ap| sieve_a(&ctx, ap)).collect());
        report.a_values += aps.len() as u64;
        for o in outs {
            report.polys_add(o.polys, o.candidates);
            for r in o.rels {
                // Duplicate relations (same y up to sign) add nothing.
                let key = r.y.abs();
                if seen_y.insert(key) {
                    rels.push(r);
                }
            }
        }
        report.full_relations = rels.iter().filter(|r| r.large == 1).count();
        report.partial_relations = rels.len() - report.full_relations;
        if let Some(cb) = progress {
            cb(&Progress {
                stage: "sieve",
                done: report.full_relations as u64,
                target: fb.primes.len() as u64,
                seconds: secs(t0),
            });
        }
        if rels.len() >= next_check {
            let rows = relation_rows(&rels, fb.primes.len());
            let (r, c) = filtered_excess(&rows);
            if r >= c + params.surplus {
                break;
            }
            next_check = rels.len() + (fb.primes.len() / 20).max(20);
        }
        if params.max_a_values > 0 && report.a_values >= params.max_a_values {
            report.failure = Some("a-value budget exhausted before enough relations".into());
            break;
        }
    }
    report.sieve_seconds = secs(t0);
    if report.failure.is_some() {
        report.total_seconds = secs(t0);
        return report;
    }
    if let Some(cb) = progress {
        cb(&Progress {
            stage: "linalg",
            done: 0,
            target: 0,
            seconds: secs(t0),
        });
    }
    let t1 = Instant::now();
    let rows = relation_rows(&rels, fb.primes.len());
    let (deps, stats) = find_dependencies(&rows, params.max_dependencies, params.surplus);
    report.linalg = stats;
    report.linalg_seconds = secs(t1);
    let t2 = Instant::now();
    for dep in &deps {
        report.dependencies_tried += 1;
        let mut x = BigUint::one();
        let mut exps: HashMap<u64, u64> = HashMap::new();
        let mut neg = 0usize;
        for &ri in dep {
            let r = &rels[ri];
            x = x * bigint_mod(&r.y, n) % n;
            for &i in &r.fb {
                *exps.entry(fb.primes[i as usize]).or_insert(0) += 1;
            }
            if r.large > 1 {
                *exps.entry(r.large).or_insert(0) += 1;
            }
            neg += r.negative as usize;
        }
        if neg % 2 == 1 || exps.values().any(|e| e % 2 == 1) {
            continue; // not a square: a bug guard, never expected
        }
        let mut y = BigUint::one();
        for (&p, &e) in &exps {
            y = y * BigUint::from(p).modpow(&BigUint::from(e / 2), n) % n;
        }
        debug_assert_eq!(&x * &x % n, &y * &y % n);
        let diff = if x >= y { &x - &y } else { &y - &x };
        if accept(&mut report, diff.gcd(n)) {
            break;
        }
    }
    report.sqrt_seconds = secs(t2);
    if report.factor.is_none() {
        report.failure = Some(format!(
            "all {} dependencies gave trivial factors",
            deps.len()
        ));
    }
    report.total_seconds = secs(t0);
    report
}

impl QsReport {
    fn polys_add(&mut self, polys: u64, candidates: u64) {
        self.polynomials += polys;
        self.candidates += candidates;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn check(n: &BigUint, p: &BigUint) {
        let r = qs(n, &QsParams::default(), None);
        assert!(r.verified, "{:?}", r.failure);
        let f = r.factor.clone().unwrap();
        let q = n / p;
        assert!(f == *p || f == q, "unexpected factor {f}");
        assert_eq!(&f * r.cofactor.unwrap(), *n);
    }

    #[test]
    fn qs_factors_20_digit_semiprime() {
        let p = BigUint::from(3_267_000_013u64);
        let q = BigUint::from(10_000_000_019u64);
        check(&(&p * &q), &p);
    }

    #[test]
    fn qs_factors_30_digit_semiprime() {
        let p: BigUint = "100000000000000003".parse().unwrap();
        let q: BigUint = "1000000000039".parse().unwrap();
        check(&(&p * &q), &p);
    }

    #[test]
    fn qs_factors_40_digit_semiprime() {
        let p: BigUint = "10000000000000000051".parse().unwrap();
        let q: BigUint = "100000000000000000039".parse().unwrap();
        check(&(&p * &q), &p);
    }

    #[test]
    fn qs_rejects_prime_input() {
        let p: BigUint = "1000000000000000000000007".parse().unwrap();
        let r = qs(&p, &QsParams::default(), None);
        assert!(r.factor.is_none());
        assert!(r.failure.is_some());
    }
}
