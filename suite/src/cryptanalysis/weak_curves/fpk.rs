//! Arithmetic in the extension field `F_{p^k} = F_p[t]/(f(t))` for an
//! irreducible monic `f` of degree `k`, and in its multiplicative group.
//!
//! Elements are coefficient vectors `[c₀, …, c_{k−1}]` (lowest degree
//! first), always reduced, so equality of vectors is equality in the
//! field.  Multiplication is schoolbook followed by reduction by the
//! monic modulus, inversion is the extended Euclidean algorithm in
//! `F_p[t]`, and square roots use Tonelli–Shanks in the group of order
//! `p^k − 1`.
//!
//! A random monic `f` of degree `k` is irreducible with probability
//! about `1/k`; irreducibility is decided by Rabin's test (Rabin 1980):
//! `f` of degree `k` is irreducible iff `f | t^{p^k} − t` and
//! `gcd(t^{p^{k/r}} − t, f) = 1` for every prime `r | k`.
//!
//! This is the target group of the MOV/Frey–Rück reduction and the home
//! of the non-split nodal singular cubic (`k = 2`).
//!
//! Reference: M. O. Rabin, *Probabilistic algorithms in finite fields*,
//! SIAM J. Comput. 9 (1980); V. Shoup, *A Computational Introduction to
//! Number Theory and Algebra*, ch. 20.

use super::arith::{add_mod, low_u64, mix64, sub_mod};
use super::dlp::DlpGroup;
use super::WeakCurveError;
use num_bigint::{BigUint, RandBigInt};
use num_traits::{One, Zero};
use rand::Rng;

/// An element of `F_{p^k}`: `k` coefficients, lowest degree first.
pub type FpkElem = Vec<BigUint>;

/// The field `F_p[t]/(f)`.
#[derive(Clone, Debug)]
pub struct Fpk {
    p: BigUint,
    k: usize,
    /// Monic modulus, `k + 1` coefficients, lowest degree first.
    modulus: Vec<BigUint>,
}

// ── Polynomials over F_p (lowest degree first, trimmed) ──────────────────

fn trim(mut v: Vec<BigUint>) -> Vec<BigUint> {
    while v.last().is_some_and(|c| c.is_zero()) {
        v.pop();
    }
    v
}

fn poly_sub(a: &[BigUint], b: &[BigUint], p: &BigUint) -> Vec<BigUint> {
    let n = a.len().max(b.len());
    let zero = BigUint::zero();
    let out = (0..n)
        .map(|i| sub_mod(a.get(i).unwrap_or(&zero), b.get(i).unwrap_or(&zero), p))
        .collect();
    trim(out)
}

fn poly_mul(a: &[BigUint], b: &[BigUint], p: &BigUint) -> Vec<BigUint> {
    if a.is_empty() || b.is_empty() {
        return Vec::new();
    }
    let mut out = vec![BigUint::zero(); a.len() + b.len() - 1];
    for (i, ai) in a.iter().enumerate() {
        if ai.is_zero() {
            continue;
        }
        for (j, bj) in b.iter().enumerate() {
            out[i + j] += ai * bj;
        }
    }
    trim(out.into_iter().map(|c| c % p).collect())
}

/// `(quotient, remainder)` of `a / b`, `b` non-zero.
fn poly_divmod(a: &[BigUint], b: &[BigUint], p: &BigUint) -> (Vec<BigUint>, Vec<BigUint>) {
    let b = trim(b.to_vec());
    let db = b.len() - 1;
    let lead_inv = b[db].modinv(p).expect("non-zero leading coefficient");
    let mut r = trim(a.to_vec());
    if r.len() < b.len() {
        return (Vec::new(), r);
    }
    let mut q = vec![BigUint::zero(); r.len() - db];
    while r.len() > db && !r.is_empty() {
        let dr = r.len() - 1;
        let c = (&r[dr] * &lead_inv) % p;
        let shift = dr - db;
        for (j, bj) in b.iter().enumerate() {
            r[shift + j] = sub_mod(&r[shift + j], &((&c * bj) % p), p);
        }
        q[shift] = c;
        r = trim(r);
    }
    (trim(q), r)
}

fn poly_mulmod(a: &[BigUint], b: &[BigUint], f: &[BigUint], p: &BigUint) -> Vec<BigUint> {
    poly_divmod(&poly_mul(a, b, p), f, p).1
}

fn poly_powmod(base: &[BigUint], e: &BigUint, f: &[BigUint], p: &BigUint) -> Vec<BigUint> {
    let mut acc = vec![BigUint::one()];
    for i in (0..e.bits()).rev() {
        acc = poly_mulmod(&acc, &acc, f, p);
        if e.bit(i) {
            acc = poly_mulmod(&acc, base, f, p);
        }
    }
    acc
}

fn poly_gcd(a: &[BigUint], b: &[BigUint], p: &BigUint) -> Vec<BigUint> {
    let mut x = trim(a.to_vec());
    let mut y = trim(b.to_vec());
    while !y.is_empty() {
        let r = poly_divmod(&x, &y, p).1;
        x = y;
        y = r;
    }
    x
}

fn prime_divisors(mut k: usize) -> Vec<usize> {
    let mut out = Vec::new();
    let mut d = 2;
    while d * d <= k {
        if k.is_multiple_of(d) {
            out.push(d);
            while k.is_multiple_of(d) {
                k /= d;
            }
        }
        d += 1;
    }
    if k > 1 {
        out.push(k);
    }
    out
}

/// Rabin's irreducibility test for a monic `f` of degree `k ≥ 1`.
fn is_irreducible(f: &[BigUint], p: &BigUint) -> bool {
    let k = f.len() - 1;
    if k == 1 {
        return true;
    }
    let t = vec![BigUint::zero(), BigUint::one()];
    // t^{p^i} mod f for i = 1..k, by repeated p-th powers.
    let mut pows = Vec::with_capacity(k + 1);
    pows.push(t.clone());
    for i in 1..=k {
        let next = poly_powmod(&pows[i - 1], p, f, p);
        pows.push(next);
    }
    if !poly_sub(&pows[k], &t, p).is_empty() {
        return false;
    }
    for r in prime_divisors(k) {
        let g = poly_gcd(&poly_sub(&pows[k / r], &t, p), f, p);
        if g.len() != 1 {
            return false;
        }
    }
    true
}

impl Fpk {
    /// `F_{p^k}` with a random irreducible modulus found by Rabin's test.
    /// For `k = 1` the modulus is `t` (so `F_{p^1} = F_p`).
    pub fn new<R: Rng + ?Sized>(
        p: &BigUint,
        k: usize,
        rng: &mut R,
    ) -> Result<Self, WeakCurveError> {
        if k == 0 {
            return Err(WeakCurveError::InvalidInput("extension degree 0".into()));
        }
        if k == 1 {
            return Ok(Fpk {
                p: p.clone(),
                k,
                modulus: vec![BigUint::zero(), BigUint::one()],
            });
        }
        for _ in 0..(200 * k) {
            let mut f: Vec<BigUint> = (0..k).map(|_| rng.gen_biguint_below(p)).collect();
            if f[0].is_zero() {
                continue;
            }
            f.push(BigUint::one());
            if is_irreducible(&f, p) {
                return Ok(Fpk {
                    p: p.clone(),
                    k,
                    modulus: f,
                });
            }
        }
        Err(WeakCurveError::SolverFailed(format!(
            "no irreducible polynomial of degree {k} found"
        )))
    }

    /// `F_p[t]/(f)` for a given monic `f` (lowest degree first).  Returns
    /// `None` if `f` is not monic or not irreducible.
    pub fn with_modulus(p: &BigUint, f: &[BigUint]) -> Option<Self> {
        let f: Vec<BigUint> = f.iter().map(|c| c % p).collect();
        if f.len() < 2 || !f.last()?.is_one() || !is_irreducible(&f, p) {
            return None;
        }
        Some(Fpk {
            p: p.clone(),
            k: f.len() - 1,
            modulus: f,
        })
    }

    /// The characteristic.
    pub fn p(&self) -> &BigUint {
        &self.p
    }

    /// The extension degree.
    pub fn degree(&self) -> usize {
        self.k
    }

    /// The modulus polynomial (monic, lowest degree first).
    pub fn modulus(&self) -> &[BigUint] {
        &self.modulus
    }

    /// Field size `p^k`.
    pub fn size(&self) -> BigUint {
        self.p.pow(self.k as u32)
    }

    /// Zero.
    pub fn zero(&self) -> FpkElem {
        vec![BigUint::zero(); self.k]
    }

    /// One.
    pub fn one(&self) -> FpkElem {
        self.from_base(&BigUint::one())
    }

    /// Embed an element of `F_p`.
    pub fn from_base(&self, c: &BigUint) -> FpkElem {
        let mut v = self.zero();
        v[0] = c % &self.p;
        v
    }

    /// Canonical element from an arbitrary polynomial.
    pub fn from_poly(&self, poly: &[BigUint]) -> FpkElem {
        let r = poly_divmod(poly, &self.modulus, &self.p).1;
        self.pad(r)
    }

    fn pad(&self, mut v: Vec<BigUint>) -> FpkElem {
        v.resize(self.k, BigUint::zero());
        v
    }

    /// Whether `a = 0`.
    pub fn is_zero(&self, a: &FpkElem) -> bool {
        a.iter().all(|c| c.is_zero())
    }

    /// `a + b`.
    pub fn add(&self, a: &FpkElem, b: &FpkElem) -> FpkElem {
        a.iter()
            .zip(b)
            .map(|(x, y)| add_mod(x, y, &self.p))
            .collect()
    }

    /// `a − b`.
    pub fn sub(&self, a: &FpkElem, b: &FpkElem) -> FpkElem {
        a.iter()
            .zip(b)
            .map(|(x, y)| sub_mod(x, y, &self.p))
            .collect()
    }

    /// `−a`.
    pub fn neg(&self, a: &FpkElem) -> FpkElem {
        let z = BigUint::zero();
        a.iter().map(|x| sub_mod(&z, x, &self.p)).collect()
    }

    /// `c·a` for `c ∈ F_p`.
    pub fn scale(&self, a: &FpkElem, c: &BigUint) -> FpkElem {
        a.iter().map(|x| (x * c) % &self.p).collect()
    }

    /// `a·b`.
    pub fn mul(&self, a: &FpkElem, b: &FpkElem) -> FpkElem {
        let k = self.k;
        let p = &self.p;
        let mut prod = vec![BigUint::zero(); 2 * k - 1];
        for i in 0..k {
            if a[i].is_zero() {
                continue;
            }
            for j in 0..k {
                prod[i + j] += &a[i] * &b[j];
            }
        }
        let mut prod: Vec<BigUint> = prod.into_iter().map(|c| c % p).collect();
        // Reduce by the monic modulus: t^k = −(f₀ + … + f_{k−1} t^{k−1}).
        for i in (k..2 * k - 1).rev() {
            let c = std::mem::take(&mut prod[i]);
            if c.is_zero() {
                continue;
            }
            for j in 0..k {
                let t = (&c * &self.modulus[j]) % p;
                prod[i - k + j] = sub_mod(&prod[i - k + j], &t, p);
            }
        }
        prod.truncate(k);
        prod
    }

    /// `a²`.
    pub fn sqr(&self, a: &FpkElem) -> FpkElem {
        self.mul(a, a)
    }

    /// `a^e`.
    pub fn pow(&self, a: &FpkElem, e: &BigUint) -> FpkElem {
        let mut acc = self.one();
        for i in (0..e.bits()).rev() {
            acc = self.sqr(&acc);
            if e.bit(i) {
                acc = self.mul(&acc, a);
            }
        }
        acc
    }

    /// `a⁻¹` by the extended Euclidean algorithm; `None` for zero.
    pub fn inv(&self, a: &FpkElem) -> Option<FpkElem> {
        let p = &self.p;
        let a_poly = trim(a.clone());
        if a_poly.is_empty() {
            return None;
        }
        // Invariant: r0 ≡ s0·a, r1 ≡ s1·a (mod f).
        let mut r0 = self.modulus.clone();
        let mut r1 = a_poly;
        let mut s0: Vec<BigUint> = Vec::new();
        let mut s1 = vec![BigUint::one()];
        while r1.len() > 1 {
            let (q, r) = poly_divmod(&r0, &r1, p);
            let s = poly_sub(&s0, &poly_mul(&q, &s1, p), p);
            r0 = r1;
            r1 = r;
            s0 = s1;
            s1 = s;
            if r1.is_empty() {
                return None; // gcd non-trivial: modulus not irreducible
            }
        }
        let c_inv = r1[0].modinv(p)?;
        let s: Vec<BigUint> = s1.iter().map(|x| (x * &c_inv) % p).collect();
        Some(self.from_poly(&s))
    }

    /// A uniformly random element.
    pub fn random<R: Rng + ?Sized>(&self, rng: &mut R) -> FpkElem {
        (0..self.k)
            .map(|_| rng.gen_biguint_below(&self.p))
            .collect()
    }

    /// Whether `a` is a non-zero square.
    pub fn is_square(&self, a: &FpkElem) -> bool {
        if self.is_zero(a) {
            return false;
        }
        let e = (self.size() - 1u32) >> 1;
        self.pow(a, &e) == self.one()
    }

    /// A square root of `a`, or `None` for non-squares (Tonelli–Shanks
    /// in the group of order `p^k − 1`).
    pub fn sqrt<R: Rng + ?Sized>(&self, a: &FpkElem, rng: &mut R) -> Option<FpkElem> {
        if self.is_zero(a) {
            return Some(self.zero());
        }
        if !self.is_square(a) {
            return None;
        }
        let q_minus_1 = self.size() - 1u32;
        let s = q_minus_1.trailing_zeros().unwrap_or(0);
        let q = &q_minus_1 >> s;
        let one = self.one();
        let z = loop {
            let z = self.random(rng);
            if !self.is_zero(&z) && !self.is_square(&z) {
                break z;
            }
        };
        let mut m = s;
        let mut c = self.pow(&z, &q);
        let mut t = self.pow(a, &q);
        let mut r = self.pow(a, &((&q + 1u32) >> 1));
        while t != one {
            let mut i = 0u64;
            let mut t2 = t.clone();
            while t2 != one {
                t2 = self.sqr(&t2);
                i += 1;
            }
            let mut b = c.clone();
            for _ in 0..(m - i - 1) {
                b = self.sqr(&b);
            }
            m = i;
            c = self.sqr(&b);
            t = self.mul(&t, &c);
            r = self.mul(&r, &b);
        }
        Some(r)
    }
}

/// The multiplicative group `F_{p^k}*` as a [`DlpGroup`].
pub struct FpkMulGroup<'a>(pub &'a Fpk);

impl DlpGroup for FpkMulGroup<'_> {
    type Elem = FpkElem;

    fn identity(&self) -> FpkElem {
        self.0.one()
    }
    fn op(&self, a: &FpkElem, b: &FpkElem) -> FpkElem {
        self.0.mul(a, b)
    }
    fn invert(&self, a: &FpkElem) -> FpkElem {
        self.0.inv(a).expect("group elements are non-zero")
    }
    fn hash64(&self, a: &FpkElem) -> u64 {
        let mut h = 0x243f_6a88_85a3_08d3u64;
        for c in a {
            h = mix64(h ^ low_u64(c));
        }
        h
    }
    fn pow(&self, a: &FpkElem, k: &BigUint) -> FpkElem {
        self.0.pow(a, k)
    }
}

#[cfg(test)]
mod tests {
    use super::super::arith::seeded_rng;
    use super::*;

    #[test]
    fn field_axioms_small_extensions() {
        let mut rng = seeded_rng(3);
        for (p, k) in [
            (1_000_003u64, 1usize),
            (1_000_003, 2),
            (101, 3),
            (65_537, 4),
            (13, 6),
        ] {
            let p = BigUint::from(p);
            let f = Fpk::new(&p, k, &mut rng).unwrap();
            for _ in 0..10 {
                let a = f.random(&mut rng);
                let b = f.random(&mut rng);
                if f.is_zero(&a) {
                    continue;
                }
                let ai = f.inv(&a).unwrap();
                assert_eq!(f.mul(&a, &ai), f.one());
                assert_eq!(f.mul(&a, &b), f.mul(&b, &a));
                // Fermat: a^{p^k − 1} = 1.
                assert_eq!(f.pow(&a, &(f.size() - 1u32)), f.one());
                let sq = f.sqr(&b);
                if !f.is_zero(&sq) {
                    let r = f.sqrt(&sq, &mut rng).unwrap();
                    assert_eq!(f.sqr(&r), sq);
                }
            }
        }
    }

    #[test]
    fn reducible_modulus_rejected() {
        let p = BigUint::from(7u32);
        // t² − 1 = (t − 1)(t + 1)
        let f = [BigUint::from(6u32), BigUint::zero(), BigUint::one()];
        assert!(Fpk::with_modulus(&p, &f).is_none());
        // t² + 1 is irreducible mod 7 (7 ≡ 3 mod 4).
        let g = [BigUint::one(), BigUint::zero(), BigUint::one()];
        assert!(Fpk::with_modulus(&p, &g).is_some());
    }
}
