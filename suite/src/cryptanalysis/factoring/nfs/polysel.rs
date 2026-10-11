//! Polynomial selection for the GNFS: **base-m** expansion with a small
//! search over the leading coefficient, scored by norm size, skewness and
//! Murphy's `α`.
//!
//! # Base-m
//!
//! For degree `d` and leading coefficient `c_d`, put
//! `m = ⌊(n / c_d)^{1/d}⌋` and write `n` in base `m`:
//! `n = Σ cᵢ mⁱ`, then balance the digits into `(−m/2, m/2]`.  Then
//! `f(x) = Σ cᵢ xⁱ` has `f(m) = n` **exactly** (Buhler–Lenstra–Pomerance).
//! Because `m` is the `d`-th root, `c_{d−1}` is small (`< d·c_d`) while
//! `c_{d−2}, …, c₀` are of size `m`: the polynomial is *skewed*, and the
//! sieve region is stretched to match (`|a| ≈ s·|b|`, skewness `s`
//! minimising `max |cᵢ| s^{i − d/2}`).
//!
//! Each base-m polynomial is also **rotated**: `f + k·(x − m)` still has
//! `f(m) = n`, changes `c₁, c₀` by `k, −k·m` (so the size barely moves)
//! and changes the number of roots modulo small primes; the rotation with
//! the best score is kept (a one-parameter version of Murphy's root
//! optimisation).
//!
//! If the coefficients share a factor `g > 1`, or `f` is reducible, the
//! factor divides `n = f(m)` directly — the checks come first.
//! Irreducibility is **proven** here by finding a prime `p` with `f`
//! irreducible mod `p`; that same "inert" prime is what the algebraic
//! square root lifts from, so a polynomial without one is rejected.
//!
//! # Scoring
//!
//! Murphy's `α(f) = Σ_{p ≤ 200} (1/(p−1) − n_p·p/(p²−1)) ln p` measures
//! how much more (negative α) or less often `F(a, b)` is divisible by
//! small primes than a random integer (`n_p` = roots of `f` mod `p`,
//! including the projective root when `p | c_d`).  A candidate's score
//! is the estimated log-probability that both norms over a region of
//! the planned area are smooth, `−u ln u` per side with
//! `u = log(norm) / log(bound)` and the algebraic log norm shifted by α.
//! This is a crude stand-in for Murphy's E; real polynomial selection
//! (Kleinjung 2006/2008, CADO's `polyselect` with root optimisation)
//! does far better and is out of scope.
//!
//! References: J. P. Buhler, H. W. Lenstra and C. Pomerance, *Factoring
//! integers with the number field sieve* (1993); B. A. Murphy, *Polynomial
//! selection for the number field sieve integer factorisation algorithm*,
//! PhD thesis, ANU (1999).

use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};

use super::super::arith::{is_prime_u64, primes_up_to};
use super::poly::{fp, IntPoly};

/// A selected polynomial pair `(f(x), x − m)` with `f(m) ≡ 0 (mod n)`.
#[derive(Clone, Debug)]
pub struct PolyChoice {
    /// The algebraic polynomial.
    pub f: IntPoly,
    /// The common root modulo `n` (the rational side is `x − m`).
    pub m: BigUint,
    /// Skewness `s` (sieve `|a| ≲ s·|b|`).
    pub skew: f64,
    /// Murphy's α (natural-log units; negative is good).
    pub alpha: f64,
    /// Estimated log-probability score (higher is better).
    pub score: f64,
    /// A prime modulo which `f` is irreducible.
    pub inert_prime: u64,
}

/// Outcome of a selection: a polynomial, or a factor found on the way.
#[derive(Clone, Debug)]
pub enum Selection {
    /// Usable polynomial.
    Poly(PolyChoice),
    /// A proper factor of `n` found by the structural checks.
    Factor(BigUint),
}

/// Base-`m` expansion with leading coefficient near `lead`; `None` if the
/// expansion degenerates (`m < 2`).
pub fn base_m(n: &BigUint, d: usize, lead: u64) -> Option<(IntPoly, BigUint)> {
    let m = (n / lead).nth_root(d as u32);
    if m < BigUint::from(2u32) {
        return None;
    }
    let mut digits: Vec<BigInt> = Vec::with_capacity(d + 1);
    let mut rest = n.clone();
    for _ in 0..d {
        let (q, r) = rest.div_rem(&m);
        digits.push(BigInt::from(r));
        rest = q;
    }
    digits.push(BigInt::from(rest));
    let mb = BigInt::from(m.clone());
    let half = &mb / 2;
    for i in 0..d {
        if digits[i] > half {
            digits[i] -= &mb;
            digits[i + 1] += 1;
        }
    }
    let f = IntPoly::new(digits);
    debug_assert_eq!(f.eval(&mb), BigInt::from(n.clone()));
    (f.degree() == d).then_some((f, m))
}

/// `ln |c|` of each coefficient (`−∞` for zero).
fn log_coeffs(f: &IntPoly) -> Vec<f64> {
    f.coeffs
        .iter()
        .map(|c| {
            if c.is_zero() {
                f64::NEG_INFINITY
            } else {
                c.abs().to_f64().unwrap_or(f64::MAX).ln()
            }
        })
        .collect()
}

/// `(ln s, ln max_i |cᵢ| s^{i − d/2})` at the skewness `s` minimising the
/// sup-norm proxy, by golden-section search on `ln s`.
fn skew_from_logs(logc: &[f64]) -> (f64, f64) {
    let d = (logc.len() - 1) as f64;
    let obj = |ls: f64| {
        logc.iter()
            .enumerate()
            .map(|(i, &lc)| lc + (i as f64 - d / 2.0) * ls)
            .fold(f64::NEG_INFINITY, f64::max)
    };
    let (mut lo, mut hi) = (0.0f64, 80.0f64);
    for _ in 0..100 {
        let a = lo + (hi - lo) * 0.382;
        let b = lo + (hi - lo) * 0.618;
        if obj(a) <= obj(b) {
            hi = b;
        } else {
            lo = a;
        }
    }
    let ls = (lo + hi) / 2.0;
    (ls, obj(ls))
}

/// Skewness minimising `max_i |cᵢ| s^{i − d/2}`.
pub fn skewness(f: &IntPoly) -> f64 {
    skew_from_logs(&log_coeffs(f)).0.exp()
}

/// `ln` of the sup-norm proxy `max |cᵢ| s^{i − d/2}`.
pub fn log_norm_at_skew(f: &IntPoly, s: f64) -> f64 {
    let d = f.degree() as f64;
    f.coeffs
        .iter()
        .enumerate()
        .filter(|(_, c)| !c.is_zero())
        .map(|(i, c)| c.abs().to_f64().unwrap_or(f64::MAX).ln() + (i as f64 - d / 2.0) * s.ln())
        .fold(f64::NEG_INFINITY, f64::max)
}

/// Murphy's α over primes ≤ `bound` (natural-log units).
pub fn murphy_alpha(f: &IntPoly, bound: u64) -> f64 {
    let lead = f.lead().clone();
    let mut alpha = 0.0;
    for p in primes_up_to(bound) {
        let fp_ = f.mod_p(p);
        let mut np = fp::roots(&fp_, p).len() as f64;
        if (&lead % p).is_zero() {
            np += 1.0; // projective root
        }
        let pf = p as f64;
        alpha += (1.0 / (pf - 1.0) - np * pf / (pf * pf - 1.0)) * pf.ln();
    }
    alpha
}

/// A prime `p ∈ [start, 2³²)` (searching upward) with `f` irreducible mod
/// `p` and `p ∤ lead(f)`; `None` after `tries` primes.
pub fn find_inert_prime(f: &IntPoly, start: u64, tries: usize) -> Option<u64> {
    let d = f.degree();
    let mut p = start | 1;
    let mut seen = 0usize;
    while seen < tries && p < (1u64 << 32) {
        if is_prime_u64(p) {
            seen += 1;
            if !(f.lead() % p).is_zero() && fp::is_irreducible(&f.mod_p(p), d, p) {
                return Some(p);
            }
        }
        p += 2;
    }
    None
}

/// Rough `ln ρ(u) ≈ −u ln u` (Canfield–Erdős–Pomerance).
fn log_rho(u: f64) -> f64 {
    if u <= 1.0 {
        0.0
    } else {
        -u * u.ln()
    }
}

/// Score from log-coefficients: `(score, skew)`.
fn score_logs(
    logc: &[f64],
    ln_m: f64,
    alpha: f64,
    area: f64,
    rat_bound: u64,
    alg_bound: u64,
) -> (f64, f64) {
    let d = (logc.len() - 1) as f64;
    let (ls, ln_norm) = skew_from_logs(logc);
    let ln_alg = ln_norm + d / 2.0 * (area / 2.0).ln() + alpha;
    let ln_rat = ln_m + 0.5 * (area / 2.0).ln() - 0.5 * ls;
    let sc = log_rho(ln_alg / (alg_bound as f64).ln())
        + log_rho(ln_rat.max(1.0) / (rat_bound as f64).ln());
    (sc, ls.exp())
}

/// Score a polynomial for a sieve of `area` cells with factor-base bounds
/// `(rat_bound, alg_bound)`: estimated `ln P(both norms smooth)`.
/// Returns `(score, skewness, α)`.
pub fn score(
    f: &IntPoly,
    m: &BigUint,
    area: f64,
    rat_bound: u64,
    alg_bound: u64,
) -> (f64, f64, f64) {
    let alpha = murphy_alpha(f, ALPHA_BOUND);
    let ln_m = m.to_f64().unwrap_or(f64::MAX).ln();
    let (sc, s) = score_logs(&log_coeffs(f), ln_m, alpha, area, rat_bound, alg_bound);
    (sc, s, alpha)
}

/// Primes used for α.
const ALPHA_BOUND: u64 = 200;

/// α of every rotation `f + (j·x + k)(x − m)`, `|j| ≤ jr`, `|k| ≤ kr`, in one
/// pass: modulo `p`, `x` is a root of the rotated polynomial iff
/// `f(x) + (j x + k)(x − m) ≡ 0`, so each `(x, j mod p)` makes exactly one
/// class of `k mod p` a root (or all of them when `x ≡ m`).  Returns
/// `alpha[j + jr][k + kr]`.
fn rotation_alphas(f: &IntPoly, m: &BigUint, jr: i64, kr: i64) -> Vec<Vec<f64>> {
    let nj = (2 * jr + 1) as usize;
    let nk = (2 * kr + 1) as usize;
    let mut alpha = vec![vec![0.0f64; nk]; nj];
    let lead = f.lead().clone();
    for p in primes_up_to(ALPHA_BOUND) {
        let pi = p as i64;
        let fp_ = f.mod_p(p);
        let mp = super::super::arith::big_mod_u64(m, p);
        let eval = |x: u64| {
            let mut acc = 0u64;
            for &c in fp_.iter().rev() {
                acc = (acc * x + c) % p;
            }
            acc
        };
        // counts[ji][km] = roots mod p of the rotation with j = ji − jr and
        // k ≡ km (mod p).
        let mut counts = vec![0u8; nj * p as usize];
        for x in 0..p {
            let v = eval(x);
            let w = (x + p - mp) % p;
            if w == 0 {
                if v == 0 {
                    counts.iter_mut().for_each(|c| *c += 1);
                }
                continue;
            }
            let winv = super::super::arith::inv_mod(w, p).expect("w ≠ 0");
            let base_k = (p - v * winv % p) % p;
            for ji in 0..nj {
                // v + (j·x + k)·w ≡ 0  ⇔  k ≡ −v/w − j·x.
                let jm = (ji as i64 - jr).rem_euclid(pi) as u64;
                let k = (base_k + p - jm * x % p) % p;
                counts[ji * p as usize + k as usize] += 1;
            }
        }
        let proj = if (&lead % p).is_zero() { 1.0 } else { 0.0 };
        let pf = p as f64;
        let base = 1.0 / (pf - 1.0);
        let w = pf / (pf * pf - 1.0) * pf.ln();
        for (ji, row) in alpha.iter_mut().enumerate() {
            for (ki, a) in row.iter_mut().enumerate() {
                let km = (ki as i64 - kr).rem_euclid(pi) as usize;
                let np = counts[ji * p as usize + km] as f64 + proj;
                *a += base * pf.ln() - np * w;
            }
        }
    }
    alpha
}

/// Structural checks on a candidate `(f, m)` for `n`: content, rational
/// root / reducibility, `gcd(m, n)`.
fn structural_factor(n: &BigUint, f: &IntPoly, m: &BigUint) -> Option<BigUint> {
    let one = BigUint::one();
    let g = m.gcd(n);
    if g > one && &g < n {
        return Some(g);
    }
    let content = f.content().magnitude().gcd(n);
    if content > one && &content < n {
        return Some(content);
    }
    None
}

/// GNFS base-m selection: try leading coefficients `1..=lead_search` for
/// degree `d`, return the best-scoring irreducible candidate.
pub fn select_base_m(
    n: &BigUint,
    d: usize,
    lead_search: u64,
    rotation: i64,
    area: f64,
    rat_bound: u64,
    alg_bound: u64,
) -> Option<Selection> {
    let mut best: Option<PolyChoice> = None;
    for lead in 1..=lead_search.max(1) {
        let Some((f0, m)) = base_m(n, d, lead) else {
            continue;
        };
        if let Some(g) = structural_factor(n, &f0, &m) {
            return Some(Selection::Factor(g));
        }
        // Rotations f + (j·x + k)(x − m) keep f(m) = n and change the
        // root properties; keep the best-scoring one.
        let mb = BigInt::from(m.clone());
        let ln_m = m.to_f64().unwrap_or(f64::MAX).ln();
        let jr = if rotation > 0 && d >= 3 { 2 } else { 0 };
        let alphas = rotation_alphas(&f0, &m, jr, rotation);
        let cf: Vec<f64> = f0
            .coeffs
            .iter()
            .map(|c| c.to_f64().unwrap_or(f64::MAX))
            .collect();
        let mf = m.to_f64().unwrap_or(f64::MAX);
        let mut best_rot: Option<(f64, f64, f64, i64, i64)> = None;
        for j in -jr..=jr {
            for k in -rotation..=rotation {
                let mut c = cf.clone();
                // (j x + k)(x − m) = j x² + (k − j m) x − k m
                c[2] += j as f64;
                c[1] += k as f64 - j as f64 * mf;
                c[0] -= k as f64 * mf;
                let logc: Vec<f64> = c
                    .iter()
                    .map(|&x| {
                        if x == 0.0 {
                            f64::NEG_INFINITY
                        } else {
                            x.abs().ln()
                        }
                    })
                    .collect();
                let alpha = alphas[(j + jr) as usize][(k + rotation) as usize];
                let (sc, s) = score_logs(&logc, ln_m, alpha, area, rat_bound, alg_bound);
                if best_rot.is_none_or(|b| sc > b.0) {
                    best_rot = Some((sc, s, alpha, j, k));
                }
            }
        }
        let cand = best_rot.and_then(|(sc, s, alpha, j, k)| {
            let mut c = f0.coeffs.clone();
            c[2] += j;
            c[1] += BigInt::from(k) - &mb * j;
            c[0] -= &mb * k;
            let f = IntPoly::new(c);
            (f.degree() == d).then_some((sc, s, alpha, f))
        });
        let Some((sc, s, alpha, f)) = cand else {
            continue;
        };
        if let Some(g) = structural_factor(n, &f, &m) {
            return Some(Selection::Factor(g));
        }
        if best.as_ref().is_some_and(|b| b.score >= sc) {
            continue;
        }
        // Irreducibility (and the square-root prime) in one search.
        let Some(inert) = find_inert_prime(&f, 1 << 20, 200) else {
            // Either reducible or with non-cyclic Galois group: a linear
            // factor gives a factor of n directly.
            if let Some(g) = super::poly::find_integer_factor(&f) {
                let v = g.eval(&BigInt::from(m.clone())).magnitude().gcd(n);
                if v > BigUint::one() && &v < n {
                    return Some(Selection::Factor(v));
                }
            }
            continue;
        };
        best = Some(PolyChoice {
            f,
            m,
            skew: s,
            alpha,
            score: sc,
            inert_prime: inert,
        });
    }
    best.map(Selection::Poly)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_m_evaluates_to_n() {
        let n: BigUint = "1000000000000000000000000000000000000000000000000000000021"
            .parse()
            .unwrap();
        for d in 3..=5 {
            for lead in [1u64, 7, 60] {
                let (f, m) = base_m(&n, d, lead).unwrap();
                assert_eq!(f.eval(&BigInt::from(m.clone())), BigInt::from(n.clone()));
                assert_eq!(f.degree(), d);
                // c_{d−1} is small by construction.
                assert!(f.coeffs[d - 1].abs() < BigInt::from(4 * d as u64 * lead + 4));
            }
        }
    }

    #[test]
    fn alpha_of_x3_minus_2() {
        // Sanity: a polynomial with many small roots has negative α.
        let good = IntPoly::from_i64(&[0, -6, 11, -6, 1]); // many roots mod small p
        let plain = IntPoly::from_i64(&[3, 0, 0, 0, 1]);
        assert!(murphy_alpha(&good, 100) < murphy_alpha(&plain, 100));
    }

    #[test]
    fn skewness_balances_extremes() {
        // x³ + 10⁸ has optimal skew (10⁸)^{1/3}.
        let f = IntPoly::from_i64(&[100_000_000, 0, 0, 1]);
        let s = skewness(&f);
        assert!((s / 464.1588).ln().abs() < 0.01, "s = {s}");
    }
}
