//! **Pollard's rho** for integer factorisation, with **Brent's** cycle
//! finding and batched gcds.
//!
//! Iterate the pseudo-random map `x ↦ x² + c (mod n)`.  Modulo an unknown
//! prime `p | n` the sequence is eventually periodic with tail + cycle of
//! expected length `√(πp/2)` (birthday paradox), and a collision
//! `x_i ≡ x_j (mod p)` shows up as `1 < gcd(x_i − x_j, n)`.  Expected cost:
//! `O(√p)` multiplications mod `n` — so rho is the right tool for factors
//! up to ~12–15 digits and useless much beyond 20 digits, where ECM takes
//! over.
//!
//! Brent (1980) replaces Floyd's two-pointer walk by powers-of-two
//! checkpoints (≈ 24% fewer multiplications) and multiplies `m` successive
//! differences together before each gcd.  If a batch overshoots (the gcd
//! is `n`), the batch is replayed one step at a time.
//!
//! References: J. M. Pollard, *A Monte Carlo method for factorization*,
//! BIT 15 (1975); R. P. Brent, *An improved Monte Carlo factorization
//! algorithm*, BIT 20 (1980).

use num_bigint::BigUint;
use num_integer::Integer;
use num_traits::{One, Zero};
use serde::Serialize;
use std::time::Instant;

use super::serde_big;

/// Options for [`rho`].
#[derive(Clone, Debug, Serialize)]
pub struct RhoParams {
    /// Maximum iterations of `x ↦ x² + c` per constant `c`.
    pub max_iterations: u64,
    /// How many constants `c = 1, 2, …` to try before giving up.
    pub attempts: u32,
    /// Differences multiplied together per gcd.
    pub batch: u64,
}

impl Default for RhoParams {
    fn default() -> Self {
        RhoParams {
            max_iterations: 1 << 22,
            attempts: 8,
            batch: 128,
        }
    }
}

/// Outcome of [`rho`].
#[derive(Clone, Debug, Serialize)]
pub struct RhoResult {
    /// The number that was attacked.
    #[serde(with = "serde_big::biguint")]
    pub n: BigUint,
    /// A non-trivial factor, if one was found.
    #[serde(with = "serde_big::opt_biguint")]
    pub factor: Option<BigUint>,
    /// `n / factor`.
    #[serde(with = "serde_big::opt_biguint")]
    pub cofactor: Option<BigUint>,
    /// `factor · cofactor == n` was checked.
    pub verified: bool,
    /// Total map iterations across all attempts.
    pub iterations: u64,
    /// Constant `c` of the successful walk.
    pub c: Option<u64>,
    /// Wall-clock seconds.
    pub seconds: f64,
}

/// One Brent walk with constant `c` over `u64` arithmetic (`n < 2⁶³`).
fn brent_u64(n: u64, c: u64, max_iter: u64, batch: u64, iters: &mut u64) -> Option<u64> {
    let f = |x: u64| ((x as u128 * x as u128 + c as u128) % n as u128) as u64;
    let (mut y, mut r, mut q) = (2u64, 1u64, 1u64);
    let (mut x, mut ys) = (y, y);
    let mut g = 1u64;
    while g == 1 {
        x = y;
        for _ in 0..r {
            y = f(y);
        }
        let mut k = 0;
        while k < r && g == 1 {
            ys = y;
            for _ in 0..batch.min(r - k) {
                y = f(y);
                q = (q as u128 * x.abs_diff(y) as u128 % n as u128) as u64;
            }
            g = q.gcd(&n);
            k += batch;
        }
        *iters += r;
        r *= 2;
        if *iters > max_iter {
            break;
        }
    }
    if g == n {
        loop {
            ys = f(ys);
            g = x.abs_diff(ys).gcd(&n);
            if g > 1 {
                break;
            }
        }
    }
    (g > 1 && g < n).then_some(g)
}

/// One Brent walk with constant `c` over big integers.
fn brent_big(n: &BigUint, c: u64, max_iter: u64, batch: u64, iters: &mut u64) -> Option<BigUint> {
    let cb = BigUint::from(c);
    let f = |x: &BigUint| (x * x + &cb) % n;
    let diff = |a: &BigUint, b: &BigUint| if a > b { a - b } else { b - a };
    let mut y = BigUint::from(2u32);
    let (mut r, mut q) = (1u64, BigUint::one());
    let (mut x, mut ys) = (y.clone(), y.clone());
    let mut g = BigUint::one();
    while g.is_one() {
        x = y.clone();
        for _ in 0..r {
            y = f(&y);
        }
        let mut k = 0;
        while k < r && g.is_one() {
            ys = y.clone();
            for _ in 0..batch.min(r - k) {
                y = f(&y);
                q = q * diff(&x, &y) % n;
            }
            g = q.gcd(n);
            k += batch;
        }
        *iters += r;
        r *= 2;
        if *iters > max_iter {
            break;
        }
    }
    if &g == n {
        loop {
            ys = f(&ys);
            g = diff(&x, &ys).gcd(n);
            if !g.is_one() {
                break;
            }
        }
    }
    (!g.is_one() && &g != n).then_some(g)
}

/// Find a non-trivial factor of composite `n` with Pollard–Brent rho.
/// `n` should be odd and composite; even `n` returns the factor 2.
pub fn rho(n: &BigUint, params: &RhoParams) -> RhoResult {
    let t0 = Instant::now();
    let mut result = RhoResult {
        n: n.clone(),
        factor: None,
        cofactor: None,
        verified: false,
        iterations: 0,
        c: None,
        seconds: 0.0,
    };
    let mut found: Option<(BigUint, u64)> = None;
    if n <= &BigUint::from(3u32) {
        // Nothing to split.
    } else if n.is_even() {
        found = Some((BigUint::from(2u32), 0));
    } else {
        let small = n.bits() <= 63;
        let nu = small.then(|| n.iter_u64_digits().next().unwrap_or(0));
        for c in 1..=params.attempts as u64 {
            let mut it = 0u64;
            let g = if let Some(nu) = nu {
                brent_u64(nu, c, params.max_iterations, params.batch, &mut it).map(BigUint::from)
            } else {
                brent_big(n, c, params.max_iterations, params.batch, &mut it)
            };
            result.iterations += it;
            if let Some(g) = g {
                found = Some((g, c));
                break;
            }
        }
    }
    if let Some((g, c)) = found {
        let (q, r) = n.div_rem(&g);
        if r.is_zero() && &(&g * &q) == n {
            result.verified = true;
            result.factor = Some(g);
            result.cofactor = Some(q);
            result.c = Some(c);
        }
    }
    result.seconds = t0.elapsed().as_secs_f64();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rho_splits_word_sized_semiprime() {
        let n = BigUint::from(1_000_003u64 * 998_244_353u64);
        let r = rho(&n, &RhoParams::default());
        assert!(r.verified);
        let f = r.factor.unwrap();
        assert!(f == BigUint::from(1_000_003u64) || f == BigUint::from(998_244_353u64));
    }

    #[test]
    fn rho_splits_big_integer_with_small_factor() {
        // 2^89 − 1 (prime) times 10^9 + 7.
        let m89 = (BigUint::one() << 89) - 1u32;
        let n = &m89 * 1_000_000_007u64;
        let r = rho(&n, &RhoParams::default());
        assert!(r.verified);
        assert_eq!(r.factor.unwrap(), BigUint::from(1_000_000_007u64));
    }
}
