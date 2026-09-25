//! Number theory and affine prime-field curve arithmetic shared by the
//! weak-curve attacks.
//!
//! - [`is_probable_prime`] — trial division by small primes, then
//!   Miller–Rabin with the first twelve prime bases (deterministic below
//!   `3.3·10²⁴`) plus eight further bases drawn from a generator seeded
//!   by `n` itself, so the answer is reproducible.
//! - [`factor`] / [`factor_order`] — trial division, a primality test on
//!   every cofactor, and Pollard–Brent rho (Brent 1980) with batched
//!   gcds for what is left.  Rho finds a prime factor `q` in about `√q`
//!   iterations, so orders whose second-largest prime factor is below
//!   roughly `2⁴⁰` factor in about a second; the iteration budget is
//!   explicit and an unsplit composite is reported, never guessed.
//! - [`sqrt_mod_prime`] — Tonelli–Shanks.
//! - [`Ec`] / [`AffinePoint`] — affine short-Weierstrass arithmetic over
//!   `F_p` on bare `BigUint`s, with Montgomery's simultaneous-inversion
//!   trick for the batched additions Pollard rho needs.  The crate's
//!   [`crate::ecc::point::Point`] carries its modulus in every
//!   coordinate and inverts by a Fermat ladder, which is correct but
//!   several times slower per step; results are always re-verified
//!   with the crate type before they are reported.
//!
//! References: R. P. Brent, *An improved Monte Carlo factorization
//! algorithm*, BIT 20 (1980); H. Cohen, *A Course in Computational
//! Algebraic Number Theory*, GTM 138, §1.5 (square roots), §8.2 (rho).

use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

/// Primes below 256, used for trial division before Miller–Rabin.
const SMALL_PRIMES: [u32; 54] = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
    101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193,
    197, 199, 211, 223, 227, 229, 233, 239, 241, 251,
];

/// One Miller–Rabin round: `true` when `a` is *not* a witness to the
/// compositeness of `n` (`n − 1 = d·2^s`, `d` odd).
fn miller_rabin_round(n: &BigUint, n_minus_1: &BigUint, d: &BigUint, s: u64, a: &BigUint) -> bool {
    let mut x = a.modpow(d, n);
    if x.is_one() || &x == n_minus_1 {
        return true;
    }
    for _ in 1..s {
        x = (&x * &x) % n;
        if &x == n_minus_1 {
            return true;
        }
        if x.is_one() {
            return false;
        }
    }
    false
}

/// Probable-prime test.
///
/// Deterministic for `n < 3.3·10²⁴` (Miller–Rabin with the prime bases
/// up to 37, Sorenson–Webster 2017); above that, eight additional bases
/// drawn reproducibly from `n` bound the error by `4⁻²⁰` for any fixed
/// composite.
pub fn is_probable_prime(n: &BigUint) -> bool {
    if n < &BigUint::from(2u32) {
        return false;
    }
    for &sp in SMALL_PRIMES.iter() {
        let sp = BigUint::from(sp);
        if n == &sp {
            return true;
        }
        if (n % &sp).is_zero() {
            return false;
        }
    }
    if n < &BigUint::from(65_536u32) {
        // No prime factor below 256 and n < 256².
        return true;
    }
    let n_minus_1 = n - 1u32;
    let s = n_minus_1.trailing_zeros().unwrap_or(0);
    let d = &n_minus_1 >> s;
    for &a in SMALL_PRIMES[..12].iter() {
        if !miller_rabin_round(n, &n_minus_1, &d, s, &BigUint::from(a)) {
            return false;
        }
    }
    if n.bits() > 81 {
        let seed = n.iter_u64_digits().next().unwrap_or(0) ^ 0x9e37_79b9_7f4a_7c15;
        let mut rng = StdRng::seed_from_u64(seed);
        let two = BigUint::from(2u32);
        for _ in 0..8 {
            let a = rng.gen_biguint_range(&two, &n_minus_1);
            if !miller_rabin_round(n, &n_minus_1, &d, s, &a) {
                return false;
            }
        }
    }
    true
}

/// Budget for [`factor`].
#[derive(Clone, Debug, Serialize)]
pub struct FactorOptions {
    /// Trial-divide by every integer candidate below this bound.
    pub trial_bound: u32,
    /// Total Pollard–Brent iterations across all composite cofactors.
    /// A prime factor `q` needs about `√q` of them.
    pub rho_iterations: u64,
}

impl Default for FactorOptions {
    fn default() -> Self {
        FactorOptions {
            trial_bound: 1 << 16,
            // Finds prime factors up to roughly 2⁵⁰ (√q ≈ 2²⁵ iterations
            // each) within a minute or so; raise it for harder orders.
            rho_iterations: 1 << 28,
        }
    }
}

/// Outcome of [`factor`].
#[derive(Clone, Debug, Serialize)]
pub struct Factorization {
    /// Prime factors (each passed [`is_probable_prime`]) with
    /// multiplicities, sorted by prime.
    #[serde(serialize_with = "super::ser::big_pairs")]
    pub factors: Vec<(BigUint, u32)>,
    /// Composite cofactors the rho budget could not split.  Empty when
    /// the factorisation is complete.
    #[serde(serialize_with = "super::ser::big_vec")]
    pub unfactored: Vec<BigUint>,
    /// Pollard–Brent iterations spent.
    pub rho_iterations: u64,
}

impl Factorization {
    /// Whether every factor is a (probable) prime.
    pub fn is_complete(&self) -> bool {
        self.unfactored.is_empty()
    }

    /// The largest prime factor found (not counting unfactored parts).
    pub fn largest_prime(&self) -> Option<&BigUint> {
        self.factors.iter().map(|(q, _)| q).max()
    }
}

fn push_factor(out: &mut Vec<(BigUint, u32)>, q: BigUint, e: u32) {
    if let Some(entry) = out.iter_mut().find(|(r, _)| *r == q) {
        entry.1 += e;
    } else {
        out.push((q, e));
    }
}

/// Factor `n` by trial division, primality testing and Pollard–Brent
/// rho, within the budget in `opts`.
pub fn factor(n: &BigUint, opts: &FactorOptions) -> Factorization {
    let mut factors: Vec<(BigUint, u32)> = Vec::new();
    let mut unfactored = Vec::new();
    let mut spent = 0u64;
    if n.is_zero() || n.is_one() {
        return Factorization {
            factors,
            unfactored,
            rho_iterations: 0,
        };
    }
    let mut m = n.clone();
    // Trial division, stopping as soon as the cofactor is 1 or prime.
    let mut cand = 2u32;
    while cand < opts.trial_bound {
        if m.is_one() {
            break;
        }
        let c = BigUint::from(cand);
        if &c * &c > m {
            break;
        }
        let mut e = 0u32;
        while (&m % &c).is_zero() {
            m /= &c;
            e += 1;
        }
        if e > 0 {
            factors.push((c, e));
        }
        // Test the cofactor for primality every so often so a large
        // prime cofactor ends trial division early.
        if cand % 1024 == 1023 && is_probable_prime(&m) {
            break;
        }
        cand += if cand == 2 { 1 } else { 2 };
    }
    let mut stack = if m.is_one() { Vec::new() } else { vec![m] };
    let mut rng = StdRng::seed_from_u64(0x5eed_fac7);
    while let Some(c) = stack.pop() {
        if is_probable_prime(&c) {
            push_factor(&mut factors, c, 1);
            continue;
        }
        if let Some(r) = exact_power_root(&c) {
            // c = r^j: split without rho.
            let (root, j) = r;
            for _ in 0..j {
                stack.push(root.clone());
            }
            continue;
        }
        let remaining = opts.rho_iterations.saturating_sub(spent);
        match pollard_brent(&c, remaining, &mut rng, &mut spent) {
            Some(d) => {
                let other = &c / &d;
                stack.push(d);
                stack.push(other);
            }
            None => unfactored.push(c),
        }
    }
    factors.sort_by(|a, b| a.0.cmp(&b.0));
    Factorization {
        factors,
        unfactored,
        rho_iterations: spent,
    }
}

/// Factor a group order with the default budget.
///
/// Returns `(prime, multiplicity)` pairs sorted by prime.  If the
/// Pollard–Brent budget (`2²⁸` iterations, enough for prime factors up
/// to roughly `2⁵⁰`) cannot split a composite cofactor, that
/// cofactor appears as a single entry with multiplicity 1 and fails
/// [`is_probable_prime`]; use [`factor`] to see the distinction
/// explicitly.
pub fn factor_order(n: &BigUint) -> Vec<(BigUint, u32)> {
    let f = factor(n, &FactorOptions::default());
    let mut out = f.factors;
    for c in f.unfactored {
        push_factor(&mut out, c, 1);
    }
    out.sort_by(|a, b| a.0.cmp(&b.0));
    out
}

/// If `n = r^j` for some `j ≥ 2`, return `(r, j)` with `j` maximal
/// among small exponents.  Rho cannot split a prime power.
fn exact_power_root(n: &BigUint) -> Option<(BigUint, u32)> {
    let bits = n.bits() as u32;
    for j in (2..=bits.min(64)).rev() {
        let r = n.nth_root(j);
        if r > BigUint::one() && &r.pow(j) == n {
            return Some((r, j));
        }
    }
    None
}

fn abs_diff(a: &BigUint, b: &BigUint) -> BigUint {
    if a >= b {
        a - b
    } else {
        b - a
    }
}

/// Pollard–Brent rho on composite `n` (not a prime power).  Returns a
/// non-trivial factor, or `None` once `budget` iterations are spent.
fn pollard_brent(n: &BigUint, budget: u64, rng: &mut StdRng, spent: &mut u64) -> Option<BigUint> {
    if n.is_even() {
        return Some(BigUint::from(2u32));
    }
    let mut used = 0u64;
    const M: u64 = 128;
    while used < budget {
        let c = rng.gen_biguint_below(n);
        let mut y = rng.gen_biguint_below(n);
        let f = |v: &BigUint| (v * v + &c) % n;
        let mut r = 1u64;
        let mut q = BigUint::one();
        let mut g = BigUint::one();
        let mut x = y.clone();
        let mut ys = y.clone();
        while g.is_one() {
            x = y.clone();
            for _ in 0..r {
                y = f(&y);
            }
            used += r;
            let mut k = 0u64;
            while k < r && g.is_one() {
                ys = y.clone();
                let steps = M.min(r - k);
                for _ in 0..steps {
                    y = f(&y);
                    q = (&q * abs_diff(&x, &y)) % n;
                }
                used += steps;
                g = q.gcd(n);
                k += M;
            }
            r *= 2;
            if used >= budget {
                break;
            }
        }
        if &g == n {
            // Backtrack one step at a time from the last saved point.
            loop {
                ys = f(&ys);
                used += 1;
                g = abs_diff(&x, &ys).gcd(n);
                if !g.is_one() || used >= budget {
                    break;
                }
            }
        }
        if !g.is_one() && &g != n {
            *spent += used;
            return Some(g);
        }
        // Otherwise retry with a fresh polynomial; `used` keeps counting.
    }
    *spent += used;
    None
}

/// Legendre symbol `(a | p)` for odd prime `p`: 0, 1 or −1.
pub fn legendre(a: &BigUint, p: &BigUint) -> i8 {
    let a = a % p;
    if a.is_zero() {
        return 0;
    }
    let e = (p - 1u32) >> 1;
    if a.modpow(&e, p).is_one() {
        1
    } else {
        -1
    }
}

/// Square root modulo an odd prime by Tonelli–Shanks.  Returns `None`
/// when `a` is a non-residue.
pub fn sqrt_mod_prime(a: &BigUint, p: &BigUint) -> Option<BigUint> {
    let a = a % p;
    if a.is_zero() {
        return Some(BigUint::zero());
    }
    if legendre(&a, p) != 1 {
        return None;
    }
    let p_minus_1 = p - 1u32;
    let s = p_minus_1.trailing_zeros().unwrap_or(0);
    let q = &p_minus_1 >> s;
    if s == 1 {
        let e = (p + 1u32) >> 2;
        return Some(a.modpow(&e, p));
    }
    // Find a non-residue deterministically.
    let mut z = BigUint::from(2u32);
    while legendre(&z, p) != -1 {
        z += 1u32;
    }
    let mut m = s;
    let mut c = z.modpow(&q, p);
    let mut t = a.modpow(&q, p);
    let mut r = a.modpow(&((&q + 1u32) >> 1), p);
    while !t.is_one() {
        let mut i = 0u64;
        let mut t2 = t.clone();
        while !t2.is_one() {
            t2 = (&t2 * &t2) % p;
            i += 1;
        }
        let mut b = c.clone();
        for _ in 0..(m - i - 1) {
            b = (&b * &b) % p;
        }
        m = i;
        c = (&b * &b) % p;
        t = (&t * &c) % p;
        r = (&r * &b) % p;
    }
    Some(r)
}

/// `(a − b) mod m` for `a, b < m`.
#[inline]
pub(crate) fn sub_mod(a: &BigUint, b: &BigUint, m: &BigUint) -> BigUint {
    if a >= b {
        a - b
    } else {
        m - b + a
    }
}

/// `(a + b) mod m` for `a, b < m`.
#[inline]
pub(crate) fn add_mod(a: &BigUint, b: &BigUint, m: &BigUint) -> BigUint {
    let s = a + b;
    if &s >= m {
        s - m
    } else {
        s
    }
}

/// splitmix64 finaliser: a cheap, well-mixed 64-bit hash of a word.
#[inline]
pub(crate) fn mix64(mut z: u64) -> u64 {
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

/// Lowest 64-bit limb of a `BigUint`.
#[inline]
pub(crate) fn low_u64(v: &BigUint) -> u64 {
    v.iter_u64_digits().next().unwrap_or(0)
}

// ── Affine curve arithmetic over F_p ─────────────────────────────────────

/// A point of `E(F_p)` in affine coordinates, or the identity.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum AffinePoint {
    /// The point at infinity.
    Infinity,
    /// `(x, y)` with coordinates reduced into `[0, p)`.
    Affine(BigUint, BigUint),
}

/// Short Weierstrass curve `y² = x³ + a·x + b` over `F_p`, `p > 3` prime.
///
/// Addition uses the chord-and-tangent formulas; they are also correct
/// on the non-singular points of a singular cubic, which is how the
/// singular-curve attack verifies its answers.
#[derive(Clone, Debug)]
pub struct Ec {
    /// Field prime.
    pub p: BigUint,
    /// Coefficient `a`, reduced.
    pub a: BigUint,
    /// Coefficient `b`, reduced.
    pub b: BigUint,
}

impl Ec {
    /// Build from explicit coefficients.
    pub fn new(p: &BigUint, a: &BigUint, b: &BigUint) -> Self {
        Ec {
            p: p.clone(),
            a: a % p,
            b: b % p,
        }
    }

    /// Build from the crate's curve parameters.
    pub fn from_params(curve: &CurveParams) -> Self {
        Ec::new(&curve.p, &curve.a, &curve.b)
    }

    /// Convert a crate point (coordinates reduced mod `p`).
    pub fn import(&self, pt: &Point) -> AffinePoint {
        match pt {
            Point::Infinity => AffinePoint::Infinity,
            Point::Affine { x, y } => AffinePoint::Affine(&x.value % &self.p, &y.value % &self.p),
        }
    }

    /// Convert to a crate point.
    pub fn export(&self, pt: &AffinePoint) -> Point {
        use crate::ecc::field::FieldElement;
        match pt {
            AffinePoint::Infinity => Point::Infinity,
            AffinePoint::Affine(x, y) => Point::Affine {
                x: FieldElement::new(x.clone(), self.p.clone()),
                y: FieldElement::new(y.clone(), self.p.clone()),
            },
        }
    }

    /// `x³ + a·x + b mod p`.
    pub fn rhs(&self, x: &BigUint) -> BigUint {
        let p = &self.p;
        let x2 = (x * x) % p;
        ((&x2 + &self.a) * x + &self.b) % p
    }

    /// Whether the point satisfies the curve equation.
    pub fn is_on_curve(&self, pt: &AffinePoint) -> bool {
        match pt {
            AffinePoint::Infinity => true,
            AffinePoint::Affine(x, y) => (y * y) % &self.p == self.rhs(x),
        }
    }

    /// `4a³ + 27b² mod p`; zero exactly when the cubic is singular.
    pub fn discriminant(&self) -> BigUint {
        let p = &self.p;
        let a3 = (&self.a * &self.a % p) * &self.a % p;
        (a3 * 4u32 + (&self.b * &self.b % p) * 27u32) % p
    }

    /// `−P`.
    pub fn neg(&self, pt: &AffinePoint) -> AffinePoint {
        match pt {
            AffinePoint::Infinity => AffinePoint::Infinity,
            AffinePoint::Affine(x, y) => {
                AffinePoint::Affine(x.clone(), sub_mod(&BigUint::zero(), y, &self.p))
            }
        }
    }

    /// Slope-based sum given `λ` (shared by the batched and scalar paths).
    fn finish(&self, x1: &BigUint, y1: &BigUint, x2: &BigUint, lam: &BigUint) -> AffinePoint {
        let p = &self.p;
        let l2 = (lam * lam) % p;
        let x3 = sub_mod(&sub_mod(&l2, x1, p), x2, p);
        let y3 = sub_mod(&((lam * sub_mod(x1, &x3, p)) % p), y1, p);
        AffinePoint::Affine(x3, y3)
    }

    /// `2P`.
    pub fn double(&self, pt: &AffinePoint) -> AffinePoint {
        match pt {
            AffinePoint::Infinity => AffinePoint::Infinity,
            AffinePoint::Affine(x, y) => {
                if y.is_zero() {
                    return AffinePoint::Infinity;
                }
                let p = &self.p;
                let num = ((x * x) % p * 3u32 + &self.a) % p;
                let den = (y << 1u32) % p;
                let inv = den.modinv(p).expect("2y is a unit");
                let lam = (num * inv) % p;
                self.finish(x, y, x, &lam)
            }
        }
    }

    /// `P + Q`.
    pub fn add(&self, a: &AffinePoint, b: &AffinePoint) -> AffinePoint {
        match (a, b) {
            (AffinePoint::Infinity, q) | (q, AffinePoint::Infinity) => q.clone(),
            (AffinePoint::Affine(x1, y1), AffinePoint::Affine(x2, y2)) => {
                if x1 == x2 {
                    if y1 == y2 {
                        return self.double(a);
                    }
                    return AffinePoint::Infinity;
                }
                let p = &self.p;
                let inv = sub_mod(x2, x1, p).modinv(p).expect("x2 − x1 is a unit");
                let lam = (sub_mod(y2, y1, p) * inv) % p;
                self.finish(x1, y1, x2, &lam)
            }
        }
    }

    /// `k·P` by left-to-right double-and-add in Jacobian coordinates
    /// (`x = X/Z²`, `y = Y/Z³`), with a single inversion at the end.
    pub fn mul(&self, pt: &AffinePoint, k: &BigUint) -> AffinePoint {
        let AffinePoint::Affine(px, py) = pt else {
            return AffinePoint::Infinity;
        };
        let p = &self.p;
        let m = |a: &BigUint, b: &BigUint| (a * b) % p;
        // Accumulator (X, Y, Z); Z = 0 encodes the identity.
        let mut acc: Option<(BigUint, BigUint, BigUint)> = None;
        for i in (0..k.bits()).rev() {
            if let Some((x, y, z)) = acc.take() {
                acc = self.jac_double(&x, &y, &z);
            }
            if k.bit(i) {
                acc = match acc.take() {
                    None => Some((px.clone(), py.clone(), BigUint::one())),
                    Some((x1, y1, z1)) => {
                        // Mixed addition with (px, py, 1).
                        let z1z1 = m(&z1, &z1);
                        let u2 = m(px, &z1z1);
                        let s2 = m(py, &m(&z1, &z1z1));
                        let h = sub_mod(&u2, &x1, p);
                        let r = sub_mod(&s2, &y1, p);
                        if h.is_zero() {
                            if r.is_zero() {
                                self.jac_double(&x1, &y1, &z1)
                            } else {
                                None
                            }
                        } else {
                            let hh = m(&h, &h);
                            let hhh = m(&h, &hh);
                            let v = m(&x1, &hh);
                            let x3 = sub_mod(&sub_mod(&m(&r, &r), &hhh, p), &((&v << 1u32) % p), p);
                            let y3 = sub_mod(&m(&r, &sub_mod(&v, &x3, p)), &m(&y1, &hhh), p);
                            let z3 = m(&z1, &h);
                            Some((x3, y3, z3))
                        }
                    }
                };
            }
        }
        match acc {
            None => AffinePoint::Infinity,
            Some((x, y, z)) => {
                let zi = z.modinv(p).expect("Z is a unit");
                let zi2 = m(&zi, &zi);
                AffinePoint::Affine(m(&x, &zi2), m(&y, &m(&zi2, &zi)))
            }
        }
    }

    /// Jacobian doubling; `None` for the identity (a 2-torsion input).
    fn jac_double(
        &self,
        x: &BigUint,
        y: &BigUint,
        z: &BigUint,
    ) -> Option<(BigUint, BigUint, BigUint)> {
        if y.is_zero() {
            return None;
        }
        let p = &self.p;
        let m = |a: &BigUint, b: &BigUint| (a * b) % p;
        let xx = m(x, x);
        let yy = m(y, y);
        let yyyy = m(&yy, &yy);
        let zz = m(z, z);
        let s = (m(x, &yy) << 2u32) % p;
        let mm = (&xx * 3u32 + m(&self.a, &m(&zz, &zz))) % p;
        let x3 = sub_mod(&m(&mm, &mm), &((&s << 1u32) % p), p);
        let y3 = sub_mod(&m(&mm, &sub_mod(&s, &x3, p)), &((yyyy << 3u32) % p), p);
        let z3 = (m(y, z) << 1u32) % p;
        Some((x3, y3, z3))
    }

    /// A uniformly random affine point (rejection sampling on `x`).
    pub fn random_point<R: Rng + ?Sized>(&self, rng: &mut R) -> AffinePoint {
        loop {
            let x = rng.gen_biguint_below(&self.p);
            if let Some(y) = sqrt_mod_prime(&self.rhs(&x), &self.p) {
                let y = if rng.gen::<bool>() {
                    sub_mod(&BigUint::zero(), &y, &self.p)
                } else {
                    y
                };
                return AffinePoint::Affine(x, y);
            }
        }
    }

    /// `xs[i] ← xs[i] + ys[i]` for every `i`, sharing one modular
    /// inversion across all generic additions (Montgomery's trick).
    pub fn add_batch(&self, xs: &mut [AffinePoint], ys: &[&AffinePoint]) {
        let p = &self.p;
        let n = xs.len();
        // Indices handled by the generic chord formula.
        let mut generic: Vec<usize> = Vec::with_capacity(n);
        let mut dens: Vec<BigUint> = Vec::with_capacity(n);
        for i in 0..n {
            match (&xs[i], ys[i]) {
                (AffinePoint::Affine(x1, _), AffinePoint::Affine(x2, _)) if x1 != x2 => {
                    generic.push(i);
                    dens.push(sub_mod(x2, x1, p));
                }
                _ => {
                    xs[i] = self.add(&xs[i], ys[i]);
                }
            }
        }
        if generic.is_empty() {
            return;
        }
        // prefix[j] = dens[0]·…·dens[j]
        let mut prefix = Vec::with_capacity(dens.len());
        let mut acc = BigUint::one();
        for d in &dens {
            acc = (&acc * d) % p;
            prefix.push(acc.clone());
        }
        let mut inv = acc.modinv(p).expect("product of units");
        for j in (0..generic.len()).rev() {
            let inv_j = if j == 0 {
                inv.clone()
            } else {
                (&inv * &prefix[j - 1]) % p
            };
            inv = (&inv * &dens[j]) % p;
            let i = generic[j];
            if let (AffinePoint::Affine(x1, y1), AffinePoint::Affine(x2, y2)) = (&xs[i], ys[i]) {
                let lam = (sub_mod(y2, y1, p) * inv_j) % p;
                let r = self.finish(x1, y1, x2, &lam);
                xs[i] = r;
            }
        }
    }
}

/// Seeded RNG used by every attack so runs are reproducible.
pub(crate) fn seeded_rng(seed: u64) -> StdRng {
    StdRng::seed_from_u64(seed)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn big(s: &str) -> BigUint {
        BigUint::parse_bytes(s.as_bytes(), 10).unwrap()
    }

    #[test]
    fn primality_small_and_large() {
        let primes = [
            2u64,
            3,
            5,
            65_537,
            1_000_000_007,
            18_446_744_073_709_551_557,
        ];
        for p in primes {
            assert!(is_probable_prime(&BigUint::from(p)), "{p}");
        }
        for c in [
            1u64,
            4,
            561,
            1_105,
            3_215_031_751,
            18_446_744_073_709_551_615,
        ] {
            assert!(!is_probable_prime(&BigUint::from(c)), "{c}");
        }
        // 2^127 − 1 is prime; 2^128 + 1 is not.
        let m127 = (BigUint::one() << 127u32) - 1u32;
        assert!(is_probable_prime(&m127));
        assert!(!is_probable_prime(&((BigUint::one() << 128u32) + 1u32)));
    }

    #[test]
    fn factor_mixed_sizes() {
        // 3^2 · 87721 · 1350388531 · 414225013639 · 669550864369
        let n = big("295681886263824732712120563203402323269");
        let f = factor(&n, &FactorOptions::default());
        assert!(f.is_complete());
        let prod = f
            .factors
            .iter()
            .fold(BigUint::one(), |acc, (q, e)| acc * q.pow(*e));
        assert_eq!(prod, n);
        assert!(f.factors.iter().all(|(q, _)| is_probable_prime(q)));
        assert_eq!(f.largest_prime(), Some(&big("669550864369")));
    }

    #[test]
    fn factor_prime_power_and_large_prime() {
        let q = big("1000000007");
        let n = q.pow(3);
        assert_eq!(factor_order(&n), vec![(q, 3)]);
        let m127 = (BigUint::one() << 127u32) - 1u32;
        assert_eq!(factor_order(&m127), vec![(m127.clone(), 1)]);
    }

    #[test]
    fn factor_budget_exhaustion_is_reported() {
        // Product of two ~2^61 primes: rho needs ~2^31 steps, budget 1000.
        let a = big("2305843009213693951"); // 2^61 − 1
        let b = big("2305843009213693967");
        assert!(is_probable_prime(&b));
        let n = &a * &b;
        let f = factor(
            &n,
            &FactorOptions {
                trial_bound: 1000,
                rho_iterations: 1000,
            },
        );
        assert!(!f.is_complete());
        assert_eq!(f.unfactored, vec![n]);
    }

    #[test]
    fn tonelli_shanks_roots() {
        let p = BigUint::from(1_000_000_009u64); // p ≡ 1 mod 8
        for a in 2u64..200 {
            let a = BigUint::from(a);
            if let Some(r) = sqrt_mod_prime(&a, &p) {
                assert_eq!((&r * &r) % &p, a);
            } else {
                assert_eq!(legendre(&a, &p), -1);
            }
        }
    }

    #[test]
    fn jacobian_mul_matches_repeated_addition() {
        let p = BigUint::from(1_000_003u64);
        let ec = Ec::new(&p, &BigUint::from(3u32), &BigUint::from(7u32));
        let mut rng = seeded_rng(2);
        let g = ec.random_point(&mut rng);
        let mut acc = AffinePoint::Infinity;
        for k in 0u32..300 {
            assert_eq!(ec.mul(&g, &BigUint::from(k)), acc, "k = {k}");
            acc = ec.add(&acc, &g);
        }
    }

    #[test]
    fn batched_addition_matches_scalar() {
        let p = BigUint::from(1_000_003u64);
        let ec = Ec::new(&p, &BigUint::from(3u32), &BigUint::from(7u32));
        let mut rng = seeded_rng(1);
        let pts: Vec<AffinePoint> = (0..20).map(|_| ec.random_point(&mut rng)).collect();
        let mut xs: Vec<AffinePoint> = (0..20).map(|_| ec.random_point(&mut rng)).collect();
        xs[3] = pts[3].clone(); // doubling case
        xs[5] = ec.neg(&pts[5]); // inverse case
        xs[7] = AffinePoint::Infinity;
        let expect: Vec<AffinePoint> = xs.iter().zip(&pts).map(|(x, y)| ec.add(x, y)).collect();
        let refs: Vec<&AffinePoint> = pts.iter().collect();
        ec.add_batch(&mut xs, &refs);
        assert_eq!(xs, expect);
        assert!(xs.iter().all(|x| ec.is_on_curve(x)));
    }
}
