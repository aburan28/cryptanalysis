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

/// Montgomery arithmetic modulo an odd `n < 2⁶³`, for [`brent_u64`].
struct Mont {
    n: u64,
    /// `n⁻¹ mod 2⁶⁴`.
    ninv: u64,
    /// `2⁶⁴ mod n`.
    r1: u64,
}

impl Mont {
    fn new(n: u64) -> Self {
        debug_assert!(n % 2 == 1 && n < 1 << 63);
        let mut ninv = n; // correct to 3 bits: n·n ≡ 1 (mod 8)
        for _ in 0..5 {
            ninv = ninv.wrapping_mul(2u64.wrapping_sub(n.wrapping_mul(ninv)));
        }
        let r1 = ((1u128 << 64) % n as u128) as u64;
        Mont { n, ninv, r1 }
    }

    /// `t·2⁻⁶⁴ mod n` for `t < n·2⁶⁴` (subtraction form).
    #[inline]
    fn redc(&self, t: u128) -> u64 {
        let u = (t as u64).wrapping_mul(self.ninv);
        let hi = (t >> 64) as u64;
        let mh = ((u as u128 * self.n as u128) >> 64) as u64;
        let (r, borrow) = hi.overflowing_sub(mh);
        if borrow {
            r.wrapping_add(self.n)
        } else {
            r
        }
    }

    #[inline]
    fn mul(&self, a: u64, b: u64) -> u64 {
        self.redc(a as u128 * b as u128)
    }

    #[inline]
    fn to(&self, a: u64) -> u64 {
        ((a as u128 * self.r1 as u128) % self.n as u128) as u64
    }
}

/// One Brent walk with constant `c` over `u64` arithmetic (`n < 2⁶³`,
/// odd).
///
/// The walk runs in Montgomery form: `x ↦ x² + c` is `X ↦ REDC(X²) + cR`
/// for `X = xR`, so no step divides.  Every quantity the walk inspects is
/// a gcd with `n`, and `R` is a unit mod `n`: `|X − Y| ≡ ±(x − y)R`, the
/// batched product (started at the plain `1`) is `±∏(x − y)`, and the
/// gcds, iteration counts and returned factor are the ones the plain walk
/// finds.
fn brent_u64(n: u64, c: u64, max_iter: u64, batch: u64, iters: &mut u64) -> Option<u64> {
    let m = Mont::new(n);
    let cr = m.to(c);
    let f = |x: u64| {
        let s = m.mul(x, x) + cr; // both < n < 2⁶³: no overflow
        if s >= n {
            s - n
        } else {
            s
        }
    };
    let (mut y, mut r, mut q) = (m.to(2), 1u64, 1u64);
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
                q = m.mul(q, x.abs_diff(y));
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
/// `a · b` as a 256-bit `(high, low)` pair.
#[inline]
fn mul_wide(a: u128, b: u128) -> (u128, u128) {
    let (a0, a1) = (a as u64 as u128, a >> 64);
    let (b0, b1) = (b as u64 as u128, b >> 64);
    let (p00, p01, p10, p11) = (a0 * b0, a0 * b1, a1 * b0, a1 * b1);
    let mid = (p00 >> 64) + (p01 as u64 as u128) + (p10 as u64 as u128);
    let lo = (p00 as u64 as u128) | (mid << 64);
    let hi = p11 + (p01 >> 64) + (p10 >> 64) + (mid >> 64);
    (hi, lo)
}

/// Montgomery arithmetic modulo an odd `n < 2¹²⁷` with `R = 2¹²⁸`, for
/// [`brent_u128`].
struct Mont128 {
    n: u128,
    /// `n⁻¹ mod 2¹²⁸`.
    ninv: u128,
    /// `R² mod n`.
    r2: u128,
}

impl Mont128 {
    fn new(n: u128) -> Self {
        debug_assert!(n % 2 == 1 && n < 1 << 127);
        let mut ninv = n; // correct to 3 bits: n·n ≡ 1 (mod 8)
        for _ in 0..6 {
            ninv = ninv.wrapping_mul(2u128.wrapping_sub(n.wrapping_mul(ninv)));
        }
        // R mod n, then doubled 128 times: R² mod n (sums stay below 2¹²⁸)
        let mut r2 = (u128::MAX % n + 1) % n;
        for _ in 0..128 {
            r2 <<= 1;
            if r2 >= n {
                r2 -= n;
            }
        }
        Mont128 { n, ninv, r2 }
    }

    /// `a·b·R⁻¹ mod n` for `a, b < n` (subtraction-form REDC: the low
    /// halves of `a·b` and `u·n` agree, so the quotient is exact).
    #[inline]
    fn mul(&self, a: u128, b: u128) -> u128 {
        let (hi, lo) = mul_wide(a, b);
        let u = lo.wrapping_mul(self.ninv);
        let (mh, _) = mul_wide(u, self.n);
        let (r, borrow) = hi.overflowing_sub(mh);
        if borrow {
            r.wrapping_add(self.n)
        } else {
            r
        }
    }

    fn to(&self, a: u128) -> u128 {
        self.mul(a % self.n, self.r2)
    }
}

/// [`brent_big`] for odd `n < 2¹²⁷` in fixed-width Montgomery arithmetic,
/// with the same argument as [`brent_u64`]: every quantity the walk
/// inspects is a gcd with `n`, so the gcds, iteration counts and factor
/// are the big-integer walk's, without its divisions and allocations.
fn brent_u128(n: u128, c: u64, max_iter: u64, batch: u64, iters: &mut u64) -> Option<u128> {
    let m = Mont128::new(n);
    let cr = m.to(c as u128);
    let f = |x: u128| {
        let s = m.mul(x, x) + cr; // both < n < 2¹²⁷: no overflow
        if s >= n {
            s - n
        } else {
            s
        }
    };
    let (mut y, mut r, mut q) = (m.to(2), 1u64, 1u128);
    let (mut x, mut ys) = (y, y);
    let mut g = 1u128;
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
                q = m.mul(q, x.abs_diff(y));
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
        let wide = (!small && n.bits() <= 127).then(|| {
            let mut d = n.iter_u64_digits();
            let lo = d.next().unwrap_or(0) as u128;
            lo | (d.next().unwrap_or(0) as u128) << 64
        });
        for c in 1..=params.attempts as u64 {
            let mut it = 0u64;
            let g = if let Some(nu) = nu {
                brent_u64(nu, c, params.max_iterations, params.batch, &mut it).map(BigUint::from)
            } else if let Some(nw) = wide {
                brent_u128(nw, c, params.max_iterations, params.batch, &mut it).map(BigUint::from)
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
    /// The plain-arithmetic walk `brent_u64` replaced.
    fn brent_u64_plain(n: u64, c: u64, max_iter: u64, batch: u64, iters: &mut u64) -> Option<u64> {
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

    /// The 128-bit Montgomery walk finds the same factor after the same
    /// number of iterations as the big-integer walk, on odd n from 64 to
    /// 127 bits (semiprimes with factors of assorted sizes, and random
    /// odd n), for several constants and batch sizes.
    #[test]
    fn wide_montgomery_walk_matches_the_big_integer_walk() {
        let mut state = 0x243F_6A88_85A3_08D3u64;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let mut ns: Vec<u128> = Vec::new();
        for bits in [64u32, 65, 80, 100, 120, 126, 127] {
            for _ in 0..6 {
                let hi = (next() as u128) << 64 | next() as u128;
                let n = (hi >> (128 - bits)) | 1 | (1u128 << (bits - 1));
                ns.push(n);
            }
        }
        for split in [20u32, 30, 40] {
            for _ in 0..4 {
                let p = (next() >> (64 - split)) | 1 | (1 << (split - 1));
                let q = (next() >> (64 - (100 - split))) | 1 | (1 << (100 - split - 1));
                ns.push(p as u128 * q as u128);
            }
        }
        for &n in &ns {
            for (c, batch) in [(1u64, 128u64), (5, 1), (9, 33)] {
                let (mut a, mut b) = (0, 0);
                let got = brent_u128(n, c, 60_000, batch, &mut a).map(BigUint::from);
                let want = brent_big(&BigUint::from(n), c, 60_000, batch, &mut b);
                assert_eq!((got, a), (want, b), "n={n} c={c} batch={batch}");
            }
        }
    }

    /// The Montgomery walk finds the same factor after the same number of
    /// iterations as the plain one, on odd composites from 15 to just
    /// below 2⁶³, for several constants and batch sizes.
    #[test]
    fn montgomery_walk_matches_the_plain_walk() {
        let mut state = 0x9E37_79B9_7F4A_7C15u64;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let mut ns: Vec<u64> = (15..3000).step_by(2).collect();
        ns.extend((0..300).map(|_| (next() >> 1) | 1));
        ns.extend((0..100).map(|_| ((next() >> 33) | 1) * ((next() >> 34) | 1)));
        ns.push((1u64 << 63) - 25);
        for &n in &ns {
            if n < 5 {
                continue;
            }
            for (c, batch) in [(1u64, 128u64), (3, 1), (7, 17)] {
                let (mut a, mut b) = (0, 0);
                let got = brent_u64(n, c, 200_000, batch, &mut a);
                let want = brent_u64_plain(n, c, 200_000, batch, &mut b);
                assert_eq!((got, a), (want, b), "n={n} c={c} batch={batch}");
            }
        }
    }

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
