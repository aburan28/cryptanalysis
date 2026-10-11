//! **Gaudry-style index calculus on `E(F_{p³})` with the subspace factor
//! base `{P : x(P) ∈ F_p}`** — the setting in which summation
//! polynomials have a genuine algebraic advantage, built small enough to
//! be measured against Pollard rho on the same group.
//!
//! # Why an extension field
//!
//! On a prime field there is no proper additive subspace, so a
//! "subspace factor base" has nowhere to live and the `S₃` / `S₄`
//! oracles of `residual_walk` degrade to one square root per
//! factor-base element (§10.4–10.5 of `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md`).
//! Over `F_{q^k}` the base `F = {P ∈ E(F_{q^k}) : x(P) ∈ F_q}` is an
//! `F_q`-subspace of abscissae, and a summation-polynomial equation
//! `S_{m+1}(x_1, …, x_m, x_R) = 0` with the `x_i` unknown in `F_q` Weil-
//! restricts to `k` equations over `F_q` in `m` unknowns — a
//! zero-dimensional system whose cost does not depend on `|F|`.  That
//! is Gaudry's observation (2009); for fixed `k ≥ 3` it beats rho
//! asymptotically.
//!
//! # What is implemented
//!
//! `k = 3`, `m = 3`: random curves `y² = x³ + ax + b` with
//! `a, b ∈ F_{p³}` and prime group order `n ≈ p³`, the factor base of
//! the `≈ p/2` points with `x ∈ F_p`, and the decomposition
//! `R = ±P_i ± P_j ± P_k`.  The oracle is the meet-in-the-middle form:
//! for every `P_k` in the base, `Y = R ∓ P_k` (one group operation) is
//! tested for `Y ∈ ±F ± F` by the **Weil-restricted `S₃`**:
//! `S₃(x_Y, x_1, x_2) = 0` with `x_1, x_2 ∈ F_p` unknown is three
//! quadratic equations over `F_p`; eliminating `x_2` by a `4×4`
//! Sylvester resultant leaves a degree-`8` univariate in `x_1`, whose
//! `F_p`-roots are found by Cantor–Zassenhaus and completed to `x_2` by
//! the quadratic formula.  Every pair test therefore costs `O(log p)`
//! field multiplications — independent of the base size — where the
//! prime-field `S₃` oracle needed one square root per base element.
//!
//! What is *not* implemented is Gaudry's full `O(1)` solve of the
//! three-unknown `S₄` system (symmetrised variables and a Gröbner
//! basis), which would remove the remaining factor `p` from the
//! per-residual cost; the report separates that factor so the effect of
//! adding it can be read off.
//!
//! # Accounting
//!
//! Group operations are affine additions in `E(F_{p³})`.  Oracle work is
//! counted in `F_p` multiplications and converted at the measured cost
//! of one affine addition (`FP_MULS_PER_ADD`), so `S = total / √n` is
//! comparable with the prime-field scoreboard and with rho on the same
//! group, which the module also runs.

use std::cell::Cell;
use std::collections::HashMap;
use std::time::Instant;

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

use super::residual_walk::{inv_mod, is_prime_u64, mix64, pow_mod, sqrt_mod, RelationSystem};

/// `F_p` multiplications per affine addition in `E(F_{p³})`: measured by
/// `Fp3::adds_to_muls_ratio` on construction and folded into the
/// reports; this constant is only the fallback.
pub const FP_MULS_PER_ADD: f64 = 60.0;

// ── F_p helpers ──────────────────────────────────────────────────────────

#[inline]
pub(crate) fn mm(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}
#[inline]
pub(crate) fn am(a: u64, b: u64, p: u64) -> u64 {
    let s = a + b;
    if s >= p {
        s - p
    } else {
        s
    }
}
#[inline]
pub(crate) fn sm(a: u64, b: u64, p: u64) -> u64 {
    if a >= b {
        a - b
    } else {
        a + p - b
    }
}

// ── F_{p³} = F_p[t] / (t³ − c) ───────────────────────────────────────────

/// Element `a₀ + a₁ t + a₂ t²`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
pub struct E3(pub [u64; 3]);

/// The cubic extension `F_p[t]/(t³ − c)`, `c` a non-cube, with an
/// `F_p`-multiplication counter.
#[derive(Clone, Debug, Serialize)]
pub struct Fp3 {
    pub p: u64,
    /// `t³ = c`.
    pub c: u64,
    #[serde(skip)]
    muls: Cell<u64>,
}

impl Fp3 {
    /// Build the field for a prime `p ≡ 1 (mod 3)` (so that non-cubes
    /// exist and `t³ − c` is irreducible for a non-cube `c`).
    pub fn new(p: u64, rng: &mut StdRng) -> Fp3 {
        assert!(p % 3 == 1, "need p ≡ 1 mod 3 for t³ − c irreducible");
        let c = loop {
            let g = rng.gen_range(2..p);
            if pow_mod(g, (p - 1) / 3, p) != 1 {
                break g;
            }
        };
        Fp3 {
            p,
            c,
            muls: Cell::new(0),
        }
    }

    pub fn muls(&self) -> u64 {
        self.muls.get()
    }
    pub fn reset_muls(&self) {
        self.muls.set(0);
    }
    #[inline]
    fn count(&self, k: u64) {
        self.muls.set(self.muls.get() + k);
    }

    pub const ZERO: E3 = E3([0, 0, 0]);
    pub const ONE: E3 = E3([1, 0, 0]);

    pub fn from_base(&self, a: u64) -> E3 {
        E3([a % self.p, 0, 0])
    }
    pub fn is_base(&self, a: &E3) -> bool {
        a.0[1] == 0 && a.0[2] == 0
    }
    pub fn add(&self, a: &E3, b: &E3) -> E3 {
        let p = self.p;
        E3([
            am(a.0[0], b.0[0], p),
            am(a.0[1], b.0[1], p),
            am(a.0[2], b.0[2], p),
        ])
    }
    pub fn sub(&self, a: &E3, b: &E3) -> E3 {
        let p = self.p;
        E3([
            sm(a.0[0], b.0[0], p),
            sm(a.0[1], b.0[1], p),
            sm(a.0[2], b.0[2], p),
        ])
    }
    pub fn neg(&self, a: &E3) -> E3 {
        let p = self.p;
        E3([(p - a.0[0]) % p, (p - a.0[1]) % p, (p - a.0[2]) % p])
    }
    pub fn scale(&self, a: &E3, k: u64) -> E3 {
        let p = self.p;
        self.count(3);
        E3([mm(a.0[0], k, p), mm(a.0[1], k, p), mm(a.0[2], k, p)])
    }
    /// Schoolbook product with `t³ = c` (9 + 2 multiplications).
    pub fn mul(&self, a: &E3, b: &E3) -> E3 {
        let p = self.p;
        let (a0, a1, a2) = (a.0[0], a.0[1], a.0[2]);
        let (b0, b1, b2) = (b.0[0], b.0[1], b.0[2]);
        self.count(11);
        let d0 = mm(a0, b0, p);
        let d1 = am(mm(a0, b1, p), mm(a1, b0, p), p);
        let d2 = am(am(mm(a0, b2, p), mm(a1, b1, p), p), mm(a2, b0, p), p);
        let d3 = am(mm(a1, b2, p), mm(a2, b1, p), p);
        let d4 = mm(a2, b2, p);
        E3([
            am(d0, mm(self.c, d3, p), p),
            am(d1, mm(self.c, d4, p), p),
            d2,
        ])
    }
    pub fn sq(&self, a: &E3) -> E3 {
        self.mul(a, a)
    }
    /// Inverse via the norm: `a⁻¹ = (a^{p} a^{p²}) / N(a)` computed as
    /// the adjugate of the multiplication matrix.
    pub fn inv(&self, a: &E3) -> E3 {
        let p = self.p;
        let c = self.c;
        let (a0, a1, a2) = (a.0[0], a.0[1], a.0[2]);
        // Multiplication-by-a matrix M (columns = a·1, a·t, a·t²):
        //   [a0  c·a2  c·a1]
        //   [a1  a0    c·a2]
        //   [a2  a1    a0  ]
        // Solve M x = e₀ by the adjugate.
        self.count(30);
        let ca1 = mm(c, a1, p);
        let ca2 = mm(c, a2, p);
        // Cofactors of the first row entries give the first row of adj(M)ᵀ;
        // we need the first column of M⁻¹ = adj(M)/det, i.e. cofactors of
        // the first *column* of M.
        let m = [[a0, ca2, ca1], [a1, a0, ca2], [a2, a1, a0]];
        let minor = |r: usize, cidx: usize| {
            let rows: Vec<usize> = (0..3).filter(|&i| i != r).collect();
            let cols: Vec<usize> = (0..3).filter(|&j| j != cidx).collect();
            sm(
                mm(m[rows[0]][cols[0]], m[rows[1]][cols[1]], p),
                mm(m[rows[0]][cols[1]], m[rows[1]][cols[0]], p),
                p,
            )
        };
        let cof = |r: usize, cidx: usize| {
            let v = minor(r, cidx);
            if (r + cidx).is_multiple_of(2) {
                v
            } else {
                (p - v) % p
            }
        };
        let det = am(
            sm(mm(m[0][0], cof(0, 0), p), 0, p),
            am(mm(m[0][1], cof(0, 1), p), mm(m[0][2], cof(0, 2), p), p),
            p,
        );
        assert!(det != 0, "inverse of zero in F_p³");
        let dinv = inv_mod(det, p);
        // x_i = adj(M)[i][0] / det = cof(0, i) / det.
        E3([
            mm(cof(0, 0), dinv, p),
            mm(cof(0, 1), dinv, p),
            mm(cof(0, 2), dinv, p),
        ])
    }
    pub fn pow(&self, a: &E3, mut e: u128) -> E3 {
        let mut base = *a;
        let mut acc = Fp3::ONE;
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(&acc, &base);
            }
            base = self.sq(&base);
            e >>= 1;
        }
        acc
    }
    /// Square root in `F_{p³}` (order `p³ − 1`): Tonelli–Shanks over the
    /// extension, using a random non-residue.
    pub fn sqrt(&self, a: &E3, rng: &mut StdRng) -> Option<E3> {
        if *a == Fp3::ZERO {
            return Some(Fp3::ZERO);
        }
        let q: u128 = (self.p as u128).pow(3) - 1;
        if self.pow(a, q / 2) != Fp3::ONE {
            return None;
        }
        let mut s = 0u32;
        let mut m = q;
        while m.is_multiple_of(2) {
            m /= 2;
            s += 1;
        }
        let z = loop {
            let z = E3([
                rng.gen_range(0..self.p),
                rng.gen_range(0..self.p),
                rng.gen_range(0..self.p),
            ]);
            if z != Fp3::ZERO && self.pow(&z, q / 2) != Fp3::ONE {
                break z;
            }
        };
        let mut c = self.pow(&z, m);
        let mut t = self.pow(a, m);
        let mut r = self.pow(a, m.div_ceil(2));
        let mut mm_ = s;
        loop {
            if t == Fp3::ONE {
                return Some(r);
            }
            let mut i = 0u32;
            let mut tt = t;
            while tt != Fp3::ONE {
                tt = self.sq(&tt);
                i += 1;
                if i == mm_ {
                    return None;
                }
            }
            let mut b = c;
            for _ in 0..(mm_ - i - 1) {
                b = self.sq(&b);
            }
            mm_ = i;
            c = self.sq(&b);
            t = self.mul(&t, &c);
            r = self.mul(&r, &b);
        }
    }
    /// Frobenius-free canonical "sign" of an element: the lexicographic
    /// comparison used to pick a representative of `{y, −y}`.
    pub fn is_small(&self, a: &E3) -> bool {
        let n = self.neg(a);
        a.0 <= n.0
    }
}

// ── Curve over F_{p³} ─────────────────────────────────────────────────────

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
pub struct Pt3 {
    pub x: E3,
    pub y: E3,
    pub inf: bool,
}

impl Pt3 {
    pub const INFINITY: Pt3 = Pt3 {
        x: Fp3::ZERO,
        y: Fp3::ZERO,
        inf: true,
    };
    pub fn affine(x: E3, y: E3) -> Pt3 {
        Pt3 { x, y, inf: false }
    }
}

/// `y² = x³ + ax + b` over `F_{p³}` with a generator of prime order `n`.
#[derive(Clone, Debug, Serialize)]
pub struct Curve3 {
    pub field: Fp3,
    pub a: E3,
    pub b: E3,
    pub n: u64,
    pub g: Pt3,
    #[serde(skip)]
    ops: Cell<u64>,
}

impl Curve3 {
    pub fn ops(&self) -> u64 {
        self.ops.get()
    }
    pub fn reset(&self) {
        self.ops.set(0);
        self.field.reset_muls();
    }
    pub fn neg(&self, u: &Pt3) -> Pt3 {
        if u.inf {
            *u
        } else {
            Pt3::affine(u.x, self.field.neg(&u.y))
        }
    }
    pub fn add(&self, u: &Pt3, v: &Pt3) -> Pt3 {
        if u.inf {
            return *v;
        }
        if v.inf {
            return *u;
        }
        let f = &self.field;
        if u.x == v.x {
            if f.add(&u.y, &v.y) == Fp3::ZERO {
                return Pt3::INFINITY;
            }
            return self.double(u);
        }
        self.ops.set(self.ops.get() + 1);
        let lambda = f.mul(&f.sub(&v.y, &u.y), &f.inv(&f.sub(&v.x, &u.x)));
        let x3 = f.sub(&f.sub(&f.sq(&lambda), &u.x), &v.x);
        let y3 = f.sub(&f.mul(&lambda, &f.sub(&u.x, &x3)), &u.y);
        Pt3::affine(x3, y3)
    }
    pub fn double(&self, u: &Pt3) -> Pt3 {
        if u.inf || u.y == Fp3::ZERO {
            return Pt3::INFINITY;
        }
        self.ops.set(self.ops.get() + 1);
        let f = &self.field;
        let num = f.add(&f.scale(&f.sq(&u.x), 3), &self.a);
        let lambda = f.mul(&num, &f.inv(&f.add(&u.y, &u.y)));
        let x3 = f.sub(&f.sub(&f.sq(&lambda), &u.x), &u.x);
        let y3 = f.sub(&f.mul(&lambda, &f.sub(&u.x, &x3)), &u.y);
        Pt3::affine(x3, y3)
    }
    pub fn sub(&self, u: &Pt3, v: &Pt3) -> Pt3 {
        self.add(u, &self.neg(v))
    }
    pub fn mul(&self, pt: &Pt3, k: u64) -> Pt3 {
        let mut acc = Pt3::INFINITY;
        if k == 0 || pt.inf {
            return acc;
        }
        let top = 63 - k.leading_zeros();
        for i in (0..=top).rev() {
            acc = self.double(&acc);
            if (k >> i) & 1 == 1 {
                acc = self.add(&acc, pt);
            }
        }
        acc
    }
    pub fn mul_signed(&self, pt: &Pt3, c: i64) -> Pt3 {
        if c >= 0 {
            self.mul(pt, c as u64)
        } else {
            self.mul(&self.neg(pt), c.unsigned_abs())
        }
    }
    pub fn is_on_curve(&self, u: &Pt3) -> bool {
        if u.inf {
            return true;
        }
        let f = &self.field;
        let rhs = f.add(
            &f.add(&f.mul(&f.sq(&u.x), &u.x), &f.mul(&self.a, &u.x)),
            &self.b,
        );
        f.sq(&u.y) == rhs
    }
    /// `x³ + ax + b`.
    pub fn rhs(&self, x: &E3) -> E3 {
        let f = &self.field;
        f.add(&f.add(&f.mul(&f.sq(x), x), &f.mul(&self.a, x)), &self.b)
    }
    pub fn lift(&self, x: &E3, rng: &mut StdRng) -> Option<Pt3> {
        let y = self.field.sqrt(&self.rhs(x), rng)?;
        let y = if self.field.is_small(&y) {
            y
        } else {
            self.field.neg(&y)
        };
        Some(Pt3::affine(*x, y))
    }
}

/// Known-answer instance over `F_{p³}`.
#[derive(Clone, Debug, Serialize)]
pub struct Instance3 {
    pub curve: Curve3,
    pub q: Pt3,
    pub d: u64,
}

fn isqrt(n: u128) -> u128 {
    let mut r = (n as f64).sqrt() as u128;
    while r * r > n {
        r -= 1;
    }
    while (r + 1) * (r + 1) <= n {
        r += 1;
    }
    r
}

/// Order of `pt` if it is the unique multiple in the Hasse interval
/// `[p³ + 1 − 2p^{3/2}, p³ + 1 + 2p^{3/2}]` (BSGS, `O(p^{3/4})`).
fn unique_hasse_multiple3(curve: &Curve3, pt: &Pt3) -> Option<u64> {
    let p = curve.field.p as u128;
    let n0 = p * p * p + 1;
    let two_sqrt = 2 * isqrt(p * p * p) + 2;
    let lo = n0 - two_sqrt;
    let hi = n0 + two_sqrt;
    let width = hi - lo + 1;
    let s = isqrt(width) + 1;
    let mut baby: HashMap<Pt3, u128> = HashMap::with_capacity(s as usize);
    let mut cur = Pt3::INFINITY;
    for j in 0..s {
        baby.entry(cur).or_insert(j);
        cur = curve.add(&cur, pt);
    }
    let giant = curve.mul(pt, s as u64);
    let mut t = curve.mul(pt, lo as u64);
    let mut found: Option<u128> = None;
    let mut i = 0u128;
    while lo + i * s <= hi {
        if let Some(&j) = baby.get(&curve.neg(&t)) {
            let m = lo + i * s + j;
            if (lo..=hi).contains(&m) {
                if found.is_some() && found != Some(m) {
                    return None;
                }
                found = Some(m);
            }
        }
        t = curve.add(&t, &giant);
        i += 1;
    }
    found.map(|m| m as u64)
}

/// Random prime-order curve over `F_{p³}` for the given prime `p ≡ 1
/// (mod 3)`, `p < 2^20`, with a random known-answer target.
pub fn generate_instance3(p: u64, seed: u64) -> Instance3 {
    assert!(p % 3 == 1 && is_prime_u64(p) && p < (1 << 20));
    let mut rng = StdRng::seed_from_u64(seed ^ 0x6A0D_4B17);
    loop {
        let field = Fp3::new(p, &mut rng);
        let rnd = |rng: &mut StdRng| {
            E3([
                rng.gen_range(0..p),
                rng.gen_range(0..p),
                rng.gen_range(0..p),
            ])
        };
        let a = rnd(&mut rng);
        let b = rnd(&mut rng);
        let curve = Curve3 {
            field: field.clone(),
            a,
            b,
            n: 0,
            g: Pt3::INFINITY,
            ops: Cell::new(0),
        };
        let g = loop {
            let x = rnd(&mut rng);
            if let Some(pt) = curve.lift(&x, &mut rng) {
                break pt;
            }
        };
        let Some(order) = unique_hasse_multiple3(&curve, &g) else {
            continue;
        };
        if !is_prime_u64(order) {
            continue;
        }
        let curve = Curve3 {
            field,
            a,
            b,
            n: order,
            g,
            ops: Cell::new(0),
        };
        assert!(curve.mul(&g, order).inf);
        let d = rng.gen_range(1..order);
        let q = curve.mul(&g, d);
        curve.reset();
        return Instance3 { curve, q, d };
    }
}

// ── Subspace factor base ─────────────────────────────────────────────────

/// `{P : x(P) ∈ F_p}` with the canonical `y`, indexed by `x`.
#[derive(Clone, Debug)]
pub struct SubspaceBase {
    pub points: Vec<Pt3>,
    by_x: HashMap<u64, usize>,
}

impl SubspaceBase {
    pub fn build(inst: &Instance3, rng: &mut StdRng) -> SubspaceBase {
        let curve = &inst.curve;
        let mut points = Vec::new();
        let mut by_x = HashMap::new();
        for x in 0..curve.field.p {
            let xe = curve.field.from_base(x);
            if let Some(pt) = curve.lift(&xe, rng) {
                if pt.y != Fp3::ZERO {
                    by_x.insert(x, points.len());
                    points.push(pt);
                }
            }
        }
        SubspaceBase { points, by_x }
    }
    pub fn len(&self) -> usize {
        self.points.len()
    }
    pub fn is_empty(&self) -> bool {
        self.points.is_empty()
    }
    /// `Some((i, ±1))` if `pt = ±P_i`.
    pub fn lookup(&self, field: &Fp3, pt: &Pt3) -> Option<(usize, i64)> {
        if pt.inf || !field.is_base(&pt.x) {
            return None;
        }
        let &i = self.by_x.get(&pt.x.0[0])?;
        Some((i, if self.points[i].y == pt.y { 1 } else { -1 }))
    }
}

// ── Univariate polynomials over F_p (small degree) ───────────────────────

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct UPoly(pub(crate) Vec<u64>); // coefficients, low to high, trimmed

fn trim(mut v: Vec<u64>) -> Vec<u64> {
    while v.last() == Some(&0) {
        v.pop();
    }
    v
}

pub(crate) struct PolyRing {
    p: u64,
    pub(crate) muls: Cell<u64>,
}

impl PolyRing {
    pub(crate) fn new(p: u64) -> Self {
        PolyRing {
            p,
            muls: Cell::new(0),
        }
    }
    fn count(&self, k: u64) {
        self.muls.set(self.muls.get() + k);
    }
    fn deg(f: &UPoly) -> isize {
        f.0.len() as isize - 1
    }
    fn sub(&self, f: &UPoly, g: &UPoly) -> UPoly {
        let n = f.0.len().max(g.0.len());
        let mut out = vec![0u64; n];
        for (i, o) in out.iter_mut().enumerate() {
            let a = f.0.get(i).copied().unwrap_or(0);
            let b = g.0.get(i).copied().unwrap_or(0);
            *o = sm(a, b, self.p);
        }
        UPoly(trim(out))
    }
    fn mul(&self, f: &UPoly, g: &UPoly) -> UPoly {
        if f.0.is_empty() || g.0.is_empty() {
            return UPoly(vec![]);
        }
        let mut out = vec![0u64; f.0.len() + g.0.len() - 1];
        self.count((f.0.len() * g.0.len()) as u64);
        for (i, &a) in f.0.iter().enumerate() {
            for (j, &b) in g.0.iter().enumerate() {
                out[i + j] = am(out[i + j], mm(a, b, self.p), self.p);
            }
        }
        UPoly(trim(out))
    }
    fn scale(&self, f: &UPoly, k: u64) -> UPoly {
        self.count(f.0.len() as u64);
        UPoly(trim(f.0.iter().map(|&a| mm(a, k, self.p)).collect()))
    }
    /// Remainder of `f` modulo monic-normalised `g`.
    fn rem(&self, f: &UPoly, g: &UPoly) -> UPoly {
        let dg = Self::deg(g);
        assert!(dg >= 0);
        let mut r = f.0.clone();
        let lead_inv = inv_mod(*g.0.last().unwrap(), self.p);
        while r.len() as isize > dg {
            let coef = mm(*r.last().unwrap(), lead_inv, self.p);
            let shift = r.len() - g.0.len();
            self.count(g.0.len() as u64 + 1);
            for (i, &gc) in g.0.iter().enumerate() {
                r[shift + i] = sm(r[shift + i], mm(coef, gc, self.p), self.p);
            }
            r = trim(r);
            if r.is_empty() {
                break;
            }
        }
        UPoly(r)
    }
    fn gcd(&self, f: &UPoly, g: &UPoly) -> UPoly {
        let (mut a, mut b) = (f.clone(), g.clone());
        while !b.0.is_empty() {
            let r = self.rem(&a, &b);
            a = b;
            b = r;
        }
        if a.0.is_empty() {
            return a;
        }
        let inv = inv_mod(*a.0.last().unwrap(), self.p);
        self.scale(&a, inv)
    }
    fn mulmod(&self, f: &UPoly, g: &UPoly, m: &UPoly) -> UPoly {
        self.rem(&self.mul(f, g), m)
    }
    fn powmod(&self, f: &UPoly, mut e: u64, m: &UPoly) -> UPoly {
        let mut base = self.rem(f, m);
        let mut acc = UPoly(vec![1]);
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mulmod(&acc, &base, m);
            }
            base = self.mulmod(&base, &base, m);
            e >>= 1;
        }
        acc
    }
    /// All roots in `F_p` of `f` (Cantor–Zassenhaus).
    pub(crate) fn roots(&self, f: &UPoly, rng: &mut StdRng) -> Vec<u64> {
        let f = {
            let inv = match f.0.last() {
                Some(&l) => inv_mod(l, self.p),
                None => return vec![],
            };
            self.scale(f, inv)
        };
        if Self::deg(&f) <= 0 {
            return vec![];
        }
        // gcd(f, x^p − x): the product of the distinct linear factors.
        let xp = self.powmod(&UPoly(vec![0, 1]), self.p, &f);
        let xp_minus_x = self.sub(&xp, &UPoly(vec![0, 1]));
        let g = self.gcd(&f, &xp_minus_x);
        let mut out = Vec::new();
        self.split(&g, rng, &mut out);
        out.sort_unstable();
        out.dedup();
        out
    }
    fn split(&self, g: &UPoly, rng: &mut StdRng, out: &mut Vec<u64>) {
        match Self::deg(g) {
            d if d <= 0 => {}
            1 => {
                // g = x + c0 (monic)
                out.push((self.p - g.0[0]) % self.p);
            }
            _ => {
                for _ in 0..64 {
                    let c = rng.gen_range(0..self.p);
                    // (x + c)^{(p−1)/2} − 1
                    let h = self.powmod(&UPoly(vec![c, 1]), (self.p - 1) / 2, g);
                    let h = self.sub(&h, &UPoly(vec![1]));
                    let f1 = self.gcd(g, &h);
                    let d1 = Self::deg(&f1);
                    if d1 > 0 && d1 < Self::deg(g) {
                        // g = f1 · f2
                        let f2 = self.div_exact(g, &f1);
                        self.split(&f1, rng, out);
                        self.split(&f2, rng, out);
                        return;
                    }
                }
            }
        }
    }
    fn div_exact(&self, f: &UPoly, g: &UPoly) -> UPoly {
        let dg = Self::deg(g);
        let mut r = f.0.clone();
        let mut q = vec![0u64; f.0.len().saturating_sub(g.0.len()) + 1];
        let lead_inv = inv_mod(*g.0.last().unwrap(), self.p);
        while r.len() as isize > dg && !r.is_empty() {
            let coef = mm(*r.last().unwrap(), lead_inv, self.p);
            let shift = r.len() - g.0.len();
            q[shift] = coef;
            self.count(g.0.len() as u64 + 1);
            for (i, &gc) in g.0.iter().enumerate() {
                r[shift + i] = sm(r[shift + i], mm(coef, gc, self.p), self.p);
            }
            r = trim(r);
        }
        UPoly(trim(q))
    }
    fn eval(&self, f: &UPoly, x: u64) -> u64 {
        self.count(f.0.len() as u64);
        let mut acc = 0u64;
        for &c in f.0.iter().rev() {
            acc = am(mm(acc, x, self.p), c, self.p);
        }
        acc
    }
    /// Sylvester resultant of two polynomials of degree ≤ 2 whose
    /// coefficients are themselves polynomials in another variable
    /// (`a[i]`, `b[i]` = coefficient of `x2^i`), computed by the
    /// explicit 4×4 determinant formula.
    fn resultant_deg2(&self, a: &[UPoly; 3], b: &[UPoly; 3]) -> UPoly {
        // Res(a2 x² + a1 x + a0, b2 x² + b1 x + b0)
        //  = (a2 b0 − a0 b2)² − (a2 b1 − a1 b2)(a1 b0 − a0 b1)
        let t1 = self.sub(&self.mul(&a[2], &b[0]), &self.mul(&a[0], &b[2]));
        let t2 = self.sub(&self.mul(&a[2], &b[1]), &self.mul(&a[1], &b[2]));
        let t3 = self.sub(&self.mul(&a[1], &b[0]), &self.mul(&a[0], &b[1]));
        self.sub(&self.mul(&t1, &t1), &self.mul(&t2, &t3))
    }
}

// ── Weil-restricted S₃ pair test ─────────────────────────────────────────

/// `S₃(x_Y, X₁, X₂)` over `F_{p³}` as a polynomial in `X₁, X₂` of degree
/// `≤ 2` in each, returned as the three `F_p`-components (`t⁰, t¹, t²`)
/// of each coefficient: `comp[k][i][j]` is the `t^k` part of the
/// coefficient of `X₁^i X₂^j`.
fn s3_weil_components(curve: &Curve3, xy: &E3) -> [[[u64; 3]; 3]; 3] {
    let f = &curve.field;
    // S₃(x, X₁, X₂) = (X₁ − X₂)² x² − 2[(X₁ + X₂)(X₁X₂ + a) + 2b] x
    //                 + (X₁X₂ − a)² − 4b(X₁ + X₂)      (with x = x_Y fixed)
    // Expand as Σ c[i][j] X₁^i X₂^j with c[i][j] ∈ F_{p³}.
    let x2 = f.sq(xy);
    let two_x = f.scale(xy, 2);
    let four_b = f.scale(&curve.b, 4);
    let a = curve.a;
    let a2 = f.sq(&a);
    let mut c = [[Fp3::ZERO; 3]; 3];
    // (X₁ − X₂)² x² = x²X₁² − 2x²X₁X₂ + x²X₂²
    c[2][0] = f.add(&c[2][0], &x2);
    c[1][1] = f.sub(&c[1][1], &f.scale(&x2, 2));
    c[0][2] = f.add(&c[0][2], &x2);
    // −2x[(X₁ + X₂)(X₁X₂ + a) + 2b] = −2x[X₁²X₂ + X₁X₂² + aX₁ + aX₂ + 2b]
    c[2][1] = f.sub(&c[2][1], &two_x);
    c[1][2] = f.sub(&c[1][2], &two_x);
    c[1][0] = f.sub(&c[1][0], &f.mul(&two_x, &a));
    c[0][1] = f.sub(&c[0][1], &f.mul(&two_x, &a));
    c[0][0] = f.sub(&c[0][0], &f.mul(&two_x, &f.scale(&curve.b, 2)));
    // (X₁X₂ − a)² = X₁²X₂² − 2aX₁X₂ + a²
    c[2][2] = f.add(&c[2][2], &Fp3::ONE);
    c[1][1] = f.sub(&c[1][1], &f.scale(&a, 2));
    c[0][0] = f.add(&c[0][0], &a2);
    // −4b(X₁ + X₂)
    c[1][0] = f.sub(&c[1][0], &four_b);
    c[0][1] = f.sub(&c[0][1], &four_b);
    let mut comp = [[[0u64; 3]; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            for k in 0..3 {
                comp[k][i][j] = c[i][j].0[k];
            }
        }
    }
    comp
}

/// Decide `Y = s₁P_i + s₂P_j` (`i ≤ j`) with the Weil-restricted `S₃`:
/// the three `F_p`-components are quadratics in `X₂` with coefficients
/// quadratic in `X₁`; the resultant of the first two in `X₂` is a
/// degree-`≤ 8` polynomial in `X₁` whose `F_p`-roots are found by
/// Cantor–Zassenhaus and completed by the quadratic formula, then
/// checked against the third component and against the base.  Signs are
/// settled by group arithmetic.  Returns the decompositions and the
/// `F_p` multiplications spent.
pub fn weil_s3_pair_test(
    inst: &Instance3,
    base: &SubspaceBase,
    y: &Pt3,
    rng: &mut StdRng,
) -> (Vec<Vec<(usize, i64)>>, u64) {
    let curve = &inst.curve;
    let p = curve.field.p;
    let ring = PolyRing::new(p);
    let mut found = Vec::new();
    if y.inf {
        return (found, 0);
    }
    let comp = s3_weil_components(curve, &y.x);
    // Component k as a quadratic in X₂ with coefficients in F_p[X₁].
    let as_quadratic = |k: usize| -> [UPoly; 3] {
        let coef = |j: usize| UPoly(trim(vec![comp[k][0][j], comp[k][1][j], comp[k][2][j]]));
        [coef(0), coef(1), coef(2)]
    };
    let q0 = as_quadratic(0);
    let q1 = as_quadratic(1);
    let q2 = as_quadratic(2);
    let r01 = ring.resultant_deg2(&q0, &q1);
    let candidates: Vec<u64> = if r01.0.is_empty() {
        // Degenerate (the two components share a factor): fall back to
        // the other resultant.
        ring.roots(&ring.resultant_deg2(&q0, &q2), rng)
    } else {
        ring.roots(&r01, rng)
    };
    for x1 in candidates {
        let Some(&i) = base.by_x.get(&x1) else {
            continue;
        };
        // Solve the three quadratics in X₂ at X₁ = x1 and intersect.
        let mut x2s: Option<Vec<u64>> = None;
        for q in [&q0, &q1, &q2] {
            let (c0, c1, c2) = (
                ring.eval(&q[0], x1),
                ring.eval(&q[1], x1),
                ring.eval(&q[2], x1),
            );
            let roots: Vec<u64> = if c2 == 0 {
                if c1 == 0 {
                    if c0 == 0 {
                        continue; // identically zero: no constraint
                    }
                    vec![]
                } else {
                    vec![mm((p - c0) % p, inv_mod(c1, p), p)]
                }
            } else {
                let disc = sm(mm(c1, c1, p), mm(4, mm(c2, c0, p), p), p);
                match sqrt_mod(disc, p) {
                    None => vec![],
                    Some(r) => {
                        let inv = inv_mod(mm(2, c2, p), p);
                        let mut v = vec![mm(sm(p - c1, r, p), inv, p)];
                        if r != 0 {
                            v.push(mm(am(p - c1, r, p), inv, p));
                        }
                        v
                    }
                }
            };
            ring.count(12);
            x2s = Some(match x2s {
                None => roots,
                Some(prev) => prev.into_iter().filter(|r| roots.contains(r)).collect(),
            });
        }
        for x2 in x2s.unwrap_or_default() {
            let Some(&j) = base.by_x.get(&x2) else {
                continue;
            };
            if j < i {
                continue;
            }
            for s_i in [1i64, -1] {
                let rest = curve.sub(y, &curve.mul_signed(&base.points[i], s_i));
                let pj = base.points[j];
                let s_j = if rest == pj {
                    1
                } else if rest == curve.neg(&pj) {
                    -1
                } else {
                    continue;
                };
                let terms = if i == j {
                    vec![(i, s_i + s_j)]
                } else {
                    vec![(i, s_i), (j, s_j)]
                };
                if terms.iter().all(|&(_, c)| c != 0) {
                    found.push(terms);
                }
            }
        }
    }
    found.sort();
    found.dedup();
    (found, ring.muls.get())
}

/// Triple oracle: `R = s_k P_k + (pair)` for every `P_k` in the base,
/// with the pair decided by [`weil_s3_pair_test`].  Returns the
/// decompositions (distinct-index triples and the pairs met on the way)
/// and the `F_p` multiplications spent inside the pair tests; the group
/// operations for `R ∓ P_k` are counted by the curve.
pub fn subspace_triple_oracle(
    inst: &Instance3,
    base: &SubspaceBase,
    r: &Pt3,
    rng: &mut StdRng,
) -> (Vec<Vec<(usize, i64)>>, u64) {
    let curve = &inst.curve;
    let mut found = Vec::new();
    let mut muls = 0u64;
    if let Some((i, s)) = base.lookup(&curve.field, r) {
        found.push(vec![(i, s)]);
    }
    for (k, pk) in base.points.iter().enumerate() {
        for s_k in [1i64, -1] {
            let y = if s_k == 1 {
                curve.sub(r, pk)
            } else {
                curve.add(r, pk)
            };
            if y.inf {
                found.push(vec![(k, s_k)]);
                continue;
            }
            if let Some((i, s)) = base.lookup(&curve.field, &y) {
                let mut terms = vec![(k, s_k), (i, s)];
                terms.sort_unstable();
                found.push(terms);
            }
            let (pairs, m) = weil_s3_pair_test(inst, base, &y, rng);
            muls += m;
            for pair in pairs {
                // Only keep k above both pair indices so every triple is
                // reported once.
                if pair.iter().all(|&(idx, _)| idx < k) {
                    let mut terms = pair;
                    terms.push((k, s_k));
                    found.push(terms);
                }
            }
        }
    }
    for t in found.iter_mut() {
        // Merge repeated indices.
        let mut acc: HashMap<usize, i64> = HashMap::new();
        for &(i, c) in t.iter() {
            *acc.entry(i).or_insert(0) += c;
        }
        let mut v: Vec<(usize, i64)> = acc.into_iter().filter(|&(_, c)| c != 0).collect();
        v.sort_unstable();
        *t = v;
    }
    found.retain(|t| !t.is_empty());
    found.sort();
    found.dedup();
    (found, muls)
}

// ── Gaudry's O(1) solve: symmetrised S₄, Macaulay matrix, eigenvalues ────

/// Sparse polynomial over `F_{p³}` in four variables, exponents ≤ 255.
#[derive(Clone, Debug)]
struct KPoly {
    terms: HashMap<[u8; 4], E3>,
}

impl KPoly {
    fn zero() -> KPoly {
        KPoly {
            terms: HashMap::new(),
        }
    }
    fn constant(c: E3) -> KPoly {
        let mut t = HashMap::new();
        if c != Fp3::ZERO {
            t.insert([0, 0, 0, 0], c);
        }
        KPoly { terms: t }
    }
    fn var(i: usize) -> KPoly {
        let mut e = [0u8; 4];
        e[i] = 1;
        let mut t = HashMap::new();
        t.insert(e, Fp3::ONE);
        KPoly { terms: t }
    }
    fn add_term(&mut self, f: &Fp3, e: [u8; 4], c: E3) {
        let entry = self.terms.entry(e).or_insert(Fp3::ZERO);
        *entry = f.add(entry, &c);
        if *entry == Fp3::ZERO {
            self.terms.remove(&e);
        }
    }
    fn add(&self, f: &Fp3, o: &KPoly) -> KPoly {
        let mut out = self.clone();
        for (&e, &c) in &o.terms {
            out.add_term(f, e, c);
        }
        out
    }
    fn sub(&self, f: &Fp3, o: &KPoly) -> KPoly {
        let mut out = self.clone();
        for (&e, &c) in &o.terms {
            out.add_term(f, e, f.neg(&c));
        }
        out
    }
    fn mul(&self, f: &Fp3, o: &KPoly) -> KPoly {
        let mut out = KPoly::zero();
        for (&e1, &c1) in &self.terms {
            for (&e2, &c2) in &o.terms {
                let e = [e1[0] + e2[0], e1[1] + e2[1], e1[2] + e2[2], e1[3] + e2[3]];
                out.add_term(f, e, f.mul(&c1, &c2));
            }
        }
        out
    }
    fn scale(&self, f: &Fp3, k: &E3) -> KPoly {
        let mut out = KPoly::zero();
        for (&e, &c) in &self.terms {
            out.add_term(f, e, f.mul(&c, k));
        }
        out
    }
    #[cfg(test)]
    fn eval(&self, f: &Fp3, x: &[E3; 4]) -> E3 {
        let mut acc = Fp3::ZERO;
        for (&e, &c) in &self.terms {
            let mut term = c;
            for i in 0..4 {
                for _ in 0..e[i] {
                    term = f.mul(&term, &x[i]);
                }
            }
            acc = f.add(&acc, &term);
        }
        acc
    }
}

/// `S₃(u, v, w)` for the curve as a symbolic polynomial with the three
/// arguments mapped to variable slots `su, sv, sw`.
fn s3_symbolic(curve: &Curve3, su: usize, sv: usize, sw: usize) -> KPoly {
    let f = &curve.field;
    let (u, v, w) = (KPoly::var(su), KPoly::var(sv), KPoly::var(sw));
    let a = KPoly::constant(curve.a);
    let b = KPoly::constant(curve.b);
    let two = f.from_base(2);
    let four = f.from_base(4);
    // (u − v)² w²
    let d = u.sub(f, &v);
    let t1 = d.mul(f, &d).mul(f, &w).mul(f, &w);
    // −2[(u + v)(uv + a) + 2b] w
    let inner = u
        .add(f, &v)
        .mul(f, &u.mul(f, &v).add(f, &a))
        .add(f, &b.scale(f, &two));
    let t2 = inner.mul(f, &w).scale(f, &f.neg(&two));
    // (uv − a)² − 4b(u + v)
    let uv_a = u.mul(f, &v).sub(f, &a);
    let t3 = uv_a
        .mul(f, &uv_a)
        .sub(f, &b.scale(f, &four).mul(f, &u.add(f, &v)));
    t1.add(f, &t2).add(f, &t3)
}

/// Coefficients of `X^0, X^1, X^2` of a polynomial of degree ≤ 2 in
/// variable slot `slot`, as polynomials in the other variables.
fn coeffs_in(poly: &KPoly, slot: usize) -> [KPoly; 3] {
    let mut out = [KPoly::zero(), KPoly::zero(), KPoly::zero()];
    for (&e, &c) in &poly.terms {
        let k = e[slot] as usize;
        assert!(k <= 2);
        let mut e2 = e;
        e2[slot] = 0;
        out[k].terms.insert(e2, c);
    }
    out
}

/// `S₄(x₁, x₂, x₃, x₄) = Res_X(S₃(x₁, x₂, X), S₃(x₃, x₄, X))` as a
/// symbolic polynomial in slots `0..4` (degree ≤ 4 in each).
fn s4_symbolic(curve: &Curve3) -> KPoly {
    let f = &curve.field;
    // A(X) = S₃(x₁, x₂, X): the resultant variable X borrows slot 3,
    // which x₄ does not use in A.
    let a_poly = s3_symbolic(curve, 0, 1, 3);
    let al = coeffs_in(&a_poly, 3);
    // B(X) = S₃(x₃, x₄, X): X borrows slot 0, which x₁ does not use in B.
    let b_poly = s3_symbolic(curve, 2, 3, 0);
    let be = coeffs_in(&b_poly, 0);
    // Res = (a₂b₀ − a₀b₂)² − (a₂b₁ − a₁b₂)(a₁b₀ − a₀b₁)
    let t1 = al[2].mul(f, &be[0]).sub(f, &al[0].mul(f, &be[2]));
    let t2 = al[2].mul(f, &be[1]).sub(f, &al[1].mul(f, &be[2]));
    let t3 = al[1].mul(f, &be[0]).sub(f, &al[0].mul(f, &be[1]));
    t1.mul(f, &t1).sub(f, &t2.mul(f, &t3))
}

/// `S₄` symmetrised in `(x₁, x₂, x₃)`: a polynomial in
/// `(e₁, e₂, e₃, x₄)` with `e₁ = x₁+x₂+x₃`, `e₂ = x₁x₂+x₁x₃+x₂x₃`,
/// `e₃ = x₁x₂x₃`, total degree ≤ 4 in the `e`s, degree ≤ 4 in `x₄`.
#[derive(Clone, Debug)]
pub struct SymmetrisedS4 {
    /// exponent `(a, b, c, d)` = `e₁^a e₂^b e₃^c x₄^d` → coefficient.
    terms: HashMap<[u8; 4], E3>,
    /// The demand-driven elimination's row plan, learned from this
    /// curve's first full solve (see [`BorderPlan`]).  Empty unless the
    /// lazy elimination is switched on.
    plan: std::sync::OnceLock<BorderPlan>,
}

impl SymmetrisedS4 {
    /// Once per curve.  Reduces the lex-leading term of the symmetric
    /// polynomial by the matching product of elementary symmetric
    /// polynomials until nothing is left.
    pub fn precompute(curve: &Curve3) -> SymmetrisedS4 {
        let f = &curve.field;
        let mut g = s4_symbolic(curve);
        let e1 = KPoly::var(0).add(f, &KPoly::var(1)).add(f, &KPoly::var(2));
        let e2 = KPoly::var(0)
            .mul(f, &KPoly::var(1))
            .add(f, &KPoly::var(0).mul(f, &KPoly::var(2)))
            .add(f, &KPoly::var(1).mul(f, &KPoly::var(2)));
        let e3 = KPoly::var(0).mul(f, &KPoly::var(1)).mul(f, &KPoly::var(2));
        let mut cache: HashMap<[u8; 3], KPoly> = HashMap::new();
        let mut terms = HashMap::new();
        // Lex-largest monomial (x₁ first), until none is left.
        while let Some((&lead, &coef)) = g.terms.iter().max_by_key(|(e, _)| **e) {
            let (a, b, c, d) = (lead[0], lead[1], lead[2], lead[3]);
            assert!(
                a >= b && b >= c,
                "not symmetric in x₁, x₂, x₃: lead {lead:?}"
            );
            let key = [a - b, b - c, c];
            let expansion = cache
                .entry(key)
                .or_insert_with(|| {
                    let mut acc = KPoly::constant(Fp3::ONE);
                    for _ in 0..key[0] {
                        acc = acc.mul(f, &e1);
                    }
                    for _ in 0..key[1] {
                        acc = acc.mul(f, &e2);
                    }
                    for _ in 0..key[2] {
                        acc = acc.mul(f, &e3);
                    }
                    acc
                })
                .clone();
            let entry = terms
                .entry([key[0], key[1], key[2], d])
                .or_insert(Fp3::ZERO);
            *entry = f.add(entry, &coef);
            // Subtract coef · expansion · x₄^d.
            for (&e, &c) in &expansion.terms {
                g.add_term(f, [e[0], e[1], e[2], d], f.neg(&f.mul(&c, &coef)));
            }
        }
        terms.retain(|_, c| *c != Fp3::ZERO);
        SymmetrisedS4 {
            terms,
            plan: std::sync::OnceLock::new(),
        }
    }

    /// The three `F_p`-components of `H(e₁, e₂, e₃, x_R)` as sparse
    /// coefficient maps over the monomials of total degree ≤ 4.
    pub fn weil_restrict(&self, f: &Fp3, x_r: &E3) -> [HashMap<[u8; 3], u64>; 3] {
        let mut out = [HashMap::new(), HashMap::new(), HashMap::new()];
        let mut pow = [Fp3::ONE; 5];
        for i in 1..5 {
            pow[i] = f.mul(&pow[i - 1], x_r);
        }
        for (&e, &c) in &self.terms {
            let v = f.mul(&c, &pow[e[3] as usize]);
            for k in 0..3 {
                let entry = out[k].entry([e[0], e[1], e[2]]).or_insert(0);
                *entry = am(*entry, v.0[k], f.p);
            }
        }
        for o in out.iter_mut() {
            o.retain(|_, v| *v != 0);
        }
        out
    }
}

/// Monomials of total degree ≤ `d` in three variables, grevlex
/// descending (largest first).
fn monomials_grevlex_desc(d: u8) -> Vec<[u8; 3]> {
    let mut v = Vec::new();
    for a in 0..=d {
        for b in 0..=(d - a) {
            for c in 0..=(d - a - b) {
                v.push([a, b, c]);
            }
        }
    }
    v.sort_by(|x, y| grevlex_cmp(y, x));
    v
}

fn grevlex_cmp(a: &[u8; 3], b: &[u8; 3]) -> std::cmp::Ordering {
    let da = a[0] as u16 + a[1] as u16 + a[2] as u16;
    let db = b[0] as u16 + b[1] as u16 + b[2] as u16;
    if da != db {
        return da.cmp(&db);
    }
    // Same degree: the one with the smaller last differing exponent
    // (from the right) is larger.
    for i in (0..3).rev() {
        if a[i] != b[i] {
            return b[i].cmp(&a[i]);
        }
    }
    std::cmp::Ordering::Equal
}

/// Row-reduce `m` (rows × cols) over `F_p` to reduced row echelon form;
/// returns the pivot column of each non-zero row, in order.  Counts
/// multiplications.
pub(crate) fn rref_mod_p(m: &mut [Vec<u64>], p: u64, muls: &mut u64) -> Vec<usize> {
    let rows = m.len();
    let cols = if rows > 0 { m[0].len() } else { 0 };
    let mut pivots = Vec::new();
    let mut r = 0;
    for c in 0..cols {
        if r >= rows {
            break;
        }
        let Some(pr) = (r..rows).find(|&i| m[i][c] != 0) else {
            continue;
        };
        m.swap(r, pr);
        let inv = inv_mod(m[r][c], p);
        for j in c..cols {
            m[r][j] = mm(m[r][j], inv, p);
        }
        *muls += (cols - c) as u64;
        let pivot_row = m[r].clone();
        for i in 0..rows {
            if i != r && m[i][c] != 0 {
                let fct = m[i][c];
                for j in c..cols {
                    if pivot_row[j] != 0 {
                        m[i][j] = sm(m[i][j], mm(fct, pivot_row[j], p), p);
                    }
                }
                *muls += (cols - c) as u64;
            }
        }
        pivots.push(c);
        r += 1;
    }
    pivots
}

/// Characteristic polynomial of a square matrix over `F_p` (Hessenberg
/// reduction, then the standard recurrence).  Coefficients low to high,
/// monic.
pub(crate) fn charpoly_mod_p(a: &[Vec<u64>], p: u64, muls: &mut u64) -> UPoly {
    let n = a.len();
    let mut h: Vec<Vec<u64>> = a.to_vec();
    // Reduce to upper Hessenberg form by similarity transforms.
    for j in 0..n.saturating_sub(2) {
        let Some(piv) = ((j + 1)..n).find(|&i| h[i][j] != 0) else {
            continue;
        };
        if piv != j + 1 {
            h.swap(piv, j + 1);
            for row in h.iter_mut() {
                row.swap(piv, j + 1);
            }
        }
        let inv = inv_mod(h[j + 1][j], p);
        for i in (j + 2)..n {
            if h[i][j] == 0 {
                continue;
            }
            let fct = mm(h[i][j], inv, p);
            // row_i -= fct · row_{j+1}
            for k in 0..n {
                let v = mm(fct, h[j + 1][k], p);
                h[i][k] = sm(h[i][k], v, p);
            }
            // col_{j+1} += fct · col_i
            for k in 0..n {
                let v = mm(fct, h[k][i], p);
                h[k][j + 1] = am(h[k][j + 1], v, p);
            }
            *muls += 2 * n as u64;
        }
    }
    // p_0 = 1; p_k(x) = (x − h[k-1][k-1]) p_{k-1}
    //                   − Σ_{i=1}^{k-1} h[i-1][k-1] (Π_{m=i}^{k-1} h[m][m-1]) p_{i-1}
    let mut polys: Vec<UPoly> = vec![UPoly(vec![1])];
    let ring = PolyRing::new(p);
    for k in 1..=n {
        let hk = h[k - 1][k - 1];
        let mut pk = ring.mul(&polys[k - 1], &UPoly(vec![(p - hk) % p, 1]));
        let mut prod = 1u64;
        for i in (1..k).rev() {
            prod = mm(prod, h[i][i - 1], p);
            let coef = mm(h[i - 1][k - 1], prod, p);
            if coef != 0 {
                pk = ring.sub(&pk, &ring.scale(&polys[i - 1], coef));
            }
        }
        polys.push(pk);
    }
    *muls += ring.muls.get();
    polys.pop().unwrap()
}

/// Kernel basis of `(m − λI)` for a square matrix `m` over `F_p`.
pub(crate) fn eigenvectors_mod_p(
    m: &[Vec<u64>],
    lambda: u64,
    p: u64,
    muls: &mut u64,
) -> Vec<Vec<u64>> {
    let n = m.len();
    let mut a: Vec<Vec<u64>> = m.to_vec();
    for i in 0..n {
        a[i][i] = sm(a[i][i], lambda, p);
    }
    let pivots = rref_mod_p(&mut a, p, muls);
    let free: Vec<usize> = (0..n).filter(|c| !pivots.contains(c)).collect();
    let mut basis = Vec::new();
    for &fc in &free {
        let mut v = vec![0u64; n];
        v[fc] = 1;
        for (r, &pc) in pivots.iter().enumerate() {
            v[pc] = (p - a[r][fc]) % p;
        }
        basis.push(v);
    }
    basis
}

/// Statistics of the `O(1)` solve, accumulated across calls.
#[derive(Clone, Debug, Default, Serialize)]
pub struct SolveStats {
    pub solves: u64,
    pub fp_muls: u64,
    pub macaulay_muls: u64,
    pub quotient_dim_total: u64,
    pub e_solutions: u64,
    pub split_cubics: u64,
    pub degenerate_eigenspaces: u64,
    /// Residuals whose degree-10 Macaulay matrix did not close the
    /// quotient (normal forms incomplete) and were redone at 11–13.
    pub retried_at_degree_11: u64,
    pub retried_at_degree_12: u64,
    pub retried_at_degree_13: u64,
    /// Residuals whose multiplication matrix could not be built because
    /// a border monomial landed on a non-pivot column at the top
    /// degree.  These go straight to the fallback instead of paying
    /// degrees 11, 12 and 13 to fail the same way.
    pub border_unreachable: u64,
    /// Residuals given up on after degree 13 (affine Macaulay matrix
    /// never closed the quotient); these are routed to the MITM oracle.
    pub unsolved: u64,
    /// F_p multiplications spent in the MITM fallback for unsolved
    /// residuals (also included in `fp_muls`).
    pub fallback_fp_muls: u64,
    /// Macaulay rows built, summed over attempts.
    pub macaulay_rows: u64,
    /// Split of `macaulay_muls`: forward elimination vs the normal
    /// forms read off by back-substitution.
    pub echelon_muls: u64,
    /// Split of the rest of the solve: characteristic polynomial,
    /// eigenvectors (including eigenspace splitting), root finding
    /// (eigenvalues and cubics).
    pub charpoly_muls: u64,
    pub eigenvector_muls: u64,
    pub roots_muls: u64,
    /// Demand-driven elimination (`GAUDRY_LAZY_ELIM`): solves finished
    /// on it, and solves that fell back to the full elimination — their
    /// lazy work stays charged.  `lazy_pivots_reduced` out of
    /// `lazy_pivots_planned` is how much of the echelon it built.
    pub lazy_solves: u64,
    pub lazy_fallbacks: u64,
    pub lazy_pivots_reduced: u64,
    pub lazy_pivots_planned: u64,
    /// `GAUDRY_LAZY_VERIFY`: lazy solves re-done with the full
    /// elimination (uncharged), and those whose staircase or `M_{e₁}`
    /// differed from it in any entry.
    pub lazy_verified: u64,
    pub lazy_verify_mismatches: u64,
    /// `GAUDRY_LAZY_VERIFY`: fallbacks whose residual turned out to have
    /// the plan's staircase after all — a fallback the lazy elimination
    /// should not have needed.  Every other fallback is a residual whose
    /// staircase is not the plan's, which no plan could serve.
    pub lazy_needless_fallbacks: u64,
}

/// Which elimination the `S₄` solve uses.  `Off` is the forward
/// elimination of the whole Macaulay matrix every earlier run used;
/// `On` reduces a row only when a normal form first reads it; `Verify`
/// is `On` plus an uncharged full elimination per solve, compared entry
/// by entry.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum LazyElim {
    #[default]
    Off,
    On,
    Verify,
}

/// Switches for [`solve_s4_subspace_with`]; [`solve_s4_subspace`] reads
/// them from the environment.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SolveMode {
    /// `GAUDRY_BORDER_RETRY`: retry border-unreachable residuals at
    /// degrees 11–13 instead of stopping (the pre-check behaviour).
    pub border_retry: bool,
    /// `GAUDRY_LAZY_ELIM` / `GAUDRY_LAZY_VERIFY`.
    pub lazy: LazyElim,
}

impl SolveMode {
    pub fn from_env() -> SolveMode {
        let lazy = if std::env::var_os("GAUDRY_LAZY_VERIFY").is_some() {
            LazyElim::Verify
        } else if std::env::var_os("GAUDRY_LAZY_ELIM").is_some() {
            LazyElim::On
        } else {
            LazyElim::Off
        };
        SolveMode {
            border_retry: border_retry_enabled(),
            lazy,
        }
    }
}

/// The row plan a demand-driven elimination follows: which Macaulay row
/// becomes the pivot row of which column, and which columns are
/// standard.  Learned once per curve from the first full solve — the
/// staircase is the same on every residual measured (§11.13) — and
/// never trusted blindly: a row that does not reduce to its planned
/// leading column, or meets a nonzero entry no planned pivot can clear,
/// sends that solve back to the full elimination.
#[derive(Clone, Debug)]
pub struct BorderPlan {
    degree: u8,
    leads: Vec<Option<[u8; 3]>>,
    nrows: usize,
    /// Pivot column → index of the Macaulay row that becomes its pivot row.
    pivot_row: HashMap<usize, usize>,
    /// Pivot column → the other rows nonzero there when the forward
    /// elimination reached it: the spares when the planned row's entry
    /// cancels on some residual.
    live: HashMap<usize, Vec<usize>>,
    /// Standard columns (the staircase), in column order.
    standard: Vec<usize>,
}

impl BorderPlan {
    fn fits(&self, degree: u8, leads: &[Option<[u8; 3]>], nrows: usize) -> bool {
        self.degree == degree && self.leads == leads && self.nrows == nrows
    }
}

/// Solve `S₄(x₁, x₂, x₃, x_R) = 0` for `x_i ∈ F_p` with cost
/// independent of the base: Weil-restrict the symmetrised polynomial,
/// build the Macaulay matrix at the regularity degree, read the
/// quotient and the multiplication matrix of `e₁`, take its
/// eigenvalues in `F_p`, recover `(e₂, e₃)` from eigenvectors, and split
/// the cubic.  Returns sorted triples `[x₁, x₂, x₃]` of `F_p` abscissae
/// (each a solution of the symmetric system whose cubic splits over
/// `F_p`).  Returns `None` when no Macaulay degree in 10–13 closes the
/// quotient, so the caller can fall back to a base-dependent oracle.
pub fn solve_s4_subspace(
    inst: &Instance3,
    pre: &SymmetrisedS4,
    x_r: &E3,
    rng: &mut StdRng,
    stats: &mut SolveStats,
) -> Option<Vec<[u64; 3]>> {
    solve_s4_subspace_with(inst, pre, x_r, rng, stats, SolveMode::from_env())
}

/// [`solve_s4_subspace`] with its switches passed rather than read from
/// the environment, so two modes can run side by side on one stream.
pub fn solve_s4_subspace_with(
    inst: &Instance3,
    pre: &SymmetrisedS4,
    x_r: &E3,
    rng: &mut StdRng,
    stats: &mut SolveStats,
    mode: SolveMode,
) -> Option<Vec<[u64; 3]>> {
    let f = &inst.curve.field;
    let mut muls = 0u64;
    stats.solves += 1;
    let comps = pre.weil_restrict(f, x_r);
    muls += pre.terms.len() as u64 * 15;

    let mut border_retry_seen = false;
    for degree in [10u8, 11, 12, 13] {
        let mut border_unreachable = false;
        match solve_at_degree(
            inst,
            &comps,
            degree,
            rng,
            stats,
            &mut muls,
            &mut border_unreachable,
            &pre.plan,
            mode.lazy,
        ) {
            Some(res) => {
                stats.fp_muls += muls;
                return Some(res);
            }
            None => {
                // The border monomial the multiplication matrix needs
                // is a non-pivot column at the top degree.  Raising the
                // degree reproduces the same situation one rung up —
                // measured: every retry in this module's runs ended in
                // the fallback, none in a solution — so stop now rather
                // than paying degrees 11, 12 and 13 at `Θ(d⁶)` each.
                border_retry_seen |= border_unreachable;
                if border_unreachable && !mode.border_retry {
                    stats.border_unreachable += 1;
                    stats.unsolved += 1;
                    if std::env::var_os("GAUDRY_DEBUG_SOLVE").is_some() {
                        eprintln!("  degree {degree}: border unreachable, no retry");
                    }
                    stats.fp_muls += muls;
                    return None;
                }
                match degree {
                    10 => stats.retried_at_degree_11 += 1,
                    11 => stats.retried_at_degree_12 += 1,
                    12 => stats.retried_at_degree_13 += 1,
                    _ => {}
                }
            }
        }
    }

    if border_retry_seen {
        stats.border_unreachable += 1;
    }
    stats.unsolved += 1;
    if std::env::var_os("GAUDRY_DEBUG_SOLVE").is_some() {
        eprintln!("  gave up after degree 13");
    }
    stats.fp_muls += muls;
    None
}

/// Keep retrying degrees 11-13 after the border check has already shown
/// they must fail.  Off by default; `GAUDRY_BORDER_RETRY=1` restores the
/// pre-check behaviour so the saving stays measurable both ways and the
/// earlier runs in `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md` can be reproduced.
fn border_retry_enabled() -> bool {
    std::env::var_os("GAUDRY_BORDER_RETRY").is_some()
}

/// One attempt at Macaulay degree `degree`; `None` when the quotient
/// does not close at that degree.  On success returns the sorted
/// solution triples.
/// `border_unreachable` is set when the multiplication matrix cannot be
/// built because a border monomial falls on a non-pivot column at the
/// top degree — a truncation artefact that recurs identically one
/// degree up, so the caller uses it to stop retrying.
/// With `lazy` on and a plan in `plan_slot` that fits, the solve runs on
/// [`solve_lazy`] first; the first full solve at a degree learns the plan.
fn solve_at_degree(
    inst: &Instance3,
    comps: &[HashMap<[u8; 3], u64>; 3],
    degree: u8,
    rng: &mut StdRng,
    stats: &mut SolveStats,
    muls: &mut u64,
    border_unreachable: &mut bool,
    plan_slot: &std::sync::OnceLock<BorderPlan>,
    lazy: LazyElim,
) -> Option<Vec<[u64; 3]>> {
    let p = inst.curve.field.p;
    let debug = std::env::var_os("GAUDRY_DEBUG_SOLVE").is_some();
    // Macaulay matrix at `degree`: every Weil component times every
    // monomial of degree ≤ degree − 4, columns in descending grevlex.
    let cols = monomials_grevlex_desc(degree);
    let col_index: HashMap<[u8; 3], usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();
    let shifts = monomials_grevlex_desc(degree - 4);
    // Macaulay's row selection: make the three leading monomials
    // distinct by eliminating among the components, then leave out
    // the shift `m · f_i` whenever `m` is divisible by the leading
    // monomial of an earlier component — those rows are Koszul
    // combinations of the rows kept, so the row space is unchanged.
    let (comps, leads) = triangularise_leads(comps, p, muls);
    let divides = |lm: &[u8; 3], m: &[u8; 3]| lm[0] <= m[0] && lm[1] <= m[1] && lm[2] <= m[2];
    let mut mat: Vec<Vec<u64>> = Vec::with_capacity(3 * shifts.len());
    for (i, comp) in comps.iter().enumerate() {
        for sh in &shifts {
            if leads
                .iter()
                .take(i)
                .any(|lm| lm.is_some_and(|lm| divides(&lm, sh)))
            {
                continue;
            }
            let mut row = vec![0u64; cols.len()];
            for (&e, &c) in comp {
                let m = [e[0] + sh[0], e[1] + sh[1], e[2] + sh[2]];
                let ci = col_index[&m];
                row[ci] = am(row[ci], c, p);
            }
            mat.push(row);
        }
    }
    stats.macaulay_rows += mat.len() as u64;
    let nrows = mat.len();

    // Demand-driven elimination, once this curve has a plan that fits.
    // A solve it cannot finish falls through to the full elimination
    // below, with the lazy work already in `muls`.
    if lazy != LazyElim::Off {
        if let Some(plan) = plan_slot.get().filter(|pl| pl.fits(degree, &leads, nrows)) {
            let verify = lazy == LazyElim::Verify;
            if let Some(res) = solve_lazy(
                plan, &mat, &cols, &col_index, &comps, degree, p, rng, stats, muls, verify, debug,
            ) {
                stats.lazy_solves += 1;
                return Some(res);
            }
            stats.lazy_fallbacks += 1;
            if debug {
                eprintln!("  degree {degree}: lazy elimination fell back to the full one");
            }
        }
    }

    let before = *muls;
    let (pivots, trace) = echelon_traced(&mut mat, p, muls);
    stats.echelon_muls += *muls - before;
    let pivot_set: std::collections::HashSet<usize> = pivots.iter().copied().collect();

    // Standard monomials: non-pivot columns of degree ≤ degree − 1.
    let standard: Vec<usize> = (0..cols.len())
        .filter(|&c| !pivot_set.contains(&c))
        .filter(|&c| (cols[c][0] + cols[c][1] + cols[c][2]) < degree)
        .collect();
    let dim = standard.len();
    if debug {
        // The staircase itself, not just its size: a border basis is cheap
        // and fixed-shape when every residual shares one order ideal, and
        // needs Mourrain's iteration with a commutation test when it does
        // not.  Printed as the per-variable maxima plus the monomial set so
        // a box `[0,k)^3` is recognisable at a glance.
        let mut std_mono: Vec<[u8; 3]> = standard.iter().map(|&c| cols[c]).collect();
        std_mono.sort_unstable();
        let mx = |k: usize| std_mono.iter().map(|m| m[k]).max().unwrap_or(0);
        let is_box = {
            let (a, b, c) = (mx(0) + 1, mx(1) + 1, mx(2) + 1);
            std_mono.len() == (a as usize) * (b as usize) * (c as usize)
                && std_mono.iter().all(|m| m[0] < a && m[1] < b && m[2] < c)
        };
        eprintln!(
            "  degree {degree}: rows {} cols {} pivots {} standard(dim) {dim}              maxima [{},{},{}] box={is_box} staircase={std_mono:?}",
            mat.len(),
            cols.len(),
            pivots.len(),
            mx(0),
            mx(1),
            mx(2),
        );
    }
    if dim == 0 || dim > 64 {
        stats.macaulay_muls += *muls - before;
        return None;
    }

    // **Is the border reachable?**  The multiplication matrix needs the
    // normal form of `e₁ · b` for every standard `b`.  A column is
    // reducible only if it is a pivot, and `standard` deliberately
    // stops at degree `degree − 1`, so a product landing on a *non-pivot
    // column of degree exactly `degree`* has no normal form at all.
    //
    // That is the failure this solver actually hits — not solutions at
    // infinity.  The ideal here is zero-dimensional (every variable has
    // a pure power among the leading monomials) and the quotient is
    // finite; it is the border of the staircase that the degree cut
    // truncates.  Raising the degree re-creates the same situation one
    // rung up, which is why every retry in the measured runs ended in
    // the fallback and none in a solution.  Detect it once and let the
    // caller stop, rather than paying degrees 11, 12 and 13 at `Θ(d⁶)`
    // each to fail identically.
    let standard_set: std::collections::HashSet<usize> = standard.iter().copied().collect();
    let unreachable = standard.iter().find_map(|&bc| {
        let b = cols[bc];
        let shifted = [b[0] + 1, b[1], b[2]];
        match col_index.get(&shifted) {
            None => Some(shifted),
            Some(&sc) if !pivot_set.contains(&sc) && !standard_set.contains(&sc) => Some(shifted),
            Some(_) => None,
        }
    });
    if let Some(m) = unreachable {
        *border_unreachable = true;
        if debug {
            eprintln!(
                "  degree {degree}: border monomial {m:?} (deg {}) is neither a pivot nor \
                 standard — no normal form exists at this degree",
                m[0] + m[1] + m[2]
            );
        }
        stats.macaulay_muls += *muls - before;
        return None;
    }

    stats.quotient_dim_total += dim as u64;
    let std_index: HashMap<usize, usize> =
        standard.iter().enumerate().map(|(i, &c)| (c, i)).collect();
    let mut nfs = NormalForms::new(&mut mat, &pivots, &std_index, dim, p);
    // Multiplication matrix of e₁: column b ↦ NF(e₁ · b).
    let m_e1 = mult_matrix(&cols, &col_index, &standard, [1, 0, 0], &mut nfs, muls);
    if debug {
        // How much of the echelon the normal forms actually depend on.  The
        // forward elimination reduces all 226 rows; if the border reaches
        // only a fraction of the pivots, a lazier elimination has something
        // to skip, and if it reaches nearly all of them it has nothing.
        let reached = nfs.memo.iter().filter(|m| m.is_some()).count();
        let reached_pivots = pivots.iter().filter(|&&c| nfs.memo[c].is_some()).count();
        eprintln!(
            "  degree {degree}: nf resolved {reached} columns of {}, of which              {reached_pivots} of {} pivots ({:.0}%)",
            cols.len(),
            pivots.len(),
            100.0 * reached_pivots as f64 / pivots.len().max(1) as f64,
        );
        // Two attributions of the same multiplications.  §11.13 charged
        // each to the pivot row doing the subtracting; what an elimination
        // that reduces only the rows it needs can skip is the work done
        // *on* rows nobody reads — the complement of the closure below.
        let elim = trace.total();
        let wasted: u64 = pivots
            .iter()
            .filter(|&&c| nfs.memo[c].is_none())
            .map(|&c| trace.done_by(c))
            .sum();
        let (needed, skippable) = trace.closure(&pivots, |c| nfs.memo[c].is_some());
        eprintln!(
            "  degree {degree}: elimination {elim} muls, {wasted} on pivots the \
             normal forms never reach ({:.1}% of elimination)",
            100.0 * wasted as f64 / elim.max(1) as f64,
        );
        eprintln!(
            "  degree {degree}: closure {needed} of {} pivot rows; {skippable} muls on rows \
             outside it ({:.1}% of elimination)",
            pivots.len(),
            100.0 * skippable as f64 / elim.max(1) as f64,
        );
    }
    stats.macaulay_muls += *muls - before;
    let Some(m_e1) = m_e1 else {
        if debug {
            eprintln!("  degree {degree}: normal form of e1·b unavailable");
        }
        return None;
    };
    let read = read_solutions(
        &m_e1, &cols, &col_index, &standard, &std_index, &pivots, &mut nfs, &comps, p, rng, stats,
        muls, debug, degree, false,
    );
    let Read::Solved(res) = read else {
        return None;
    };
    if lazy != LazyElim::Off && plan_slot.get().is_none() {
        let mut live: HashMap<usize, Vec<usize>> = HashMap::new();
        for &(c, r, _) in &trace.mods {
            live.entry(c).or_default().push(r);
        }
        let _ = plan_slot.set(BorderPlan {
            degree,
            leads,
            nrows,
            pivot_row: trace.pivot_row,
            live,
            standard,
        });
    }
    Some(res)
}

/// What reading the solutions off the normal forms came to.
enum Read {
    Solved(Vec<[u64; 3]>),
    /// `1`, `e₁`, `e₂` or `e₃` is not standard: no evaluation functionals.
    Failed,
    /// A degenerate eigenspace needed `M_{e₂}` or `M_{e₃}` and a normal
    /// form it reads was unavailable (reported only when `strict`; the
    /// full elimination has always gone on with the unsplit space).
    SplitUnavailable,
}

/// Everything after `M_{e₁}`: its characteristic polynomial and
/// eigenvalues, the eigenvectors (split by `e₂`, `e₃` when an eigenspace
/// is degenerate), the check of every candidate against the components,
/// and the cubic splits.  Shared by the full and the demand-driven
/// elimination, which differ only in how `nfs` produces a normal form.
fn read_solutions(
    m_e1: &[Vec<u64>],
    cols: &[[u8; 3]],
    col_index: &HashMap<[u8; 3], usize>,
    standard: &[usize],
    std_index: &HashMap<usize, usize>,
    pivots: &[usize],
    nfs: &mut NormalForms,
    comps: &[HashMap<[u8; 3], u64>],
    p: u64,
    rng: &mut StdRng,
    stats: &mut SolveStats,
    muls: &mut u64,
    debug: bool,
    degree: u8,
    strict: bool,
) -> Read {
    let dim = standard.len();
    // Eigenvalues in F_p from the characteristic polynomial.
    let before_cp = *muls;
    let cp = charpoly_mod_p(m_e1, p, muls);
    stats.charpoly_muls += *muls - before_cp;
    let ring = PolyRing::new(p);
    let lambdas = ring.roots(&cp, rng);
    stats.roots_muls += ring.muls.get();
    // Transpose for left eigenvectors (evaluation functionals).
    let mut mt = vec![vec![0u64; dim]; dim];
    for i in 0..dim {
        for j in 0..dim {
            mt[j][i] = m_e1[i][j];
        }
    }
    let idx_of = |mono: [u8; 3]| -> Option<usize> {
        col_index.get(&mono).and_then(|c| std_index.get(c)).copied()
    };
    let (Some(i1), Some(i2), Some(i3), Some(i0)) = (
        idx_of([1, 0, 0]),
        idx_of([0, 1, 0]),
        idx_of([0, 0, 1]),
        idx_of([0, 0, 0]),
    ) else {
        if debug {
            let low: Vec<[u8; 3]> = pivots
                .iter()
                .map(|&c| cols[c])
                .filter(|m| (m[0] + m[1] + m[2]) <= 3)
                .collect();
            eprintln!(
                "  degree {degree}: 1, e1, e2 or e3 is not standard; low-degree pivots {low:?}"
            );
        }
        *muls += ring.muls.get();
        return Read::Failed;
    };
    let eval_comp = |comp: &HashMap<[u8; 3], u64>, e: [u64; 3]| -> u64 {
        let mut acc = 0u64;
        for (&m, &c) in comp {
            let mut t = c;
            for (k, &v) in e.iter().enumerate() {
                for _ in 0..m[k] {
                    t = mm(t, v, p);
                }
            }
            acc = am(acc, t, p);
        }
        acc
    };
    let mut candidates: Vec<[u64; 3]> = Vec::new();
    if debug {
        eprintln!("  charpoly degree {} roots {:?}", cp.0.len() - 1, lambdas);
    }
    let mut m_other: [Option<Vec<Vec<u64>>>; 2] = [None, None];
    for lam in lambdas {
        let before_ev = *muls;
        let mut ker = eigenvectors_mod_p(&mt, lam, p, muls);
        stats.eigenvector_muls += *muls - before_ev;
        if debug {
            eprintln!("  λ = {lam}: kernel dim {}", ker.len());
        }
        if ker.len() > 1 {
            // Two or more solutions share e₁ = λ (or the point is not
            // reduced): the kernel basis vectors are not evaluation
            // functionals.  Split the eigenspace by the commuting
            // operators e₂ and then e₃, restricted to it.
            stats.degenerate_eigenspaces += 1;
            for (k, var) in [[0u8, 1, 0], [0, 0, 1]].into_iter().enumerate() {
                if ker.len() <= 1 {
                    break;
                }
                if m_other[k].is_none() {
                    let before = *muls;
                    m_other[k] = mult_matrix(cols, col_index, standard, var, nfs, muls);
                    stats.macaulay_muls += *muls - before;
                }
                let Some(mv) = &m_other[k] else {
                    if strict {
                        *muls += ring.muls.get();
                        return Read::SplitUnavailable;
                    }
                    break;
                };
                ker = split_eigenspace(&ker, mv, p, rng, muls);
                if debug {
                    eprintln!("    split by e{}: {} vectors", k + 2, ker.len());
                }
            }
        }
        for w in &ker {
            if w[i0] == 0 {
                continue;
            }
            let inv = inv_mod(w[i0], p);
            let e = [mm(w[i1], inv, p), mm(w[i2], inv, p), mm(w[i3], inv, p)];
            if e[0] != lam {
                continue;
            }
            if comps.iter().all(|comp| eval_comp(comp, e) == 0) {
                candidates.push(e);
            }
        }
    }
    candidates.sort_unstable();
    candidates.dedup();
    stats.e_solutions += candidates.len() as u64;
    // Split each cubic T³ − e₁T² + e₂T − e₃ over F_p.
    let mut result: Vec<[u64; 3]> = Vec::new();
    for e in candidates {
        let cubic = UPoly(vec![(p - e[2]) % p, e[1], (p - e[0]) % p, 1]);
        let roots = ring.roots(&cubic, rng);
        // Three roots counted with multiplicity: the cubic must equal
        // Π (T − r) for some multiset drawn from its distinct roots.
        let mut triple: Option<[u64; 3]> = None;
        'outer: for &r1 in &roots {
            for &r2 in &roots {
                for &r3 in &roots {
                    if r1 <= r2 && r2 <= r3 {
                        let s1 = am(am(r1, r2, p), r3, p);
                        let s2 = am(am(mm(r1, r2, p), mm(r1, r3, p), p), mm(r2, r3, p), p);
                        let s3 = mm(mm(r1, r2, p), r3, p);
                        if s1 == e[0] && s2 == e[1] && s3 == e[2] {
                            triple = Some([r1, r2, r3]);
                            break 'outer;
                        }
                    }
                }
            }
        }
        if let Some(t) = triple {
            stats.split_cubics += 1;
            result.push(t);
        }
    }
    *muls += ring.muls.get();
    result.sort_unstable();
    result.dedup();
    Read::Solved(result)
}

/// One solve on the demand-driven elimination.  The Macaulay rows stay
/// as built until a normal form reads one; [`NormalForms`] then reduces
/// that row — and, first, every planned pivot row it has to be cleared
/// with — and leaves the rest untouched.  `None` sends the residual back
/// to the full elimination; the multiplications spent here stay charged.
fn solve_lazy(
    plan: &BorderPlan,
    mat: &[Vec<u64>],
    cols: &[[u8; 3]],
    col_index: &HashMap<[u8; 3], usize>,
    comps: &[HashMap<[u8; 3], u64>],
    degree: u8,
    p: u64,
    rng: &mut StdRng,
    stats: &mut SolveStats,
    muls: &mut u64,
    verify: bool,
    debug: bool,
) -> Option<Vec<[u64; 3]>> {
    let before = *muls;
    let standard = &plan.standard;
    let dim = standard.len();
    let std_index: HashMap<usize, usize> =
        standard.iter().enumerate().map(|(i, &c)| (c, i)).collect();
    let mut rows = mat.to_vec();
    let mut nfs = NormalForms::lazy(&mut rows, plan, &std_index, dim, p);
    let m_e1 =
        mult_matrix(cols, col_index, standard, [1, 0, 0], &mut nfs, muls).filter(|_| !nfs.broken());
    stats.macaulay_muls += *muls - before;
    let Some(m_e1) = m_e1 else {
        if debug {
            eprintln!(
                "  degree {degree}: lazy elimination found no normal form (staircase off the plan: {})",
                nfs.broken()
            );
        }
        stats.echelon_muls += nfs.elim_muls;
        stats.lazy_pivots_reduced += nfs.reduced;
        stats.lazy_pivots_planned += plan.pivot_row.len() as u64;
        if verify && staircase_of(mat, cols, degree, p) == *standard {
            stats.lazy_needless_fallbacks += 1;
        }
        return None;
    };
    if verify {
        // The full elimination on the same rows, uncharged: its staircase
        // must be the plan's and its `M_{e₁}` must agree in every entry.
        let mut scratch = 0u64;
        let mut full = mat.to_vec();
        let (pivots_f, _) = echelon_traced(&mut full, p, &mut scratch);
        let pivot_set: std::collections::HashSet<usize> = pivots_f.iter().copied().collect();
        let standard_f: Vec<usize> = (0..cols.len())
            .filter(|&c| !pivot_set.contains(&c))
            .filter(|&c| (cols[c][0] + cols[c][1] + cols[c][2]) < degree)
            .collect();
        let same = standard_f == *standard && {
            let mut nfs_f = NormalForms::new(&mut full, &pivots_f, &std_index, dim, p);
            mult_matrix(
                cols,
                col_index,
                standard,
                [1, 0, 0],
                &mut nfs_f,
                &mut scratch,
            )
            .as_ref()
                == Some(&m_e1)
        };
        stats.lazy_verified += 1;
        if !same {
            stats.lazy_verify_mismatches += 1;
            if debug {
                eprintln!(
                    "  degree {degree}: lazy/full mismatch (staircase equal: {})",
                    standard_f == *standard
                );
            }
        }
    }
    let mut planned: Vec<usize> = plan.pivot_row.keys().copied().collect();
    planned.sort_unstable();
    let read = read_solutions(
        &m_e1, cols, col_index, standard, &std_index, &planned, &mut nfs, comps, p, rng, stats,
        muls, debug, degree, true,
    );
    let read = if nfs.broken() {
        Read::SplitUnavailable
    } else {
        read
    };
    stats.echelon_muls += nfs.elim_muls;
    stats.lazy_pivots_reduced += nfs.reduced;
    stats.lazy_pivots_planned += plan.pivot_row.len() as u64;
    if debug {
        eprintln!(
            "  degree {degree}: lazy elimination reduced {} of {} planned pivot rows, {} muls",
            nfs.reduced,
            plan.pivot_row.len(),
            nfs.elim_muls
        );
    }
    match read {
        Read::Solved(res) => {
            stats.quotient_dim_total += dim as u64;
            Some(res)
        }
        Read::Failed | Read::SplitUnavailable => {
            if verify && staircase_of(mat, cols, degree, p) == *standard {
                stats.lazy_needless_fallbacks += 1;
            }
            None
        }
    }
}

/// The standard columns of `mat` at `degree` — non-pivot columns below
/// the top degree — from a full elimination on a copy, uncharged.  Only
/// the verification mode calls it.
fn staircase_of(mat: &[Vec<u64>], cols: &[[u8; 3]], degree: u8, p: u64) -> Vec<usize> {
    let mut scratch = 0u64;
    let (pivots, _) = echelon_traced(&mut mat.to_vec(), p, &mut scratch);
    let pivot_set: std::collections::HashSet<usize> = pivots.into_iter().collect();
    (0..cols.len())
        .filter(|&c| !pivot_set.contains(&c))
        .filter(|&c| (cols[c][0] + cols[c][1] + cols[c][2]) < degree)
        .collect()
}

/// What a forward elimination did, by original row index: the row each
/// pivot column took, the multiplications normalising it, and every
/// reduction of one row by a pivot row with its cost.  The demand-driven
/// elimination learns its plan from `pivot_row`; the rest prices what
/// it can skip.
struct EchelonTrace {
    pivot_row: HashMap<usize, usize>,
    norm: HashMap<usize, u64>,
    /// `(pivot column, original index of the row it reduced, multiplications)`.
    mods: Vec<(usize, usize, u64)>,
}

impl EchelonTrace {
    fn total(&self) -> u64 {
        self.norm.values().sum::<u64>() + self.mods.iter().map(|m| m.2).sum::<u64>()
    }

    /// §11.13's attribution: the work pivot column `c` *did* — its
    /// normalisation and every reduction it performed, on any row.
    fn done_by(&self, c: usize) -> u64 {
        self.norm.get(&c).copied().unwrap_or(0)
            + self
                .mods
                .iter()
                .filter(|m| m.0 == c)
                .map(|m| m.2)
                .sum::<u64>()
    }

    /// The rows a set of normal forms depends on — the pivot rows of the
    /// columns they reached and, transitively, every pivot row subtracted
    /// from one of those — and the multiplications spent on rows outside
    /// that set, which nothing ever reads.  Returns `(rows, muls)`.
    fn closure(&self, pivots: &[usize], reached: impl Fn(usize) -> bool) -> (usize, u64) {
        let mut needed: std::collections::HashSet<usize> = pivots
            .iter()
            .filter(|&&c| reached(c))
            .map(|c| self.pivot_row[c])
            .collect();
        let mut reduces: HashMap<usize, Vec<usize>> = HashMap::new();
        for &(c, r, _) in &self.mods {
            reduces.entry(c).or_default().push(r);
        }
        // A pivot row reduces only rows that become pivots further right
        // (or end as zero rows, which nothing reads), so one right-to-left
        // pass settles every row before anything that reduced it is asked.
        for &c in pivots.iter().rev() {
            let r = self.pivot_row[&c];
            if !needed.contains(&r)
                && reduces
                    .get(&c)
                    .is_some_and(|rs| rs.iter().any(|x| needed.contains(x)))
            {
                needed.insert(r);
            }
        }
        let skippable = pivots
            .iter()
            .filter(|c| !needed.contains(&self.pivot_row[c]))
            .map(|c| self.norm[c])
            .sum::<u64>()
            + self
                .mods
                .iter()
                .filter(|m| !needed.contains(&m.1))
                .map(|m| m.2)
                .sum::<u64>();
        (needed.len(), skippable)
    }
}

/// Forward elimination to row echelon form over `F_p` (pivot rows
/// normalised to a leading `1`), sparse-aware: only rows with a nonzero
/// entry in the pivot column are touched, and only the nonzero entries
/// of the pivot row are multiplied — `muls` counts exactly those.
/// Returns the pivot columns in order — row `k` is the pivot row of
/// `pivots[k]` and rows from `pivots.len()` on are zero — and the
/// [`EchelonTrace`] of which original row went where at what cost.
fn echelon_traced(m: &mut [Vec<u64>], p: u64, muls: &mut u64) -> (Vec<usize>, EchelonTrace) {
    let rows = m.len();
    let cols = if rows > 0 { m[0].len() } else { 0 };
    let mut orig: Vec<usize> = (0..rows).collect();
    let mut trace = EchelonTrace {
        pivot_row: HashMap::new(),
        norm: HashMap::new(),
        mods: Vec::new(),
    };
    let mut pivots = Vec::new();
    let mut r = 0;
    for c in 0..cols {
        if r >= rows {
            break;
        }
        let Some(pr) = (r..rows).find(|&i| m[i][c] != 0) else {
            continue;
        };
        m.swap(r, pr);
        orig.swap(r, pr);
        let inv = inv_mod(m[r][c], p);
        let mut nz: Vec<usize> = Vec::new();
        for j in c..cols {
            if m[r][j] != 0 {
                m[r][j] = mm(m[r][j], inv, p);
                nz.push(j);
            }
        }
        *muls += nz.len() as u64;
        trace.norm.insert(c, nz.len() as u64);
        let pivot_row = m[r].clone();
        for i in (r + 1)..rows {
            if m[i][c] != 0 {
                let fct = m[i][c];
                for &j in &nz {
                    m[i][j] = sm(m[i][j], mm(fct, pivot_row[j], p), p);
                }
                *muls += nz.len() as u64;
                trace.mods.push((c, orig[i], nz.len() as u64));
            }
        }
        trace.pivot_row.insert(c, orig[r]);
        pivots.push(c);
        r += 1;
    }
    (pivots, trace)
}

/// Forward elimination mod `p` returning the pivot columns, counting the
/// multiplications in `muls`.  The untraced form of the traced echelon
/// above; kept as the plain reference it is checked against in the tests.
#[cfg(test)]
fn echelon_mod_p(m: &mut [Vec<u64>], p: u64, muls: &mut u64) -> Vec<usize> {
    let rows = m.len();
    let cols = if rows > 0 { m[0].len() } else { 0 };
    let mut pivots = Vec::new();
    let mut r = 0;
    for c in 0..cols {
        if r >= rows {
            break;
        }
        let Some(pr) = (r..rows).find(|&i| m[i][c] != 0) else {
            continue;
        };
        m.swap(r, pr);
        let inv = inv_mod(m[r][c], p);
        let mut nz: Vec<usize> = Vec::new();
        for j in c..cols {
            if m[r][j] != 0 {
                m[r][j] = mm(m[r][j], inv, p);
                nz.push(j);
            }
        }
        *muls += nz.len() as u64;
        let pivot_row = m[r].clone();
        for i in (r + 1)..rows {
            if m[i][c] != 0 {
                let fct = m[i][c];
                for &j in &nz {
                    m[i][j] = sm(m[i][j], mm(fct, pivot_row[j], p), p);
                }
                *muls += nz.len() as u64;
            }
        }
        pivots.push(c);
        r += 1;
    }
    pivots
}

/// Normal forms over the standard monomials, by memoised
/// back-substitution in the echelon form — the reduced echelon form is
/// never built, only the normal forms actually asked for.
///
/// In demand-driven mode ([`NormalForms::lazy`]) the echelon form is not
/// built either: the rows are the Macaulay rows as constructed, and a
/// pivot row is found and reduced the first time a normal form reads it.
struct NormalForms<'a> {
    m: &'a mut [Vec<u64>],
    /// Pivot column → row.  Complete after a full elimination; filled in
    /// as rows are reduced in demand-driven mode.
    pivot_row: HashMap<usize, usize>,
    std_index: &'a HashMap<usize, usize>,
    dim: usize,
    p: u64,
    memo: Vec<Option<Vec<u64>>>,
    lazy: Option<LazyRows<'a>>,
    /// Multiplications the demand-driven mode spent reducing rows (also
    /// counted in the caller's `muls`), and how many pivot rows it built.
    elim_muls: u64,
    reduced: u64,
}

/// Demand-driven mode's bookkeeping, per Macaulay row.
struct LazyRows<'a> {
    plan: &'a BorderPlan,
    /// Row `r` has no nonzero entry left of column `upto[r]`.
    upto: Vec<usize>,
    /// Already some column's pivot row.
    used: Vec<bool>,
    /// Being reduced further up the call stack.
    busy: Vec<bool>,
    /// Rows tried for a column whose entry there cancelled: they lead
    /// further right, so they are the first spares for later columns.
    displaced: Vec<usize>,
    /// Some row led at a column the plan does not pivot: this residual's
    /// staircase is not the plan's, and no normal form here is trusted.
    broken: bool,
}

/// What clearing a row left of a column came to.
enum Cleared {
    /// It leads at the column.
    Leads,
    /// Its entry there cancelled too; it leads further right.
    Cancelled,
    /// It leads at an earlier pivot column that had no free row, and
    /// has become that column's pivot row instead.
    Adopted,
    /// It leads at a column with no pivot in the plan.
    Broken,
}

impl<'a> NormalForms<'a> {
    /// Over a forward-eliminated matrix: row `k` is the pivot row of
    /// `pivots[k]`.
    fn new(
        m: &'a mut [Vec<u64>],
        pivots: &[usize],
        std_index: &'a HashMap<usize, usize>,
        dim: usize,
        p: u64,
    ) -> Self {
        let pivot_row = pivots.iter().enumerate().map(|(r, &c)| (c, r)).collect();
        Self::build(m, pivot_row, std_index, dim, p, None)
    }

    /// Over the Macaulay rows as built, following `plan`: nothing is
    /// eliminated until a normal form reads it.
    fn lazy(
        m: &'a mut [Vec<u64>],
        plan: &'a BorderPlan,
        std_index: &'a HashMap<usize, usize>,
        dim: usize,
        p: u64,
    ) -> Self {
        let rows = m.len();
        let lazy = LazyRows {
            plan,
            upto: vec![0; rows],
            used: vec![false; rows],
            busy: vec![false; rows],
            displaced: Vec::new(),
            broken: false,
        };
        Self::build(m, HashMap::new(), std_index, dim, p, Some(lazy))
    }

    fn build(
        m: &'a mut [Vec<u64>],
        pivot_row: HashMap<usize, usize>,
        std_index: &'a HashMap<usize, usize>,
        dim: usize,
        p: u64,
        lazy: Option<LazyRows<'a>>,
    ) -> Self {
        let cols = if m.is_empty() { 0 } else { m[0].len() };
        NormalForms {
            m,
            pivot_row,
            std_index,
            dim,
            p,
            memo: vec![None; cols],
            lazy,
            elim_muls: 0,
            reduced: 0,
        }
    }

    /// Demand-driven mode found a row leading off the plan's staircase.
    fn broken(&self) -> bool {
        self.lazy.as_ref().is_some_and(|lz| lz.broken)
    }

    /// The reduced row whose leading entry is column `c`.  `None` when
    /// `c` is not a pivot column or — demand-driven — when no row can be
    /// brought to lead there.
    ///
    /// Demand-driven, any row of the Macaulay matrix that leads at `c`
    /// once its entries to the left are cleared will do: it is in the
    /// row space with leading monomial `c`, and the normal forms read
    /// off distinct-lead rows do not depend on which rows they are.  The
    /// plan's row is tried first; if its entry at `c` cancels — an
    /// accident of the values, probability about `1/p` per entry — the
    /// rows displaced that way earlier are tried, then the rows that were
    /// live in column `c` when the plan was learned, then any row left.
    fn pivot(&mut self, c: usize, muls: &mut u64) -> Option<usize> {
        if let Some(&r) = self.pivot_row.get(&c) {
            return Some(r);
        }
        let lz = self.lazy.as_ref()?;
        if lz.broken {
            return None;
        }
        let mut tries = vec![*lz.plan.pivot_row.get(&c)?];
        tries.extend(lz.displaced.iter().copied());
        if let Some(live) = lz.plan.live.get(&c) {
            tries.extend(live.iter().copied());
        }
        // Last resort, as the forward elimination itself searches: every
        // row not yet spent.
        tries.extend((0..lz.used.len()).filter(|&r| !lz.used[r]));
        for r in tries {
            let lz = self.lazy.as_ref()?;
            if lz.used[r] || lz.busy[r] {
                continue;
            }
            match self.clear(r, c, muls) {
                Cleared::Leads => {
                    let p = self.p;
                    let inv = inv_mod(self.m[r][c], p);
                    let mut spent = 0u64;
                    for x in self.m[r].iter_mut().skip(c) {
                        if *x != 0 {
                            *x = mm(*x, inv, p);
                            spent += 1;
                        }
                    }
                    *muls += spent;
                    self.elim_muls += spent;
                    self.reduced += 1;
                    self.pivot_row.insert(c, r);
                    let lz = self.lazy.as_mut()?;
                    lz.used[r] = true;
                    lz.displaced.retain(|&x| x != r);
                    return Some(r);
                }
                Cleared::Cancelled => {
                    let lz = self.lazy.as_mut()?;
                    if !lz.displaced.contains(&r) {
                        lz.displaced.push(r);
                    }
                }
                Cleared::Adopted => {}
                Cleared::Broken => {
                    self.lazy.as_mut()?.broken = true;
                    return None;
                }
            }
        }
        None
    }

    /// Clear row `r` left of column `c` with the pivot rows of those
    /// columns — finding and reducing them first if nothing has read
    /// them yet — exactly as the forward elimination would, but one row
    /// at a time, so a row nobody reads is never touched and a row that
    /// is read costs what it costs there.
    fn clear(&mut self, r: usize, c: usize, muls: &mut u64) -> Cleared {
        let p = self.p;
        let Some(lz) = self.lazy.as_mut() else {
            return Cleared::Broken;
        };
        let start = lz.upto[r];
        if start > c {
            return Cleared::Cancelled;
        }
        lz.busy[r] = true;
        let mut row = std::mem::take(&mut self.m[r]);
        let width = row.len();
        let mut spent = 0u64;
        let mut outcome = None;
        let mut upto = c;
        for j in start..c {
            let a = row[j];
            if a == 0 {
                continue;
            }
            // Every entry left of `j` is zero: the row leads at `j`.
            let planned = self
                .lazy
                .as_ref()
                .is_some_and(|lz| lz.plan.pivot_row.contains_key(&j));
            if !planned {
                outcome = Some(Cleared::Broken);
                upto = j;
                break;
            }
            let Some(rj) = self.pivot(j, muls) else {
                upto = j;
                if self.broken() {
                    outcome = Some(Cleared::Broken);
                    break;
                }
                // No free row leads at `j` and this one does — the rows
                // that could are further up the call stack — so, as in
                // the forward elimination, it becomes `j`'s pivot row.
                let inv = inv_mod(a, p);
                for x in row.iter_mut().skip(j) {
                    if *x != 0 {
                        *x = mm(*x, inv, p);
                        spent += 1;
                    }
                }
                outcome = Some(Cleared::Adopted);
                break;
            };
            let piv = &self.m[rj];
            for k in j..width {
                if piv[k] != 0 {
                    row[k] = sm(row[k], mm(a, piv[k], p), p);
                    spent += 1;
                }
            }
        }
        let outcome = match outcome {
            Some(o) => o,
            None if row[c] != 0 => Cleared::Leads,
            None => {
                upto = c + 1;
                Cleared::Cancelled
            }
        };
        self.m[r] = row;
        *muls += spent;
        self.elim_muls += spent;
        if let Some(lz) = self.lazy.as_mut() {
            lz.busy[r] = false;
            lz.upto[r] = upto;
            if matches!(outcome, Cleared::Adopted) {
                lz.used[r] = true;
                lz.displaced.retain(|&x| x != r);
            }
        }
        if matches!(outcome, Cleared::Adopted) {
            self.pivot_row.insert(upto, r);
            self.reduced += 1;
        }
        outcome
    }

    /// `None` when column `c` is neither standard nor a pivot (a
    /// monomial the matrix does not reduce at this degree), or — in
    /// demand-driven mode — when no row can be brought to lead there.
    fn nf(&mut self, c: usize, muls: &mut u64) -> Option<Vec<u64>> {
        if let Some(v) = &self.memo[c] {
            return Some(v.clone());
        }
        let p = self.p;
        let mut v = vec![0u64; self.dim];
        if let Some(&i) = self.std_index.get(&c) {
            v[i] = 1;
            self.memo[c] = Some(v.clone());
            return Some(v);
        }
        let r = self.pivot(c, muls)?;
        let cols = self.m[r].len();
        for j in (c + 1)..cols {
            let a = self.m[r][j];
            if a == 0 {
                continue;
            }
            if let Some(&i) = self.std_index.get(&j) {
                v[i] = sm(v[i], a, p);
            } else {
                let w = self.nf(j, muls)?;
                for (k, &wk) in w.iter().enumerate() {
                    if wk != 0 {
                        v[k] = sm(v[k], mm(a, wk, p), p);
                        *muls += 1;
                    }
                }
            }
        }
        self.memo[c] = Some(v.clone());
        Some(v)
    }
}

/// Grevlex-leading monomial of a sparse polynomial, if any.
fn leading_monomial(f: &HashMap<[u8; 3], u64>) -> Option<[u8; 3]> {
    f.iter()
        .filter(|(_, &c)| c != 0)
        .map(|(m, _)| *m)
        .max_by(grevlex_cmp)
}

/// Eliminate among the three components so that their leading
/// monomials are distinct (and of degree 4, generically); returns the
/// new components in decreasing order of leading monomial and those
/// leading monomials (`None` for a component that vanished).
fn triangularise_leads(
    comps: &[HashMap<[u8; 3], u64>; 3],
    p: u64,
    muls: &mut u64,
) -> (Vec<HashMap<[u8; 3], u64>>, Vec<Option<[u8; 3]>>) {
    let mut fs: Vec<HashMap<[u8; 3], u64>> = comps.to_vec();
    for _round in 0..8 {
        fs.sort_by(|a, b| match (leading_monomial(a), leading_monomial(b)) {
            (Some(x), Some(y)) => grevlex_cmp(&y, &x),
            (Some(_), None) => std::cmp::Ordering::Less,
            (None, Some(_)) => std::cmp::Ordering::Greater,
            (None, None) => std::cmp::Ordering::Equal,
        });
        let mut changed = false;
        for i in 1..fs.len() {
            let (Some(li), Some(lj)) = (leading_monomial(&fs[i]), leading_monomial(&fs[i - 1]))
            else {
                continue;
            };
            if li == lj {
                // f_i ← f_i − (lc_i / lc_{i−1}) f_{i−1}.
                let f = mm(fs[i][&li], inv_mod(fs[i - 1][&lj], p), p);
                let prev = fs[i - 1].clone();
                for (&m, &c) in &prev {
                    let e = fs[i].entry(m).or_insert(0);
                    *e = sm(*e, mm(f, c, p), p);
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
    let leads = fs.iter().map(leading_monomial).collect();
    (fs, leads)
}

/// Multiplication matrix of the variable `var` on the quotient:
/// column `b` ↦ `NF(var · b)`, `None` when some product's normal form
/// is unavailable at this degree.
fn mult_matrix(
    cols: &[[u8; 3]],
    col_index: &HashMap<[u8; 3], usize>,
    standard: &[usize],
    var: [u8; 3],
    nfs: &mut NormalForms,
    muls: &mut u64,
) -> Option<Vec<Vec<u64>>> {
    let dim = standard.len();
    let debug = std::env::var_os("GAUDRY_DEBUG_SOLVE").is_some();
    let mut m = vec![vec![0u64; dim]; dim];
    for (bi, &bc) in standard.iter().enumerate() {
        let b = cols[bc];
        let shifted = [b[0] + var[0], b[1] + var[1], b[2] + var[2]];
        let Some(&sc) = col_index.get(&shifted) else {
            if debug {
                eprintln!(
                    "    mult_matrix: {shifted:?} (deg {}) is not a column",
                    shifted[0] + shifted[1] + shifted[2]
                );
            }
            return None;
        };
        let Some(nf) = nfs.nf(sc, muls) else {
            if debug {
                eprintln!(
                    "    mult_matrix: no normal form for {shifted:?} (deg {}), from standard \
                     {b:?} (deg {})",
                    shifted[0] + shifted[1] + shifted[2],
                    b[0] + b[1] + b[2]
                );
            }
            return None;
        };
        for (ri, &val) in nf.iter().enumerate() {
            m[ri][bi] = val;
        }
    }
    Some(m)
}

/// Given a basis `w` of an eigenspace of `M_{e₁}ᵀ` (row functionals)
/// and another multiplication matrix `mv` (commuting with `M_{e₁}`),
/// return the eigenvectors of `mv`ᵀ restricted to that space: the
/// space is invariant, so `wᵢ · mv = Σⱼ aᵢⱼ wⱼ`, and the left
/// eigenvectors of the small matrix `a` combine the `wⱼ` into
/// functionals that are simultaneous eigenvectors.  Vectors of an
/// eigenvalue whose kernel is still degenerate are returned as they
/// are (for a further split by the next variable).
pub(crate) fn split_eigenspace(
    w: &[Vec<u64>],
    mv: &[Vec<u64>],
    p: u64,
    rng: &mut StdRng,
    muls: &mut u64,
) -> Vec<Vec<u64>> {
    let k = w.len();
    let dim = mv.len();
    // y_i = w_i · mv.
    let mut y = vec![vec![0u64; dim]; k];
    for i in 0..k {
        for l in 0..dim {
            if w[i][l] == 0 {
                continue;
            }
            for j in 0..dim {
                if mv[l][j] != 0 {
                    y[i][j] = am(y[i][j], mm(w[i][l], mv[l][j], p), p);
                    *muls += 1;
                }
            }
        }
    }
    // Coefficients a_{ij} with y_i = Σ_j a_{ij} w_j: solve [Wᵀ | y_iᵀ].
    let mut a = vec![vec![0u64; k]; k];
    for i in 0..k {
        let mut sys: Vec<Vec<u64>> = (0..dim)
            .map(|r| {
                let mut row: Vec<u64> = (0..k).map(|j| w[j][r]).collect();
                row.push(y[i][r]);
                row
            })
            .collect();
        let pivots = rref_mod_p(&mut sys, p, muls);
        for (r, &pc) in pivots.iter().enumerate() {
            if pc < k {
                a[i][pc] = sys[r][k];
            }
        }
    }
    // Left eigenvectors of a: kernel of (aᵀ − μ I).
    let mut at = vec![vec![0u64; k]; k];
    for i in 0..k {
        for j in 0..k {
            at[j][i] = a[i][j];
        }
    }
    let cp = charpoly_mod_p(&a, p, muls);
    let ring = PolyRing::new(p);
    let mus = ring.roots(&cp, rng);
    *muls += ring.muls.get();
    let mut out = Vec::new();
    for mu in mus {
        for v in eigenvectors_mod_p(&at, mu, p, muls) {
            let mut u = vec![0u64; dim];
            for j in 0..k {
                if v[j] == 0 {
                    continue;
                }
                for r in 0..dim {
                    if w[j][r] != 0 {
                        u[r] = am(u[r], mm(v[j], w[j][r], p), p);
                        *muls += 1;
                    }
                }
            }
            out.push(u);
        }
    }
    out
}

/// Triple oracle built on [`solve_s4_subspace`]: decompositions of `R`
/// as `±P_i ± P_j ± P_k` (distinct or repeated indices), signs settled
/// by group arithmetic, plus `R = ±P_i`.
pub fn subspace_triple_oracle_groebner(
    inst: &Instance3,
    base: &SubspaceBase,
    pre: &SymmetrisedS4,
    r: &Pt3,
    rng: &mut StdRng,
    stats: &mut SolveStats,
) -> Vec<Vec<(usize, i64)>> {
    let curve = &inst.curve;
    let mut found = Vec::new();
    if r.inf {
        return found;
    }
    if let Some((i, s)) = base.lookup(&curve.field, r) {
        found.push(vec![(i, s)]);
    }
    let Some(triples) = solve_s4_subspace(inst, pre, &r.x, rng, stats) else {
        // Affine Macaulay failure (components at infinity): counted
        // fallback to the base-dependent MITM oracle.
        let (decs, muls) = subspace_triple_oracle(inst, base, r, rng);
        stats.fallback_fp_muls += muls;
        stats.fp_muls += muls;
        return decs;
    };
    for [x1, x2, x3] in triples {
        let idx: Option<Vec<usize>> = [x1, x2, x3]
            .iter()
            .map(|x| base.by_x.get(x).copied())
            .collect();
        let Some(idx) = idx else {
            continue;
        };
        // R = s₁P₁ + s₂P₂ + s₃P₃ for some signs.
        for s1 in [1i64, -1] {
            let a1 = curve.sub(r, &curve.mul_signed(&base.points[idx[0]], s1));
            for s2 in [1i64, -1] {
                let a2 = curve.sub(&a1, &curve.mul_signed(&base.points[idx[1]], s2));
                let p3 = base.points[idx[2]];
                let s3 = if a2 == p3 {
                    1
                } else if a2 == curve.neg(&p3) {
                    -1
                } else {
                    continue;
                };
                let mut acc: HashMap<usize, i64> = HashMap::new();
                for (i, s) in [(idx[0], s1), (idx[1], s2), (idx[2], s3)] {
                    *acc.entry(i).or_insert(0) += s;
                }
                let mut terms: Vec<(usize, i64)> =
                    acc.into_iter().filter(|&(_, c)| c != 0).collect();
                terms.sort_unstable();
                if !terms.is_empty() {
                    found.push(terms);
                }
            }
        }
    }
    found.sort();
    found.dedup();
    found
}

// ── Relation collection and the rho reference ────────────────────────────

/// Report of one Gaudry-style run.
#[derive(Clone, Debug, Serialize)]
pub struct GaudryReport {
    pub p: u64,
    pub n: u64,
    pub bits: f64,
    pub base: usize,
    pub residuals: u64,
    pub decompositions: u64,
    pub relations_verified: u64,
    pub relations_independent: u64,
    pub rank: usize,
    pub solved: bool,
    pub correct: Option<bool>,
    /// Affine additions in `E(F_{p³})` (sampling, neighbours, verification).
    pub group_ops: u64,
    /// `F_p` multiplications inside the pair tests.
    pub oracle_fp_muls: u64,
    /// `F_p` multiplications per affine addition, measured.
    pub fp_muls_per_add: f64,
    /// `group_ops + oracle_fp_muls / fp_muls_per_add`.
    pub total_ops: f64,
    pub s: f64,
    pub pair_tests: u64,
    pub fp_muls_per_pair_test: f64,
    pub decomposition_rate: f64,
    pub wall_ms: f64,
    pub linear_algebra_ms: f64,
    pub solver: Solver,
    /// `F_p` multiplications of the once-per-curve symmetrised-`S₄`
    /// precomputation (included in `total_ops`).
    pub precompute_fp_muls: u64,
    pub solve_stats: SolveStats,
    pub cross_checked: u64,
    pub cross_check_mismatches: u64,
    /// Linear algebra: `"dense"` (incremental elimination) or
    /// `"wiedemann"`; multiplications modulo `n` it performed; the
    /// number of unknowns and rows it was given; the mean row weight
    /// of those rows; solve attempts (Wiedemann retries with more rows).
    pub la_mode: String,
    pub la_ops: u64,
    /// Relations the merge-level cap discarded: residuals paid for and
    /// thrown away, which is what the cap costs.
    pub lp_abandoned: u64,
    /// Mean pivot reductions a surviving relation went through.
    pub lp_mean_merge_depth: f64,
    /// The cap in force, echoed so a row states its own configuration.
    pub lp_max_merge_level: u8,
    /// Multiplications the **eliminator** spent merging pivots, separated
    /// from the solve.  A merge-level cap trades one against the other --
    /// it makes the matrix sparser and the eliminator busier -- so lumping
    /// them in `la_ops` hides which way the trade went.
    pub lp_merge_ops: u64,
    pub la_unknowns: usize,
    pub la_rows: usize,
    pub la_avg_weight: f64,
    pub la_attempts: u64,
    /// Relations dropped by the filtering step (singleton columns and
    /// the surplus above square).
    pub la_filtered_out: usize,
    /// `F_p`-multiplication equivalents charged per multiplication
    /// modulo `n` (`n ≈ p³`: schoolbook, `9`).
    pub la_fp_equiv: f64,
    /// Large primes: the small base `|F'|` (`= |F|` when unused), the
    /// maximum number of large primes accepted per relation, the
    /// decompositions by number of large primes (`0, 1, 2, ≥ 3`), and
    /// the full relations produced by eliminating large primes.
    pub small_base: usize,
    pub max_large_primes: u8,
    pub lp_histogram: [u64; 4],
    pub lp_full_relations: u64,
}

/// Options of a Gaudry-style run; see [`run_gaudry_opts`].
#[derive(Clone, Debug, Serialize)]
pub struct GaudryOptions {
    pub max_residuals: u64,
    pub solver: Solver,
    /// Run the other oracle on every residual and count disagreements.
    pub cross_check: bool,
    /// Solve the relation system by sequential Wiedemann on a square
    /// selection of rows instead of incremental dense elimination.
    pub sparse_la: bool,
    /// Size of the small factor base `F'` (the first `small_base`
    /// points of the base); `0` means the whole base and no large
    /// primes.
    pub small_base: usize,
    /// Decompositions with more large primes than this are discarded.
    pub max_large_primes: u8,
    /// **Merge-level cap.**  A relation is abandoned once it has been
    /// reduced against this many stored pivots, instead of being chained
    /// until every large prime cancels.  `0` means no cap, which is what
    /// this module did before it was measured and what section 11.7 of
    /// `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md` records
    /// as its loose end: chaining merges the pivots' columns in, so row
    /// weight grows with `n` and the linear algebra measures `n^{0.56}`
    /// against its own `4/9`.  Capping holds the weight down and pays for
    /// it in discarded residuals; which side of that trade wins is
    /// [`GaudryReport::lp_abandoned`] against the fitted exponent.
    pub max_merge_level: u8,
}

impl Default for GaudryOptions {
    fn default() -> Self {
        GaudryOptions {
            max_residuals: 1_000_000,
            solver: Solver::MeetInTheMiddle,
            cross_check: false,
            sparse_la: false,
            small_base: 0,
            max_large_primes: 0,
            max_merge_level: 0,
        }
    }
}

/// A relation as a sparse row: `Σ coeff · x_col ≡ rhs (mod n)`.
#[derive(Clone, Debug)]
pub struct SparseRel {
    pub cols: Vec<(usize, u64)>,
    pub rhs: u64,
}

impl SparseRel {
    /// `self − f · other`, columns merged; counts the multiplications.
    fn sub_scaled(&self, f: u64, other: &SparseRel, n: u64, ops: &mut u64) -> SparseRel {
        let mut acc: HashMap<usize, u64> = self.cols.iter().copied().collect();
        for &(c, v) in &other.cols {
            let e = acc.entry(c).or_insert(0);
            *e = (*e + n - mm(f, v, n)) % n;
            *ops += 1;
        }
        let mut cols: Vec<(usize, u64)> = acc.into_iter().filter(|&(_, v)| v != 0).collect();
        cols.sort_unstable();
        *ops += 1;
        SparseRel {
            cols,
            rhs: (self.rhs + n - mm(f, other.rhs, n)) % n,
        }
    }
}

/// Structured elimination of large-prime columns (columns `≥ small`):
/// each large prime gets at most one pivot relation; a new relation is
/// reduced by the pivots of its large primes until either none is
/// left (a full relation over the small base, returned) or one is
/// left without a pivot (the relation becomes that prime's pivot).
/// Pivots only ever contain primes that had no pivot when they were
/// stored, so reduction terminates.  This is the graph method of the
/// double-large-prime variation with arbitrary coefficients.
pub struct LargePrimeEliminator {
    small: usize,
    n: u64,
    pivots: HashMap<usize, SparseRel>,
    /// Abandon a relation after this many pivot reductions; `0` is no cap.
    max_merge_level: u8,
    /// Relations discarded by the cap: residuals paid for and thrown away,
    /// which is exactly what the cap costs.
    pub abandoned: u64,
    /// Merge depth summed over relations that survived, and how many did,
    /// so the realised depth can be reported rather than assumed.
    pub depth_sum: u64,
    pub depth_count: u64,
}

impl LargePrimeEliminator {
    pub fn new(small: usize, n: u64) -> Self {
        Self::with_cap(small, n, 0)
    }

    pub fn with_cap(small: usize, n: u64, max_merge_level: u8) -> Self {
        LargePrimeEliminator {
            small,
            n,
            pivots: HashMap::new(),
            max_merge_level,
            abandoned: 0,
            depth_sum: 0,
            depth_count: 0,
        }
    }

    pub fn feed(&mut self, mut rel: SparseRel, ops: &mut u64) -> Option<SparseRel> {
        let mut depth = 0u8;
        loop {
            let lp: Vec<(usize, u64)> = rel
                .cols
                .iter()
                .copied()
                .filter(|&(c, _)| c >= self.small)
                .collect();
            if lp.is_empty() {
                self.depth_sum += u64::from(depth);
                self.depth_count += 1;
                return Some(rel);
            }
            // The cap.  Uncapped, this loop chains until every large prime
            // cancels, and each reduction merges a pivot's columns in; that
            // unbounded chaining is the fill-in section 11.7 measures.  Past
            // the cap the relation is dropped rather than densified -- it is
            // not stored as a pivot either, since a capped relation is not a
            // reduced one and would seed the same growth from a new column.
            if self.max_merge_level != 0 && depth >= self.max_merge_level {
                self.abandoned += 1;
                return None;
            }
            let Some(&(c, v)) = lp.iter().find(|(c, _)| self.pivots.contains_key(c)) else {
                // No pivot for any of its large primes: store under one.
                let (c, v) = lp[0];
                let inv = inv_mod(v, self.n);
                *ops += rel.cols.len() as u64 + 1;
                let cols = rel
                    .cols
                    .iter()
                    .map(|&(cc, vv)| (cc, mm(vv, inv, self.n)))
                    .collect();
                let rhs = mm(rel.rhs, inv, self.n);
                self.pivots.insert(c, SparseRel { cols, rhs });
                return None;
            };
            let piv = self.pivots[&c].clone();
            rel = rel.sub_scaled(v, &piv, self.n, ops);
            depth += 1;
        }
    }

    /// Mean number of pivot reductions a surviving relation went through.
    pub fn mean_merge_depth(&self) -> f64 {
        if self.depth_count == 0 {
            0.0
        } else {
            self.depth_sum as f64 / self.depth_count as f64
        }
    }
}

/// Berlekamp–Massey over `Z/n` (`n` prime): the shortest linear
/// recurrence `Σ_{j=0}^{L} c_j s_{i−j} = 0` (`c_0 = 1`) satisfied by
/// the sequence; returns `c`.
fn berlekamp_massey_u64(seq: &[u64], n: u64, ops: &mut u64) -> Vec<u64> {
    let mut c = vec![1u64];
    let mut b = vec![1u64];
    let mut l = 0usize;
    let mut m = 1usize;
    let mut bb = 1u64;
    for i in 0..seq.len() {
        let mut d = seq[i];
        for j in 1..=l {
            if j < c.len() {
                d = am(d, mm(c[j], seq[i - j], n), n);
                *ops += 1;
            }
        }
        if d == 0 {
            m += 1;
            continue;
        }
        let coef = mm(d, inv_mod(bb, n), n);
        let t = c.clone();
        if c.len() < b.len() + m {
            c.resize(b.len() + m, 0);
        }
        for j in 0..b.len() {
            c[j + m] = sm(c[j + m], mm(coef, b[j], n), n);
            *ops += 1;
        }
        if 2 * l <= i {
            l = i + 1 - l;
            b = t;
            bb = d;
            m = 1;
        } else {
            m += 1;
        }
    }
    c.truncate(l + 1);
    c
}

/// A square, singleton-free selection of relations: which relations
/// (`rows`) and which columns (`columns`) it spans.
pub struct SquareCore {
    pub rows: Vec<usize>,
    pub columns: Vec<bool>,
}

/// Filtering, as every sieve pipeline does it between relation
/// collection and the logarithm solve (compare
/// [`super::koblitz_sparse_la::filter_relations`]): a column of weight
/// one determines nothing, so its relation is dropped, which may
/// create new singletons; then the surplus above square is trimmed,
/// dropping the relation that creates the fewest new singletons and
/// re-filtering.  `keep` (the `d` column) is never treated as a
/// singleton.  `None` when the relations left do not cover their own
/// columns — collect more.
pub fn square_core(rels: &[SparseRel], keep: usize) -> Option<SquareCore> {
    let ncols = rels
        .iter()
        .flat_map(|r| r.cols.iter().map(|&(c, _)| c + 1))
        .max()
        .unwrap_or(0)
        .max(keep + 1);
    let mut alive: Vec<bool> = vec![true; rels.len()];
    let weights = |alive: &[bool]| -> Vec<usize> {
        let mut w = vec![0usize; ncols];
        for (i, r) in rels.iter().enumerate() {
            if alive[i] {
                for &(c, _) in &r.cols {
                    w[c] += 1;
                }
            }
        }
        w
    };
    loop {
        // Singleton elimination to a fixed point.
        loop {
            let w = weights(&alive);
            let mut dropped = false;
            for (i, r) in rels.iter().enumerate() {
                if alive[i] && r.cols.iter().any(|&(c, _)| c != keep && w[c] == 1) {
                    alive[i] = false;
                    dropped = true;
                }
            }
            if !dropped {
                break;
            }
        }
        let w = weights(&alive);
        let n_rows = alive.iter().filter(|&&a| a).count();
        let n_cols = w.iter().filter(|&&x| x > 0).count();
        if n_rows == 0 || w[keep] == 0 {
            return None;
        }
        if n_rows == n_cols {
            return Some(SquareCore {
                rows: (0..rels.len()).filter(|&i| alive[i]).collect(),
                columns: (0..ncols).map(|c| w[c] > 0).collect(),
            });
        }
        if n_rows < n_cols {
            return None;
        }
        // Surplus: drop the relation touching the fewest weight-2
        // columns, so the fewest new singletons appear.
        let victim = (0..rels.len()).filter(|&i| alive[i]).min_by_key(|&i| {
            rels[i]
                .cols
                .iter()
                .filter(|&&(c, _)| c != keep && w[c] == 2)
                .count()
        })?;
        alive[victim] = false;
    }
}

/// Sequential Wiedemann for `A x = b` with `A` the square sparse
/// matrix whose rows are `rows` (rhs inside each row), `ncols`
/// unknowns.  Returns `x` verified against every row, or `None` when
/// the minimal polynomial found has a zero constant term (singular
/// selection, or an unlucky projection after the retries).
pub fn wiedemann_u64(
    rows: &[SparseRel],
    ncols: usize,
    n: u64,
    rng: &mut StdRng,
    ops: &mut u64,
) -> Option<Vec<u64>> {
    assert_eq!(rows.len(), ncols);
    let mat_vec = |v: &[u64], ops: &mut u64| -> Vec<u64> {
        rows.iter()
            .map(|r| {
                let mut acc = 0u64;
                for &(c, a) in &r.cols {
                    acc = am(acc, mm(a, v[c], n), n);
                }
                *ops += r.cols.len() as u64;
                acc
            })
            .collect()
    };
    let b: Vec<u64> = rows.iter().map(|r| r.rhs).collect();
    for _attempt in 0..3 {
        let u: Vec<u64> = (0..ncols).map(|_| rng.gen_range(0..n)).collect();
        let mut seq = Vec::with_capacity(2 * ncols);
        let mut v = b.clone();
        for _ in 0..2 * ncols {
            let mut d = 0u64;
            for i in 0..ncols {
                d = am(d, mm(u[i], v[i], n), n);
            }
            *ops += ncols as u64;
            seq.push(d);
            v = mat_vec(&v, ops);
        }
        let c = berlekamp_massey_u64(&seq, n, ops);
        let l = c.len() - 1;
        if l == 0 || c[l] == 0 {
            continue;
        }
        // x = −(1/c_L) Σ_{j<L} c_j A^{L−1−j} b, by Horner.
        let mut acc = vec![0u64; ncols];
        for &cj in c.iter().take(l) {
            acc = mat_vec(&acc, ops);
            for i in 0..ncols {
                acc[i] = am(acc[i], mm(cj, b[i], n), n);
            }
            *ops += ncols as u64;
        }
        let neg_inv = (n - inv_mod(c[l], n)) % n;
        let x: Vec<u64> = acc.iter().map(|&a| mm(a, neg_inv, n)).collect();
        *ops += ncols as u64;
        if mat_vec(&x, ops) == b {
            return Some(x);
        }
    }
    None
}

/// Which triple oracle a run uses.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Solver {
    /// `2|F|` Weil-restricted `S₃` pair tests per residual.
    MeetInTheMiddle,
    /// Gaudry's `O(1)` symmetrised-`S₄` solve per residual.
    Groebner,
    /// **Joux–Vitse**: look for decompositions into `k − 1 = 2` base
    /// points instead of `k = 3`, with one Weil-restricted `S₃` pair
    /// test on the residual itself.
    ///
    /// The trade is the one that variant is named for.  The solve
    /// collapses — no Macaulay matrix, no eigenvalues, just a resultant
    /// of two conics and Cantor–Zassenhaus, so the per-residual cost
    /// falls from `≈ 0.9·10⁶` `F_p` multiplications to `≈ 1.8·10³`.
    /// Against that, a random residual is a *pair* far less often than
    /// it is a triple: `≈ 2|F|²/p³` against `≈ |F|³/6p³`, a factor
    /// `≈ p/12` fewer, so the residual count rises from `Θ(|F|)` to
    /// `Θ(p³/|F|) = Θ(p²)`.
    ///
    /// For `k = 3` that is `n^{2/3}` residuals against `n^{1/3}`, and
    /// the exponent moves the wrong way — the variant's exponential
    /// saving in the Gröbner step has nothing to bite on at `k = 3`.
    /// It is here to be measured rather than assumed; see
    /// `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md` §11.9.
    PairOnly,
}

/// Collect relations by full decomposition of random `R = aG + bQ` until
/// `d` is determined, with the meet-in-the-middle oracle.
pub fn run_gaudry(
    inst: &Instance3,
    base: &SubspaceBase,
    seed: u64,
    max_residuals: u64,
) -> GaudryReport {
    run_gaudry_with(
        inst,
        base,
        seed,
        max_residuals,
        Solver::MeetInTheMiddle,
        false,
    )
}

/// As [`run_gaudry`] with a choice of oracle; `cross_check` also runs
/// the other oracle on every residual and counts disagreements.
pub fn run_gaudry_with(
    inst: &Instance3,
    base: &SubspaceBase,
    seed: u64,
    max_residuals: u64,
    solver: Solver,
    cross_check: bool,
) -> GaudryReport {
    run_gaudry_opts(
        inst,
        base,
        seed,
        &GaudryOptions {
            max_residuals,
            solver,
            cross_check,
            ..GaudryOptions::default()
        },
    )
}

/// The general run: oracle choice, cross-check, sparse linear algebra
/// and the large-prime variation, per [`GaudryOptions`].
pub fn run_gaudry_opts(
    inst: &Instance3,
    base: &SubspaceBase,
    seed: u64,
    opts: &GaudryOptions,
) -> GaudryReport {
    let max_residuals = opts.max_residuals;
    let solver = opts.solver;
    let cross_check = opts.cross_check;
    let small = if opts.small_base == 0 || opts.small_base >= base.len() {
        base.len()
    } else {
        opts.small_base
    };
    let max_lp = if small == base.len() {
        0
    } else {
        opts.max_large_primes
    };
    let unknowns = small + 1;
    let la_fp_equiv = 9.0;
    let curve = &inst.curve;
    let n = curve.n;
    let mut rng = StdRng::seed_from_u64(seed ^ 0x9A0D);
    curve.reset();
    let start = Instant::now();
    // Measure F_p multiplications per affine addition on this field.
    let fp_per_add = {
        let f = &curve.field;
        f.reset_muls();
        let mut acc = curve.g;
        for _ in 0..64 {
            acc = curve.add(&acc, &inst.q);
        }
        let m = f.muls() as f64 / 64.0;
        curve.reset();
        m
    };
    let pre = if solver == Solver::Groebner || cross_check {
        Some(SymmetrisedS4::precompute(curve))
    } else {
        None
    };
    let precompute_muls = curve.field.muls();
    curve.reset();
    let mut stats = SolveStats::default();
    let mut system = RelationSystem::new(n, unknowns);
    let mut eliminator = LargePrimeEliminator::with_cap(small, n, opts.max_merge_level);
    let mut full_rels: Vec<SparseRel> = Vec::new();
    let mut la_ops = 0u64;
    // The eliminator's share of `la_ops`, tracked alongside it so the solve's
    // share is the difference.
    let mut merge_ops = 0u64;
    let mut la_attempts = 0u64;
    let mut next_attempt = unknowns;
    let mut la_rows_used = 0usize;
    let mut rep = GaudryReport {
        p: curve.field.p,
        n,
        bits: (n as f64).log2(),
        base: base.len(),
        residuals: 0,
        decompositions: 0,
        relations_verified: 0,
        relations_independent: 0,
        rank: 0,
        solved: false,
        correct: None,
        group_ops: 0,
        oracle_fp_muls: 0,
        fp_muls_per_add: fp_per_add,
        total_ops: 0.0,
        s: 0.0,
        pair_tests: 0,
        fp_muls_per_pair_test: 0.0,
        decomposition_rate: 0.0,
        wall_ms: 0.0,
        linear_algebra_ms: 0.0,
        solver,
        precompute_fp_muls: 0,
        solve_stats: SolveStats::default(),
        cross_checked: 0,
        cross_check_mismatches: 0,
        la_mode: if opts.sparse_la {
            "wiedemann".to_string()
        } else {
            "dense".to_string()
        },
        la_ops: 0,
        lp_abandoned: 0,
        lp_mean_merge_depth: 0.0,
        lp_max_merge_level: opts.max_merge_level,
        lp_merge_ops: 0,
        la_unknowns: unknowns,
        la_rows: 0,
        la_avg_weight: 0.0,
        la_attempts: 0,
        la_filtered_out: 0,
        la_fp_equiv,
        small_base: small,
        max_large_primes: max_lp,
        lp_histogram: [0; 4],
        lp_full_relations: 0,
    };
    let mut la = std::time::Duration::ZERO;
    while rep.residuals < max_residuals {
        rep.residuals += 1;
        let a = rng.gen_range(0..n);
        let b = rng.gen_range(1..n);
        let r = curve.add(&curve.mul(&curve.g, a), &curve.mul(&inst.q, b));
        let decs = match solver {
            Solver::MeetInTheMiddle => {
                let (decs, muls) = subspace_triple_oracle(inst, base, &r, &mut rng);
                rep.oracle_fp_muls += muls;
                rep.pair_tests += 2 * base.len() as u64;
                decs
            }
            Solver::Groebner => {
                let before = stats.fp_muls;
                let decs = subspace_triple_oracle_groebner(
                    inst,
                    base,
                    pre.as_ref().unwrap(),
                    &r,
                    &mut rng,
                    &mut stats,
                );
                rep.oracle_fp_muls += stats.fp_muls - before;
                decs
            }
            Solver::PairOnly => {
                // One pair test on the residual itself: `R = ±P_i ±P_j`.
                let (decs, muls) = weil_s3_pair_test(inst, base, &r, &mut rng);
                rep.oracle_fp_muls += muls;
                rep.pair_tests += 1;
                decs
            }
        };
        if cross_check {
            let other = match solver {
                // The pair channel has no independent second oracle
                // here: `weil_s3_pair_test` *is* what the other two use
                // for pairs, so cross-checking it against them would be
                // checking it against itself.
                Solver::PairOnly => decs.clone(),
                Solver::MeetInTheMiddle => {
                    let mut st = SolveStats::default();
                    subspace_triple_oracle_groebner(
                        inst,
                        base,
                        pre.as_ref().unwrap(),
                        &r,
                        &mut rng,
                        &mut st,
                    )
                }
                Solver::Groebner => subspace_triple_oracle(inst, base, &r, &mut rng).0,
            };
            // Compare distinct-index triples and singles only (the pair
            // channel differs between the two oracles).
            let filt = |v: &Vec<Vec<(usize, i64)>>| -> Vec<Vec<(usize, i64)>> {
                v.iter().filter(|t| t.len() != 2).cloned().collect()
            };
            if filt(&decs) != filt(&other) {
                rep.cross_check_mismatches += 1;
                if std::env::var_os("GAUDRY_DEBUG").is_some() {
                    eprintln!(
                        "cross-check mismatch at residual {} (a={a}, b={b}): {:?} produced {:?}, other produced {:?}; stats {:?}",
                        rep.residuals, solver, filt(&decs), filt(&other), stats
                    );
                }
            }
            rep.cross_checked += 1;
        }
        for terms in decs {
            rep.decompositions += 1;
            // Verify aG + bQ = Σ c_i P_i.
            let mut acc = r;
            for &(i, c) in &terms {
                acc = curve.sub(&acc, &curve.mul_signed(&base.points[i], c));
            }
            if !acc.inf {
                continue;
            }
            rep.relations_verified += 1;
            // Sparse relation: base columns, then the `d` column at
            // index `small`; large primes keep their base index (≥ small
            // and < base.len()), shifted by one to make room for `d`.
            let mut cols: Vec<(usize, u64)> = terms
                .iter()
                .map(|&(i, c)| {
                    let v = c.unsigned_abs() % n;
                    let v = if c >= 0 { v } else { (n - v) % n };
                    (if i < small { i } else { i + 1 }, v)
                })
                .collect();
            cols.push((small, (n - b) % n));
            cols.sort_unstable();
            let lp_count = cols.iter().filter(|&&(c, _)| c > small).count();
            rep.lp_histogram[lp_count.min(3)] += 1;
            if lp_count > max_lp as usize {
                continue;
            }
            let t0 = Instant::now();
            let rel = SparseRel { cols, rhs: a };
            let full = if lp_count == 0 {
                Some(rel)
            } else {
                let before = la_ops;
                let f = eliminator.feed(rel, &mut la_ops);
                merge_ops += la_ops - before;
                if f.is_some() {
                    rep.lp_full_relations += 1;
                }
                f
            };
            if let Some(full) = full {
                if opts.sparse_la {
                    full_rels.push(full);
                    rep.relations_independent = full_rels.len() as u64;
                    if full_rels.len() >= next_attempt {
                        // Filter to a square core before solving: a
                        // random square selection of a sparse system
                        // misses ≈ e^{-w} of the columns entirely
                        // (coupon collector) and is then singular by
                        // construction.
                        let core = square_core(&full_rels, small);
                        if let Some(core) = core {
                            la_attempts += 1;
                            let mut map = vec![usize::MAX; unknowns];
                            let mut k = 0;
                            for c in 0..unknowns {
                                if core.columns[c] {
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
                            la_rows_used = sel.len();
                            rep.la_unknowns = sel.len();
                            rep.la_filtered_out = full_rels.len() - sel.len();
                            let x = wiedemann_u64(&sel, sel.len(), n, &mut rng, &mut la_ops);
                            // Accept only a logarithm the group confirms.
                            let dd = x.map(|x| x[map[small]]);
                            if dd.is_some_and(|dd| curve.mul(&curve.g, dd) == inst.q) {
                                rep.solved = true;
                                rep.correct = Some(dd == Some(inst.d));
                            } else {
                                next_attempt = full_rels.len() + (sel.len() / 20).max(1);
                            }
                        } else {
                            next_attempt = full_rels.len() + (unknowns / 20).max(1);
                        }
                    }
                } else {
                    let mut row = vec![0u64; unknowns];
                    for &(c, v) in &full.cols {
                        row[c] = v;
                    }
                    if system.insert(row, full.rhs) {
                        rep.relations_independent += 1;
                        if let Some(dd) = system.solved(small) {
                            rep.solved = true;
                            rep.correct = Some(dd == inst.d);
                        }
                    }
                    la_rows_used = system.rank();
                }
            }
            la += t0.elapsed();
        }
        if rep.solved {
            break;
        }
    }
    rep.rank = if opts.sparse_la {
        if rep.solved {
            unknowns
        } else {
            0
        }
    } else {
        system.rank()
    };
    rep.group_ops = curve.ops();
    rep.solver = solver;
    rep.precompute_fp_muls = precompute_muls;
    rep.solve_stats = stats;
    rep.la_ops = la_ops + system.ops();
    rep.lp_merge_ops = merge_ops;
    rep.lp_abandoned = eliminator.abandoned;
    rep.lp_mean_merge_depth = eliminator.mean_merge_depth();
    rep.la_rows = la_rows_used;
    rep.la_attempts = la_attempts;
    if opts.sparse_la {
        rep.la_avg_weight = if full_rels.is_empty() {
            0.0
        } else {
            full_rels.iter().map(|r| r.cols.len()).sum::<usize>() as f64 / full_rels.len() as f64
        };
    }
    rep.total_ops = rep.group_ops as f64
        + (rep.oracle_fp_muls + precompute_muls) as f64 / fp_per_add
        + rep.la_ops as f64 * la_fp_equiv / fp_per_add;
    rep.s = rep.total_ops / (n as f64).sqrt();
    rep.fp_muls_per_pair_test = rep.oracle_fp_muls as f64 / rep.pair_tests.max(1) as f64;
    rep.decomposition_rate = rep.decompositions as f64 / rep.residuals as f64;
    rep.wall_ms = start.elapsed().as_secs_f64() * 1e3;
    rep.linear_algebra_ms = la.as_secs_f64() * 1e3;
    rep
}

/// Plain r-adding Pollard rho on the same group, exhaustive storage, for
/// the reference cost in the same units.
#[derive(Clone, Debug, Serialize)]
pub struct RhoReport3 {
    pub p: u64,
    pub n: u64,
    pub steps: u64,
    pub group_ops: u64,
    pub solved: bool,
    pub correct: Option<bool>,
    pub s: f64,
    pub wall_ms: f64,
}

pub fn run_rho3(inst: &Instance3, seed: u64) -> RhoReport3 {
    let curve = &inst.curve;
    let n = curve.n;
    let mut rng = StdRng::seed_from_u64(seed ^ 0x8D0);
    curve.reset();
    let start = Instant::now();
    let r = 32usize;
    let mults: Vec<(u64, u64, Pt3)> = (0..r)
        .map(|_| {
            let al = rng.gen_range(0..n);
            let be = rng.gen_range(1..n);
            (
                al,
                be,
                curve.add(&curve.mul(&curve.g, al), &curve.mul(&inst.q, be)),
            )
        })
        .collect();
    let mut table: HashMap<Pt3, (u64, u64)> = HashMap::new();
    let mut steps = 0u64;
    let mut solved = None;
    'outer: loop {
        let mut a = rng.gen_range(0..n);
        let mut b = rng.gen_range(1..n);
        let mut l = curve.add(&curve.mul(&curve.g, a), &curve.mul(&inst.q, b));
        loop {
            steps += 1;
            if let Some(&(a2, b2)) = table.get(&l) {
                // a + b d = a2 + b2 d
                let db = (b + n - b2) % n;
                if db != 0 {
                    let da = (a2 + n - a) % n;
                    let d = mm(da, inv_mod(db, n), n);
                    solved = Some(d);
                    break 'outer;
                }
                break;
            }
            table.insert(l, (a, b));
            let j = (mix64(l.x.0[0] ^ l.x.0[1].wrapping_mul(0x9E37)) % r as u64) as usize;
            l = curve.add(&l, &mults[j].2);
            a = (a + mults[j].0) % n;
            b = (b + mults[j].1) % n;
            if steps > 64 * (n as f64).sqrt() as u64 + 1_000_000 {
                break 'outer;
            }
        }
    }
    RhoReport3 {
        p: curve.field.p,
        n,
        steps,
        group_ops: curve.ops(),
        solved: solved.is_some(),
        correct: solved.map(|d| d == inst.d),
        s: curve.ops() as f64 / (n as f64).sqrt(),
        wall_ms: start.elapsed().as_secs_f64() * 1e3,
    }
}

// ── Tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    /// The plain echelon finds the pivot columns of a rank-deficient
    /// matrix and counts its multiplications.
    #[test]
    fn plain_echelon_finds_the_pivots() {
        let p = 7;
        let mut m = vec![vec![1, 2, 3], vec![2, 4, 6], vec![0, 1, 1]];
        let mut muls = 0u64;
        let pivots = super::echelon_mod_p(&mut m, p, &mut muls);
        assert_eq!(pivots, vec![0, 1]);
        assert!(muls > 0);
        assert!(m[2].iter().all(|&x| x == 0), "{m:?}");
    }

    use super::*;

    fn small_field() -> (Fp3, StdRng) {
        let mut rng = StdRng::seed_from_u64(1);
        (Fp3::new(1009, &mut rng), rng)
    }

    #[test]
    fn fp3_field_axioms() {
        let (f, mut rng) = small_field();
        for _ in 0..200 {
            let a = E3([
                rng.gen_range(0..f.p),
                rng.gen_range(0..f.p),
                rng.gen_range(0..f.p),
            ]);
            if a == Fp3::ZERO {
                continue;
            }
            assert_eq!(f.mul(&a, &f.inv(&a)), Fp3::ONE);
            let b = E3([
                rng.gen_range(0..f.p),
                rng.gen_range(0..f.p),
                rng.gen_range(0..f.p),
            ]);
            assert_eq!(f.mul(&a, &b), f.mul(&b, &a));
            let sq = f.sq(&a);
            let r = f.sqrt(&sq, &mut rng).unwrap();
            assert!(r == a || r == f.neg(&a));
        }
        // t³ = c and the field has p³ − 1 as the multiplicative order.
        let t = E3([0, 1, 0]);
        assert_eq!(f.mul(&f.mul(&t, &t), &t), f.from_base(f.c));
        let q = (f.p as u128).pow(3) - 1;
        assert_eq!(f.pow(&t, q), Fp3::ONE);
    }

    #[test]
    fn instance3_has_prime_order_and_known_answer() {
        let inst = generate_instance3(67, 3);
        let c = &inst.curve;
        assert!(is_prime_u64(c.n));
        assert!(c.is_on_curve(&c.g) && c.is_on_curve(&inst.q));
        assert!(c.mul(&c.g, c.n).inf);
        assert_eq!(c.mul(&c.g, inst.d), inst.q);
        let n0 = 67u128.pow(3) + 1;
        assert!((c.n as i128 - n0 as i128).unsigned_abs() <= 2 * isqrt(67u128.pow(3)) + 2);
    }

    #[test]
    fn weil_pair_test_agrees_with_brute_force() {
        let inst = generate_instance3(67, 5);
        let c = &inst.curve;
        let mut rng = StdRng::seed_from_u64(9);
        let base = SubspaceBase::build(&inst, &mut rng);
        assert!(base.len() > 20);
        let brute = |y: &Pt3| {
            let mut out = Vec::new();
            for i in 0..base.len() {
                for j in i..base.len() {
                    for s_i in [1i64, -1] {
                        for s_j in [1i64, -1] {
                            let pt = c.add(
                                &c.mul_signed(&base.points[i], s_i),
                                &c.mul_signed(&base.points[j], s_j),
                            );
                            if pt == *y && !(i == j && s_i + s_j == 0) {
                                out.push(if i == j {
                                    vec![(i, s_i + s_j)]
                                } else {
                                    vec![(i, s_i), (j, s_j)]
                                });
                            }
                        }
                    }
                }
            }
            out.sort();
            out.dedup();
            out
        };
        let mut targets = vec![
            c.add(&base.points[1], &base.points[7]),
            c.sub(&base.points[3], &base.points[12]),
            c.double(&base.points[5]),
        ];
        for k in 1..30u64 {
            targets.push(c.mul(&c.g, k * 7919 + 1));
        }
        let mut hits = 0;
        for y in &targets {
            let (got, _) = weil_s3_pair_test(&inst, &base, y, &mut rng);
            assert_eq!(got, brute(y), "pair test disagrees at {y:?}");
            hits += got.len();
        }
        assert!(hits >= 3);
    }

    #[test]
    fn triple_oracle_finds_constructed_triples_and_verifies() {
        let inst = generate_instance3(67, 8);
        let c = &inst.curve;
        let mut rng = StdRng::seed_from_u64(4);
        let base = SubspaceBase::build(&inst, &mut rng);
        let r = c.add(
            &c.add(&base.points[2], &base.points[9]),
            &c.neg(&base.points[14]),
        );
        let (decs, _) = subspace_triple_oracle(&inst, &base, &r, &mut rng);
        assert!(decs.contains(&vec![(2, 1), (9, 1), (14, -1)]), "{decs:?}");
        for terms in &decs {
            let mut acc = r;
            for &(i, coef) in terms {
                acc = c.sub(&acc, &c.mul_signed(&base.points[i], coef));
            }
            assert!(acc.inf, "oracle returned a false decomposition {terms:?}");
        }
    }

    #[test]
    fn symbolic_s4_vanishes_on_sums_and_symmetrisation_is_exact() {
        let inst = generate_instance3(67, 6);
        let c = &inst.curve;
        let f = &c.field;
        let mut rng = StdRng::seed_from_u64(3);
        let g = s4_symbolic(c);
        // S₄(x₁, x₂, x₃, x(P₁+P₂+P₃)) = 0 for random points.
        for k in 1..6u64 {
            let p1 = c.mul(&c.g, 11 * k + 1);
            let p2 = c.mul(&c.g, 23 * k + 5);
            let p3 = c.mul(&c.g, 37 * k + 7);
            let s = c.add(&c.add(&p1, &p2), &p3);
            assert_eq!(g.eval(f, &[p1.x, p2.x, p3.x, s.x]), Fp3::ZERO);
            let s2 = c.add(&c.sub(&p1, &p2), &p3);
            assert_eq!(g.eval(f, &[p1.x, p2.x, p3.x, s2.x]), Fp3::ZERO);
        }
        // H(e(x), x₄) = G(x) at random points.
        let pre = SymmetrisedS4::precompute(c);
        for _ in 0..20 {
            let x: [E3; 4] = std::array::from_fn(|_| {
                E3([
                    rng.gen_range(0..f.p),
                    rng.gen_range(0..f.p),
                    rng.gen_range(0..f.p),
                ])
            });
            let e1 = f.add(&f.add(&x[0], &x[1]), &x[2]);
            let e2 = f.add(
                &f.add(&f.mul(&x[0], &x[1]), &f.mul(&x[0], &x[2])),
                &f.mul(&x[1], &x[2]),
            );
            let e3 = f.mul(&f.mul(&x[0], &x[1]), &x[2]);
            let mut h = Fp3::ZERO;
            for (&e, &coef) in &pre.terms {
                let mut t = coef;
                for _ in 0..e[0] {
                    t = f.mul(&t, &e1);
                }
                for _ in 0..e[1] {
                    t = f.mul(&t, &e2);
                }
                for _ in 0..e[2] {
                    t = f.mul(&t, &e3);
                }
                for _ in 0..e[3] {
                    t = f.mul(&t, &x[3]);
                }
                h = f.add(&h, &t);
            }
            assert_eq!(h, g.eval(f, &x));
        }
        assert!(pre.terms.len() <= 175, "{}", pre.terms.len());
    }

    #[test]
    fn groebner_solve_agrees_with_the_meet_in_the_middle_oracle() {
        let inst = generate_instance3(67, 8);
        let c = &inst.curve;
        let mut rng = StdRng::seed_from_u64(4);
        let base = SubspaceBase::build(&inst, &mut rng);
        let pre = SymmetrisedS4::precompute(c);
        let mut stats = SolveStats::default();
        // Constructed triple.
        let r = c.add(
            &c.add(&base.points[2], &base.points[9]),
            &c.neg(&base.points[14]),
        );
        let decs = subspace_triple_oracle_groebner(&inst, &base, &pre, &r, &mut rng, &mut stats);
        assert!(decs.contains(&vec![(2, 1), (9, 1), (14, -1)]), "{decs:?}");
        // Random residuals: the same distinct-index triples as the MITM oracle.
        let filt = |v: &Vec<Vec<(usize, i64)>>| -> Vec<Vec<(usize, i64)>> {
            v.iter().filter(|t| t.len() != 2).cloned().collect()
        };
        let mut agree = 0;
        for k in 1..40u64 {
            let r = c.mul(&c.g, k * 104_729 + 3);
            let a = subspace_triple_oracle_groebner(&inst, &base, &pre, &r, &mut rng, &mut stats);
            let (b, _) = subspace_triple_oracle(&inst, &base, &r, &mut rng);
            assert_eq!(
                filt(&a),
                filt(&b),
                "residual {k}: groebner {a:?} vs mitm {b:?}"
            );
            agree += filt(&a).len();
        }
        assert!(agree > 0, "no triples found on random residuals");
        // The regularity degree 10 suffices for almost every residual; a
        // few need the degree-11 matrix.
        assert!(stats.retried_at_degree_11 * 10 <= stats.solves, "{stats:?}");
        assert!(stats.quotient_dim_total >= 40 * 60, "{stats:?}");
    }

    /// The border check must be *exactly* the residuals no Macaulay
    /// degree solves — it may not lose a single solution.
    ///
    /// This is the guard on the one thing that could go wrong: the
    /// check runs before the multiplication matrix is built, so a
    /// false positive would silently send a solvable residual to the
    /// fallback and cost a relation.  Running the same residual stream
    /// with and without the retries (`GAUDRY_BORDER_RETRY`) has to give
    /// the same answer on every residual, not merely the same counts.
    #[test]
    fn the_border_check_sends_only_the_residuals_no_degree_solves_to_the_fallback() {
        let inst = generate_instance3(271, 1);
        let pre = SymmetrisedS4::precompute(&inst.curve);
        let p = inst.curve.field.p;

        let run = |retry: bool| -> (Vec<Option<Vec<[u64; 3]>>>, SolveStats) {
            // The env var is process-wide, so the two passes are run
            // back to back rather than in parallel.
            if retry {
                std::env::set_var("GAUDRY_BORDER_RETRY", "1");
            } else {
                std::env::remove_var("GAUDRY_BORDER_RETRY");
            }
            let mut rng = StdRng::seed_from_u64(7);
            let mut stats = SolveStats::default();
            let mut out = Vec::new();
            for k in 0..600u64 {
                let x_r = E3([
                    (k * 7919 + 1) % p,
                    (k * 104_729 + 13) % p,
                    (k * 15_485_863 + 7) % p,
                ]);
                out.push(solve_s4_subspace(&inst, &pre, &x_r, &mut rng, &mut stats));
            }
            (out, stats)
        };

        let (with_retry, stats_retry) = run(true);
        let (without, stats_skip) = run(false);
        std::env::remove_var("GAUDRY_BORDER_RETRY");

        assert_eq!(
            with_retry, without,
            "skipping the retries changed an answer"
        );
        assert!(
            stats_retry.border_unreachable > 0,
            "no residual hit the border case, so this test proves nothing"
        );
        assert_eq!(
            stats_retry.border_unreachable, stats_skip.border_unreachable,
            "the two passes disagree about which residuals are border cases"
        );
        // The retries the check removes, and the work they cost.
        assert!(stats_retry.retried_at_degree_11 > 0);
        assert_eq!(stats_skip.retried_at_degree_11, 0);
        assert!(
            stats_skip.fp_muls < stats_retry.fp_muls,
            "skipping three Theta(d^6) reductions should cost less: {} vs {}",
            stats_skip.fp_muls,
            stats_retry.fp_muls
        );
    }

    /// The demand-driven elimination must give the full elimination's
    /// answer on every residual and build the same `M_{e₁}` entry for
    /// entry — on one residual stream, in lockstep, with the modes passed
    /// explicitly so no environment variable is shared with the tests
    /// that set them.
    #[test]
    fn the_lazy_elimination_reads_the_same_normal_forms() {
        let inst = generate_instance3(271, 1);
        let p = inst.curve.field.p;
        let pre_full = SymmetrisedS4::precompute(&inst.curve);
        let pre_lazy = SymmetrisedS4::precompute(&inst.curve);
        let full = SolveMode::default();
        let lazy = SolveMode {
            lazy: LazyElim::Verify,
            ..SolveMode::default()
        };
        let mut rng_full = StdRng::seed_from_u64(7);
        let mut rng_lazy = StdRng::seed_from_u64(7);
        let mut st_full = SolveStats::default();
        let mut st_lazy = SolveStats::default();
        for k in 0..200u64 {
            let x_r = E3([
                (k * 7919 + 1) % p,
                (k * 104_729 + 13) % p,
                (k * 15_485_863 + 7) % p,
            ]);
            let a =
                solve_s4_subspace_with(&inst, &pre_full, &x_r, &mut rng_full, &mut st_full, full);
            let b =
                solve_s4_subspace_with(&inst, &pre_lazy, &x_r, &mut rng_lazy, &mut st_lazy, lazy);
            assert_eq!(a, b, "residual {k}: full {a:?} vs lazy {b:?}");
        }
        assert!(pre_lazy.plan.get().is_some(), "no plan was learned");
        assert!(
            pre_full.plan.get().is_none(),
            "the full mode learned a plan"
        );
        assert_eq!(st_lazy.lazy_verify_mismatches, 0, "{st_lazy:?}");
        assert_eq!(st_lazy.lazy_verified, st_lazy.lazy_solves, "{st_lazy:?}");
        // Every residual after the one that taught the plan is tried
        // lazily, and every one that falls back has a staircase no plan
        // could serve — an accidental cancellation (probability ~`1/p`
        // per entry) is absorbed by trying another row, never a fallback.
        assert!(
            st_lazy.lazy_solves + st_lazy.lazy_fallbacks + 1 >= st_lazy.solves,
            "{st_lazy:?}"
        );
        assert_eq!(st_lazy.lazy_needless_fallbacks, 0, "{st_lazy:?}");
        assert!(st_lazy.lazy_fallbacks * 20 <= st_lazy.solves, "{st_lazy:?}");
        // It skips rows, though not many: whether that pays is the
        // measurement's question (§11.14), not this test's.
        assert!(
            st_lazy.lazy_pivots_reduced < st_lazy.lazy_pivots_planned,
            "reduced every planned row: {st_lazy:?}"
        );
    }

    #[test]
    fn wiedemann_solves_random_sparse_systems() {
        let n = 1_000_003u64;
        let mut rng = StdRng::seed_from_u64(5);
        for trial in 0..5 {
            let m = 40 + trial * 7;
            let x: Vec<u64> = (0..m).map(|_| rng.gen_range(0..n)).collect();
            let rows: Vec<SparseRel> = (0..m)
                .map(|i| {
                    let mut cols: Vec<(usize, u64)> = vec![(i, rng.gen_range(1..n))];
                    for _ in 0..3 {
                        let c = rng.gen_range(0..m);
                        if cols.iter().all(|&(cc, _)| cc != c) {
                            cols.push((c, rng.gen_range(1..n)));
                        }
                    }
                    cols.sort_unstable();
                    let rhs = cols
                        .iter()
                        .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
                    SparseRel { cols, rhs }
                })
                .collect();
            let mut ops = 0u64;
            let sol = wiedemann_u64(&rows, m, n, &mut rng, &mut ops);
            assert_eq!(sol.as_deref(), Some(&x[..]), "trial {trial}");
            assert!(ops > 0);
        }
        // Berlekamp–Massey on a known recurrence: Fibonacci mod n has
        // connection polynomial 1 − x − x².
        let mut seq = vec![0u64, 1];
        for i in 2..40 {
            seq.push(am(seq[i - 1], seq[i - 2], n));
        }
        let mut ops = 0u64;
        let c = berlekamp_massey_u64(&seq, n, &mut ops);
        assert_eq!(c, vec![1, n - 1, n - 1]);
    }

    #[test]
    fn square_core_is_square_and_free_of_singletons() {
        let n = 1_000_003u64;
        let mut rng = StdRng::seed_from_u64(17);
        let ncols = 60usize;
        let keep = ncols - 1;
        let x: Vec<u64> = (0..ncols).map(|_| rng.gen_range(0..n)).collect();
        // Relations of weight 4: three random columns plus `keep`, as
        // the Gaudry rows are shaped.
        let make = |rng: &mut StdRng| -> SparseRel {
            let mut cols: Vec<(usize, u64)> = vec![(keep, rng.gen_range(1..n))];
            while cols.len() < 4 {
                let c = rng.gen_range(0..keep);
                if cols.iter().all(|&(cc, _)| cc != c) {
                    cols.push((c, rng.gen_range(1..n)));
                }
            }
            cols.sort_unstable();
            let rhs = cols
                .iter()
                .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
            SparseRel { cols, rhs }
        };
        // The failure mode a square selection has: a column no
        // selected relation touches (coupon collector leaves ≈ e^{-w}
        // of them untouched when the selection is as small as the
        // number of columns) makes the matrix singular by
        // construction.
        let mut ops = 0u64;
        let mut rels: Vec<SparseRel> = (0..ncols).map(|_| make(&mut rng)).collect();
        for r in rels.iter_mut() {
            // Move every use of column 0 elsewhere: nothing touches it.
            for e in r.cols.iter_mut() {
                if e.0 == 0 {
                    e.0 = 1;
                }
            }
            r.cols.sort_unstable();
            r.cols.dedup_by_key(|e| e.0);
        }
        assert!(
            wiedemann_u64(&rels, ncols, n, &mut rng, &mut ops).is_none(),
            "a selection that misses a column must be singular"
        );
        // With enough relations the filtered core is square, covers
        // every column it spans at weight ≥ 2, and solves.
        let rels: Vec<SparseRel> = (0..6 * ncols).map(|_| make(&mut rng)).collect();
        let core = square_core(&rels, keep).expect("core");
        let n_cols = core.columns.iter().filter(|&&c| c).count();
        assert_eq!(core.rows.len(), n_cols, "core must be square");
        assert!(core.columns[keep]);
        let mut weight = vec![0usize; core.columns.len()];
        for &i in &core.rows {
            for &(c, _) in &rels[i].cols {
                assert!(core.columns[c], "core row uses a column outside the core");
                weight[c] += 1;
            }
        }
        assert!(
            (0..core.columns.len()).all(|c| !core.columns[c] || c == keep || weight[c] >= 2),
            "no singleton column may remain"
        );
        let mut map = vec![usize::MAX; core.columns.len()];
        let mut k = 0;
        for c in 0..core.columns.len() {
            if core.columns[c] {
                map[c] = k;
                k += 1;
            }
        }
        let sel: Vec<SparseRel> = core
            .rows
            .iter()
            .map(|&i| SparseRel {
                cols: rels[i].cols.iter().map(|&(c, v)| (map[c], v)).collect(),
                rhs: rels[i].rhs,
            })
            .collect();
        let sol = wiedemann_u64(&sel, n_cols, n, &mut rng, &mut ops).expect("core solves");
        assert_eq!(sol[map[keep]], x[keep]);
    }

    #[test]
    fn the_merge_cap_bounds_depth_and_charges_what_it_discards() {
        // Section 11.10's cap.  Uncapped, `feed` chains pivot reductions until
        // every large prime cancels, and each one merges a pivot's columns in;
        // that is the fill-in section 11.7 measures.  Capped, a relation past
        // the depth bound is dropped instead, and the drop is counted because
        // it is a residual that was paid for.
        let n = 1_000_003u64;
        let small = 5usize;
        let build = |cap: u8| {
            let mut rng = StdRng::seed_from_u64(9);
            let mut el = LargePrimeEliminator::with_cap(small, n, cap);
            let x: Vec<u64> = (0..small + 6).map(|_| rng.gen_range(0..n)).collect();
            let mut ops = 0u64;
            let mut full = 0usize;
            for _ in 0..400 {
                let mut cols: Vec<(usize, u64)> = Vec::new();
                for _ in 0..3 {
                    let c = if rng.gen_bool(0.6) {
                        small + rng.gen_range(0..6)
                    } else {
                        rng.gen_range(0..small)
                    };
                    let v = if rng.gen_bool(0.5) { 1 } else { n - 1 };
                    if let Some(e) = cols.iter_mut().find(|(cc, _)| *cc == c) {
                        e.1 = am(e.1, v, n);
                    } else {
                        cols.push((c, v));
                    }
                }
                cols.retain(|&(_, v)| v != 0);
                cols.sort_unstable();
                let rhs = cols
                    .iter()
                    .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
                if let Some(r) = el.feed(SparseRel { cols, rhs }, &mut ops) {
                    // Whatever survives is still a true relation over the
                    // small base: a cap must not corrupt what it lets through.
                    assert!(r.cols.iter().all(|&(c, _)| c < small));
                    let lhs = r
                        .cols
                        .iter()
                        .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
                    assert_eq!(lhs, r.rhs);
                    full += 1;
                }
            }
            (el, full)
        };

        let (uncapped, full_uncapped) = build(0);
        let (capped, full_capped) = build(1);

        // The cap binds: nothing survives past depth 1, and the uncapped run
        // went deeper than that.
        assert!(capped.abandoned > 0, "a depth-1 cap must discard something");
        assert_eq!(uncapped.abandoned, 0, "no cap means nothing is discarded");
        assert!(capped.mean_merge_depth() <= 1.0);
        assert!(
            uncapped.mean_merge_depth() > capped.mean_merge_depth(),
            "uncapped {} vs capped {}",
            uncapped.mean_merge_depth(),
            capped.mean_merge_depth()
        );
        // And it costs relations, which is the trade being measured.
        assert!(
            full_capped < full_uncapped,
            "capped {full_capped} should yield fewer full relations than {full_uncapped}"
        );
    }

    #[test]
    fn large_prime_elimination_cancels_every_large_prime() {
        let n = 1_000_003u64;
        let small = 5usize;
        let mut rng = StdRng::seed_from_u64(9);
        let mut el = LargePrimeEliminator::new(small, n);
        // Hidden solution over 5 small columns and 6 large primes.
        let x: Vec<u64> = (0..small + 6).map(|_| rng.gen_range(0..n)).collect();
        let mut full = 0;
        let mut ops = 0u64;
        for _ in 0..200 {
            let mut cols: Vec<(usize, u64)> = Vec::new();
            for _ in 0..3 {
                let c = if rng.gen_bool(0.6) {
                    small + rng.gen_range(0..6)
                } else {
                    rng.gen_range(0..small)
                };
                let v = if rng.gen_bool(0.5) { 1 } else { n - 1 };
                if let Some(e) = cols.iter_mut().find(|(cc, _)| *cc == c) {
                    e.1 = am(e.1, v, n);
                } else {
                    cols.push((c, v));
                }
            }
            cols.retain(|&(_, v)| v != 0);
            cols.sort_unstable();
            let rhs = cols
                .iter()
                .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
            if let Some(f) = el.feed(SparseRel { cols, rhs }, &mut ops) {
                assert!(f.cols.iter().all(|&(c, _)| c < small), "{f:?}");
                let lhs = f
                    .cols
                    .iter()
                    .fold(0u64, |acc, &(c, v)| am(acc, mm(v, x[c], n), n));
                assert_eq!(lhs, f.rhs, "combined relation must still hold");
                full += 1;
            }
        }
        assert!(full > 100, "{full}");
    }

    #[test]
    fn sparse_and_large_prime_runs_recover_the_logarithm() {
        let inst = generate_instance3(67, 11);
        let mut rng = StdRng::seed_from_u64(3);
        let base = SubspaceBase::build(&inst, &mut rng);
        let sparse = run_gaudry_opts(
            &inst,
            &base,
            1,
            &GaudryOptions {
                max_residuals: 50_000,
                solver: Solver::Groebner,
                sparse_la: true,
                ..GaudryOptions::default()
            },
        );
        assert_eq!(sparse.correct, Some(true), "{sparse:?}");
        assert_eq!(sparse.la_mode, "wiedemann");
        assert!(
            sparse.la_ops > 0 && sparse.la_avg_weight <= 4.0,
            "{sparse:?}"
        );
        let lp = run_gaudry_opts(
            &inst,
            &base,
            1,
            &GaudryOptions {
                max_residuals: 200_000,
                solver: Solver::Groebner,
                sparse_la: true,
                small_base: base.len() / 3,
                max_large_primes: 2,
                ..GaudryOptions::default()
            },
        );
        assert_eq!(lp.correct, Some(true), "{lp:?}");
        assert!(lp.lp_full_relations > 0, "{lp:?}");
        assert!(lp.lp_histogram[1] + lp.lp_histogram[2] > 0, "{lp:?}");
        assert_eq!(lp.la_unknowns, base.len() / 3 + 1);
    }

    #[test]
    fn gaudry_and_rho_recover_the_planted_logarithm() {
        let inst = generate_instance3(67, 11);
        let mut rng = StdRng::seed_from_u64(2);
        let base = SubspaceBase::build(&inst, &mut rng);
        let rep = run_gaudry(&inst, &base, 1, 20_000);
        assert_eq!(rep.correct, Some(true), "{rep:?}");
        assert!(rep.decomposition_rate > 0.02);
        let grob = run_gaudry_with(&inst, &base, 1, 20_000, Solver::Groebner, true);
        assert_eq!(grob.correct, Some(true), "{grob:?}");
        assert_eq!(grob.cross_check_mismatches, 0, "{grob:?}");
        assert!(grob.solve_stats.solves == grob.residuals);
        let rho = run_rho3(&inst, 1);
        assert_eq!(rho.correct, Some(true), "{rho:?}");
    }

    /// The Joux–Vitse `k − 1` variant recovers the same planted
    /// logarithm, from decompositions into **two** base points and no
    /// Macaulay step at all.
    ///
    /// The two properties worth pinning are the ones that make it a
    /// different method rather than a tuning of the other two: it must
    /// build no symmetrised-`S₄` machinery (`solve_stats.solves == 0`),
    /// and it must need far more residuals per relation, because that
    /// is the trade it is making.
    #[test]
    fn the_pair_only_variant_recovers_the_logarithm_without_a_macaulay_step() {
        let inst = generate_instance3(67, 11);
        let mut rng = StdRng::seed_from_u64(2);
        let base = SubspaceBase::build(&inst, &mut rng);

        let pair = run_gaudry_with(&inst, &base, 1, 400_000, Solver::PairOnly, false);
        assert_eq!(pair.correct, Some(true), "{pair:?}");
        assert_eq!(
            pair.solve_stats.solves, 0,
            "PairOnly must not run the S4 solve at all"
        );
        assert_eq!(pair.solve_stats.macaulay_muls, 0);
        assert!(pair.relations_verified > 0);

        // The trade: many more residuals per relation than the
        // three-point oracle needs on the same instance.
        let grob = run_gaudry_with(&inst, &base, 1, 20_000, Solver::Groebner, false);
        assert_eq!(grob.correct, Some(true), "{grob:?}");
        let pair_per_rel = pair.residuals as f64 / pair.relations_verified.max(1) as f64;
        let grob_per_rel = grob.residuals as f64 / grob.relations_verified.max(1) as f64;
        assert!(
            pair_per_rel > 4.0 * grob_per_rel,
            "pair {pair_per_rel:.1} vs triple {grob_per_rel:.1} residuals per relation"
        );
        // …bought by a per-residual cost orders of magnitude lower.
        let pair_each = pair.oracle_fp_muls / pair.residuals.max(1);
        let grob_each = grob.oracle_fp_muls / grob.residuals.max(1);
        assert!(
            pair_each * 50 < grob_each,
            "pair {pair_each} vs triple {grob_each} F_p muls per residual"
        );
    }
}
