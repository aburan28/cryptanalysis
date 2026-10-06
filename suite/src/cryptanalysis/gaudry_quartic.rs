//! **Gaudry's index calculus at `k = 4`: the `S₅` solve, measured before
//! the pipeline.**
//!
//! Companion to `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md`
//! §11.16–11.17.  §11.16 derived everything the `k = 4` crossover with rho
//! depends on except `C₄`, the cost of one solve of the symmetrised `S₅`
//! system over `F_{p⁴}`, and bounded it below at `7.1·10¹⁰` `F_p`
//! multiplications from the characteristic polynomial alone.  This module
//! measures it, in the design of [`super::gaudry_cubic`] (§11.4–11.6):
//! Weil restriction of the symmetrised summation polynomial, a Macaulay
//! matrix at the regularity degree with Macaulay's row selection, forward
//! elimination, memoised normal forms, the multiplication matrix of `e₁`,
//! its characteristic polynomial and eigenvectors, and the split of the
//! quartic whose roots are the four abscissae.
//!
//! It builds nothing else of the pipeline — no relation collection, no
//! linear algebra — and every solve is checked against an independent
//! meet-in-the-middle decomposition oracle ([`mitm_decompositions`]).
//!
//! `p ≡ 1 (mod 4)` throughout: `F_{p⁴} = F_p[t]/(t⁴ − c)` needs it, since for
//! `p ≡ 3 (mod 4)` every binomial `t⁴ − c` is reducible.

use std::cell::Cell;
use std::collections::{BTreeSet, HashMap};
use std::time::Instant;

use rand::rngs::StdRng;
use rand::Rng;
use rayon::prelude::*;
use serde::Serialize;

use super::gaudry_cubic::{
    am, charpoly_mod_p, eigenvectors_mod_p, mm, sm, split_eigenspace, PolyRing, UPoly,
};
use super::residual_walk::{inv_mod, pow_mod};

// ── F_{p⁴} = F_p[t] / (t⁴ − c) ───────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Default, PartialOrd, Ord)]
pub struct E4(pub [u64; 4]);

impl E4 {
    pub const ZERO: E4 = E4([0; 4]);
    pub const ONE: E4 = E4([1, 0, 0, 0]);
    pub fn is_zero(&self) -> bool {
        self.0 == [0; 4]
    }
    pub fn in_fp(&self) -> bool {
        self.0[1] == 0 && self.0[2] == 0 && self.0[3] == 0
    }
}

/// `F_{p⁴}` with a multiplication counter in `F_p` multiplications, charged
/// by the convention [`super::gaudry_cubic::Fp3`] uses at `k = 3`.
#[derive(Clone)]
pub struct Fp4 {
    pub p: u64,
    pub c: u64,
    muls: Cell<u64>,
}

impl Fp4 {
    pub fn new(p: u64) -> Fp4 {
        assert!(
            p % 4 == 1,
            "t⁴ − c is irreducible over F_p only when p ≡ 1 (mod 4)"
        );
        let c = (2..p)
            .find(|&c| pow_mod(c, (p - 1) / 2, p) == p - 1)
            .expect("a non-square");
        Fp4 {
            p,
            c,
            muls: Cell::new(0),
        }
    }
    fn count(&self, k: u64) {
        self.muls.set(self.muls.get() + k);
    }
    pub fn muls(&self) -> u64 {
        self.muls.get()
    }
    pub fn reset_muls(&self) {
        self.muls.set(0);
    }
    pub fn from_fp(&self, x: u64) -> E4 {
        E4([x % self.p, 0, 0, 0])
    }
    pub fn add(&self, a: &E4, b: &E4) -> E4 {
        E4(core::array::from_fn(|i| am(a.0[i], b.0[i], self.p)))
    }
    pub fn sub(&self, a: &E4, b: &E4) -> E4 {
        E4(core::array::from_fn(|i| sm(a.0[i], b.0[i], self.p)))
    }
    pub fn neg(&self, a: &E4) -> E4 {
        E4(core::array::from_fn(|i| (self.p - a.0[i]) % self.p))
    }
    /// Multiplication by an element of `F_p`: four multiplications.
    pub fn scale(&self, a: &E4, k: u64) -> E4 {
        self.count(4);
        E4(core::array::from_fn(|i| mm(a.0[i], k, self.p)))
    }
    /// Schoolbook with `t⁴ = c`: 16 products and 3 reductions.
    pub fn mul(&self, a: &E4, b: &E4) -> E4 {
        let p = self.p;
        self.count(19);
        let mut d = [0u64; 7];
        for i in 0..4 {
            for j in 0..4 {
                d[i + j] = am(d[i + j], mm(a.0[i], b.0[j], p), p);
            }
        }
        E4([
            am(d[0], mm(self.c, d[4], p), p),
            am(d[1], mm(self.c, d[5], p), p),
            am(d[2], mm(self.c, d[6], p), p),
            d[3],
        ])
    }
    pub fn sq(&self, a: &E4) -> E4 {
        self.mul(a, a)
    }
    /// Inverse through the norm to `F_{p²} = F_p[s]/(s² − c)`, `s = t²`:
    /// with `a = A + B t`, `a⁻¹ = (A − B t) / (A² − s B²)`.  Twenty-four
    /// multiplications and one inversion in `F_p`, charged `16` as the count
    /// of `30` for `Fp3::inv` implies (it performs `14`): `40` in all, the
    /// figure §11.16's `97` per addition rests on.
    pub fn inv(&self, a: &E4) -> E4 {
        let p = self.p;
        let c = self.c;
        let (a0, a1, a2, a3) = (a.0[0], a.0[1], a.0[2], a.0[3]);
        let sqr = |x0: u64, x1: u64| -> (u64, u64) {
            let x01 = mm(x0, x1, p);
            (
                am(mm(x0, x0, p), mm(c, mm(x1, x1, p), p), p),
                am(x01, x01, p),
            )
        };
        let m2 = |x0: u64, x1: u64, y0: u64, y1: u64| -> (u64, u64) {
            (
                am(mm(x0, y0, p), mm(c, mm(x1, y1, p), p), p),
                am(mm(x0, y1, p), mm(x1, y0, p), p),
            )
        };
        let (aa0, aa1) = sqr(a0, a2);
        let (bb0, bb1) = sqr(a1, a3);
        // s·B² = c·bb1 + bb0·s.
        let (n0, n1) = (sm(aa0, mm(c, bb1, p), p), sm(aa1, bb0, p));
        let d = sm(mm(n0, n0, p), mm(c, mm(n1, n1, p), p), p);
        assert!(d != 0, "inverse of zero in F_p⁴");
        let dinv = inv_mod(d, p);
        let (i0, i1) = (mm(n0, dinv, p), (p - mm(n1, dinv, p)) % p);
        let (x0, x2) = m2(a0, a2, i0, i1);
        let (y0, y2) = m2(a1, a3, i0, i1);
        self.count(40);
        E4([x0, (p - y0) % p, x2, (p - y2) % p])
    }
    pub fn pow(&self, a: &E4, mut e: u128) -> E4 {
        let mut base = *a;
        let mut acc = E4::ONE;
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(&acc, &base);
            }
            base = self.sq(&base);
            e >>= 1;
        }
        acc
    }
    fn order(&self) -> u128 {
        (self.p as u128).pow(4) - 1
    }
    pub fn is_square(&self, a: &E4) -> bool {
        a.is_zero() || self.pow(a, self.order() / 2) == E4::ONE
    }
    pub fn random(&self, rng: &mut StdRng) -> E4 {
        E4(core::array::from_fn(|_| rng.gen_range(0..self.p)))
    }
    /// Tonelli–Shanks over `F_{p⁴}^×`.
    pub fn sqrt(&self, a: &E4, rng: &mut StdRng) -> Option<E4> {
        if a.is_zero() {
            return Some(E4::ZERO);
        }
        if !self.is_square(a) {
            return None;
        }
        let q1 = self.order();
        let s = q1.trailing_zeros();
        let odd = q1 >> s;
        let z = loop {
            let z = self.random(rng);
            if !z.is_zero() && !self.is_square(&z) {
                break z;
            }
        };
        let mut m = s;
        let mut cc = self.pow(&z, odd);
        let mut t = self.pow(a, odd);
        let mut r = self.pow(a, odd.div_ceil(2));
        while t != E4::ONE {
            let mut i = 0;
            let mut tt = t;
            while tt != E4::ONE {
                tt = self.sq(&tt);
                i += 1;
            }
            let mut b = cc;
            for _ in 0..(m - i - 1) {
                b = self.sq(&b);
            }
            m = i;
            cc = self.sq(&b);
            t = self.mul(&t, &cc);
            r = self.mul(&r, &b);
        }
        Some(r)
    }
}

// ── The curve `y² = x³ + a x + b` over `F_{p⁴}` ─────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Pt4 {
    pub x: E4,
    pub y: E4,
    pub inf: bool,
}

impl Pt4 {
    pub const INF: Pt4 = Pt4 {
        x: E4::ZERO,
        y: E4::ZERO,
        inf: true,
    };
}

#[derive(Clone)]
pub struct Curve4 {
    pub f: Fp4,
    pub a: E4,
    pub b: E4,
    /// Group operations (additions and doublings) performed.
    ops: Cell<u64>,
}

impl Curve4 {
    /// Coefficients drawn outside `F_{p²}` so that the curve is not a
    /// twist of one defined over a subfield.
    pub fn random(p: u64, rng: &mut StdRng) -> Curve4 {
        let f = Fp4::new(p);
        loop {
            let a = f.random(rng);
            let b = f.random(rng);
            if a.0[1] == 0 && a.0[3] == 0 || b.0[1] == 0 && b.0[3] == 0 {
                continue;
            }
            let a3 = f.mul(&f.sq(&a), &a);
            let disc = f.add(&f.scale(&a3, 4), &f.scale(&f.sq(&b), 27));
            if !disc.is_zero() {
                return Curve4 {
                    f,
                    a,
                    b,
                    ops: Cell::new(0),
                };
            }
        }
    }
    pub fn rhs(&self, x: &E4) -> E4 {
        let f = &self.f;
        f.add(&f.mul(&f.add(&f.sq(x), &self.a), x), &self.b)
    }
    pub fn lift_x(&self, x: &E4, rng: &mut StdRng) -> Option<Pt4> {
        let y = self.f.sqrt(&self.rhs(x), rng)?;
        Some(Pt4 {
            x: *x,
            y,
            inf: false,
        })
    }
    pub fn on_curve(&self, pt: &Pt4) -> bool {
        pt.inf || self.f.sq(&pt.y) == self.rhs(&pt.x)
    }
    pub fn neg(&self, pt: &Pt4) -> Pt4 {
        if pt.inf {
            return *pt;
        }
        Pt4 {
            x: pt.x,
            y: self.f.neg(&pt.y),
            inf: false,
        }
    }
    /// Affine addition: one inversion and three multiplications for
    /// distinct points, the decomposition behind §11.16's `c_add`.
    pub fn add(&self, p1: &Pt4, p2: &Pt4) -> Pt4 {
        let f = &self.f;
        self.ops.set(self.ops.get() + 1);
        if p1.inf {
            return *p2;
        }
        if p2.inf {
            return *p1;
        }
        let lambda = if p1.x == p2.x {
            if p1.y != p2.y || p1.y.is_zero() {
                return Pt4::INF;
            }
            // (3x² + a) / 2y
            let x2 = f.sq(&p1.x);
            let num = f.add(&f.add(&f.add(&x2, &x2), &x2), &self.a);
            f.mul(&num, &f.inv(&f.add(&p1.y, &p1.y)))
        } else {
            f.mul(&f.sub(&p2.y, &p1.y), &f.inv(&f.sub(&p2.x, &p1.x)))
        };
        let x3 = f.sub(&f.sub(&f.sq(&lambda), &p1.x), &p2.x);
        let y3 = f.sub(&f.mul(&lambda, &f.sub(&p1.x, &x3)), &p1.y);
        Pt4 {
            x: x3,
            y: y3,
            inf: false,
        }
    }
    pub fn sub(&self, p1: &Pt4, p2: &Pt4) -> Pt4 {
        self.add(p1, &self.neg(p2))
    }
    pub fn ops(&self) -> u64 {
        self.ops.get()
    }
    /// A fresh curve with its own counters, for a worker thread.
    pub fn with_params(p: u64, a: E4, b: E4) -> Curve4 {
        Curve4 {
            f: Fp4::new(p),
            a,
            b,
            ops: Cell::new(0),
        }
    }
    pub fn reset_ops(&self) {
        self.ops.set(0);
    }
    /// Double-and-add.
    pub fn mul(&self, pt: &Pt4, mut k: u64) -> Pt4 {
        let mut acc = Pt4::INF;
        let mut base = *pt;
        while k > 0 {
            if k & 1 == 1 {
                acc = self.add(&acc, &base);
            }
            base = self.add(&base, &base);
            k >>= 1;
        }
        acc
    }
}

// ── Summation polynomials, numerically ───────────────────────────────────

/// Univariate polynomials over `F_{p⁴}`, low to high.
fn poly_mul(f: &Fp4, a: &[E4], b: &[E4]) -> Vec<E4> {
    let mut out = vec![E4::ZERO; a.len() + b.len() - 1];
    for (i, x) in a.iter().enumerate() {
        for (j, y) in b.iter().enumerate() {
            out[i + j] = f.add(&out[i + j], &f.mul(x, y));
        }
    }
    out
}
fn poly_sub(f: &Fp4, a: &[E4], b: &[E4]) -> Vec<E4> {
    let n = a.len().max(b.len());
    (0..n)
        .map(|i| f.sub(a.get(i).unwrap_or(&E4::ZERO), b.get(i).unwrap_or(&E4::ZERO)))
        .collect()
}
fn poly_scale(f: &Fp4, a: &[E4], k: &E4) -> Vec<E4> {
    a.iter().map(|x| f.mul(x, k)).collect()
}

/// Determinant over `F_{p⁴}` by Gaussian elimination.
fn det4(f: &Fp4, mut m: Vec<Vec<E4>>) -> E4 {
    let n = m.len();
    let mut det = E4::ONE;
    for c in 0..n {
        let Some(r) = (c..n).find(|&r| !m[r][c].is_zero()) else {
            return E4::ZERO;
        };
        if r != c {
            m.swap(r, c);
            det = f.neg(&det);
        }
        det = f.mul(&det, &m[c][c]);
        let inv = f.inv(&m[c][c]);
        for r in (c + 1)..n {
            if m[r][c].is_zero() {
                continue;
            }
            let k = f.mul(&m[r][c], &inv);
            for j in c..n {
                let v = f.mul(&k, &m[c][j]);
                m[r][j] = f.sub(&m[r][j], &v);
            }
        }
    }
    det
}

impl Curve4 {
    /// `S₃(x₁, x₂, X)` as a polynomial in `X` (Semaev):
    /// `(x₁ − x₂)² X² − 2((x₁ + x₂)(x₁x₂ + a) + 2b) X + (x₁x₂ − a)² − 4b(x₁ + x₂)`.
    fn s3_in_last(&self, x1: &E4, x2: &E4) -> [E4; 3] {
        let f = &self.f;
        let s = f.add(x1, x2);
        let pr = f.mul(x1, x2);
        let two_b = f.add(&self.b, &self.b);
        let t = f.add(&f.mul(&s, &f.add(&pr, &self.a)), &two_b);
        let c1 = f.neg(&f.add(&t, &t));
        let u = f.sub(&pr, &self.a);
        let c0 = f.sub(&f.sq(&u), &f.mul(&f.add(&two_b, &two_b), &s));
        [c0, c1, f.sq(&f.sub(x1, x2))]
    }

    /// `S₄(x₃, x₄, x₅, Y)` as a polynomial in `Y`, of degree ≤ 4:
    /// `Res_Z(S₃(x₃, x₄, Z), S₃(x₅, Y, Z))`, with the resultant of two
    /// quadratics `(a₂b₀ − a₀b₂)² − (a₂b₁ − a₁b₂)(a₁b₀ − a₀b₁)`.
    fn s4_in_last(&self, x3: &E4, x4: &E4, x5: &E4) -> Vec<E4> {
        let f = &self.f;
        let [a0, a1, a2] = self.s3_in_last(x3, x4);
        let (a, b) = (&self.a, &self.b);
        let x5s = f.sq(x5);
        let two = |v: &E4| f.add(v, v);
        let four = |v: &E4| two(&two(v));
        // S₃(x₅, Y, Z) = b₂(Y) Z² + b₁(Y) Z + b₀(Y).
        let b2 = vec![x5s, f.neg(&two(x5)), E4::ONE];
        let b1 = vec![
            f.neg(&two(&f.add(&f.mul(a, x5), &two(b)))),
            f.neg(&two(&f.add(&x5s, a))),
            f.neg(&two(x5)),
        ];
        let b0 = vec![
            f.sub(&f.sq(a), &four(&f.mul(b, x5))),
            f.neg(&f.add(&two(&f.mul(a, x5)), &four(b))),
            x5s,
        ];
        let p1 = poly_sub(f, &poly_scale(f, &b0, &a2), &poly_scale(f, &b2, &a0));
        let p2 = poly_sub(f, &poly_scale(f, &b1, &a2), &poly_scale(f, &b2, &a1));
        let p3 = poly_sub(f, &poly_scale(f, &b0, &a1), &poly_scale(f, &b1, &a0));
        poly_sub(f, &poly_mul(f, &p1, &p1), &poly_mul(f, &p2, &p3))
    }

    /// `S₅(x₁, …, x₅) = Res_Y(S₃(x₁, x₂, Y), S₄(x₃, x₄, x₅, Y))`, the
    /// recursive definition, as the determinant of the `6 × 6` Sylvester
    /// matrix at formal degrees `2` and `4`.
    pub fn s5(&self, x: &[E4; 5]) -> E4 {
        let f = &self.f;
        let a = self.s3_in_last(&x[0], &x[1]);
        let mut b = self.s4_in_last(&x[2], &x[3], &x[4]);
        b.resize(5, E4::ZERO);
        let mut m = vec![vec![E4::ZERO; 6]; 6];
        for i in 0..4 {
            for k in 0..3 {
                m[i][i + k] = a[2 - k];
            }
        }
        for i in 0..2 {
            for k in 0..5 {
                m[4 + i][i + k] = b[4 - k];
            }
        }
        det4(f, m)
    }
}

// ── The symmetrised S₅, by interpolation ──────────────────────────────────

/// Monomials `e₁^a e₂^b e₃^c e₄^d` of total degree `≤ d`.
fn exponents4(d: u8) -> Vec<[u8; 4]> {
    let mut v = Vec::new();
    for a in 0..=d {
        for b in 0..=(d - a) {
            for c in 0..=(d - a - b) {
                for e in 0..=(d - a - b - c) {
                    v.push([a, b, c, e]);
                }
            }
        }
    }
    v
}

/// `S₅(x₁, x₂, x₃, x₄, x_R) = H(e₁, e₂, e₃, e₄, x_R)`, with `H` of total
/// degree `≤ 8` in the elementary symmetric `e`'s and degree `≤ 8` in `x_R`:
/// `495 · 9` coefficients in `F_{p⁴}`.  Found by interpolation rather than
/// symbolic symmetrisation — `S₅` evaluated as a resultant at `495` random
/// points and the `495 × 495` system solved once for all nine powers of
/// `x_R` — and then checked against fresh evaluations.
pub struct SymmetrisedS5 {
    pub monos: Vec<[u8; 4]>,
    pub coef: Vec<[E4; 9]>,
    /// `F_p` multiplications spent building it (once per curve).
    pub precompute_muls: u64,
}

fn elementary(f: &Fp4, x: &[E4; 4]) -> [E4; 4] {
    let e1 = f.add(&f.add(&x[0], &x[1]), &f.add(&x[2], &x[3]));
    let mut e2 = E4::ZERO;
    let mut e3 = E4::ZERO;
    for i in 0..4 {
        for j in (i + 1)..4 {
            let xij = f.mul(&x[i], &x[j]);
            e2 = f.add(&e2, &xij);
            for k in (j + 1)..4 {
                e3 = f.add(&e3, &f.mul(&xij, &x[k]));
            }
        }
    }
    let e4 = f.mul(&f.mul(&x[0], &x[1]), &f.mul(&x[2], &x[3]));
    [e1, e2, e3, e4]
}

fn mono_values(f: &Fp4, e: &[E4; 4], monos: &[[u8; 4]]) -> Vec<E4> {
    let mut pows = [[E4::ONE; 9]; 4];
    for i in 0..4 {
        for k in 1..9 {
            pows[i][k] = f.mul(&pows[i][k - 1], &e[i]);
        }
    }
    monos
        .iter()
        .map(|m| {
            f.mul(
                &f.mul(&pows[0][m[0] as usize], &pows[1][m[1] as usize]),
                &f.mul(&pows[2][m[2] as usize], &pows[3][m[3] as usize]),
            )
        })
        .collect()
}

impl SymmetrisedS5 {
    /// The nine coefficients of `S₅(x₁, …, x₄, X)` in `X`, from values at
    /// `X = 0, …, 8` through the inverse Vandermonde matrix over `F_p`.
    fn coefficients_in_last(curve: &Curve4, x: &[E4; 4], vinv: &[[u64; 9]; 9]) -> [E4; 9] {
        let f = &curve.f;
        let vals: Vec<E4> = (0..9u64)
            .map(|k| curve.s5(&[x[0], x[1], x[2], x[3], f.from_fp(k)]))
            .collect();
        core::array::from_fn(|j| {
            vals.iter()
                .enumerate()
                .fold(E4::ZERO, |acc, (k, v)| f.add(&acc, &f.scale(v, vinv[j][k])))
        })
    }

    pub fn precompute(curve: &Curve4, rng: &mut StdRng) -> SymmetrisedS5 {
        let f = &curve.f;
        let p = f.p;
        let before = f.muls();
        // Inverse Vandermonde at the nodes 0..8, over F_p.
        let vinv: [[u64; 9]; 9] = {
            let mut m: Vec<Vec<u64>> = (0..9u64)
                .map(|k| {
                    let mut row: Vec<u64> = (0..9).map(|j| pow_mod(k, j, p)).collect();
                    row.extend((0..9).map(|i| u64::from(i == k)));
                    row
                })
                .collect();
            let mut scratch = 0u64;
            super::gaudry_cubic::rref_mod_p(&mut m, p, &mut scratch);
            // Row j of the reduced matrix is [I | V⁻¹]; V maps coefficients to
            // values, so coefficient j = Σ_k V⁻¹[j][k] · value_k.
            core::array::from_fn(|j| core::array::from_fn(|k| m[j][9 + k]))
        };
        let monos = exponents4(8);
        let n = monos.len();
        loop {
            // Augmented system [V | C] over F_{p⁴}: one row per sample.
            let mut sys: Vec<Vec<E4>> = Vec::with_capacity(n);
            for _ in 0..n {
                let x: [E4; 4] = core::array::from_fn(|_| f.random(rng));
                let e = elementary(f, &x);
                let mut row = mono_values(f, &e, &monos);
                row.extend(Self::coefficients_in_last(curve, &x, &vinv));
                sys.push(row);
            }
            // Gauss–Jordan.
            let mut ok = true;
            for c in 0..n {
                let Some(r) = (c..n).find(|&r| !sys[r][c].is_zero()) else {
                    ok = false;
                    break;
                };
                sys.swap(r, c);
                let inv = f.inv(&sys[c][c]);
                let pivot: Vec<E4> = sys[c].iter().map(|v| f.mul(v, &inv)).collect();
                sys[c] = pivot.clone();
                sys.par_iter_mut().enumerate().for_each(|(r, row)| {
                    if r == c || row[c].is_zero() {
                        return;
                    }
                    // A local field for the parallel rows: the counter is
                    // charged below, from the operation count.
                    let fl = Fp4::new(p);
                    let k = row[c];
                    for j in c..row.len() {
                        if !pivot[j].is_zero() {
                            let v = fl.mul(&k, &pivot[j]);
                            row[j] = fl.sub(&row[j], &v);
                        }
                    }
                });
                f.count(19 * (n as u64) * (n + 9 - c) as u64);
            }
            if !ok {
                continue;
            }
            let coef: Vec<[E4; 9]> = (0..n)
                .map(|r| core::array::from_fn(|j| sys[r][n + j]))
                .collect();
            let pre = SymmetrisedS5 {
                monos: monos.clone(),
                coef,
                precompute_muls: 0,
            };
            // Check against fresh evaluations of the resultant.
            let good = (0..8).all(|_| {
                let x: [E4; 4] = core::array::from_fn(|_| f.random(rng));
                let want = Self::coefficients_in_last(curve, &x, &vinv);
                let e = elementary(f, &x);
                let mv = mono_values(f, &e, &pre.monos);
                (0..9).all(|j| {
                    let got = mv
                        .iter()
                        .zip(&pre.coef)
                        .fold(E4::ZERO, |acc, (m, c)| f.add(&acc, &f.mul(m, &c[j])));
                    got == want[j]
                })
            });
            assert!(good, "the symmetrised S₅ does not reproduce the resultant");
            return SymmetrisedS5 {
                precompute_muls: f.muls() - before,
                ..pre
            };
        }
    }

    /// The four `F_p`-components of `H(e₁, …, e₄, x_R)`, as sparse maps
    /// over the monomials of total degree `≤ 8`.
    pub fn weil_restrict(&self, f: &Fp4, x_r: &E4) -> [HashMap<[u8; 4], u64>; 4] {
        let mut pows = [E4::ONE; 9];
        for k in 1..9 {
            pows[k] = f.mul(&pows[k - 1], x_r);
        }
        let mut out: [HashMap<[u8; 4], u64>; 4] = Default::default();
        for (m, c) in self.monos.iter().zip(&self.coef) {
            let v = (0..9).fold(E4::ZERO, |acc, j| f.add(&acc, &f.mul(&c[j], &pows[j])));
            for (i, comp) in out.iter_mut().enumerate() {
                if v.0[i] != 0 {
                    comp.insert(*m, v.0[i]);
                }
            }
        }
        out
    }
}

// ── Monomials in four variables ───────────────────────────────────────────

fn deg4(m: &[u8; 4]) -> u16 {
    m.iter().map(|&x| x as u16).sum()
}

fn grevlex_cmp4(a: &[u8; 4], b: &[u8; 4]) -> std::cmp::Ordering {
    let (da, db) = (deg4(a), deg4(b));
    if da != db {
        return da.cmp(&db);
    }
    for i in (0..4).rev() {
        if a[i] != b[i] {
            return b[i].cmp(&a[i]);
        }
    }
    std::cmp::Ordering::Equal
}

/// Monomials of total degree `≤ d` in four variables, grevlex descending.
fn monomials4_desc(d: u8) -> Vec<[u8; 4]> {
    let mut v = exponents4(d);
    v.sort_by(|x, y| grevlex_cmp4(y, x));
    v
}

fn leading_monomial4(f: &HashMap<[u8; 4], u64>) -> Option<[u8; 4]> {
    f.iter()
        .filter(|(_, &c)| c != 0)
        .map(|(m, _)| *m)
        .max_by(grevlex_cmp4)
}

/// As `gaudry_cubic`'s `triangularise_leads`, for four components.
fn triangularise_leads4(
    comps: &[HashMap<[u8; 4], u64>],
    p: u64,
    muls: &mut u64,
) -> (Vec<HashMap<[u8; 4], u64>>, Vec<Option<[u8; 4]>>) {
    let mut fs: Vec<HashMap<[u8; 4], u64>> = comps.to_vec();
    for _round in 0..16 {
        fs.sort_by(|a, b| match (leading_monomial4(a), leading_monomial4(b)) {
            (Some(x), Some(y)) => grevlex_cmp4(&y, &x),
            (Some(_), None) => std::cmp::Ordering::Less,
            (None, Some(_)) => std::cmp::Ordering::Greater,
            (None, None) => std::cmp::Ordering::Equal,
        });
        let mut changed = false;
        for i in 1..fs.len() {
            let (Some(li), Some(lj)) = (leading_monomial4(&fs[i]), leading_monomial4(&fs[i - 1]))
            else {
                continue;
            };
            if li == lj {
                let k = mm(fs[i][&li], inv_mod(fs[i - 1][&lj], p), p);
                let prev = fs[i - 1].clone();
                for (&m, &c) in &prev {
                    let e = fs[i].entry(m).or_insert(0);
                    *e = sm(*e, mm(k, c, p), p);
                    *muls += 1;
                }
                fs[i].retain(|_, c| *c != 0);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    let leads = fs.iter().map(leading_monomial4).collect();
    (fs, leads)
}

// ── Arithmetic on u16 rows ────────────────────────────────────────────────

/// `row ← row − f·piv` elementwise mod `P`, vectorisable when `P` is a
/// compile-time constant; the solver's matrices are dense `u16` rows.
#[inline(always)]
fn axpy_const<const P: u32>(row: &mut [u16], piv: &[u16], f: u32) {
    let nf = P - f;
    for (r, &v) in row.iter_mut().zip(piv) {
        *r = ((*r as u32 + nf * v as u32) % P) as u16;
    }
}

fn axpy_dyn(row: &mut [u16], piv: &[u16], f: u32, p: u32) {
    let nf = p - f;
    for (r, &v) in row.iter_mut().zip(piv) {
        *r = ((*r as u32 + nf * v as u32) % p) as u16;
    }
}

fn axpy(row: &mut [u16], piv: &[u16], f: u32, p: u32) {
    match p {
        269 => axpy_const::<269>(row, piv, f),
        257 => axpy_const::<257>(row, piv, f),
        _ => axpy_dyn(row, piv, f, p),
    }
}

// ── The solve ─────────────────────────────────────────────────────────────

/// Everything one solve cost, by phase, in `F_p` multiplications counted as
/// `gaudry_cubic` counts them: only multiplications actually performed in
/// the elimination and the normal forms, the characteristic polynomial and
/// eigenvectors through the same routines.
#[derive(Clone, Debug, Default, Serialize)]
pub struct QuarticSolve {
    pub equation_degree: u8,
    pub macaulay_degree: u8,
    pub rows: usize,
    pub cols: usize,
    pub pivots: usize,
    pub zero_rows: usize,
    pub dim: usize,
    pub reached_pivots: usize,
    pub weil_muls: u64,
    pub triangularise_muls: u64,
    pub echelon_muls: u64,
    pub nf_muls: u64,
    pub charpoly_muls: u64,
    pub roots_muls: u64,
    pub eigenvector_muls: u64,
    pub verify_muls: u64,
    pub split_muls: u64,
    pub total_muls: u64,
    pub rational_eigenvalues: usize,
    pub degenerate_eigenspaces: usize,
    pub e_solutions: usize,
    pub build_ms: f64,
    pub echelon_ms: f64,
    pub nf_ms: f64,
    pub charpoly_ms: f64,
    pub eigen_ms: f64,
    pub total_ms: f64,
    pub outcome: String,
}

impl QuarticSolve {
    fn close(&mut self) {
        self.total_muls = self.weil_muls
            + self.triangularise_muls
            + self.echelon_muls
            + self.nf_muls
            + self.charpoly_muls
            + self.roots_muls
            + self.eigenvector_muls
            + self.verify_muls
            + self.split_muls;
    }
}

struct Echelon {
    rows: Vec<Vec<u16>>,
    pivot_row: Vec<u32>,
    zero_rows: usize,
}

/// Forward elimination by leading column.  Every unused row has zeros
/// left of its lead, so the rows with a nonzero entry in column `c` are
/// exactly those whose lead is `c`: the lowest-indexed becomes the pivot,
/// is normalised, and is subtracted from the rest, which then move to the
/// bucket of their new lead.  The same operations as a column-by-column
/// elimination, without scanning rows that are already zero there;
/// `muls` counts the nonzero entries of each pivot row once per row it is
/// subtracted from, and once for its normalisation.
fn echelon_by_lead(mut rows: Vec<Vec<u16>>, p: u32, muls: &mut u64, debug: bool) -> Echelon {
    let ncols = rows.first().map_or(0, |r| r.len());
    let mut buckets: Vec<Vec<u32>> = vec![Vec::new(); ncols];
    let mut zero_rows = 0usize;
    for (r, row) in rows.iter().enumerate() {
        match row.iter().position(|&x| x != 0) {
            Some(c) => buckets[c].push(r as u32),
            None => zero_rows += 1,
        }
    }
    let mut pivot_row = vec![u32::MAX; ncols];
    let start = Instant::now();
    let mut npiv = 0usize;
    for c in 0..ncols {
        let mut b = std::mem::take(&mut buckets[c]);
        if b.is_empty() {
            continue;
        }
        b.sort_unstable();
        let pr = b[0] as usize;
        let mut piv = std::mem::take(&mut rows[pr]);
        let inv = inv_mod(piv[c] as u64, p as u64) as u32;
        let mut nz: Vec<u32> = Vec::new();
        for j in c..ncols {
            if piv[j] != 0 {
                piv[j] = ((piv[j] as u32 * inv) % p) as u16;
                nz.push(j as u32);
            }
        }
        *muls += nz.len() as u64;
        let dense = nz.len() * 8 > ncols - c;
        let mut others: Vec<(u32, Vec<u16>, Option<usize>)> = b[1..]
            .iter()
            .map(|&r| (r, std::mem::take(&mut rows[r as usize]), None))
            .collect();
        *muls += (others.len() * nz.len()) as u64;
        others.par_iter_mut().for_each(|(_, row, lead)| {
            let f = row[c] as u32;
            if dense {
                axpy(&mut row[c..], &piv[c..], f, p);
            } else {
                let nf = p - f;
                for &j in &nz {
                    let j = j as usize;
                    row[j] = ((row[j] as u32 + nf * piv[j] as u32) % p) as u16;
                }
            }
            *lead = row[c + 1..].iter().position(|&x| x != 0).map(|k| k + c + 1);
        });
        for (r, row, lead) in others {
            rows[r as usize] = row;
            match lead {
                Some(l) => buckets[l].push(r),
                None => zero_rows += 1,
            }
        }
        rows[pr] = piv;
        pivot_row[c] = pr as u32;
        npiv += 1;
        if debug && npiv.is_multiple_of(2000) {
            eprintln!(
                "    echelon: {npiv} pivots at column {c}/{ncols}, {:.3e} muls, {:.0} s",
                *muls as f64,
                start.elapsed().as_secs_f64()
            );
        }
    }
    Echelon {
        rows,
        pivot_row,
        zero_rows,
    }
}

/// Memoised normal forms over the standard monomials, computed for a set
/// of target columns by one sweep from the right over the pivots they
/// reach — iteratively, since a chain of pivots can be tens of thousands
/// deep.
struct NormalForms4<'a> {
    ech: &'a Echelon,
    is_std: Vec<bool>,
    std_index: Vec<u32>,
    dim: usize,
    p: u32,
    memo: Vec<Option<(Vec<u16>, u64)>>,
    reached: usize,
}

impl<'a> NormalForms4<'a> {
    /// Make every column in `targets` resolvable.  `Err(c)` names a column
    /// reached that is neither standard nor a pivot.
    fn ensure(&mut self, targets: &[usize], muls: &mut u64) -> Result<(), usize> {
        let ncols = self.is_std.len();
        let mut need: Vec<usize> = Vec::new();
        let mut seen = vec![false; ncols];
        let mut stack: Vec<usize> = Vec::new();
        for &t in targets {
            if !self.is_std[t] && self.memo[t].is_none() && !seen[t] {
                seen[t] = true;
                stack.push(t);
            }
        }
        while let Some(c) = stack.pop() {
            let pr = self.ech.pivot_row[c];
            if pr == u32::MAX {
                return Err(c);
            }
            need.push(c);
            let row = &self.ech.rows[pr as usize];
            for j in (c + 1)..ncols {
                if row[j] != 0 && !self.is_std[j] && self.memo[j].is_none() && !seen[j] {
                    seen[j] = true;
                    stack.push(j);
                }
            }
        }
        need.sort_unstable_by(|a, b| b.cmp(a));
        let p = self.p;
        for c in need {
            let row = &self.ech.rows[self.ech.pivot_row[c] as usize];
            let mut v = vec![0u16; self.dim];
            for j in (c + 1)..ncols {
                let a = row[j] as u32;
                if a == 0 {
                    continue;
                }
                if self.is_std[j] {
                    let i = self.std_index[j] as usize;
                    v[i] = ((v[i] as u32 + p - a) % p) as u16;
                } else {
                    let (w, nnz) = self.memo[j].as_ref().expect("computed right to left");
                    axpy(&mut v, w, a, p);
                    *muls += *nnz;
                }
            }
            let nnz = v.iter().filter(|&&x| x != 0).count() as u64;
            self.memo[c] = Some((v, nnz));
            self.reached += 1;
        }
        Ok(())
    }

    fn vector(&self, c: usize) -> Vec<u64> {
        if self.is_std[c] {
            let mut v = vec![0u64; self.dim];
            v[self.std_index[c] as usize] = 1;
            v
        } else {
            let (w, _) = self.memo[c].as_ref().expect("ensured");
            w.iter().map(|&x| x as u64).collect()
        }
    }
}

fn eval4(comp: &HashMap<[u8; 4], u64>, e: &[u64; 4], p: u64, muls: &mut u64) -> u64 {
    let mut acc = 0u64;
    for (m, &c) in comp {
        let mut t = c;
        for k in 0..4 {
            for _ in 0..m[k] {
                t = mm(t, e[k], p);
                *muls += 1;
            }
        }
        acc = am(acc, t, p);
    }
    acc
}

/// All `F_p`-rational solutions of four polynomial equations in four
/// unknowns, each of total degree `equation_degree`, through a Macaulay
/// matrix at `macaulay_degree` (the regularity bound `4(d − 1) + 1` for a
/// generic system) and the eigenvectors of the multiplication matrix of
/// the first unknown.  `None` when the degree cut does not close the
/// quotient; every returned solution satisfies all four equations.
pub fn solve_system4(
    comps: &[HashMap<[u8; 4], u64>],
    equation_degree: u8,
    macaulay_degree: u8,
    p: u64,
    rng: &mut StdRng,
    st: &mut QuarticSolve,
    debug: bool,
) -> Option<Vec<[u64; 4]>> {
    assert!(p < 1 << 15, "rows are u16 and products must fit u32");
    let t0 = Instant::now();
    st.equation_degree = equation_degree;
    st.macaulay_degree = macaulay_degree;
    let cols = monomials4_desc(macaulay_degree);
    let col_index: HashMap<[u8; 4], usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();
    let shifts = monomials4_desc(macaulay_degree - equation_degree);
    let mut tri = 0u64;
    let (comps, leads) = triangularise_leads4(comps, p, &mut tri);
    st.triangularise_muls += tri;
    let divides = |lm: &[u8; 4], m: &[u8; 4]| (0..4).all(|k| lm[k] <= m[k]);
    let mut rows: Vec<Vec<u16>> = Vec::new();
    for (i, comp) in comps.iter().enumerate() {
        for sh in &shifts {
            if leads
                .iter()
                .take(i)
                .any(|lm| lm.is_some_and(|lm| divides(&lm, sh)))
            {
                continue;
            }
            let mut row = vec![0u16; cols.len()];
            for (&e, &c) in comp {
                let m = [e[0] + sh[0], e[1] + sh[1], e[2] + sh[2], e[3] + sh[3]];
                let ci = col_index[&m];
                row[ci] = am(row[ci] as u64, c, p) as u16;
            }
            rows.push(row);
        }
    }
    st.rows = rows.len();
    st.cols = cols.len();
    st.build_ms = t0.elapsed().as_secs_f64() * 1e3;
    if debug {
        eprintln!(
            "  macaulay degree {macaulay_degree}: {} rows × {} columns ({:.2} GB), leads {leads:?}",
            st.rows,
            st.cols,
            (st.rows * st.cols * 2) as f64 / 1e9
        );
    }
    let t1 = Instant::now();
    let mut ech_muls = 0u64;
    let ech = echelon_by_lead(rows, p as u32, &mut ech_muls, debug);
    st.echelon_muls += ech_muls;
    st.echelon_ms = t1.elapsed().as_secs_f64() * 1e3;
    st.zero_rows = ech.zero_rows;
    st.pivots = ech.pivot_row.iter().filter(|&&r| r != u32::MAX).count();
    let is_std: Vec<bool> = (0..cols.len())
        .map(|c| ech.pivot_row[c] == u32::MAX && deg4(&cols[c]) < macaulay_degree as u16)
        .collect();
    let standard: Vec<usize> = (0..cols.len()).filter(|&c| is_std[c]).collect();
    let dim = standard.len();
    st.dim = dim;
    let mut std_index = vec![u32::MAX; cols.len()];
    for (i, &c) in standard.iter().enumerate() {
        std_index[c] = i as u32;
    }
    if debug {
        eprintln!(
            "  echelon: {} pivots, {} zero rows, dim {dim}, {:.3e} muls, {:.0} s",
            st.pivots,
            st.zero_rows,
            st.echelon_muls as f64,
            st.echelon_ms / 1e3
        );
    }
    let find = |m: [u8; 4]| col_index.get(&m).copied();
    let (Some(c0), Some(c1), Some(c2), Some(c3), Some(c4)) = (
        find([0, 0, 0, 0]),
        find([1, 0, 0, 0]),
        find([0, 1, 0, 0]),
        find([0, 0, 1, 0]),
        find([0, 0, 0, 1]),
    ) else {
        st.outcome = "low-degree monomials missing".into();
        return None;
    };
    if [c0, c1, c2, c3, c4].iter().any(|&c| !is_std[c]) {
        st.outcome = "1 or a variable is not standard".into();
        return None;
    }
    let idx = [c0, c1, c2, c3, c4].map(|c| std_index[c] as usize);
    let t2 = Instant::now();
    let mut nfs = NormalForms4 {
        ech: &ech,
        is_std,
        std_index,
        dim,
        p: p as u32,
        memo: vec![None; cols.len()],
        reached: 0,
    };
    // Multiplication matrix of a variable: column b ↦ NF(var · b).
    let mult_matrix =
        |nfs: &mut NormalForms4, var: usize, muls: &mut u64| -> Option<Vec<Vec<u64>>> {
            let mut targets = Vec::with_capacity(dim);
            for &bc in &standard {
                let mut m = cols[bc];
                m[var] += 1;
                targets.push(*col_index.get(&m)?);
            }
            nfs.ensure(&targets, muls).ok()?;
            let mut out = vec![vec![0u64; dim]; dim];
            for (bi, &tc) in targets.iter().enumerate() {
                for (ri, v) in nfs.vector(tc).into_iter().enumerate() {
                    out[ri][bi] = v;
                }
            }
            Some(out)
        };
    let mut nf_muls = 0u64;
    let m_e1 = mult_matrix(&mut nfs, 0, &mut nf_muls);
    st.nf_muls += nf_muls;
    st.nf_ms = t2.elapsed().as_secs_f64() * 1e3;
    st.reached_pivots = nfs.reached;
    let Some(m_e1) = m_e1 else {
        st.outcome = "border unreachable at this degree".into();
        return None;
    };
    if debug {
        eprintln!(
            "  normal forms: {} pivots reached, {:.3e} muls, {:.0} s",
            st.reached_pivots,
            st.nf_muls as f64,
            st.nf_ms / 1e3
        );
    }
    let t3 = Instant::now();
    let mut cp_muls = 0u64;
    let cp = charpoly_mod_p(&m_e1, p, &mut cp_muls);
    st.charpoly_muls += cp_muls;
    st.charpoly_ms = t3.elapsed().as_secs_f64() * 1e3;
    let t4 = Instant::now();
    let ring = PolyRing::new(p);
    let lambdas = ring.roots(&cp, rng);
    st.roots_muls += ring.muls.get();
    st.rational_eigenvalues = lambdas.len();
    let mut mt = vec![vec![0u64; dim]; dim];
    for i in 0..dim {
        for j in 0..dim {
            mt[j][i] = m_e1[i][j];
        }
    }
    drop(m_e1);
    let mut others: [Option<Vec<Vec<u64>>>; 3] = [None, None, None];
    let mut out = Vec::new();
    for lam in lambdas {
        let mut ev = 0u64;
        let mut ker = eigenvectors_mod_p(&mt, lam, p, &mut ev);
        if ker.len() > 1 {
            st.degenerate_eigenspaces += 1;
            for k in 0..3 {
                if ker.len() <= 1 {
                    break;
                }
                if others[k].is_none() {
                    let mut nm = 0u64;
                    others[k] = mult_matrix(&mut nfs, k + 1, &mut nm);
                    st.nf_muls += nm;
                }
                let Some(mv) = &others[k] else {
                    break;
                };
                ker = split_eigenspace(&ker, mv, p, rng, &mut ev);
            }
        }
        st.eigenvector_muls += ev;
        for w in &ker {
            if w[idx[0]] == 0 {
                continue;
            }
            let inv = inv_mod(w[idx[0]], p);
            let e: [u64; 4] = core::array::from_fn(|k| mm(w[idx[k + 1]], inv, p));
            if e[0] != lam {
                continue;
            }
            let mut vm = 0u64;
            let ok = comps.iter().all(|c| eval4(c, &e, p, &mut vm) == 0);
            st.verify_muls += vm;
            if ok {
                out.push(e);
            }
        }
    }
    st.eigen_ms = t4.elapsed().as_secs_f64() * 1e3;
    out.sort_unstable();
    out.dedup();
    st.e_solutions = out.len();
    st.outcome = "solved".into();
    st.total_ms = t0.elapsed().as_secs_f64() * 1e3;
    st.close();
    Some(out)
}

/// The multisets `{x₁, …, x₄} ⊂ F_p` whose elementary symmetric functions
/// are `e` — the roots of `T⁴ − e₁T³ + e₂T² − e₃T + e₄`, when it splits.
fn split_quartic(e: &[u64; 4], p: u64, rng: &mut StdRng, muls: &mut u64) -> Option<[u64; 4]> {
    let ring = PolyRing::new(p);
    let f = UPoly(vec![e[3], (p - e[2]) % p, e[1], (p - e[0]) % p, 1]);
    let roots = ring.roots(&f, rng);
    *muls += ring.muls.get();
    for &r1 in &roots {
        for &r2 in &roots {
            for &r3 in &roots {
                for &r4 in &roots {
                    if !(r1 <= r2 && r2 <= r3 && r3 <= r4) {
                        continue;
                    }
                    let x = [r1, r2, r3, r4];
                    let mut sy = [0u64; 5];
                    sy[0] = 1;
                    for &v in &x {
                        for k in (1..5).rev() {
                            sy[k] = am(sy[k], mm(sy[k - 1], v, p), p);
                        }
                    }
                    if sy[1] == e[0] && sy[2] == e[1] && sy[3] == e[2] && sy[4] == e[3] {
                        return Some(x);
                    }
                }
            }
        }
    }
    None
}

/// Gaudry's solve at `k = 4`: the abscissae `x₁ ≤ … ≤ x₄` in `F_p` with
/// `S₅(x₁, …, x₄, x_R) = 0`.  `C₄` is `st.total_muls`.
pub fn solve_s5_subspace(
    curve: &Curve4,
    pre: &SymmetrisedS5,
    x_r: &E4,
    rng: &mut StdRng,
    st: &mut QuarticSolve,
    debug: bool,
) -> Option<Vec<[u64; 4]>> {
    let f = &curve.f;
    let before = f.muls();
    let comps = pre.weil_restrict(f, x_r);
    st.weil_muls += f.muls() - before;
    let es = solve_system4(&comps, 8, 29, f.p, rng, st, debug)?;
    let mut out = Vec::new();
    for e in es {
        let mut sm_ = 0u64;
        if let Some(x) = split_quartic(&e, f.p, rng, &mut sm_) {
            out.push(x);
        }
        st.split_muls += sm_;
    }
    st.close();
    out.sort_unstable();
    Some(out)
}

// ── The independent check ─────────────────────────────────────────────────

/// The subspace factor base: one point per `x ∈ F_p` whose right-hand side
/// is a square in `F_{p⁴}`.
pub fn factor_base(curve: &Curve4, rng: &mut StdRng) -> Vec<Pt4> {
    (0..curve.f.p)
        .filter_map(|x| curve.lift_x(&curve.f.from_fp(x), rng))
        .collect()
}

/// Every set of four distinct base abscissae `{x_i, x_j, x_k, x_l}` with
/// `±P_i ± P_j ± P_k ± P_l = R`, by meet in the middle over pairs:
/// `x(R − s_k P_k − s_l P_l)` looked up among the `x(P_i ± P_j)`.
pub fn mitm_decompositions(curve: &Curve4, base: &[Pt4], r: &Pt4) -> BTreeSet<[u64; 4]> {
    let n = base.len();
    let mut table: HashMap<E4, Vec<(usize, usize)>> = HashMap::new();
    for i in 0..n {
        for j in (i + 1)..n {
            for q in [curve.add(&base[i], &base[j]), curve.sub(&base[i], &base[j])] {
                if !q.inf {
                    table.entry(q.x).or_default().push((i, j));
                }
            }
        }
    }
    let mut out = BTreeSet::new();
    for k in 0..n {
        for l in (k + 1)..n {
            for (sk, sl) in [(1, 1), (1, -1), (-1, 1), (-1, -1)] {
                let pk = if sk == 1 {
                    base[k]
                } else {
                    curve.neg(&base[k])
                };
                let pl = if sl == 1 {
                    base[l]
                } else {
                    curve.neg(&base[l])
                };
                let v = curve.sub(&curve.sub(r, &pk), &pl);
                if v.inf {
                    continue;
                }
                if let Some(pairs) = table.get(&v.x) {
                    for &(i, j) in pairs {
                        if i == k || i == l || j == k || j == l {
                            continue;
                        }
                        let mut xs = [
                            base[i].x.0[0],
                            base[j].x.0[0],
                            base[k].x.0[0],
                            base[l].x.0[0],
                        ];
                        xs.sort_unstable();
                        out.insert(xs);
                    }
                }
            }
        }
    }
    out
}

/// The solver's decompositions in the oracle's terms: four distinct
/// abscissae, all in the base.
pub fn base_quadruples(sols: &[[u64; 4]], base: &[Pt4]) -> BTreeSet<[u64; 4]> {
    let xs: std::collections::HashSet<u64> = base.iter().map(|q| q.x.0[0]).collect();
    sols.iter()
        .filter(|x| x[0] < x[1] && x[1] < x[2] && x[2] < x[3])
        .filter(|x| x.iter().all(|v| xs.contains(v)))
        .copied()
        .collect()
}

// ── r∞: the linear algebra and rho at k = 4, measured (§11.18) ───────────

/// A prime-order curve over `F_{p⁴}` with a planted logarithm `Q = [d]G`.
pub struct Instance4 {
    pub curve: Curve4,
    pub n: u64,
    pub g: Pt4,
    pub d: u64,
    pub q: Pt4,
}

/// The same instance as plain data, shareable across threads.
#[derive(Clone, Copy)]
pub struct Spec4 {
    pub p: u64,
    pub a: E4,
    pub b: E4,
    pub n: u64,
    pub g: Pt4,
    pub d: u64,
    pub q: Pt4,
}

impl Instance4 {
    pub fn spec(&self) -> Spec4 {
        Spec4 {
            p: self.curve.f.p,
            a: self.curve.a,
            b: self.curve.b,
            n: self.n,
            g: self.g,
            d: self.d,
            q: self.q,
        }
    }
}

fn random_point(curve: &Curve4, rng: &mut StdRng) -> Pt4 {
    loop {
        let x = curve.f.random(rng);
        if let Some(pt) = curve.lift_x(&x, rng) {
            return pt;
        }
    }
}

/// `#E(F_{p⁴})` when it is prime: baby-step giant-step for the multiple of a
/// random point's order inside the Hasse interval `q + 1 ± 2p²`, accepted
/// only when that multiple is prime (then it is the point's order, and the
/// group's, since the interval is shorter than the order).
fn prime_group_order(curve: &Curve4, rng: &mut StdRng) -> Option<u64> {
    let p = curve.f.p;
    let q = p.pow(4);
    let lo = q + 1 - 2 * p * p;
    let width = 4 * p * p;
    let pt = random_point(curve, rng);
    let steps = (width as f64).sqrt() as u64 + 1;
    let mut table: HashMap<(E4, E4), u64> = HashMap::new();
    let mut jp = Pt4::INF;
    for j in 0..steps {
        if !jp.inf {
            table.entry((jp.x, jp.y)).or_insert(j);
        }
        jp = curve.add(&jp, &pt);
    }
    let giant = curve.mul(&pt, steps);
    let mut t = curve.mul(&pt, lo);
    let mut i = 0u64;
    while i * steps <= width + steps {
        let m = if t.inf {
            Some(lo + i * steps)
        } else {
            let neg = curve.neg(&t);
            table.get(&(neg.x, neg.y)).map(|&j| lo + i * steps + j)
        };
        if let Some(m) = m {
            return super::residual_walk::is_prime_u64(m).then_some(m);
        }
        t = curve.add(&t, &giant);
        i += 1;
    }
    None
}

pub fn generate_instance4(p: u64, seed: u64) -> Instance4 {
    let mut rng = <StdRng as rand::SeedableRng>::seed_from_u64(seed ^ 0x4A11);
    loop {
        let curve = Curve4::random(p, &mut rng);
        let Some(n) = prime_group_order(&curve, &mut rng) else {
            continue;
        };
        let g = random_point(&curve, &mut rng);
        if !curve.mul(&g, n).inf {
            continue;
        }
        let d = rng.gen_range(1..n);
        let q = curve.mul(&g, d);
        curve.reset_ops();
        curve.f.reset_muls();
        return Instance4 { curve, n, g, d, q };
    }
}

/// `x(P_i + s·P_j) ↦ (i, j, s, y)` over the base, built once per curve.
pub struct PairTable {
    map: HashMap<E4, Vec<(u32, u32, i8, E4)>>,
}

pub fn pair_table(curve: &Curve4, base: &[Pt4]) -> PairTable {
    let mut map: HashMap<E4, Vec<(u32, u32, i8, E4)>> = HashMap::new();
    for i in 0..base.len() {
        for j in (i + 1)..base.len() {
            for (s, v) in [
                (1i8, curve.add(&base[i], &base[j])),
                (-1, curve.sub(&base[i], &base[j])),
            ] {
                if !v.inf {
                    map.entry(v.x)
                        .or_default()
                        .push((i as u32, j as u32, s, v.y));
                }
            }
        }
    }
    PairTable { map }
}

/// Every decomposition `R = Σ s_t P_{i_t}` over four distinct base points,
/// with its signs, by meet in the middle against the pair table.
pub fn mitm_signed(
    curve: &Curve4,
    base: &[Pt4],
    table: &PairTable,
    r: &Pt4,
) -> Vec<Vec<(usize, i64)>> {
    let n = base.len();
    let mut out: BTreeSet<Vec<(usize, i64)>> = BTreeSet::new();
    for k in 0..n {
        for sk in [1i64, -1] {
            let pk = if sk == 1 {
                base[k]
            } else {
                curve.neg(&base[k])
            };
            let tk = curve.sub(r, &pk);
            for l in (k + 1)..n {
                for sl in [1i64, -1] {
                    let pl = if sl == 1 {
                        base[l]
                    } else {
                        curve.neg(&base[l])
                    };
                    let v = curve.sub(&tk, &pl);
                    if v.inf {
                        continue;
                    }
                    let Some(cands) = table.map.get(&v.x) else {
                        continue;
                    };
                    for &(i, j, s, y) in cands {
                        let (i, j) = (i as usize, j as usize);
                        if i == k || i == l || j == k || j == l {
                            continue;
                        }
                        let t: i64 = if v.y == y { 1 } else { -1 };
                        let mut terms = vec![(k, sk), (l, sl), (i, t), (j, t * s as i64)];
                        terms.sort_unstable();
                        out.insert(terms);
                    }
                }
            }
        }
    }
    out.into_iter().collect()
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct RhoRun4 {
    pub seed: u64,
    pub steps: u64,
    pub group_ops: u64,
    pub s: f64,
    pub correct: bool,
}

/// r-adding Pollard rho with exhaustive storage, as `gaudry_cubic::run_rho3`
/// runs it, charging every group operation including the walk's setup.
pub fn rho4(inst: &Spec4, seed: u64) -> RhoRun4 {
    let curve = Curve4::with_params(inst.p, inst.a, inst.b);
    let n = inst.n;
    let mut rng = <StdRng as rand::SeedableRng>::seed_from_u64(seed ^ 0x8D04);
    let r = 32usize;
    let mults: Vec<(u64, u64, Pt4)> = (0..r)
        .map(|_| {
            let al = rng.gen_range(0..n);
            let be = rng.gen_range(1..n);
            (
                al,
                be,
                curve.add(&curve.mul(&inst.g, al), &curve.mul(&inst.q, be)),
            )
        })
        .collect();
    let mut table: HashMap<Pt4, (u64, u64)> = HashMap::new();
    let mut steps = 0u64;
    let mut found = None;
    'outer: loop {
        let mut a = rng.gen_range(0..n);
        let mut b = rng.gen_range(1..n);
        let mut l = curve.add(&curve.mul(&inst.g, a), &curve.mul(&inst.q, b));
        loop {
            steps += 1;
            if let Some(&(a2, b2)) = table.get(&l) {
                let db = (b + n - b2) % n;
                if db != 0 {
                    let da = (a2 + n - a) % n;
                    found = Some(mm(da, inv_mod(db, n), n));
                    break 'outer;
                }
                break;
            }
            table.insert(l, (a, b));
            let h = l.x.0[0] ^ l.x.0[1].wrapping_mul(0x9E37_79B9) ^ l.x.0[2].rotate_left(17);
            let j = (super::residual_walk::mix64(h) % r as u64) as usize;
            l = curve.add(&l, &mults[j].2);
            a = (a + mults[j].0) % n;
            b = (b + mults[j].1) % n;
            if steps > 64 * (n as f64).sqrt() as u64 + 1_000_000 {
                break 'outer;
            }
        }
    }
    let ops = curve.ops();
    RhoRun4 {
        seed,
        steps,
        group_ops: ops,
        s: ops as f64 / (n as f64).sqrt(),
        correct: found == Some(inst.d),
    }
}

/// One `k = 4` run of §11.18: relations from [`mitm_signed`], filtered and
/// solved as §11.7 does, the logarithm verified, and rho on the same group.
#[derive(Clone, Debug, Default, Serialize)]
pub struct K4LaReport {
    pub p: u64,
    pub seed: u64,
    pub n: u64,
    pub bits: f64,
    pub base: usize,
    pub residuals: u64,
    pub decompositions: u64,
    pub decomposition_rate: f64,
    pub relations: usize,
    /// Unknowns in the square core the successful solve used.
    pub unknowns: usize,
    pub filtered_out: usize,
    pub phi: f64,
    pub row_weight: f64,
    pub la_attempts: u64,
    /// Multiplications mod `n`, every attempt.
    pub la_ops: u64,
    pub la_ops_last: u64,
    /// `la_ops / unknowns²`, against §11.16's `20`.
    pub wiedemann_constant: f64,
    pub solved: bool,
    pub correct: bool,
    /// Group operations the relation phase spent (residuals and the oracle),
    /// kept out of `r`.
    pub relation_group_ops: u64,
    pub fp_muls_per_add: f64,
    pub rho: Vec<RhoRun4>,
    pub rho_s_mean: f64,
    pub rho_s_sd: f64,
    /// `LA / rho` in `F_p` multiplications: `la_ops·16 / (S_rho·√n·c_add)`.
    pub r: f64,
    pub wall_ms: f64,
}

pub fn run_k4_la(p: u64, seed: u64, rho_runs: usize) -> K4LaReport {
    use super::gaudry_cubic::{square_core, wiedemann_u64, SparseRel};
    let start = Instant::now();
    let inst = generate_instance4(p, seed);
    let curve = &inst.curve;
    let n = inst.n;
    let mut rng = <StdRng as rand::SeedableRng>::seed_from_u64(seed ^ 0x1A4);
    let base = factor_base(curve, &mut rng);
    let fp_per_add = {
        curve.f.reset_muls();
        let mut acc = base[0];
        for _ in 0..64 {
            acc = curve.add(&acc, &base[1]);
        }
        curve.f.muls() as f64 / 64.0
    };
    curve.reset_ops();
    let table = pair_table(curve, &base);
    let spec = inst.spec();
    let small = base.len();
    let unknowns = small + 1;
    let mut rep = K4LaReport {
        p,
        seed,
        n,
        bits: (n as f64).log2(),
        base: small,
        fp_muls_per_add: fp_per_add,
        ..Default::default()
    };
    let mut rel_ops = curve.ops();
    let mut full_rels: Vec<SparseRel> = Vec::new();
    let mut next_attempt = unknowns;
    let mut la_ops = 0u64;
    'collect: while rep.residuals < 50_000_000 {
        let batch: Vec<(u64, u64)> = (0..64)
            .map(|_| (rng.gen_range(0..n), rng.gen_range(1..n)))
            .collect();
        let found: Vec<(u64, u64, Pt4, Vec<Vec<(usize, i64)>>, u64)> = batch
            .par_iter()
            .map(|&(a, b)| {
                let c = Curve4::with_params(spec.p, spec.a, spec.b);
                let r = c.add(&c.mul(&spec.g, a), &c.mul(&spec.q, b));
                let decs = mitm_signed(&c, &base, &table, &r);
                (a, b, r, decs, c.ops())
            })
            .collect();
        for (a, b, r, decs, ops) in found {
            rep.residuals += 1;
            rel_ops += ops;
            for terms in decs {
                // Verify aG + bQ = Σ s P before using it.
                let mut acc = r;
                for &(i, s) in &terms {
                    acc = if s == 1 {
                        curve.sub(&acc, &base[i])
                    } else {
                        curve.add(&acc, &base[i])
                    };
                }
                if !acc.inf {
                    continue;
                }
                rep.decompositions += 1;
                let mut cols: Vec<(usize, u64)> = terms
                    .iter()
                    .map(|&(i, s)| (i, if s == 1 { 1 } else { n - 1 }))
                    .collect();
                cols.push((small, (n - b) % n));
                cols.sort_unstable();
                full_rels.push(SparseRel { cols, rhs: a });
            }
            if full_rels.len() >= next_attempt {
                if let Some(core) = square_core(&full_rels, small) {
                    rep.la_attempts += 1;
                    let mut map = vec![usize::MAX; unknowns];
                    let mut k = 0;
                    for c in 0..unknowns {
                        if core.columns.get(c).copied().unwrap_or(false) {
                            map[c] = k;
                            k += 1;
                        }
                    }
                    let sel: Vec<SparseRel> = core
                        .rows
                        .iter()
                        .map(|&i| SparseRel {
                            cols: full_rels[i]
                                .cols
                                .iter()
                                .map(|&(c, v)| (map[c], v))
                                .collect(),
                            rhs: full_rels[i].rhs,
                        })
                        .collect();
                    let before = la_ops;
                    let x = wiedemann_u64(&sel, sel.len(), n, &mut rng, &mut la_ops);
                    let dd = x.map(|x| x[map[small]]);
                    if dd.is_some_and(|dd| curve.mul(&inst.g, dd) == inst.q) {
                        rep.solved = true;
                        rep.correct = dd == Some(inst.d);
                        rep.unknowns = sel.len();
                        rep.filtered_out = full_rels.len() - sel.len();
                        rep.la_ops_last = la_ops - before;
                        break 'collect;
                    }
                    next_attempt = full_rels.len() + (sel.len() / 20).max(1);
                } else {
                    next_attempt = full_rels.len() + (unknowns / 20).max(1);
                }
            }
        }
    }
    rep.relations = full_rels.len();
    rep.relation_group_ops = rel_ops;
    rep.la_ops = la_ops;
    rep.decomposition_rate = rep.decompositions as f64 / rep.residuals.max(1) as f64;
    rep.phi = rep.unknowns as f64 / small as f64;
    rep.row_weight = full_rels.iter().map(|r| r.cols.len()).sum::<usize>() as f64
        / full_rels.len().max(1) as f64;
    rep.wiedemann_constant = la_ops as f64 / (rep.unknowns.max(1) as f64).powi(2);
    rep.rho = (0..rho_runs as u64)
        .into_par_iter()
        .map(|k| rho4(&spec, seed * 1000 + k))
        .collect();
    let ss: Vec<f64> = rep.rho.iter().map(|r| r.s).collect();
    rep.rho_s_mean = ss.iter().sum::<f64>() / ss.len().max(1) as f64;
    rep.rho_s_sd = (ss.iter().map(|s| (s - rep.rho_s_mean).powi(2)).sum::<f64>()
        / (ss.len().max(2) - 1) as f64)
        .sqrt();
    rep.r = la_ops as f64 * 16.0 / (rep.rho_s_mean * (n as f64).sqrt() * fp_per_add);
    rep.wall_ms = start.elapsed().as_secs_f64() * 1e3;
    rep
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;

    #[test]
    fn fp4_is_a_field() {
        let f = Fp4::new(269);
        let mut rng = StdRng::seed_from_u64(1);
        for _ in 0..50 {
            let a = f.random(&mut rng);
            let b = f.random(&mut rng);
            assert_eq!(f.mul(&a, &b), f.mul(&b, &a));
            if !a.is_zero() {
                assert_eq!(f.mul(&a, &f.inv(&a)), E4::ONE);
            }
            let s = f.sq(&a);
            let r = f.sqrt(&s, &mut rng).expect("a square has a root");
            assert_eq!(f.sq(&r), s);
        }
        // The inversion is charged as §11.16 derives it: 40.
        f.reset_muls();
        f.inv(&E4([3, 1, 4, 1]));
        assert_eq!(f.muls(), 40);
    }

    #[test]
    fn s5_vanishes_on_four_point_sums_and_is_symmetric() {
        let mut rng = StdRng::seed_from_u64(2);
        let curve = Curve4::random(269, &mut rng);
        let f = &curve.f;
        let mut pts: Vec<Pt4> = Vec::new();
        while pts.len() < 4 {
            let x = f.random(&mut rng);
            if let Some(q) = curve.lift_x(&x, &mut rng) {
                pts.push(q);
            }
        }
        let sum = pts.iter().fold(Pt4::INF, |acc, q| curve.add(&acc, q));
        assert!(curve.on_curve(&sum));
        let x = [pts[0].x, pts[1].x, pts[2].x, pts[3].x, sum.x];
        assert!(curve.s5(&x).is_zero(), "S5 must vanish on a four-point sum");
        // Signs do not matter: x(P1 − P2 + P3 + P4) is a root too.
        let mixed = curve.add(&curve.add(&curve.sub(&pts[0], &pts[1]), &pts[2]), &pts[3]);
        let xm = [pts[0].x, pts[1].x, pts[2].x, pts[3].x, mixed.x];
        assert!(curve.s5(&xm).is_zero());
        // Symmetric in the first four arguments at a random point.
        let r: [E4; 5] = core::array::from_fn(|_| f.random(&mut rng));
        let v = curve.s5(&r);
        assert!(!v.is_zero());
        for perm in [[1, 0, 2, 3], [2, 3, 0, 1], [3, 1, 2, 0], [0, 2, 1, 3]] {
            let q = [r[perm[0]], r[perm[1]], r[perm[2]], r[perm[3]], r[4]];
            assert_eq!(curve.s5(&q), v, "not symmetric under {perm:?}");
        }
    }

    /// Four random equations of total degree `d` in four unknowns with a
    /// planted `F_p`-rational root: the solver must find it, every answer
    /// must satisfy all four, and the quotient must have the Bézout
    /// dimension `d⁴` at the Macaulay bound `4(d − 1) + 1`.
    fn planted(d: u8, seed: u64) {
        let p = 269u64;
        let mut rng = StdRng::seed_from_u64(seed);
        let root: [u64; 4] = core::array::from_fn(|_| rng.gen_range(0..p));
        let monos = exponents4(d);
        let comps: Vec<HashMap<[u8; 4], u64>> = (0..4)
            .map(|_| {
                let mut c: HashMap<[u8; 4], u64> =
                    monos.iter().map(|m| (*m, rng.gen_range(0..p))).collect();
                let mut dummy = 0u64;
                let v = eval4(&c, &root, p, &mut dummy);
                let e = c.entry([0, 0, 0, 0]).or_insert(0);
                *e = sm(*e, v, p);
                c
            })
            .collect();
        let mut st = QuarticSolve::default();
        let sols = solve_system4(&comps, d, 4 * (d - 1) + 1, p, &mut rng, &mut st, false)
            .expect("a generic system closes at the Macaulay bound");
        assert_eq!(st.dim, (d as usize).pow(4), "{st:?}");
        assert!(sols.contains(&root), "planted {root:?} not in {sols:?}");
        for s in &sols {
            let mut dummy = 0u64;
            assert!(comps.iter().all(|c| eval4(c, s, p, &mut dummy) == 0));
        }
        assert!(st.total_muls > 0 && st.echelon_muls > 0 && st.charpoly_muls > 0);
    }

    #[test]
    fn the_solver_finds_planted_roots_of_quadrics() {
        for seed in 0..4 {
            planted(2, seed);
        }
    }

    #[test]
    fn the_solver_finds_planted_roots_of_cubics() {
        planted(3, 7);
    }

    /// §11.18's pipeline end to end at a toy size: a prime-order curve,
    /// relations from the meet-in-the-middle oracle, filtering, Wiedemann,
    /// the planted logarithm recovered — and rho recovering it too.
    #[test]
    fn k4_linear_algebra_and_rho_recover_the_planted_logarithm() {
        let rep = run_k4_la(29, 3, 4);
        assert!(rep.solved && rep.correct, "{rep:?}");
        assert!(super::super::residual_walk::is_prime_u64(rep.n));
        assert!(rep.rho.iter().all(|r| r.correct), "{:?}", rep.rho);
        assert!(rep.la_ops > 0 && rep.r > 0.0);
        assert!(
            (rep.row_weight - 5.0).abs() < 1e-9,
            "four points and d: {}",
            rep.row_weight
        );
        assert_eq!(rep.fp_muls_per_add, 97.0);
    }
}
