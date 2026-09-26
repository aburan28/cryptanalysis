//! Polynomials for the NFS: over `ℤ` (big coefficients), over `F_p`
//! (word-size `p < 2³²`), and numerically over `ℂ`.
//!
//! - [`IntPoly`] — `f ∈ ℤ[x]`, evaluation, the homogenised form
//!   `F(a, b) = bᵈ f(a/b)` (the algebraic norm of `a − bα` times the
//!   leading coefficient), derivative, exact division and the
//!   monic transform `F(y) = c^{d−1} f(y/c)`.
//! - [`fp`] — arithmetic in `F_p[x]`: multiplication, remainder, gcd,
//!   modular powering, **roots** by Cantor–Zassenhaus
//!   (`gcd(f, x^p − x)` then random splitting with `(x + δ)^{(p−1)/2} − 1`)
//!   and an **irreducibility test** (`gcd(f, x^{pⁱ} − x) = 1` for
//!   `i ≤ d/2`, `f` squarefree).
//! - [`complex_roots`] (Durand–Kerner) and [`find_integer_factor`], which
//!   recombines numerical roots into candidate integer factors and checks
//!   each by exact division.  Used on small-coefficient SNFS polynomials,
//!   which are often reducible (`x⁴ + 4 = (x² + 2x + 2)(x² − 2x + 2)`).

use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};
use std::fmt;

use super::super::arith::bigint_mod_u64;

/// Polynomial with integer coefficients, lowest degree first.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IntPoly {
    /// `coeffs[i]` is the coefficient of `xⁱ`; the last entry is non-zero.
    pub coeffs: Vec<BigInt>,
}

impl IntPoly {
    /// Build from coefficients (lowest first); trailing zeros are removed.
    pub fn new(mut coeffs: Vec<BigInt>) -> Self {
        while coeffs.len() > 1 && coeffs.last().is_some_and(|c| c.is_zero()) {
            coeffs.pop();
        }
        if coeffs.is_empty() {
            coeffs.push(BigInt::zero());
        }
        IntPoly { coeffs }
    }

    /// From machine integers (lowest first).
    pub fn from_i64(coeffs: &[i64]) -> Self {
        IntPoly::new(coeffs.iter().map(|&c| BigInt::from(c)).collect())
    }

    /// Degree (the zero polynomial has degree 0).
    pub fn degree(&self) -> usize {
        self.coeffs.len() - 1
    }

    /// Leading coefficient.
    pub fn lead(&self) -> &BigInt {
        self.coeffs.last().expect("non-empty")
    }

    /// `f(x)` by Horner.
    pub fn eval(&self, x: &BigInt) -> BigInt {
        let mut acc = BigInt::zero();
        for c in self.coeffs.iter().rev() {
            acc = acc * x + c;
        }
        acc
    }

    /// Homogenised value `F(a, b) = Σ cᵢ aⁱ b^{d−i}`.
    pub fn eval_hom(&self, a: i64, b: i64) -> BigInt {
        let (a, b) = (BigInt::from(a), BigInt::from(b));
        let mut acc = BigInt::zero();
        let mut bpow = BigInt::one();
        // Horner in a with b-powers: F = (((c_d a + c_{d−1} b) a + c_{d−2} b²) …).
        for (k, c) in self.coeffs.iter().rev().enumerate() {
            if k == 0 {
                acc = c.clone();
            } else {
                bpow *= &b;
                acc = acc * &a + c * &bpow;
            }
        }
        acc
    }

    /// `log₂ |F(a, b)|` in floating point (for sieve thresholds).
    pub fn log2_hom(&self, a: f64, b: f64) -> f64 {
        let mut acc = 0.0f64;
        let mut bpow = 1.0f64;
        for (k, c) in self.coeffs.iter().rev().enumerate() {
            let cf = c.to_f64().unwrap_or(f64::MAX);
            if k == 0 {
                acc = cf;
            } else {
                bpow *= b;
                acc = acc * a + cf * bpow;
            }
        }
        acc.abs().max(1.0).log2()
    }

    /// Formal derivative.
    pub fn derivative(&self) -> IntPoly {
        if self.coeffs.len() <= 1 {
            return IntPoly::new(vec![BigInt::zero()]);
        }
        IntPoly::new(
            self.coeffs
                .iter()
                .enumerate()
                .skip(1)
                .map(|(i, c)| c * BigInt::from(i))
                .collect(),
        )
    }

    /// Coefficients reduced modulo `p` (not trimmed: index = degree).
    pub fn mod_p(&self, p: u64) -> Vec<u64> {
        self.coeffs.iter().map(|c| bigint_mod_u64(c, p)).collect()
    }

    /// Gcd of the coefficients (non-negative).
    pub fn content(&self) -> BigInt {
        self.coeffs.iter().fold(BigInt::zero(), |g, c| g.gcd(c))
    }

    /// Product.
    pub fn mul(&self, other: &IntPoly) -> IntPoly {
        let mut out = vec![BigInt::zero(); self.coeffs.len() + other.coeffs.len() - 1];
        for (i, a) in self.coeffs.iter().enumerate() {
            for (j, b) in other.coeffs.iter().enumerate() {
                out[i + j] += a * b;
            }
        }
        IntPoly::new(out)
    }

    /// `self / g` if `g` divides `self` exactly in `ℤ[x]`.
    pub fn exact_div(&self, g: &IntPoly) -> Option<IntPoly> {
        if g.coeffs.iter().all(|c| c.is_zero()) || g.degree() > self.degree() {
            return None;
        }
        let mut rem = self.coeffs.clone();
        let dg = g.degree();
        let lg = g.lead();
        let mut q = vec![BigInt::zero(); self.degree() - dg + 1];
        for i in (0..q.len()).rev() {
            let top = &rem[i + dg];
            if top.is_zero() {
                continue;
            }
            let (qi, r) = top.div_rem(lg);
            if !r.is_zero() {
                return None;
            }
            for (j, gc) in g.coeffs.iter().enumerate() {
                rem[i + j] -= &qi * gc;
            }
            q[i] = qi;
        }
        if rem.iter().all(|c| c.is_zero()) {
            Some(IntPoly::new(q))
        } else {
            None
        }
    }

    /// Monic transform: for `f` of degree `d` with leading coefficient `c`,
    /// `F(y) = c^{d−1} f(y / c)`, whose root is `β = c·α`.  Coefficients:
    /// `Fᵢ = fᵢ · c^{d−1−i}` for `i < d`, `F_d = 1`.
    pub fn monic_transform(&self) -> IntPoly {
        let d = self.degree();
        let c = self.lead().clone();
        let mut out = vec![BigInt::zero(); d + 1];
        let mut cpow = BigInt::one();
        for i in (0..d).rev() {
            out[i] = &self.coeffs[i] * &cpow;
            cpow *= &c;
        }
        out[d] = BigInt::one();
        IntPoly::new(out)
    }
}

impl fmt::Display for IntPoly {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut first = true;
        for (i, c) in self.coeffs.iter().enumerate().rev() {
            if c.is_zero() && self.coeffs.len() > 1 {
                continue;
            }
            let neg = c.is_negative();
            let mag = c.abs();
            if first {
                if neg {
                    write!(f, "-")?;
                }
            } else {
                write!(f, " {} ", if neg { "-" } else { "+" })?;
            }
            first = false;
            let show_coeff = !mag.is_one() || i == 0;
            match (show_coeff, i) {
                (_, 0) => write!(f, "{mag}")?,
                (true, 1) => write!(f, "{mag}*x")?,
                (false, 1) => write!(f, "x")?,
                (true, _) => write!(f, "{mag}*x^{i}")?,
                (false, _) => write!(f, "x^{i}")?,
            }
        }
        Ok(())
    }
}

/// Arithmetic in `F_p[x]` for primes `p < 2³²`; polynomials are `Vec<u64>`
/// with the lowest coefficient first.
pub mod fp {
    use super::super::super::arith::{inv_mod, mul_mod};
    use num_bigint::BigUint;

    /// Remove leading zeros (the zero polynomial becomes empty).
    pub fn trim(mut a: Vec<u64>) -> Vec<u64> {
        while a.last() == Some(&0) {
            a.pop();
        }
        a
    }

    /// Degree, or `None` for the zero polynomial.
    pub fn deg(a: &[u64]) -> Option<usize> {
        a.iter().rposition(|&c| c != 0)
    }

    /// Sum.
    pub fn add(a: &[u64], b: &[u64], p: u64) -> Vec<u64> {
        let mut out = vec![0; a.len().max(b.len())];
        for (i, o) in out.iter_mut().enumerate() {
            let x = a.get(i).copied().unwrap_or(0) + b.get(i).copied().unwrap_or(0);
            *o = x % p;
        }
        trim(out)
    }

    /// Difference.
    pub fn sub(a: &[u64], b: &[u64], p: u64) -> Vec<u64> {
        let mut out = vec![0; a.len().max(b.len())];
        for (i, o) in out.iter_mut().enumerate() {
            let x = a.get(i).copied().unwrap_or(0) + p - b.get(i).copied().unwrap_or(0) % p;
            *o = x % p;
        }
        trim(out)
    }

    /// Product.
    pub fn mul(a: &[u64], b: &[u64], p: u64) -> Vec<u64> {
        if a.is_empty() || b.is_empty() {
            return Vec::new();
        }
        let mut out = vec![0u64; a.len() + b.len() - 1];
        for (i, &x) in a.iter().enumerate() {
            if x == 0 {
                continue;
            }
            for (j, &y) in b.iter().enumerate() {
                out[i + j] = (out[i + j] + mul_mod(x, y, p)) % p;
            }
        }
        trim(out)
    }

    /// Quotient and remainder of `a / m` (`m ≠ 0`).
    pub fn divrem(a: &[u64], m: &[u64], p: u64) -> (Vec<u64>, Vec<u64>) {
        let m = trim(m.to_vec());
        let dm = m.len() - 1;
        let inv = inv_mod(m[dm], p).expect("leading coefficient invertible");
        let mut r = trim(a.to_vec());
        if r.len() < m.len() {
            return (Vec::new(), r);
        }
        let mut q = vec![0u64; r.len() - dm];
        for i in (0..q.len()).rev() {
            let c = mul_mod(r[i + dm], inv, p);
            q[i] = c;
            if c == 0 {
                continue;
            }
            for (j, &mj) in m.iter().enumerate() {
                r[i + j] = (r[i + j] + p - mul_mod(c, mj, p)) % p;
            }
        }
        (trim(q), trim(r))
    }

    /// Remainder of `a` modulo `m`.
    pub fn rem(a: &[u64], m: &[u64], p: u64) -> Vec<u64> {
        divrem(a, m, p).1
    }

    /// Monic gcd.
    pub fn gcd(a: &[u64], b: &[u64], p: u64) -> Vec<u64> {
        let (mut a, mut b) = (trim(a.to_vec()), trim(b.to_vec()));
        while !b.is_empty() {
            let r = rem(&a, &b, p);
            a = b;
            b = r;
        }
        if let Some(&l) = a.last() {
            let inv = inv_mod(l, p).expect("non-zero");
            for c in a.iter_mut() {
                *c = mul_mod(*c, inv, p);
            }
        }
        a
    }

    /// `base^e mod m`.
    pub fn powmod(base: &[u64], e: &BigUint, m: &[u64], p: u64) -> Vec<u64> {
        let mut result = vec![1u64];
        let b = rem(base, m, p);
        for i in (0..e.bits()).rev() {
            result = rem(&mul(&result, &result, p), m, p);
            if e.bit(i) {
                result = rem(&mul(&result, &b, p), m, p);
            }
        }
        result
    }

    /// Formal derivative.
    pub fn derivative(a: &[u64], p: u64) -> Vec<u64> {
        trim(
            a.iter()
                .enumerate()
                .skip(1)
                .map(|(i, &c)| mul_mod(c, i as u64 % p, p))
                .collect(),
        )
    }

    /// Distinct roots of `f` in `F_p`, sorted.
    pub fn roots(f: &[u64], p: u64) -> Vec<u64> {
        let f = trim(f.to_vec());
        let Some(d) = deg(&f) else {
            return Vec::new();
        };
        if d == 0 {
            return Vec::new();
        }
        if p < 64 {
            let mut out: Vec<u64> = (0..p)
                .filter(|&x| {
                    let mut acc = 0u64;
                    for &c in f.iter().rev() {
                        acc = (mul_mod(acc, x, p) + c) % p;
                    }
                    acc == 0
                })
                .collect();
            out.sort_unstable();
            return out;
        }
        // g = gcd(f, x^p − x): the product of the distinct linear factors.
        let xp = powmod(&[0, 1], &BigUint::from(p), &f, p);
        let g = gcd(&f, &sub(&xp, &[0, 1], p), p);
        let mut out = Vec::new();
        split_linear(&g, p, &mut out, 1);
        out.sort_unstable();
        out
    }

    fn split_linear(g: &[u64], p: u64, out: &mut Vec<u64>, mut delta: u64) {
        match deg(g) {
            None | Some(0) => {}
            Some(1) => {
                let inv = inv_mod(g[1], p).expect("non-zero");
                out.push((p - mul_mod(g[0], inv, p)) % p);
            }
            Some(dg) => {
                let e = BigUint::from((p - 1) / 2);
                loop {
                    let h = powmod(&[delta % p, 1], &e, g, p);
                    delta += 1;
                    let h1 = sub(&h, &[1], p);
                    let d = gcd(g, &h1, p);
                    let dd = deg(&d).unwrap_or(0);
                    if dd > 0 && dd < dg {
                        let (q, _) = divrem(g, &d, p);
                        split_linear(&d, p, out, delta);
                        split_linear(&q, p, out, delta);
                        return;
                    }
                }
            }
        }
    }

    /// `true` iff `f` has degree `d` modulo `p` and is irreducible over `F_p`.
    pub fn is_irreducible(f: &[u64], d: usize, p: u64) -> bool {
        let f = trim(f.to_vec());
        if deg(&f) != Some(d) {
            return false;
        }
        if d == 1 {
            return true;
        }
        let g = gcd(&f, &derivative(&f, p), p);
        if deg(&g) != Some(0) {
            return false;
        }
        let pb = BigUint::from(p);
        let mut h = vec![0u64, 1];
        for _ in 1..=d / 2 {
            h = powmod(&h, &pb, &f, p);
            let g = gcd(&f, &sub(&h, &[0, 1], p), p);
            if deg(&g) != Some(0) {
                return false;
            }
        }
        true
    }
}

/// A complex number (just enough for Durand–Kerner).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Complex {
    /// Real part.
    pub re: f64,
    /// Imaginary part.
    pub im: f64,
}

impl Complex {
    fn mul(self, o: Complex) -> Complex {
        Complex {
            re: self.re * o.re - self.im * o.im,
            im: self.re * o.im + self.im * o.re,
        }
    }
    fn sub(self, o: Complex) -> Complex {
        Complex {
            re: self.re - o.re,
            im: self.im - o.im,
        }
    }
    fn div(self, o: Complex) -> Complex {
        let d = o.re * o.re + o.im * o.im;
        Complex {
            re: (self.re * o.re + self.im * o.im) / d,
            im: (self.im * o.re - self.re * o.im) / d,
        }
    }
    fn norm(self) -> f64 {
        self.re.hypot(self.im)
    }
}

/// All complex roots of `f` by Durand–Kerner (Weierstrass) iteration.
pub fn complex_roots(f: &IntPoly) -> Vec<Complex> {
    let d = f.degree();
    if d == 0 {
        return Vec::new();
    }
    let lead = f.lead().to_f64().unwrap_or(1.0);
    let c: Vec<f64> = f
        .coeffs
        .iter()
        .map(|x| x.to_f64().unwrap_or(0.0) / lead)
        .collect();
    // Cauchy bound for the initial circle.
    let radius = 1.0 + c[..d].iter().fold(0.0f64, |m, x| m.max(x.abs()));
    let eval = |z: Complex| {
        let mut acc = Complex { re: 1.0, im: 0.0 };
        for i in (0..d).rev() {
            acc = acc.mul(z);
            acc.re += c[i];
        }
        acc
    };
    let mut roots: Vec<Complex> = (0..d)
        .map(|k| {
            let t = 0.4 + 2.0 * std::f64::consts::PI * k as f64 / d as f64;
            Complex {
                re: radius.min(1e6) * 0.9 * t.cos(),
                im: radius.min(1e6) * 0.9 * t.sin(),
            }
        })
        .collect();
    for _ in 0..2000 {
        let mut delta = 0.0f64;
        for i in 0..d {
            let mut den = Complex { re: 1.0, im: 0.0 };
            for j in 0..d {
                if i != j {
                    den = den.mul(roots[i].sub(roots[j]));
                }
            }
            if den.norm() == 0.0 {
                den.re = 1e-12;
            }
            let step = eval(roots[i]).div(den);
            roots[i] = roots[i].sub(step);
            delta = delta.max(step.norm() / (1.0 + roots[i].norm()));
        }
        if delta < 1e-15 {
            break;
        }
    }
    roots
}

/// Try to find a proper factor of `f` in `ℤ[x]` by recombining numerical
/// roots.  Sound (every returned factor divides `f` exactly), not
/// complete: a factor is missed only when floating point cannot resolve
/// its coefficients, which does not happen for the small-coefficient
/// polynomials this is used on.
pub fn find_integer_factor(f: &IntPoly) -> Option<IntPoly> {
    let d = f.degree();
    if d < 2 {
        return None;
    }
    let roots = complex_roots(f);
    let lead = f.lead().abs().to_u64().filter(|&l| l <= 1_000_000)?;
    let divisors: Vec<u64> = (1..=lead).filter(|k| lead.is_multiple_of(*k)).collect();
    for size in 1..=d / 2 {
        for mask in 0u32..(1 << d) {
            if mask.count_ones() as usize != size {
                continue;
            }
            // ∏ (x − r_i) over the subset.
            let mut prod = vec![Complex { re: 1.0, im: 0.0 }];
            for (i, &r) in roots.iter().enumerate() {
                if mask & (1 << i) == 0 {
                    continue;
                }
                let mut next = vec![Complex { re: 0.0, im: 0.0 }; prod.len() + 1];
                for (k, &c) in prod.iter().enumerate() {
                    next[k + 1].re += c.re;
                    next[k + 1].im += c.im;
                    let t = c.mul(r);
                    next[k].re -= t.re;
                    next[k].im -= t.im;
                }
                prod = next;
            }
            if prod.iter().any(|c| c.im.abs() > 1e-6 * (1.0 + c.re.abs())) {
                continue;
            }
            for &l in &divisors {
                let coeffs: Option<Vec<BigInt>> = prod
                    .iter()
                    .map(|c| {
                        let v = c.re * l as f64;
                        (v.abs() < 1e15 && (v - v.round()).abs() < 1e-6 * (1.0 + v.abs()))
                            .then(|| BigInt::from(v.round() as i64))
                    })
                    .collect();
                let Some(coeffs) = coeffs else { continue };
                let g = IntPoly::new(coeffs);
                if g.degree() == size && f.exact_div(&g).is_some() {
                    return Some(g);
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn homogeneous_evaluation_matches_definition() {
        let f = IntPoly::from_i64(&[-7, 3, 0, 2]); // 2x³ + 3x − 7
        for (a, b) in [(5i64, 3i64), (-11, 7), (1, 1), (0, 5)] {
            // b³ f(a/b) = 2a³ + 3ab² − 7b³
            let want = 2 * a.pow(3) + 3 * a * b * b - 7 * b.pow(3);
            assert_eq!(f.eval_hom(a, b), BigInt::from(want));
        }
    }

    #[test]
    fn roots_mod_p_are_roots() {
        let f = IntPoly::from_i64(&[-2, 0, 0, 1]); // x³ − 2
        for p in [7u64, 31, 43, 1_000_003, 4_294_967_291] {
            let fp_ = f.mod_p(p);
            let rs = fp::roots(&fp_, p);
            for &r in &rs {
                let v = (super::super::super::arith::pow_mod(r, 3, p) + p - 2) % p;
                assert_eq!(v, 0);
            }
            // x³ = 2 has 0 or 3 roots when p ≡ 1 (mod 3), exactly 1 otherwise.
            if p % 3 == 2 {
                assert_eq!(rs.len(), 1);
            } else {
                assert!(rs.is_empty() || rs.len() == 3);
            }
        }
    }

    #[test]
    fn irreducibility_mod_p() {
        let f = IntPoly::from_i64(&[-2, 0, 0, 1]).mod_p(7); // 2 is not a cube mod 7
        assert!(fp::is_irreducible(&f, 3, 7));
        let g = IntPoly::from_i64(&[-1, 0, 0, 1]).mod_p(7); // x³ − 1 has root 1
        assert!(!fp::is_irreducible(&g, 3, 7));
    }

    #[test]
    fn finds_aurifeuillian_factor() {
        let f = IntPoly::from_i64(&[4, 0, 0, 0, 1]); // x⁴ + 4
        let g = find_integer_factor(&f).expect("x^4 + 4 is reducible");
        assert_eq!(g.degree(), 2);
        assert!(f.exact_div(&g).is_some());
        assert!(find_integer_factor(&IntPoly::from_i64(&[2, 0, 0, 1])).is_none());
    }

    #[test]
    fn monic_transform_root() {
        // f = 3x² − 5, F(y) = y² − 15, β = 3α.
        let f = IntPoly::from_i64(&[-5, 0, 3]);
        assert_eq!(f.monic_transform(), IntPoly::from_i64(&[-15, 0, 1]));
        assert_eq!(format!("{f}"), "3*x^2 - 5");
    }
}
