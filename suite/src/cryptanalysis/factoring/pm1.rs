//! **Pollard's p − 1** and **Williams' p + 1** factoring methods.
//!
//! # p − 1 (Pollard 1974)
//!
//! If a prime `p | n` has `p − 1` **B₁-smooth** (every prime-power
//! divisor ≤ B₁), then with `E = ∏_{q ≤ B₁} q^{⌊log_q B₁⌋}` we have
//! `(p − 1) | E`, so `a^E ≡ 1 (mod p)` by Fermat and `p | gcd(a^E − 1, n)`.
//! **Stage 1** computes `a^E`; **stage 2** allows one extra prime
//! `q ∈ (B₁, B₂]` in `p − 1` by accumulating `∏ (a^{Eq} − 1)` over the
//! primes `q`, stepping between consecutive primes with a table of
//! `a^{E·δ}` for the (small, even) prime gaps `δ` — one multiplication per
//! prime.  Cost: `π(B₁)·log B₁` squarings plus ~2 multiplications per
//! stage-2 prime.
//!
//! # p + 1 (Williams 1982)
//!
//! The same idea in the norm-1 torus of `F_{p²}`: with Lucas sequences
//! `V_k(A)` (`V₀ = 2`, `V₁ = A`, `V_{2k} = V_k² − 2`,
//! `V_{j+k} = V_j V_k − V_{j−k}`), `p | gcd(V_E(A) − 2, n)` when `p + 1 | E`
//! **and** `(A² − 4 / p) = −1`; since the Legendre symbol is unknown, a few
//! seeds `A` are tried (half of them give the `p + 1` group, the others
//! the `p − 1` one).  Stage 1 only here.
//!
//! These are *special-purpose*: they find `p` only when `p ∓ 1` is smooth,
//! which is exactly why RSA key-generation standards once demanded
//! "strong primes".  For random primes ECM supersedes both.
//!
//! References: J. M. Pollard, *Theorems on factorization and primality
//! testing*, Proc. Camb. Phil. Soc. 76 (1974); H. C. Williams, *A p + 1
//! method of factoring*, Math. Comp. 39 (1982); P. L. Montgomery,
//! *Speeding the Pollard and elliptic curve methods*, Math. Comp. 48
//! (1987).

use num_bigint::BigUint;
use num_integer::Integer;
use num_traits::{One, Zero};
use serde::Serialize;
use std::time::Instant;

use super::arith::primes_up_to;
use super::serde_big;

/// Options for [`pm1`].
#[derive(Clone, Debug, Serialize)]
pub struct Pm1Params {
    /// Stage-1 smoothness bound.
    pub b1: u64,
    /// Stage-2 bound (`≤ b1` disables stage 2).
    pub b2: u64,
    /// Base `a` of the exponentiation.
    pub base: u64,
}

impl Default for Pm1Params {
    fn default() -> Self {
        Pm1Params {
            b1: 100_000,
            b2: 5_000_000,
            base: 3,
        }
    }
}

/// Outcome of [`pm1`] or [`pp1`].
#[derive(Clone, Debug, Serialize)]
pub struct Pm1Result {
    /// The number that was attacked.
    #[serde(with = "serde_big::biguint")]
    pub n: BigUint,
    /// `"p-1"` or `"p+1"`.
    pub method: &'static str,
    /// A non-trivial factor, if one was found.
    #[serde(with = "serde_big::opt_biguint")]
    pub factor: Option<BigUint>,
    /// `n / factor`.
    #[serde(with = "serde_big::opt_biguint")]
    pub cofactor: Option<BigUint>,
    /// `factor · cofactor == n` was checked.
    pub verified: bool,
    /// Stage that produced the factor (1 or 2), 0 if none.
    pub stage: u8,
    /// Stage-1 primes processed.
    pub stage1_primes: usize,
    /// Stage-2 primes processed.
    pub stage2_primes: usize,
    /// Wall-clock seconds.
    pub seconds: f64,
}

impl Pm1Result {
    fn new(n: &BigUint, method: &'static str) -> Self {
        Pm1Result {
            n: n.clone(),
            method,
            factor: None,
            cofactor: None,
            verified: false,
            stage: 0,
            stage1_primes: 0,
            stage2_primes: 0,
            seconds: 0.0,
        }
    }

    fn accept(&mut self, g: BigUint, stage: u8) -> bool {
        if g.is_one() || g == self.n || g.is_zero() {
            return false;
        }
        let (q, r) = self.n.div_rem(&g);
        if r.is_zero() && &g * &q == self.n {
            self.factor = Some(g);
            self.cofactor = Some(q);
            self.verified = true;
            self.stage = stage;
            true
        } else {
            false
        }
    }
}

fn prime_power_below(p: u64, bound: u64) -> u64 {
    let mut q = p;
    while let Some(next) = q.checked_mul(p) {
        if next > bound {
            break;
        }
        q = next;
    }
    q
}

fn sub1(x: &BigUint, n: &BigUint) -> BigUint {
    if x.is_zero() {
        n - 1u32
    } else {
        x - 1u32
    }
}

/// Pollard p − 1 with a prime-by-prime stage 2.
pub fn pm1(n: &BigUint, params: &Pm1Params) -> Pm1Result {
    let t0 = Instant::now();
    let mut res = Pm1Result::new(n, "p-1");
    if n <= &BigUint::from(3u32) {
        return res;
    }
    let primes = primes_up_to(params.b1.max(params.b2));
    let s1: Vec<u64> = primes
        .iter()
        .copied()
        .take_while(|&p| p <= params.b1)
        .collect();
    let mut a = BigUint::from(params.base) % n;
    // Stage 1 in batches of 64 primes, with a replay if a batch overshoots.
    for chunk in s1.chunks(64) {
        let saved = a.clone();
        for &p in chunk {
            a = a.modpow(&BigUint::from(prime_power_below(p, params.b1)), n);
        }
        res.stage1_primes += chunk.len();
        let g = sub1(&a, n).gcd(n);
        if g.is_one() {
            continue;
        }
        if &g == n {
            // Every prime of n appeared in this batch: replay one by one.
            let mut b = saved;
            for &p in chunk {
                let pk = prime_power_below(p, params.b1);
                for _ in 0..pk.ilog(p) {
                    b = b.modpow(&BigUint::from(p), n);
                    let g = sub1(&b, n).gcd(n);
                    if res.accept(g.clone(), 1) {
                        res.seconds = t0.elapsed().as_secs_f64();
                        return res;
                    }
                    if &g == n {
                        break;
                    }
                }
            }
            res.seconds = t0.elapsed().as_secs_f64();
            return res;
        }
        res.accept(g, 1);
        res.seconds = t0.elapsed().as_secs_f64();
        return res;
    }
    // Stage 2: primes q in (B1, B2].
    let s2: Vec<u64> = primes.iter().copied().filter(|&p| p > params.b1).collect();
    if !s2.is_empty() && params.b2 > params.b1 {
        let max_gap = s2.windows(2).map(|w| w[1] - w[0]).max().unwrap_or(2);
        let a2 = &a * &a % n;
        let mut table = vec![BigUint::one(); (max_gap / 2 + 1) as usize];
        for i in 1..table.len() {
            table[i] = &table[i - 1] * &a2 % n;
        }
        let mut x = a.modpow(&BigUint::from(s2[0]), n);
        let mut acc = BigUint::one();
        let mut last_ok = x.clone();
        let mut last_ok_idx = 0usize;
        for i in 0..s2.len() {
            acc = acc * sub1(&x, n) % n;
            res.stage2_primes += 1;
            if i + 1 < s2.len() {
                x = &x * &table[((s2[i + 1] - s2[i]) / 2) as usize] % n;
            }
            if (i + 1).is_multiple_of(256) || i + 1 == s2.len() {
                let g = acc.gcd(n);
                if g.is_one() {
                    last_ok = x.clone();
                    last_ok_idx = i + 1;
                    continue;
                }
                if &g == n {
                    // Replay the block one prime at a time.
                    let mut y = last_ok.clone();
                    for j in last_ok_idx..=i {
                        let g = sub1(&y, n).gcd(n);
                        if res.accept(g, 2) {
                            break;
                        }
                        if j + 1 < s2.len() {
                            y = &y * &table[((s2[j + 1] - s2[j]) / 2) as usize] % n;
                        }
                    }
                } else {
                    res.accept(g, 2);
                }
                break;
            }
        }
    }
    res.seconds = t0.elapsed().as_secs_f64();
    res
}

/// Options for [`pp1`].
#[derive(Clone, Debug, Serialize)]
pub struct Pp1Params {
    /// Stage-1 smoothness bound.
    pub b1: u64,
    /// Number of seeds `A` to try.
    pub seeds: u32,
}

impl Default for Pp1Params {
    fn default() -> Self {
        Pp1Params {
            b1: 100_000,
            seeds: 3,
        }
    }
}

/// `V_k(v)` modulo `n` by the Montgomery Lucas ladder, where `v = V₁`.
fn lucas_v(v: &BigUint, k: u64, n: &BigUint) -> BigUint {
    if k == 0 {
        return BigUint::from(2u32) % n;
    }
    let two = BigUint::from(2u32);
    let sub = |a: BigUint, b: &BigUint| (a + n - b % n) % n;
    let mut x = v.clone();
    let mut y = sub(v * v, &two);
    for i in (0..k.ilog2()).rev() {
        if (k >> i) & 1 == 1 {
            x = sub(&x * &y, v);
            y = sub(&y * &y, &two);
        } else {
            y = sub(&x * &y, v);
            x = sub(&x * &x, &two);
        }
    }
    x
}

/// Williams p + 1, stage 1, with seeds `A = 2/7, 6/5, 3, 4, …` (mod `n`).
pub fn pp1(n: &BigUint, params: &Pp1Params) -> Pm1Result {
    let t0 = Instant::now();
    let mut res = Pm1Result::new(n, "p+1");
    if n <= &BigUint::from(3u32) || n.is_even() {
        return res;
    }
    let primes = primes_up_to(params.b1);
    let inv = |x: u64| crate::utils::mod_inverse(&BigUint::from(x), n);
    let mut seeds: Vec<BigUint> = Vec::new();
    if let Some(i7) = inv(7) {
        seeds.push(BigUint::from(2u32) * i7 % n);
    }
    if let Some(i5) = inv(5) {
        seeds.push(BigUint::from(6u32) * i5 % n);
    }
    for k in 3u32..20 {
        seeds.push(BigUint::from(k) % n);
    }
    let two = BigUint::from(2u32);
    for a0 in seeds.into_iter().take(params.seeds as usize) {
        let mut v = a0;
        for chunk in primes.chunks(128) {
            for &p in chunk {
                v = lucas_v(&v, prime_power_below(p, params.b1), n);
            }
            res.stage1_primes += chunk.len();
            let g = ((&v + n - &two) % n).gcd(n);
            if &g == n {
                break;
            }
            if res.accept(g, 1) {
                res.seconds = t0.elapsed().as_secs_f64();
                return res;
            }
        }
    }
    res.seconds = t0.elapsed().as_secs_f64();
    res
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pm1_stage1_finds_smooth_p_minus_1() {
        // p − 1 = 2·5·7·11·13·17·19·23·29 is 100-smooth; q = 10¹⁸ + 3 has
        // the 11-digit prime 52445056723 in q − 1.
        let p = BigUint::from(2_156_564_411u64);
        let q = BigUint::from(1_000_000_000_000_000_003u64);
        let n = &p * &q;
        let r = pm1(
            &n,
            &Pm1Params {
                b1: 100,
                b2: 100,
                base: 3,
            },
        );
        assert!(r.verified, "{r:?}");
        assert_eq!(r.factor.unwrap(), p);
        assert_eq!(r.stage, 1);
    }

    #[test]
    fn pm1_stage2_catches_one_large_prime() {
        // p − 1 = 2² · 3 · 5 · 7 · 104729 (104729 is prime > B1).
        let p = BigUint::from(4u64 * 3 * 5 * 7 * 104_729 + 1);
        assert!(super::super::arith::is_probable_prime(&p));
        let q = BigUint::from(1_000_000_000_000_000_003u64);
        let n = &p * &q;
        let r = pm1(
            &n,
            &Pm1Params {
                b1: 1000,
                b2: 200_000,
                base: 3,
            },
        );
        assert!(r.verified, "{r:?}");
        assert_eq!(r.stage, 2);
        assert_eq!(r.factor.unwrap(), p);
    }

    #[test]
    fn pp1_finds_smooth_p_plus_1() {
        // p + 1 = 2·3²·5·7·11·13·17·19 is smooth, p − 1 = 4·7274767 is not.
        let p = BigUint::from(29_099_069u64);
        let q = BigUint::from(1_000_000_000_000_000_003u64);
        let n = &p * &q;
        let r = pp1(&n, &Pp1Params { b1: 100, seeds: 6 });
        assert!(r.verified, "{r:?}");
        assert_eq!(r.factor.unwrap(), p);
    }
}
