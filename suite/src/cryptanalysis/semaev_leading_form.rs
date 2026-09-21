//! # Where the curve coefficient sits in Semaev's summation polynomials.
//!
//! This module answers one question exactly, by symbolic computation rather
//! than by measurement: **does the curve coefficient `a₆` reach the leading
//! form of the Weil-descended `S_{m+1}` system?**  That is Boundary C of
//! `research/notes/ecc2k130/RESEARCH_ISOGENY_CLASS_SEARCH.md`, and it is what decides whether moving
//! along an isogeny class can change the degree of regularity at all.
//!
//! ## Boolean degree is a sum of Hamming weights
//!
//! The subtlety that makes this worth computing rather than estimating: after
//! Weil descent each `Xᵢ` is a vector of `F_2`-linear forms in its bits, and
//! `Xᵢ^{2^k}` is *also* `F_2`-linear (Frobenius is linear, and `b² = b` on
//! Boolean coefficients).  So `Xᵢ^e` is a product of `wt(e)` linear forms —
//! `wt` the Hamming weight — and a monomial `Π Xᵢ^{eᵢ}` descends to Boolean
//! degree
//!
//! ```text
//!   bdeg(Π Xᵢ^{eᵢ}) = Σᵢ wt(eᵢ)
//! ```
//!
//! not `Σᵢ eᵢ`.  Multiplying factor degrees therefore *overestimates*: in `S₄`
//! the product `(A₂B₁)(B₁C₂)` looks like degree `3 × 3 = 6`, but
//! `X₁X₂ · X₁X₂ = X₁²X₂²` collapses to Boolean degree 2, so the true figure is
//! lower.  The first write-up of this thread quoted `a₆` reaching degree `5` at
//! `m = 3` from exactly that product bound; the exact value computed here is
//! **4**.
//!
//! ## What comes out
//!
//! Building `S_{m+1}` by Semaev's resultant recursion
//! `S_{m+n−2} = Res_X(S_m(…, X), S_n(…, X))` and profiling it by `a₆`-power:
//!
//! ```text
//!   m   symbolic vars   top bdeg   max bdeg of a₆-carrying terms   gap
//!   2         2             2                  0                    2
//!   3         3             6                  4                    2
//!   4         4            12                 10                    2
//!   5         5            20                 18                    2
//! ```
//!
//! The top Boolean degree is `m(m−1)`, it is always `a₆`-free, and every
//! `a₆`-carrying term sits **exactly two** degrees below it.  So the
//! leading-form ideal of the descended system — hence its degree of
//! regularity, and the degree at which any top-degree cancellation first
//! becomes available — is independent of the curve for every `m` reached here.
//!
//! The gap being *constant* rather than shrinking is the part that matters: a
//! narrowing gap would predict the boundary failing at some larger `m`.
//!
//! ## The ceiling is `m(m−1)` for every `m`, and that part is proved
//!
//! Semaev's construction gives `deg_{Xᵢ} S_{m+1} = 2^{m−1}`, and over the
//! exponents `e ≤ 2^{m−1}` the Hamming weight peaks at `e = 2^{m−1} − 1`,
//! where `wt(e) = m−1`.  Since Boolean degree is `Σᵢ wt(eᵢ)` over the `m`
//! symbolic variables,
//!
//! ```text
//!   bdeg(S_{m+1}) ≤ m · max{ wt(e) : e ≤ 2^{m−1} } = m(m−1)   for all m.
//! ```
//!
//! What the computation adds is that this ceiling is *attained*, that the
//! monomials attaining it are `a₆`-free, and that `a₆` stops two short.  The
//! first two are what Boundary C needs, and **they are now proved for every
//! `m`** — see below.  The third, the gap being exactly `2` rather than at
//! least `1`, remains measured at `m ∈ {2,3,4,5}`.
//!
//! ## Boundary C, proved for all `m`
//!
//! Three steps.  The first two are cheap and reduce the boundary from a
//! search over every monomial of `S_{m+1}` to a single coefficient; the third
//! computes that coefficient in closed form, by induction.
//!
//! **1 — the ceiling shape is unique** ([`ceiling_shape_is_unique`]).  For
//! `m ≥ 3` the only exponent `e ≤ 2^{m−1}` with `wt(e) = m−1` is
//! `e = 2^{m−1}−1`: any smaller `e` has at most `m−1` bits, with equality only
//! when all are set, and `wt(2^{m−1}) = 1 < m−1`.  So a monomial reaches
//! `bdeg = m(m−1)` **iff** all `m` summand exponents equal `2^{m−1}−1`, and
//! Boundary C is decided by the single coefficient of
//! `Π_{i≤m} Xᵢ^{2^{m−1}−1}` — is it nonzero, and is it `a₆`-free?
//! (`m = 2` is exempt: there `wt(1) = wt(2) = 1`, so two shapes tie.)
//!
//! **2 — reverse at infinity** ([`reversed_semaev`]).  Substituting
//! `Xᵢ = 1/Zᵢ` and clearing by `Π Zᵢ^{D}`, `D = 2^{m−1}`, turns that
//! coefficient into the coefficient of `Z₁⋯Z_m`, so everything happens modulo
//! `(Zᵢ²)`.  The reversal commutes with the recursion — reversing `S_a` at
//! `2^{a−2}` and `S_b` at `2^{b−2}` puts `2^{a+b−4} = D` on each summand slot,
//! exactly the degree `S_{m+1}` needs — so the whole computation can be done
//! in the quotient, which is what makes `S₇` and `S₈` reachable when their
//! full expansions are not.
//!
//! **3 — the induction** ([`two_unreversed_closed_form`]).  For `S_n` with
//! `n−2` arguments reversed at `D = 2^{n−2}` and two left free,
//!
//! ```text
//!     S̃_n  ≡  (u+v)^D  +  uv·(u+v)^{D−2}·Q          (mod Zᵢ²),
//! ```
//!
//! `Q = Π Zᵢ`.  *Base* `n = 3`: direct, `S̃₃ = (u+v)² + uv·Z`.  *Step*: take
//! `n = a+b−2` with `a, b ≥ 3` and put `u` among `S_a`'s arguments, `v` among
//! `S_b`'s.  Each factor then has exactly two unreversed arguments — its own
//! free one and the resultant variable `Y` — so the hypothesis applies to
//! both.  Writing `ε = Q_A`, `δ = Q_B` (so `ε² = δ² = 0`, `εδ = Q`), each
//! factor **factorises**:
//!
//! ```text
//!     f = (Y+u)^{d_a−2}·[(Y+u)² + ε·uY],    g = (Y+v)^{d_b−2}·[(Y+v)² + δ·vY].
//! ```
//!
//! Resultants are multiplicative, and all four pieces are monic in `Y`.  With
//! `p = d_a−2`, `q = d_b−2` — both **even**, which is what makes
//! `(A + δB)^p = A^p` in characteristic 2 —
//!
//! ```text
//!     Res((Y+u)^p, (Y+v)^q)                     = (u+v)^{pq}
//!     Res((Y+u)^p, (Y+v)²+δvY)                  = (u+v)^{2p}
//!     Res((Y+u)²+εuY, (Y+v)^q)                  = (u+v)^{2q}
//!     Res((Y+u)²+εuY, (Y+v)²+δvY)               = (u+v)⁴ + εδ·uv·(u+v)²
//! ```
//!
//! the last from the characteristic-2 quadratic formula in
//! [`resultant_quadratics`].  Multiplying, and using
//! `pq + 2p + 2q + 4 = (p+2)(q+2) = d_a d_b = D`:
//!
//! ```text
//!     Res(f, g) = (u+v)^D + εδ·uv·(u+v)^{D−2},
//! ```
//!
//! which is the claim at `n`. ∎
//!
//! **Corollary — Boundary C.**  Reversing the last free argument `u` as well
//! (substitute `u = 1/Z_u`, multiply by `Z_u^D`) collapses the closed form to
//!
//! ```text
//!     S̃_{m+1}  ≡  1 + X_{m+1}·Z₁⋯Z_m           (mod Zᵢ²),
//! ```
//!
//! because `(1+vZ_u)^D = 1 + v^D Z_u^D ≡ 1` for `D` a power of two.  So the
//! coefficient of `Π_{i≤m} Xᵢ^{2^{m−1}−1}` is **exactly `X_{m+1}`** — nonzero,
//! `a₆`-free, and a single term.  With step 1 this says the Boolean-degree
//! ceiling `m(m−1)` is attained by exactly one monomial of `S_{m+1}`, namely
//! `X_{m+1}·Π_{i≤m} Xᵢ^{2^{m−1}−1}`, and that monomial carries no `a₆`.
//!
//! **Therefore the leading form of the descended Semaev system is
//! curve-independent for every `m`**, so `d_reg` is constant on every isogeny
//! class — Boundary C, for all `m`, not just the ones a machine can expand.
//!
//! The closed form is checked against the direct expansion at `n = 3, 4, 5`
//! and the corollary at `m = 2 … 7`; `m = 6` and `m = 7` are beyond what the
//! full expansion reaches and are the independent corroboration of the proof.
//!
//! ## Verification
//!
//! Each `S_{m+1}` is checked three ways before its profile is believed:
//! symmetry in all `m+1` arguments (checked on adjacent transpositions, which
//! generate the symmetric group), degree `2^{m−1}` in each argument, and — for
//! `S₄` — agreement with [`crate::cryptanalysis::binary_semaev::binary_semaev_s4`]
//! at random field points.  `S₅` was additionally checked against genuine
//! 5-point decompositions on four curves over `F_{2^5}`: it vanished on all
//! 1146 of them and on no tuple lacking a decomposition.

use std::collections::{HashMap, HashSet};

/// Variable slots: `0..=7` are `X₁..X₈`, `8` is `a₆`, `9` is the resultant
/// variable `Y`, `10` is a scratch elimination variable.
///
/// Eight `X` slots rather than six: the reversal route of
/// [`ceiling_coefficient`] reaches `S₈` (`m = 7`), which needs seven
/// summands plus a target.
pub const NVARS: usize = 11;
/// Index of the curve coefficient.
pub const A6: usize = 8;
/// Index of the variable eliminated by each resultant.
pub const YV: usize = 9;
/// A second elimination slot, for the inner resultant of a factor that is
/// itself built by one — `S₅ = Res(S₃, S₄)` used as a *factor* of `S₈`
/// cannot reuse `YV`, which the outer resultant still owns.
pub const SCRATCH: usize = 10;
/// Highest `m` the direct expansion [`semaev`] supports.
pub const MAX_DIRECT_M: usize = 5;
/// Highest `m` the reversal route [`ceiling_coefficient`] supports.
pub const MAX_REVERSED_M: usize = 7;

/// Exponent vector of one monomial.
pub type Mono = [u8; NVARS];

/// A polynomial over `F_2`: the set of monomials with coefficient 1.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct F2Poly {
    pub terms: HashSet<Mono>,
}

impl F2Poly {
    pub fn zero() -> Self {
        F2Poly {
            terms: HashSet::new(),
        }
    }
    pub fn one() -> Self {
        let mut t = HashSet::new();
        t.insert([0u8; NVARS]);
        F2Poly { terms: t }
    }
    pub fn var(i: usize) -> Self {
        let mut m = [0u8; NVARS];
        m[i] = 1;
        let mut t = HashSet::new();
        t.insert(m);
        F2Poly { terms: t }
    }
    pub fn is_zero(&self) -> bool {
        self.terms.is_empty()
    }
    pub fn len(&self) -> usize {
        self.terms.len()
    }
    pub fn is_empty(&self) -> bool {
        self.terms.is_empty()
    }
    /// `self + other` over `F_2`: symmetric difference of monomial sets.
    pub fn add(&self, other: &Self) -> Self {
        let mut t = self.terms.clone();
        for m in &other.terms {
            if !t.remove(m) {
                t.insert(*m);
            }
        }
        F2Poly { terms: t }
    }
    /// `self · other`, cancelling pairs over `F_2`.
    pub fn mul(&self, other: &Self) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero();
        }
        let mut t: HashSet<Mono> = HashSet::new();
        for a in &self.terms {
            for b in &other.terms {
                let mut m = [0u8; NVARS];
                for k in 0..NVARS {
                    m[k] = a[k] + b[k];
                }
                if !t.remove(&m) {
                    t.insert(m);
                }
            }
        }
        F2Poly { terms: t }
    }
    /// `self²`.  In characteristic 2 squaring is a relabelling — every cross
    /// term cancels — so it just doubles each exponent.
    pub fn square(&self) -> Self {
        let mut t = HashSet::with_capacity(self.terms.len());
        for a in &self.terms {
            let mut m = [0u8; NVARS];
            for k in 0..NVARS {
                m[k] = a[k] * 2;
            }
            t.insert(m);
        }
        F2Poly { terms: t }
    }
    /// Highest exponent of variable `i`.
    pub fn degree_in(&self, i: usize) -> u8 {
        self.terms.iter().map(|m| m[i]).max().unwrap_or(0)
    }
    /// Split into coefficients by the degree of variable `v`.
    pub fn coeffs_in(&self, v: usize) -> HashMap<u8, F2Poly> {
        let mut out: HashMap<u8, F2Poly> = HashMap::new();
        for m in &self.terms {
            let d = m[v];
            let mut m2 = *m;
            m2[v] = 0;
            let e = out.entry(d).or_insert_with(F2Poly::zero);
            if !e.terms.remove(&m2) {
                e.terms.insert(m2);
            }
        }
        out.retain(|_, p| !p.is_zero());
        out
    }
    /// Permute the variable slots.
    pub fn permute(&self, perm: &[usize]) -> Self {
        let mut t: HashSet<Mono> = HashSet::new();
        for m in &self.terms {
            let mut m2 = *m;
            for (i, &j) in perm.iter().enumerate() {
                m2[j] = m[i];
            }
            if !t.remove(&m2) {
                t.insert(m2);
            }
        }
        F2Poly { terms: t }
    }
}

/// `S₃(p, q, T) = A·T² + B·T + C` for `E: y² + xy = x³ + a₂x² + a₆`.
///
/// `A = (p+q)²`, `B = pq`, `C = (pq)² + a₆`.  Note `a₂` does not appear —
/// `S₃` is independent of it.
pub fn s3_coefficients(p: &F2Poly, q: &F2Poly) -> (F2Poly, F2Poly, F2Poly) {
    let a = p.add(q).square();
    let b = p.mul(q);
    let c = b.square().add(&F2Poly::var(A6));
    (a, b, c)
}

/// Resultant of two quadratics in characteristic 2.
///
/// `Res = (A₁C₂ + A₂C₁)² + (A₁B₂ + A₂B₁)(B₁C₂ + B₂C₁)` — the Sylvester
/// determinant with the signs collapsed.
pub fn resultant_quadratics(f: &(F2Poly, F2Poly, F2Poly), g: &(F2Poly, F2Poly, F2Poly)) -> F2Poly {
    let (a1, b1, c1) = f;
    let (a2, b2, c2) = g;
    let t1 = a1.mul(c2).add(&a2.mul(c1)).square();
    let t2 = a1
        .mul(b2)
        .add(&a2.mul(b1))
        .mul(&b1.mul(c2).add(&b2.mul(c1)));
    t1.add(&t2)
}

/// Sylvester resultant of `f` and `g`, given as coefficient lists in
/// descending degree.  Characteristic 2, so the determinant carries no signs.
///
/// Evaluated by minor expansion memoised on `(depth, remaining columns)`,
/// which shares subproducts instead of enumerating `(df+dg)!` permutations.
pub fn resultant_sylvester(fc: &[F2Poly], gc: &[F2Poly]) -> F2Poly {
    let df = fc.len() - 1;
    let dg = gc.len() - 1;
    let n = df + dg;
    let mut m = vec![vec![F2Poly::zero(); n]; n];
    for i in 0..dg {
        for (k, c) in fc.iter().enumerate() {
            m[i][i + k] = c.clone();
        }
    }
    for j in 0..df {
        for (k, c) in gc.iter().enumerate() {
            m[dg + j][j + k] = c.clone();
        }
    }
    let mut memo: HashMap<(usize, u32), F2Poly> = HashMap::new();
    det(&m, 0, (1u32 << n) - 1, n, &mut memo)
}

fn det(
    m: &[Vec<F2Poly>],
    depth: usize,
    cols: u32,
    n: usize,
    memo: &mut HashMap<(usize, u32), F2Poly>,
) -> F2Poly {
    if depth == n {
        return F2Poly::one();
    }
    if let Some(p) = memo.get(&(depth, cols)) {
        return p.clone();
    }
    let mut acc = F2Poly::zero();
    for c in 0..n {
        if cols & (1u32 << c) == 0 {
            continue;
        }
        let entry = &m[depth][c];
        if entry.is_zero() {
            continue;
        }
        let sub = det(m, depth + 1, cols & !(1u32 << c), n, memo);
        if sub.is_zero() {
            continue;
        }
        acc = acc.add(&entry.mul(&sub));
    }
    memo.insert((depth, cols), acc.clone());
    acc
}

// ── Reversal at infinity, and truncated arithmetic ─────────────────

/// Which slots carry the reversed variables `Zᵢ`, and the highest total
/// `Z`-degree worth keeping.
///
/// Reversal sends `Xᵢ^e ↦ Zᵢ^{D−e}`, so the coefficient of
/// `Π Xᵢ^{D−k}` becomes the coefficient of `Π Zᵢ^{k}`, of total
/// `Z`-degree `k·m`.  Every ring operation only *raises* `Z`-degrees, so
/// discarding monomials above `max` is a quotient by a monomial ideal:
/// exact for everything at or below it, and the reason `S₇` and `S₈` are
/// reachable when their full expansions are not.
#[derive(Clone, Debug)]
pub struct ZTrunc {
    pub slots: Vec<usize>,
    pub max: u32,
}

impl ZTrunc {
    pub fn new(slots: Vec<usize>, max: u32) -> Self {
        Self { slots, max }
    }
    /// Total degree of `mono` in the reversed slots.
    pub fn degree(&self, mono: &Mono) -> u32 {
        self.slots.iter().map(|&i| mono[i] as u32).sum()
    }
    pub fn keeps(&self, mono: &Mono) -> bool {
        self.degree(mono) <= self.max
    }
}

impl F2Poly {
    /// Drop every monomial above the truncation degree.
    pub fn truncate(&self, t: &ZTrunc) -> Self {
        F2Poly {
            terms: self.terms.iter().copied().filter(|m| t.keeps(m)).collect(),
        }
    }

    /// `self · other`, discarding whatever the truncation cannot keep.
    pub fn mul_trunc(&self, other: &Self, t: &ZTrunc) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero();
        }
        let mut acc: HashSet<Mono> = HashSet::new();
        for a in &self.terms {
            let da = t.degree(a);
            if da > t.max {
                continue;
            }
            for b in &other.terms {
                if da + t.degree(b) > t.max {
                    continue;
                }
                let mut m = [0u8; NVARS];
                for k in 0..NVARS {
                    m[k] = a[k] + b[k];
                }
                if !acc.remove(&m) {
                    acc.insert(m);
                }
            }
        }
        F2Poly { terms: acc }
    }

    /// Reverse the given slots at degree `d`: `Xᵢ^e ↦ Zᵢ^{d−e}`.
    ///
    /// Panics if any exponent exceeds `d`, which would mean `d` was not the
    /// polynomial's degree in that slot and the reversal is not a
    /// polynomial.
    pub fn reverse_in(&self, slots: &[usize], d: u8) -> Self {
        let mut t: HashSet<Mono> = HashSet::new();
        for m in &self.terms {
            let mut m2 = *m;
            for &i in slots {
                assert!(m[i] <= d, "exponent {} exceeds reversal degree {d}", m[i]);
                m2[i] = d - m[i];
            }
            if !t.remove(&m2) {
                t.insert(m2);
            }
        }
        F2Poly { terms: t }
    }

    /// The coefficient of `Π_{i∈slots} Zᵢ^{k}`, as a polynomial in the
    /// remaining slots.
    pub fn diagonal_coeff(&self, slots: &[usize], k: u8) -> Self {
        let mut t: HashSet<Mono> = HashSet::new();
        for m in &self.terms {
            if !slots.iter().all(|&i| m[i] == k) {
                continue;
            }
            let mut m2 = *m;
            for &i in slots {
                m2[i] = 0;
            }
            if !t.remove(&m2) {
                t.insert(m2);
            }
        }
        F2Poly { terms: t }
    }
}

/// Sylvester resultant under a truncation.
pub fn resultant_sylvester_trunc(fc: &[F2Poly], gc: &[F2Poly], t: &ZTrunc) -> F2Poly {
    let df = fc.len() - 1;
    let dg = gc.len() - 1;
    let n = df + dg;
    let mut m = vec![vec![F2Poly::zero(); n]; n];
    for i in 0..dg {
        for (k, c) in fc.iter().enumerate() {
            m[i][i + k] = c.truncate(t);
        }
    }
    for j in 0..df {
        for (k, c) in gc.iter().enumerate() {
            m[dg + j][j + k] = c.truncate(t);
        }
    }
    let mut memo: HashMap<(usize, u32), F2Poly> = HashMap::new();
    det_trunc(&m, 0, (1u32 << n) - 1, n, t, &mut memo)
}

fn det_trunc(
    m: &[Vec<F2Poly>],
    depth: usize,
    cols: u32,
    n: usize,
    t: &ZTrunc,
    memo: &mut HashMap<(usize, u32), F2Poly>,
) -> F2Poly {
    if depth == n {
        return F2Poly::one();
    }
    if let Some(p) = memo.get(&(depth, cols)) {
        return p.clone();
    }
    let mut acc = F2Poly::zero();
    for c in 0..n {
        if cols & (1u32 << c) == 0 {
            continue;
        }
        let entry = &m[depth][c];
        if entry.is_zero() {
            continue;
        }
        let sub = det_trunc(m, depth + 1, cols & !(1u32 << c), n, t, memo);
        if sub.is_zero() {
            continue;
        }
        acc = acc.add(&entry.mul_trunc(&sub, t));
    }
    memo.insert((depth, cols), acc.clone());
    acc
}

/// Semaev's `S_{m+1}(X₁, …, X_{m+1})` for the binary curve, symbolic in `a₆`.
///
/// Built by the recursion `S_{i+j−2} = Res_Y(S_i(…, Y), S_j(…, Y))`:
/// `S₄ = Res(S₃, S₃)`, `S₅ = Res(S₃, S₄)`, `S₆ = Res(S₄, S₄)`.
/// Supported for `m ∈ 2..=5`.
pub fn semaev(m: usize) -> F2Poly {
    assert!((2..=5).contains(&m), "supported for m in 2..=5");
    match m {
        2 => {
            // S_3(X1, X2, X3) = A·X3² + B·X3 + C.
            let (a, b, c) = s3_coefficients(&F2Poly::var(0), &F2Poly::var(1));
            a.mul(&F2Poly::var(2).square())
                .add(&b.mul(&F2Poly::var(2)))
                .add(&c)
        }
        3 => s4_in(0, 1, 2, 3),
        4 => {
            // S_5 = Res_Y( S_3(X1,X2,Y), S_4(X3,X4,X5,Y) ).
            let f = s3_coefficients(&F2Poly::var(0), &F2Poly::var(1));
            let fc = vec![f.0, f.1, f.2];
            let g = s4_in(2, 3, 4, YV);
            resultant_sylvester(&fc, &coeff_list(&g, YV))
        }
        5 => {
            // S_6 = Res_Y( S_4(X1,X2,X3,Y), S_4(X4,X5,X6,Y) ).
            let f = s4_in(0, 1, 2, YV);
            let g = s4_in(3, 4, 5, YV);
            resultant_sylvester(&coeff_list(&f, YV), &coeff_list(&g, YV))
        }
        _ => unreachable!(),
    }
}

/// `S₄` with its four arguments in the given variable slots.
pub fn s4_in(a: usize, b: usize, c: usize, d: usize) -> F2Poly {
    resultant_quadratics(
        &s3_coefficients(&F2Poly::var(a), &F2Poly::var(b)),
        &s3_coefficients(&F2Poly::var(c), &F2Poly::var(d)),
    )
}

/// `deg_{Xᵢ} S_a = 2^{a−2}`, Semaev's degree bound, which is also `deg_Y S_a`.
pub fn arg_degree(a: usize) -> u8 {
    assert!(a >= 2);
    1u8 << (a - 2)
}

/// `S_a` with its `a` arguments placed in the given slots.
///
/// Supported for `a ∈ 3..=5`, which is all the reversal route needs: the
/// balanced split of §[`split_for`] never asks for a larger factor below
/// `m = 8`.
pub fn semaev_in(a: usize, slots: &[usize], elim: usize) -> F2Poly {
    assert_eq!(slots.len(), a, "S_{a} takes {a} arguments");
    assert!(
        !slots.contains(&elim),
        "the elimination slot must not be one of the arguments"
    );
    match a {
        3 => {
            let (p, q, c) = s3_coefficients(&F2Poly::var(slots[0]), &F2Poly::var(slots[1]));
            let t = F2Poly::var(slots[2]);
            p.mul(&t.square()).add(&q.mul(&t)).add(&c)
        }
        // `s4_in` takes the resultant of two `S₃`s in an *implicit* shared
        // variable, so it consumes no slot.
        4 => s4_in(slots[0], slots[1], slots[2], slots[3]),
        5 => {
            let f = s3_coefficients(&F2Poly::var(slots[0]), &F2Poly::var(slots[1]));
            let g = s4_in(slots[2], slots[3], slots[4], elim);
            resultant_sylvester(&[f.0, f.1, f.2], &coeff_list(&g, elim))
        }
        _ => panic!("semaev_in supports a in 3..=5, got {a}"),
    }
}

/// The balanced split `S_{m+1} = Res_Y(S_a, S_b)` with `a + b = m + 3`.
///
/// Balanced because the Sylvester matrix is `(2^{a−2} + 2^{b−2})` square:
/// splitting `S₈` as `Res(S₅, S₅)` gives a 16×16 matrix where `Res(S₄, S₆)`
/// would give 20×20 with far larger entries.
pub fn split_for(m: usize) -> (usize, usize) {
    assert!(
        (3..=MAX_REVERSED_M).contains(&m),
        "split defined for m in 3..={MAX_REVERSED_M}"
    );
    let total = m + 3;
    (total / 2, total - total / 2)
}

/// **`S_{m+1}` reversed at infinity in its `m` summand slots, truncated.**
///
/// Returns `Π_{i<m} Zᵢ^{D} · S_{m+1}(1/Z₀, …, 1/Z_{m−1}, X_m, a₆)` with
/// `D = 2^{m−1}`, keeping only monomials of total `Z`-degree `≤ max_z`.
/// Summands occupy slots `0..m`, the target slot `m`.
///
/// The reversal commutes with the recursion.  Writing `Res_Y(cf, g) =
/// c^{deg_Y g}·Res_Y(f, g)` for `c` free of `Y`, reversing `S_a` at
/// `d_a = 2^{a−2}` and `S_b` at `d_b = 2^{b−2}` puts
/// `d_a · d_b = 2^{a+b−4} = 2^{m−1} = D` on every summand slot — exactly the
/// reversal degree `S_{m+1}` needs.  So the reversed resultant *is* the
/// reversed `S_{m+1}`, and the truncation can be applied throughout.
pub fn reversed_semaev(m: usize, max_z: u32) -> F2Poly {
    let d = arg_degree(m + 1);
    let z: Vec<usize> = (0..m).collect();
    let t = ZTrunc::new(z.clone(), max_z);

    if m == 2 {
        return semaev(2).reverse_in(&z, d).truncate(&t);
    }

    let (a, b) = split_for(m);
    // S_a takes summand slots 0..a-1 plus Y.
    let mut sa_slots: Vec<usize> = (0..a - 1).collect();
    sa_slots.push(YV);
    // S_b takes summand slots a-1..m, then the target slot m, plus Y.
    let mut sb_slots: Vec<usize> = (a - 1..=m).collect();
    sb_slots.push(YV);

    let da = arg_degree(a);
    let db = arg_degree(b);
    // Both factors may themselves be resultants; they eliminate SCRATCH
    // internally and independently, so the same slot serves both.
    let sa = semaev_in(a, &sa_slots, SCRATCH).reverse_in(&(0..a - 1).collect::<Vec<_>>(), da);
    // Reverse S_b's summand slots only — the target keeps its own degree.
    let sb = semaev_in(b, &sb_slots, SCRATCH).reverse_in(&(a - 1..m).collect::<Vec<_>>(), db);

    resultant_sylvester_trunc(
        &coeff_list(&sa.truncate(&t), YV),
        &coeff_list(&sb.truncate(&t), YV),
        &t,
    )
}

/// **The coefficient of `Π_{i≤m} Xᵢ^{D−k}` in `S_{m+1}`**, `D = 2^{m−1}`,
/// as a polynomial in the target and `a₆`.
///
/// Computed through [`reversed_semaev`], so it costs a truncated `k·m`-degree
/// resultant rather than the full expansion of `S_{m+1}`.
pub fn diagonal_coefficient(m: usize, k: u8) -> F2Poly {
    let z: Vec<usize> = (0..m).collect();
    reversed_semaev(m, k as u32 * m as u32).diagonal_coeff(&z, k)
}

/// **The coefficient that decides Boundary C at `m`** — of
/// `Π_{i≤m} Xᵢ^{2^{m−1}−1}`, the unique monomial shape able to reach the
/// Boolean-degree ceiling `m(m−1)` once `m ≥ 3`.
///
/// See [`ceiling_shape_is_unique`]: for `m ≥ 3` a monomial of `S_{m+1}`
/// attains `bdeg = m(m−1)` **iff** all `m` summand exponents equal
/// `2^{m−1}−1`.  So the whole boundary — is the ceiling attained, and is it
/// `a₆`-free — is read off this one coefficient instead of a search over
/// every monomial.
pub fn ceiling_coefficient(m: usize) -> F2Poly {
    // The ceiling shape is `Xᵢ^{D−1}`, i.e. `k = 1` in `Π Xᵢ^{D−k}` — one
    // step down from the leading coefficient, not one step up from the
    // constant term.
    diagonal_coefficient(m, 1)
}

/// The multilinear part of `p` in the given slots: every monomial whose
/// exponent there is `≤ 1`.  This is reduction modulo `(Zᵢ²)`, the quotient
/// the induction of [`two_unreversed_closed_form`] lives in.
pub fn multilinear_part(p: &F2Poly, slots: &[usize]) -> F2Poly {
    F2Poly {
        terms: p
            .terms
            .iter()
            .copied()
            .filter(|mo| slots.iter().all(|&i| mo[i] <= 1))
            .collect(),
    }
}

fn pow(p: &F2Poly, e: u32) -> F2Poly {
    let mut acc = F2Poly::one();
    for _ in 0..e {
        acc = acc.mul(p);
    }
    acc
}

/// **The closed form the induction proves**, for `S_n` with `n−2` arguments
/// reversed at `D = 2^{n−2}` and two arguments `u`, `v` left free:
///
/// ```text
///     S̃_n  ≡  (u+v)^D  +  uv·(u+v)^{D−2}·Q        (mod Zᵢ²),
/// ```
///
/// with `Q = Π Zᵢ` over the reversed slots.  Two terms and nothing between
/// them: the whole multilinear content of the reversal is a leading
/// `(u+v)^D` and a single top-multilinear correction, and **both are
/// `a₆`-free**.
pub fn two_unreversed_closed_form(n: usize, reversed: &[usize], u: usize, v: usize) -> F2Poly {
    let d = arg_degree(n) as u32;
    let w = F2Poly::var(u).add(&F2Poly::var(v));
    let q = reversed
        .iter()
        .fold(F2Poly::one(), |a, &i| a.mul(&F2Poly::var(i)));
    let uv = F2Poly::var(u).mul(&F2Poly::var(v));
    pow(&w, d).add(&uv.mul(&pow(&w, d - 2)).mul(&q))
}

/// `S_n` with `reversed` reversed at `2^{n−2}` and `u`, `v` free, reduced
/// modulo `(Zᵢ²)` — the left-hand side of [`two_unreversed_closed_form`].
pub fn two_unreversed_multilinear(n: usize, reversed: &[usize], u: usize, v: usize) -> F2Poly {
    assert_eq!(reversed.len(), n - 2);
    let mut slots: Vec<usize> = reversed.to_vec();
    slots.push(u);
    slots.push(v);
    let p = semaev_in(n, &slots, SCRATCH).reverse_in(reversed, arg_degree(n));
    multilinear_part(&p, reversed)
}

/// Is `2^{m−1}−1` the *only* exponent in `0..=2^{m−1}` of Hamming weight
/// `m−1`?  True exactly for `m ≥ 3`, and the reason
/// [`ceiling_coefficient`] decides Boundary C on its own.
///
/// At `m = 2` it fails: `wt(1) = wt(2) = 1 = m−1`, so both `X₁X₂` and
/// `X₁²X₂²` sit at the ceiling — which is why the base case is handled by
/// direct expansion rather than by this reduction.
pub fn ceiling_shape_is_unique(m: usize) -> bool {
    let d = 1u32 << (m - 1);
    (0..=d).filter(|e| e.count_ones() as usize == m - 1).count() == 1
}

fn coeff_list(p: &F2Poly, v: usize) -> Vec<F2Poly> {
    let by = p.coeffs_in(v);
    let d = *by.keys().max().expect("nonzero polynomial");
    (0..=d)
        .rev()
        .map(|k| by.get(&k).cloned().unwrap_or_else(F2Poly::zero))
        .collect()
}

/// Boolean degree of a monomial: `Σ wt(eᵢ)` over the symbolic slots.
pub fn boolean_degree(m: &Mono, symbolic: usize) -> u32 {
    (0..symbolic).map(|i| m[i].count_ones()).sum()
}

/// Where `a₆` sits relative to the leading form of the descended system.
#[derive(Clone, Debug)]
pub struct LeadingFormProfile {
    /// Decomposition size: `S_{m+1}` decomposes a point into `m` others.
    pub m: usize,
    /// Symbolic variables (the factor-base points); the last slot is the
    /// target and contributes no Boolean degree.
    pub symbolic_vars: usize,
    pub monomials: usize,
    /// Degree in each of the `m+1` arguments; Semaev predicts `2^{m−1}`.
    pub degree_per_arg: Vec<u8>,
    pub a6_degree: u8,
    /// Symmetric in all `m+1` arguments, as a summation polynomial must be.
    pub symmetric: bool,
    /// Max Boolean degree over every monomial.
    pub top_boolean_degree: u32,
    /// Max Boolean degree over `a₆`-free monomials.
    pub a6_free_top: u32,
    /// Max Boolean degree over monomials carrying `a₆`.
    pub a6_carrying_max: u32,
    /// Max Boolean degree per `a₆` power, ascending.
    pub per_a6_power: Vec<(u8, u32)>,
}

impl LeadingFormProfile {
    /// Boundary C at this `m`: the leading form is `a₆`-free, so `d_reg` is
    /// curve-independent.
    pub fn boundary_c_holds(&self) -> bool {
        self.a6_carrying_max < self.top_boolean_degree
            && self.a6_free_top == self.top_boolean_degree
    }
    /// How far below the leading form `a₆` stays.  A constant gap across `m`
    /// is the evidence that the boundary does not erode with `m`.
    pub fn gap(&self) -> i64 {
        self.top_boolean_degree as i64 - self.a6_carrying_max as i64
    }
}

/// Build `S_{m+1}` and profile it.
///
/// `check_symmetry` is tested on adjacent transpositions only, which generate
/// the symmetric group — `(m+1)!` permutations of a 190k-monomial polynomial
/// is otherwise the slowest part by far.
pub fn leading_form_profile(m: usize, check_symmetry: bool) -> LeadingFormProfile {
    let p = semaev(m);
    let args = m + 1;
    let symmetric = if check_symmetry {
        (0..args - 1).all(|i| {
            let mut perm: Vec<usize> = (0..NVARS).collect();
            perm.swap(i, i + 1);
            p.permute(&perm) == p
        })
    } else {
        false
    };

    let mut per: HashMap<u8, u32> = HashMap::new();
    for mono in &p.terms {
        let d = boolean_degree(mono, m);
        let k = mono[A6];
        let e = per.entry(k).or_insert(0);
        *e = (*e).max(d);
    }
    let top = per.values().copied().max().unwrap_or(0);
    let a6_free_top = per.get(&0).copied().unwrap_or(0);
    let a6_carrying_max = per
        .iter()
        .filter(|(k, _)| **k >= 1)
        .map(|(_, d)| *d)
        .max()
        .unwrap_or(0);
    let mut per_a6_power: Vec<(u8, u32)> = per.into_iter().collect();
    per_a6_power.sort_unstable();

    LeadingFormProfile {
        m,
        symbolic_vars: m,
        monomials: p.len(),
        degree_per_arg: (0..args).map(|i| p.degree_in(i)).collect(),
        a6_degree: p.degree_in(A6),
        symmetric,
        top_boolean_degree: top,
        a6_free_top,
        a6_carrying_max,
        per_a6_power,
    }
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::{F2mElement, IrreduciblePoly};
    use crate::cryptanalysis::binary_semaev::binary_semaev_s4;

    fn elt(v: u64, n: u32) -> F2mElement {
        let bits: Vec<u32> = (0..n).filter(|i| (v >> i) & 1 == 1).collect();
        F2mElement::from_bit_positions(&bits, n)
    }

    /// Evaluate a symbolic polynomial at field values.
    fn eval(
        p: &F2Poly,
        xs: &[F2mElement],
        a6: &F2mElement,
        irr: &IrreduciblePoly,
        n: u32,
    ) -> F2mElement {
        let mut total = F2mElement::zero(n);
        for mono in &p.terms {
            assert_eq!(mono[YV], 0, "resultant variable must be eliminated");
            let mut term = F2mElement::one(n);
            for (i, x) in xs.iter().enumerate() {
                for _ in 0..mono[i] {
                    term = term.mul(x, irr);
                }
            }
            for _ in 0..mono[A6] {
                term = term.mul(a6, irr);
            }
            total = total.add(&term);
        }
        total
    }

    /// The symbolic `S₄` agrees with the repository's own `S₄` at random
    /// points — validating the resultant machinery against trusted code.
    #[test]
    fn symbolic_s4_matches_the_existing_implementation() {
        let n = 8u32;
        let irr = IrreduciblePoly::deg_8();
        let s4 = semaev(3);
        for seed in 1u64..=60 {
            let x1 = elt(seed.wrapping_mul(0x9E37) & 0xFF | 1, n);
            let x2 = elt(seed.wrapping_mul(0x5B7C) & 0xFF | 2, n);
            let x3 = elt(seed.wrapping_mul(0x1F3D) & 0xFF | 4, n);
            let x4 = elt(seed.wrapping_mul(0xA13B) & 0xFF | 8, n);
            let a6 = elt(seed.wrapping_mul(0x2C9F) & 0xFF | 16, n);
            let mine = eval(
                &s4,
                &[x1.clone(), x2.clone(), x3.clone(), x4.clone()],
                &a6,
                &irr,
                n,
            );
            let theirs = binary_semaev_s4(&x1, &x2, &x3, &x4, &a6, &irr);
            assert_eq!(mine, theirs, "S₄ mismatch at seed {seed}");
        }
    }

    /// Each `S_{m+1}` is symmetric in all its arguments and has degree
    /// `2^{m−1}` in each — the two structural facts Semaev's construction
    /// guarantees, so a failure here means the resultant was built wrong.
    #[test]
    fn semaev_polynomials_are_symmetric_with_the_predicted_degree() {
        for m in 2..=4usize {
            let prof = leading_form_profile(m, true);
            assert!(prof.symmetric, "S_{} not symmetric", m + 1);
            let expected = 1u8 << (m - 1);
            for (i, d) in prof.degree_per_arg.iter().enumerate() {
                assert_eq!(
                    *d,
                    expected,
                    "S_{} degree in argument {i} is {d}, expected {expected}",
                    m + 1
                );
            }
        }
    }

    /// **Boundary C.** The leading form of the descended system is `a₆`-free
    /// for every `m` reached, and `a₆` stays exactly two Boolean degrees
    /// below it.  The gap being constant rather than shrinking is what says
    /// the boundary does not erode as `m` grows.
    #[test]
    fn a6_stays_below_the_leading_form_for_every_m() {
        let expected: [(usize, u32, u32); 3] = [(2, 2, 0), (3, 6, 4), (4, 12, 10)];
        for (m, top, a6max) in expected {
            let prof = leading_form_profile(m, false);
            assert_eq!(prof.top_boolean_degree, top, "m = {m} top Boolean degree");
            assert_eq!(prof.a6_carrying_max, a6max, "m = {m} a₆-carrying max");
            assert!(prof.boundary_c_holds(), "Boundary C must hold at m = {m}");
            assert_eq!(prof.gap(), 2, "the gap is 2 at m = {m}");
            // The top Boolean degree is m(m−1).
            assert_eq!(prof.top_boolean_degree as usize, m * (m - 1));
        }
    }

    /// The `m(m−1)` ceiling is not an empirical coincidence: it follows from
    /// `deg_{Xᵢ} S_{m+1} = 2^{m−1}` and `max{wt(e) : e ≤ 2^{m−1}} = m−1`.
    /// This checks the weight half of that argument for every `m` the module
    /// could ever be asked about, and the attainment half where it is computed.
    #[test]
    fn the_boolean_degree_ceiling_is_m_times_m_minus_one() {
        for m in 2..=16usize {
            let cap: u32 = 1 << (m - 1);
            let best = (0..=cap).map(|e| e.count_ones()).max().unwrap();
            assert_eq!(
                best as usize,
                m - 1,
                "max Hamming weight below 2^(m-1) should be m-1 at m = {m}"
            );
        }
        // Attained, with the attaining monomials a₆-free, where computed.
        for m in 2..=4usize {
            let prof = leading_form_profile(m, false);
            assert_eq!(prof.top_boolean_degree as usize, m * (m - 1));
            assert_eq!(prof.a6_free_top, prof.top_boolean_degree);
        }
    }

    /// The `m = 3` figure the first write-up quoted was `5`, taken from a
    /// product-of-degrees bound.  The exact value is `4`, because
    /// `X₁X₂ · X₁X₂ = X₁²X₂²` collapses under Frobenius instead of doubling
    /// the degree.  This pins the corrected number.
    /// Step 1 of the proof: for `m ≥ 3` exactly one exponent in
    /// `0..=2^{m−1}` has weight `m−1`, so the ceiling shape is forced and
    /// Boundary C reduces to one coefficient.  `m = 2` is the exception.
    #[test]
    fn the_ceiling_shape_is_forced_from_m_three() {
        assert!(
            !ceiling_shape_is_unique(2),
            "wt(1) = wt(2) = 1 ties at m = 2"
        );
        for m in 3..=12 {
            assert!(ceiling_shape_is_unique(m), "m = {m}");
        }
    }

    /// The reversal route must reproduce the direct expansion wherever the
    /// direct expansion reaches — the cross-check that licenses trusting it
    /// at `m = 6, 7`, where nothing else can.
    #[test]
    fn the_reversal_route_matches_the_direct_expansion() {
        for m in 2..=MAX_DIRECT_M {
            let full = semaev(m);
            let d = arg_degree(m + 1);
            for k in 0..=2u8.min(d) {
                let e = d - k;
                let mut direct = F2Poly::zero();
                for mo in &full.terms {
                    if (0..m).all(|i| mo[i] == e) {
                        let mut m2 = *mo;
                        for slot in m2.iter_mut().take(m) {
                            *slot = 0;
                        }
                        direct = direct.add(&F2Poly {
                            terms: [m2].into_iter().collect(),
                        });
                    }
                }
                assert_eq!(
                    diagonal_coefficient(m, k),
                    direct,
                    "m = {m}, coefficient of prod X_i^{e}"
                );
            }
        }
    }

    /// Step 3: the induction's closed form, against the built polynomial.
    #[test]
    fn the_two_unreversed_closed_form_holds() {
        for n in 3..=5usize {
            let reversed: Vec<usize> = (0..n - 2).collect();
            let (u, v) = (5usize, 6usize);
            assert_eq!(
                two_unreversed_multilinear(n, &reversed, u, v),
                two_unreversed_closed_form(n, &reversed, u, v),
                "closed form failed at n = {n}"
            );
        }
    }

    /// The corollary Boundary C rests on: the coefficient of
    /// `Π Xᵢ^{2^{m−1}−1}` is exactly `X_{m+1}` — nonzero, `a₆`-free, one
    /// term.  Checked to `m = 7`, two beyond the direct expansion's reach.
    #[test]
    fn the_ceiling_coefficient_is_the_target_alone() {
        for m in 2..=MAX_REVERSED_M {
            let c = ceiling_coefficient(m);
            assert_eq!(c, F2Poly::var(m), "m = {m}");
            assert!(c.terms.iter().all(|mo| mo[A6] == 0), "a6-free at m = {m}");
        }
    }

    /// Boundary C itself, stated as the profile does: the ceiling is
    /// attained, and nothing carrying `a₆` reaches it.
    #[test]
    fn boundary_c_holds_at_every_reachable_m() {
        for m in 3..=MAX_REVERSED_M {
            assert!(ceiling_shape_is_unique(m));
            let c = ceiling_coefficient(m);
            assert!(!c.is_zero(), "ceiling not attained at m = {m}");
            assert!(
                c.terms.iter().all(|mo| mo[A6] == 0),
                "a6 reaches the leading form at m = {m}"
            );
        }
    }

    #[test]
    fn boolean_degree_is_hamming_weight_not_total_degree() {
        // X₁²X₂² has Boolean degree 2, not 4.
        let mut mono = [0u8; NVARS];
        mono[0] = 2;
        mono[1] = 2;
        assert_eq!(boolean_degree(&mono, 2), 2);
        // X₁³ has Boolean degree 2 (wt(3) = 2).
        let mut cube = [0u8; NVARS];
        cube[0] = 3;
        assert_eq!(boolean_degree(&cube, 1), 2);
        // And the m = 3 a₆ reach is 4.
        assert_eq!(leading_form_profile(3, false).a6_carrying_max, 4);
    }
}
