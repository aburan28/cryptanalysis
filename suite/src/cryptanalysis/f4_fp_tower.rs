//! # F4 over a tower quotient ring: the sparse engine for PKM systems.
//!
//! The decomposition systems of Petit–Kosters–Messeng tower factor bases
//! (`research/notes/index-calculus/RESEARCH_PKM_TOWER_ORACLE.md`) live in
//! the quotient `R = F_p[y, u] / (towers)`. Every tower variable `y_j`
//! satisfies one quadratic relation
//!
//! ```text
//!     y_j² = a·y_j·y_{j+1} + b·y_{j+1} + c·y_j + d
//! ```
//!
//! with `y_{j+1}` the next level of the same tower. The relation for each
//! family:
//! - Kummer: `y_j² = y_{j+1}`;
//! - Dickson: `y_j² = y_{j+1} + 2`;
//! - a 2-isogeny step: `y_j² = y_j·y_{j+1} − ξ·y_{j+1} + ξ·y_j − τ`.
//!
//! On the top level `a = b = 0`. Under grevlex with every level larger than
//! the next, these relations are a Gröbner basis with leading monomials
//! `y_j²` (Lemma 1 of the note). Every element of `R` therefore has a
//! unique normal form that is square-free in the tower variables. The
//! chain presentation's free unknowns `u_k`, the abscissae of partial sums,
//! stay ordinary polynomial variables.
//!
//! This engine is Faugère's F4 on `R`, built like
//! [`pq_f4_f2`](crate::cryptanalysis::pq_f4_f2), which is F4 on the boolean
//! ring. Its parts:
//! - **Monomials** are a 64-bit tower mask plus up to four free exponents,
//!   packed into one `u128` whose integer order is grevlex with variable 0
//!   largest, the order [`f4_fp`](crate::cryptanalysis::f4_fp) uses.
//! - **Products are rewritten by the tower as they are formed**, so the
//!   tower equations never enter a matrix.
//! - **A tower pair `(g, y)`** exists for every tower variable `y` of
//!   `LM(g)`. It is the S-polynomial of `g` against `y² − …`, at degree
//!   `deg LM(g) + 1`, and enters the matrix as the single row `NF(y·g)`.
//!   Without these pairs the basis is not closed in `R`.
//! - **Critical pairs** go through Gebauer–Möller (Becker–Weispfenning
//!   `UPDATE`). Tower pairs are never pruned and never used to prune, as the
//!   boolean engine treats its field pairs.
//! - **The elimination follows Faugère–Lachartre.** Symbolic preprocessing
//!   gives reducer rows with distinct leading columns, and the shortest
//!   S-row at each lcm column joins them. The columns no reducer leads are
//!   then exactly the monomials without a divisor. The reducer block is
//!   reduced to dense rows over those columns (`B' = A⁻¹B`, the rightmost
//!   lead first), every S-row is reduced by it in one pass (`D − C·B'`), and
//!   the residues are echelonized in chunks, each reduced in parallel by the
//!   pivots found before it. Every pivot is a new leading monomial.
//! - **Rows are formed on demand.** A row is kept as the product that makes
//!   it and formed again, a block at a time, when it is eliminated, so a
//!   step's memory is `B'` rather than the matrix.
//! - **Arithmetic** below `2³¹` is lazy: an accumulator is reduced only when
//!   it crosses `2⁶³`, and the loop is dispatched at run time to AVX2 or
//!   AVX-512. Above `2³¹` every step is reduced (Barrett).
//!
//! What it measures:
//! - `solving_degree_max`: the highest degree of a step at which the basis
//!   gained an element. This is the solving degree of `f4_fp` and of the
//!   framework (`docs/ic/FRAMEWORK.md` §3).
//! - The unit: `F_p` multiply-adds in the eliminations.
//!
//! The input polynomials must already be tower normal forms. [`TowerRing::from_raw`]
//! reduces arbitrary ones. The engine therefore measures the note's
//! `reduced` presentation (§2.2): a summation polynomial of raw degree 4
//! enters at its normal form's degree, which is 2 on a Kummer tower.
//!
//! Limits: at most 64 tower variables, 4 free variables with exponents
//! below 256, and `p < 2³²`.

use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::sync::atomic::{AtomicBool, Ordering as AtomicOrdering};
use std::time::{Duration, Instant};

use rayon::prelude::*;

// ── Arithmetic in F_p, p < 2^32 ──────────────────────────────────────

#[derive(Clone, Copy, Debug)]
struct Fp {
    p: u64,
    m: u64,
}

impl Fp {
    fn new(p: u64) -> Self {
        assert!(
            (3..1 << 32).contains(&p),
            "f4_fp_tower: the prime must be odd and below 2^32"
        );
        Fp {
            p,
            m: (u128::from(u64::MAX) + 1).div_euclid(u128::from(p)) as u64,
        }
    }
    /// `x mod p` for any `x < 2⁶⁴` (Barrett; the quotient estimate is low
    /// by at most one).
    #[inline(always)]
    fn reduce(self, x: u64) -> u64 {
        let q = ((u128::from(x) * u128::from(self.m)) >> 64) as u64;
        let r = x - q * self.p;
        if r >= self.p {
            r - self.p
        } else {
            r
        }
    }
    #[inline(always)]
    fn mul(self, a: u64, b: u64) -> u64 {
        self.reduce(a * b)
    }
    #[inline(always)]
    fn add(self, a: u64, b: u64) -> u64 {
        let s = a + b;
        if s >= self.p {
            s - self.p
        } else {
            s
        }
    }
    #[inline(always)]
    fn neg(self, a: u64) -> u64 {
        if a == 0 {
            0
        } else {
            self.p - a
        }
    }
    fn pow(self, mut a: u64, mut e: u64) -> u64 {
        let mut r = 1u64;
        a %= self.p;
        while e > 0 {
            if e & 1 == 1 {
                r = self.mul(r, a);
            }
            a = self.mul(a, a);
            e >>= 1;
        }
        r
    }
    fn inv(self, a: u64) -> u64 {
        assert!(!a.is_multiple_of(self.p), "f4_fp_tower: inverse of zero");
        self.pow(a, self.p - 2)
    }
}

// ── Monomials ────────────────────────────────────────────────────────

/// A monomial of `R`, stored as its grevlex sort key: the larger key is
/// the larger monomial.
///
/// Layout, least significant first:
/// - bits `0..64`: the complement of the tower mask. Bit `j` of the mask is
///   `y_j`, variable `j`.
/// - bits `64..96`: for free variable `f` (global index `n_tower + f`), the
///   byte `255 − e_f` at bit `64 + 8f`.
/// - bits `96..104`: the total degree.
///
/// Grevlex compares degrees first, then the exponent of the *last*
/// variable, smaller winning, then the one before it, and so on. The last
/// free variable is the most significant byte of the free field, and the
/// free field sits above the tower field, so integer comparison is
/// grevlex. Within the tower field the highest differing bit decides,
/// which is the last differing variable, and the complement makes a 0
/// there, the smaller exponent, the larger key.
pub type Mono = u128;

const FREE_SHIFT: u32 = 64;
const DEG_SHIFT: u32 = 96;
/// Free variables a monomial can carry.
pub const MAX_FREE: usize = 4;

/// The monomial with tower mask `mask` and free exponents `free`.
#[inline]
pub fn mono(mask: u64, free: [u8; MAX_FREE]) -> Mono {
    let deg = mask.count_ones() + free.iter().map(|&e| u32::from(e)).sum::<u32>();
    let mut key = (u128::from(deg) << DEG_SHIFT) | u128::from(!mask);
    for (k, &e) in free.iter().enumerate() {
        key |= u128::from(255 - e) << (FREE_SHIFT + 8 * k as u32);
    }
    key
}

/// The tower variables of `m`, as a mask.
#[inline]
pub fn mask_of(m: Mono) -> u64 {
    !(m as u64)
}

/// The free exponents of `m`.
#[inline]
pub fn free_of(m: Mono) -> [u8; MAX_FREE] {
    let mut f = [0u8; MAX_FREE];
    for (k, e) in f.iter_mut().enumerate() {
        *e = 255 - ((m >> (FREE_SHIFT + 8 * k as u32)) & 0xff) as u8;
    }
    f
}

/// Total degree of `m`.
#[inline]
pub fn degree_of(m: Mono) -> u32 {
    (m >> DEG_SHIFT) as u32
}

/// The monomial `1`.
pub const ONE: Mono = (0xffff_ffffu128 << FREE_SHIFT) | (u64::MAX as u128);

/// `a | b` in the polynomial ring.
#[inline]
fn divides(a: Mono, b: Mono) -> bool {
    if mask_of(a) & !mask_of(b) != 0 || degree_of(a) > degree_of(b) {
        return false;
    }
    let (fa, fb) = (free_of(a), free_of(b));
    fa.iter().zip(&fb).all(|(x, y)| x <= y)
}

#[inline]
fn lcm(a: Mono, b: Mono) -> Mono {
    let (fa, fb) = (free_of(a), free_of(b));
    let mut f = [0u8; MAX_FREE];
    for k in 0..MAX_FREE {
        f[k] = fa[k].max(fb[k]);
    }
    mono(mask_of(a) | mask_of(b), f)
}

/// `a / b`, for `b | a`.
#[inline]
fn quotient(a: Mono, b: Mono) -> Mono {
    let (fa, fb) = (free_of(a), free_of(b));
    let mut f = [0u8; MAX_FREE];
    for k in 0..MAX_FREE {
        f[k] = fa[k] - fb[k];
    }
    mono(mask_of(a) & !mask_of(b), f)
}

#[inline]
fn coprime(a: Mono, b: Mono) -> bool {
    if mask_of(a) & mask_of(b) != 0 {
        return false;
    }
    let (fa, fb) = (free_of(a), free_of(b));
    fa.iter().zip(&fb).all(|(x, y)| *x == 0 || *y == 0)
}

#[inline]
fn add_free(a: [u8; MAX_FREE], b: [u8; MAX_FREE]) -> [u8; MAX_FREE] {
    let mut f = [0u8; MAX_FREE];
    for k in 0..MAX_FREE {
        f[k] = a[k]
            .checked_add(b[k])
            .expect("f4_fp_tower: a free exponent passed 255");
    }
    f
}

/// splitmix64 over both halves of a monomial key: the low half is a
/// complemented mask whose low bits barely vary between the monomials of
/// one system, so a multiplicative hash would crowd them into few buckets
/// (see `fx_hash::MaskHasher`).
#[derive(Default, Clone, Copy)]
struct MonoHasher(u64);

impl Hasher for MonoHasher {
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }
    fn write(&mut self, bytes: &[u8]) {
        for chunk in bytes.chunks(8) {
            let mut w = [0u8; 8];
            w[..chunk.len()].copy_from_slice(chunk);
            self.write_u64(u64::from_le_bytes(w));
        }
    }
    #[inline]
    fn write_u64(&mut self, value: u64) {
        let mut z = (self.0 ^ value).wrapping_add(0x9e37_79b9_7f4a_7c15);
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        self.0 = z ^ (z >> 31);
    }
    #[inline]
    fn write_u128(&mut self, value: u128) {
        self.write_u64(value as u64);
        self.write_u64((value >> 64) as u64);
    }
    #[inline]
    fn write_usize(&mut self, value: usize) {
        self.write_u64(value as u64);
    }
}

type MonoMap<V> = HashMap<Mono, V, BuildHasherDefault<MonoHasher>>;

// ── The ring ─────────────────────────────────────────────────────────

/// How one tower variable's square rewrites:
/// `y_j² = a·y_j·y_next + b·y_next + c·y_j + d`, all coefficients in
/// `[0, p)`. On a tower's top level `next` is `None` and `a = b = 0`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SquareRule {
    pub next: Option<u8>,
    pub a: u64,
    pub b: u64,
    pub c: u64,
    pub d: u64,
}

/// Combine repeated masks and drop zero coefficients, in place.
fn merge_masks(fp: Fp, terms: &mut Vec<(u64, u64)>) {
    if terms.len() < 2 {
        return;
    }
    terms.sort_unstable_by_key(|t| t.0);
    let mut out = 0usize;
    let mut i = 0usize;
    while i < terms.len() {
        let m = terms[i].0;
        let mut c = 0u64;
        while i < terms.len() && terms[i].0 == m {
            c = fp.add(c, terms[i].1);
            i += 1;
        }
        if c != 0 {
            terms[out] = (m, c);
            out += 1;
        }
    }
    terms.truncate(out);
}

/// `F_p[y_0, …, y_{n−1}, u_0, …] / (y_j² − rule_j)`. The tower variables
/// come first; the free variables follow, at global indices
/// `n_tower .. n_tower + n_free`.
#[derive(Clone, Debug)]
pub struct TowerRing {
    pub p: u64,
    /// One rule per tower variable.
    pub rules: Vec<SquareRule>,
    pub n_free: usize,
}

impl TowerRing {
    pub fn n_tower(&self) -> usize {
        self.rules.len()
    }

    pub fn n_vars(&self) -> usize {
        self.rules.len() + self.n_free
    }

    /// Panics unless the rules describe a tower this engine handles: every
    /// `next` is a later tower variable, so that each rewrite lowers the
    /// monomial in grevlex, and a top rule has `a = b = 0`.
    pub fn check(&self) {
        assert!(
            self.rules.len() <= 64,
            "f4_fp_tower: at most 64 tower variables"
        );
        assert!(
            self.n_free <= MAX_FREE,
            "f4_fp_tower: at most {MAX_FREE} free variables"
        );
        for (j, r) in self.rules.iter().enumerate() {
            for &x in &[r.a, r.b, r.c, r.d] {
                assert!(x < self.p, "f4_fp_tower: rule {j} has a coefficient ≥ p");
            }
            match r.next {
                Some(nx) => assert!(
                    (nx as usize) > j && (nx as usize) < self.rules.len(),
                    "f4_fp_tower: rule {j} must point at a later tower variable"
                ),
                None => assert!(
                    r.a == 0 && r.b == 0,
                    "f4_fp_tower: top rule {j} cannot use a next level"
                ),
            }
        }
    }

    /// `y_j · (mask, coef)` in normal form, pushed onto `out` as tower
    /// masks with coefficients (repeats allowed).
    fn mul_var_into(&self, fp: Fp, m: u64, j: usize, coef: u64, out: &mut Vec<(u64, u64)>) {
        let bit = 1u64 << j;
        if m & bit == 0 {
            out.push((m | bit, coef));
            return;
        }
        let r = self.rules[j];
        let m0 = m & !bit;
        if r.d != 0 {
            out.push((m0, fp.mul(coef, r.d)));
        }
        if r.c != 0 {
            out.push((m, fp.mul(coef, r.c)));
        }
        if let Some(nx) = r.next {
            let nx = nx as usize;
            if r.b != 0 {
                self.mul_var_into(fp, m0, nx, fp.mul(coef, r.b), out);
            }
            if r.a != 0 {
                self.mul_var_into(fp, m, nx, fp.mul(coef, r.a), out);
            }
        }
    }

    /// `coef · y^ma · y^mb` in normal form (tower parts only), pushed onto
    /// `out` with repeats allowed.
    fn mask_product_into(&self, fp: Fp, ma: u64, mb: u64, coef: u64, out: &mut Vec<(u64, u64)>) {
        let common = ma & mb;
        if common == 0 {
            out.push((ma | mb, coef));
            return;
        }
        // y^ma · y^mb = y^(ma ∪ mb) · Π_{j ∈ ma ∩ mb} y_j.
        let mut cur = vec![(ma | mb, coef)];
        let mut next = Vec::new();
        let mut bits = common;
        while bits != 0 {
            let j = bits.trailing_zeros() as usize;
            bits &= bits - 1;
            next.clear();
            for &(m, c) in &cur {
                self.mul_var_into(fp, m, j, c, &mut next);
            }
            // Without merging, a chain of rewrites repeats monomials and
            // the list grows exponentially in the number of common bits.
            merge_masks(fp, &mut next);
            std::mem::swap(&mut cur, &mut next);
        }
        out.extend(cur);
    }

    /// `u · g` in normal form.
    pub fn mul_mono(&self, g: &RPoly, u: Mono) -> RPoly {
        let fp = Fp::new(self.p);
        self.mul_mono_fp(fp, g, u)
    }

    fn mul_mono_fp(&self, fp: Fp, g: &RPoly, u: Mono) -> RPoly {
        let (mu, fu) = (mask_of(u), free_of(u));
        let mut terms: Vec<(Mono, u64)> = Vec::with_capacity(g.monos.len());
        let mut carried = false;
        let mut tmp: Vec<(u64, u64)> = Vec::new();
        for (&m, &c) in g.monos.iter().zip(&g.coefs) {
            let mm = mask_of(m);
            let f = add_free(free_of(m), fu);
            if mm & mu == 0 {
                terms.push((mono(mm | mu, f), u64::from(c)));
            } else {
                carried = true;
                tmp.clear();
                self.mask_product_into(fp, mm, mu, u64::from(c), &mut tmp);
                for &(x, cc) in &tmp {
                    terms.push((mono(x, f), cc));
                }
            }
        }
        if carried {
            RPoly::from_terms(fp, terms)
        } else {
            // A product by a monomial without carries is injective and
            // order-preserving: the terms are distinct and still descending.
            RPoly {
                monos: terms.iter().map(|t| t.0).collect(),
                coefs: terms.iter().map(|t| t.1 as u32).collect(),
            }
        }
    }

    /// The normal form of a polynomial given by arbitrary exponent vectors
    /// (length [`n_vars`](Self::n_vars)) and coefficients.
    pub fn from_raw(&self, terms: &[(Vec<u32>, u64)]) -> RPoly {
        let fp = Fp::new(self.p);
        let n_t = self.n_tower();
        let mut out: Vec<(Mono, u64)> = Vec::new();
        let mut cur: Vec<(u64, u64)> = Vec::new();
        let mut next: Vec<(u64, u64)> = Vec::new();
        for (e, c) in terms {
            assert_eq!(e.len(), self.n_vars(), "f4_fp_tower: exponent length");
            let c = c % self.p;
            if c == 0 {
                continue;
            }
            let mut f = [0u8; MAX_FREE];
            for k in 0..self.n_free {
                f[k] = u8::try_from(e[n_t + k]).expect("f4_fp_tower: free exponent above 255");
            }
            cur.clear();
            cur.push((0, c));
            for (j, &ej) in e.iter().take(n_t).enumerate() {
                for _ in 0..ej {
                    next.clear();
                    for &(m, cc) in &cur {
                        self.mul_var_into(fp, m, j, cc, &mut next);
                    }
                    merge_masks(fp, &mut next);
                    std::mem::swap(&mut cur, &mut next);
                }
            }
            for &(m, cc) in &cur {
                out.push((mono(m, f), cc));
            }
        }
        RPoly::from_terms(fp, out)
    }

    /// `g` at a point: one value per variable, tower variables first.
    pub fn eval(&self, g: &RPoly, x: &[u64]) -> u64 {
        let fp = Fp::new(self.p);
        let n_t = self.n_tower();
        let mut acc = 0u64;
        for (&m, &c) in g.monos.iter().zip(&g.coefs) {
            let mut t = u64::from(c);
            let mut bits = mask_of(m);
            while bits != 0 {
                let j = bits.trailing_zeros() as usize;
                bits &= bits - 1;
                t = fp.mul(t, x[j] % self.p);
            }
            for (k, &e) in free_of(m).iter().enumerate().take(self.n_free) {
                if e > 0 {
                    t = fp.mul(t, fp.pow(x[n_t + k], u64::from(e)));
                }
            }
            acc = fp.add(acc, t);
        }
        acc
    }
}

// ── Polynomials ──────────────────────────────────────────────────────

/// An element of `R` in normal form: monomials strictly descending,
/// coefficients non-zero and below `p`.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RPoly {
    pub monos: Vec<Mono>,
    pub coefs: Vec<u32>,
}

impl RPoly {
    /// Sort, merge repeats and drop zeros.
    fn from_terms(fp: Fp, mut terms: Vec<(Mono, u64)>) -> RPoly {
        terms.sort_unstable_by_key(|t| std::cmp::Reverse(t.0));
        let mut monos = Vec::with_capacity(terms.len());
        let mut coefs: Vec<u32> = Vec::with_capacity(terms.len());
        let mut i = 0;
        while i < terms.len() {
            let m = terms[i].0;
            let mut c = 0u64;
            while i < terms.len() && terms[i].0 == m {
                c = fp.add(c, terms[i].1 % fp.p);
                i += 1;
            }
            if c != 0 {
                monos.push(m);
                coefs.push(c as u32);
            }
        }
        RPoly { monos, coefs }
    }

    pub fn len(&self) -> usize {
        self.monos.len()
    }

    pub fn is_empty(&self) -> bool {
        self.monos.is_empty()
    }

    /// Leading monomial.
    pub fn lm(&self) -> Option<Mono> {
        self.monos.first().copied()
    }

    pub fn degree(&self) -> u32 {
        self.monos.iter().map(|&m| degree_of(m)).max().unwrap_or(0)
    }

    /// Whether this is a non-zero constant.
    pub fn is_unit(&self) -> bool {
        self.monos.len() == 1 && self.monos[0] == ONE
    }

    fn monic(mut self, fp: Fp) -> RPoly {
        if let Some(&c) = self.coefs.first() {
            if c != 1 {
                let inv = fp.inv(u64::from(c));
                for x in self.coefs.iter_mut() {
                    *x = fp.mul(u64::from(*x), inv) as u32;
                }
            }
        }
        self
    }
}

// ── Options and report ───────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct TowerF4Options {
    /// Pairs above this degree are not processed; the run then stops and
    /// reports how many were left.
    pub max_degree: u32,
    /// Cooperative stop: the run returns `timed_out` once past it.
    pub deadline: Option<Instant>,
    /// Stop once the leading monomials of the basis leave at most this many
    /// standard monomials (with pairs pending: the basis is then not
    /// certified). The count bounds the number of solutions.
    pub stop_staircase: Option<usize>,
    /// Stop, reporting `oversize`, before building a matrix with more than
    /// this many non-zero entries, or a reduced reducer block with more
    /// than this many dense entries.
    pub max_nnz: Option<u64>,
}

impl TowerF4Options {
    pub fn new(max_degree: u32) -> Self {
        TowerF4Options {
            max_degree,
            deadline: None,
            stop_staircase: None,
            max_nnz: None,
        }
    }
    pub fn with_budget(mut self, budget: Duration) -> Self {
        self.deadline = Some(Instant::now() + budget);
        self
    }
    pub fn stopping_below(mut self, standard_monomials: usize) -> Self {
        self.stop_staircase = Some(standard_monomials);
        self
    }
    pub fn with_max_nnz(mut self, nnz: u64) -> Self {
        self.max_nnz = Some(nnz);
        self
    }
}

/// One F4 step, for traces.
#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct StepTrace {
    pub degree: u32,
    pub critical_pairs: usize,
    pub tower_pairs: usize,
    pub s_rows: usize,
    pub reducer_rows: usize,
    /// S-rows moved into the reducers, one per lcm column.
    pub promoted_rows: usize,
    pub cols: usize,
    pub nnz: u64,
    /// S-rows the reducers alone do not reduce to zero, and the columns
    /// their residues live on (those without a divisor).
    pub residual_rows: usize,
    pub residual_cols: usize,
    /// Entries of the reduced reducer block, dense over those columns.
    pub dense_entries: u64,
    pub fresh: usize,
    pub fresh_min_degree: u32,
    pub muladds: u64,
    pub basis_active: usize,
    pub pairs_left: usize,
    pub ms: f64,
    /// Where `ms` went: symbolic preprocessing, the reduced reducer block
    /// `B'`, the S-rows and their echelon (rows formed on demand count
    /// where they are used), and the basis update.
    pub ms_rows: f64,
    pub ms_reduce: f64,
    pub ms_echelon: f64,
    pub ms_update: f64,
}

#[derive(Clone, Debug, Default)]
pub struct TowerF4Report {
    /// The active basis when the run ended (`[1]` when inconsistent). It
    /// is a Gröbner basis only if the run ended with no pairs left.
    pub basis: Vec<RPoly>,
    pub inconsistent: bool,
    /// Highest step degree processed.
    pub degree_reached: u32,
    /// Highest step degree at which the basis gained an element, or at
    /// which `1` appeared: the solving degree.
    pub solving_degree_max: u32,
    /// Degree of the last such step.
    pub last_productive_degree: u32,
    /// Widest matrix, and steps, up to and including the last productive
    /// step.
    pub max_cols_to_solution: usize,
    pub steps_to_solution: usize,
    pub steps: usize,
    pub max_rows: usize,
    pub max_cols: usize,
    pub max_nnz: u64,
    pub max_residual_rows: usize,
    pub max_dense_entries: u64,
    /// The unit: `F_p` multiply-adds in the eliminations.
    pub muladds: u64,
    pub critical_pairs_reduced: u64,
    pub tower_pairs_reduced: u64,
    pub pairs_product_skipped: u64,
    pub pairs_chain_skipped: u64,
    pub reducer_rows: u64,
    /// Pairs left above `max_degree` when the run stopped there.
    pub pairs_above_bound: usize,
    /// Set when [`TowerF4Options::stop_staircase`] ended the run.
    pub staircase_at_stop: Option<usize>,
    pub timed_out: bool,
    pub oversize: bool,
    pub ms: f64,
    pub trace: Vec<StepTrace>,
}

// ── Sparse rows and the two eliminations ─────────────────────────────

/// A sparse row: ascending column indices (column 0 is the largest
/// monomial) and non-zero coefficients.
#[derive(Clone, Debug, Default)]
struct Row {
    cols: Vec<u32>,
    vals: Vec<u32>,
}

const NONE: u32 = u32::MAX;

/// A dense accumulator with a bitset of the columns it may be non-zero
/// in, scanned in ascending order while rows are subtracted. `hi` is the
/// last bitset word anything was written to, so a scan stops there instead
/// of at the end of the matrix.
struct Acc {
    vals: Vec<u64>,
    bits: Vec<u64>,
    hi: usize,
}

impl Acc {
    fn new(n_cols: usize) -> Self {
        Acc {
            vals: vec![0; n_cols],
            bits: vec![0; n_cols.div_ceil(64).max(1)],
            hi: 0,
        }
    }

    #[inline]
    fn load(&mut self, row: &Row) {
        for (&c, &v) in row.cols.iter().zip(&row.vals) {
            self.vals[c as usize] = u64::from(v);
            self.bits[c as usize / 64] |= 1u64 << (c % 64);
        }
        self.hi = row.cols.last().map_or(0, |&c| c as usize / 64);
    }

    /// Subtract `f · row` (without its lead, which the caller zeroes). New
    /// columns are always to the right of the lead, so a scan standing on
    /// the lead's word sees those in its own word through `word`.
    #[inline]
    fn sub_tail(&mut self, fp: Fp, f: u64, row: &Row, cur_word: usize, word: &mut u64) -> u64 {
        let nf = fp.neg(f);
        for (&c, &v) in row.cols[1..].iter().zip(&row.vals[1..]) {
            let ci = c as usize;
            let x = self.vals[ci] + nf * u64::from(v);
            self.vals[ci] = fp.reduce(x);
            let (w, b) = (ci / 64, 1u64 << (ci % 64));
            if w == cur_word {
                *word |= b;
            } else {
                self.bits[w] |= b;
            }
        }
        if let Some(&c) = row.cols.last() {
            self.hi = self.hi.max(c as usize / 64);
        }
        row.cols.len() as u64 - 1
    }

    /// Move every non-zero entry from word `w` on into `out`, scaled by
    /// `scale`, leaving the accumulator clean.
    fn drain_from(&mut self, fp: Fp, w: usize, scale: u64, out: &mut Row) {
        let mut w = w;
        while w <= self.hi {
            let mut word = self.bits[w];
            self.bits[w] = 0;
            while word != 0 {
                let b = word.trailing_zeros() as usize;
                word &= word - 1;
                let c = w * 64 + b;
                let v = self.vals[c];
                self.vals[c] = 0;
                if v != 0 {
                    out.cols.push(c as u32);
                    out.vals.push(fp.mul(v, scale) as u32);
                }
            }
            w += 1;
        }
    }
}

/// Echelon form of `rows`: each row is reduced, at its lead, by the
/// pivots so far and kept, monic, if anything survives. Rows are
/// semi-reduced: once the lead is a new pivot column the rest is kept as it
/// stands. Returns the pivots, or `None` past the deadline.
fn echelon(
    fp: Fp,
    mut rows: Vec<Row>,
    n_cols: usize,
    muladds: &mut u64,
    deadline: Option<Instant>,
) -> Option<Vec<Row>> {
    rows.retain(|r| !r.cols.is_empty());
    rows.sort_by_key(|r| (r.cols[0], r.cols.len()));
    let mut pivot_of = vec![NONE; n_cols];
    let mut pivots: Vec<Row> = Vec::new();
    let mut acc = Acc::new(n_cols);
    for (k, row) in rows.into_iter().enumerate() {
        if k % 256 == 0 && deadline.is_some_and(|d| Instant::now() >= d) {
            return None;
        }
        // A lead nobody holds: the row is a pivot as it stands.
        if pivot_of[row.cols[0] as usize] == NONE {
            let inv = fp.inv(u64::from(row.vals[0]));
            let vals = row
                .vals
                .iter()
                .map(|&v| fp.mul(u64::from(v), inv) as u32)
                .collect();
            pivot_of[row.cols[0] as usize] = pivots.len() as u32;
            pivots.push(Row {
                cols: row.cols,
                vals,
            });
            continue;
        }
        acc.load(&row);
        let mut w = row.cols[0] as usize / 64;
        let mut found: Option<Row> = None;
        'scan: while w <= acc.hi {
            let mut word = acc.bits[w];
            acc.bits[w] = 0;
            while word != 0 {
                let b = word.trailing_zeros() as usize;
                word &= word - 1;
                let c = w * 64 + b;
                let v = acc.vals[c];
                acc.vals[c] = 0;
                if v == 0 {
                    continue;
                }
                let p = pivot_of[c];
                if p != NONE {
                    *muladds += acc.sub_tail(fp, v, &pivots[p as usize], w, &mut word);
                    continue;
                }
                // A new lead: keep the rest of the row as it stands.
                let inv = fp.inv(v);
                let mut out = Row {
                    cols: vec![c as u32],
                    vals: vec![1],
                };
                acc.bits[w] = word;
                acc.drain_from(fp, w, inv, &mut out);
                found = Some(out);
                break 'scan;
            }
            w += 1;
        }
        if let Some(out) = found {
            pivot_of[out.cols[0] as usize] = pivots.len() as u32;
            pivots.push(out);
        }
    }
    Some(pivots)
}

/// `acc += a · b` with lazy reduction: every entry stays below `2⁶³`
/// because `a · b < 2⁶²` and `m`, a multiple of `p` at least `2⁶³ − p`, is
/// subtracted whenever an entry reaches `2⁶³`.
#[inline(always)]
fn lazy_axpy(acc: &mut [u64], a: u32, b: &[u32], m: u64) {
    let n = acc.len().min(b.len());
    for (x, &y) in acc[..n].iter_mut().zip(&b[..n]) {
        let s = *x + u64::from(a) * u64::from(y);
        *x = s - ((s >> 63).wrapping_neg() & m);
    }
}

/// [`lazy_axpy`] compiled for AVX2.
///
/// # Safety
/// The CPU must support AVX2.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn lazy_axpy_avx2(acc: &mut [u64], a: u32, b: &[u32], m: u64) {
    lazy_axpy(acc, a, b, m)
}

/// [`lazy_axpy`] compiled for AVX-512.
///
/// # Safety
/// The CPU must support AVX-512F.
#[cfg(all(target_arch = "x86_64", suite_avx512))]
#[clippy::msrv = "1.89"]
#[target_feature(enable = "avx512f")]
unsafe fn lazy_axpy_avx512(acc: &mut [u64], a: u32, b: &[u32], m: u64) {
    lazy_axpy(acc, a, b, m)
}

/// The widest vector unit the lazy kernel can use on this CPU.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Lanes {
    Scalar,
    Avx2,
    /// Only on a toolchain with stable AVX-512 target features (1.89+).
    #[cfg(suite_avx512)]
    Avx512,
}

impl Lanes {
    fn detect() -> Self {
        #[cfg(target_arch = "x86_64")]
        {
            #[cfg(suite_avx512)]
            if std::is_x86_feature_detected!("avx512f") {
                return Lanes::Avx512;
            }
            if std::is_x86_feature_detected!("avx2") {
                return Lanes::Avx2;
            }
        }
        Lanes::Scalar
    }
}

/// `F_p` accumulation for the dense kernels. Below `2³¹` a product fits in
/// 62 bits, so an accumulator is kept below `2⁶³` by subtracting a multiple
/// of `p` only when it crosses `2⁶³`, and read through [`Fp::reduce`]
/// (lazy reduction); that loop vectorizes. Above, every step is reduced.
#[derive(Clone, Copy)]
struct Kernel {
    fp: Fp,
    /// The largest multiple of `p` at most `2⁶³`, when `p < 2³¹`.
    lazy: Option<u64>,
    lanes: Lanes,
}

impl Kernel {
    fn new(fp: Fp) -> Self {
        Self::with_lanes(fp, Lanes::detect())
    }

    fn with_lanes(fp: Fp, lanes: Lanes) -> Self {
        Kernel {
            fp,
            lazy: (fp.p < 1 << 31).then(|| ((1u64 << 63) / fp.p) * fp.p),
            lanes,
        }
    }

    /// `acc += a · b` entrywise, for `a < p`. Every entry of `acc` must be
    /// below `2⁶³` (lazy) or below `p` (otherwise), and stays so.
    #[inline]
    fn axpy(self, acc: &mut [u64], a: u32, b: &[u32]) {
        match (self.lazy, self.lanes) {
            #[cfg(all(target_arch = "x86_64", suite_avx512))]
            // SAFETY: `Lanes::detect` found AVX-512F on this CPU.
            (Some(m), Lanes::Avx512) => unsafe { lazy_axpy_avx512(acc, a, b, m) },
            #[cfg(target_arch = "x86_64")]
            // SAFETY: `Lanes::detect` found AVX2 on this CPU.
            (Some(m), Lanes::Avx2) => unsafe { lazy_axpy_avx2(acc, a, b, m) },
            (Some(m), _) => lazy_axpy(acc, a, b, m),
            (None, _) => {
                let fp = self.fp;
                for (x, &y) in acc.iter_mut().zip(b) {
                    *x = fp.reduce(*x + u64::from(a) * u64::from(y));
                }
            }
        }
    }

    /// `acc −= v · b`, the step every elimination takes.
    #[inline]
    fn sub(self, acc: &mut [u64], v: u64, b: &[u32]) -> u64 {
        self.axpy(acc, self.fp.neg(self.fp.reduce(v)) as u32, b);
        b.len() as u64
    }
}

/// Why an elimination stopped early.
enum Stop {
    Deadline,
    Oversize,
}

/// Counters of one elimination, for the trace.
#[derive(Default)]
struct ElimStats {
    /// S-rows that the reducers alone do not reduce to zero.
    residual_rows: usize,
    /// Columns no reducer leads: those without a divisor.
    q_cols: usize,
    /// Entries of the reduced reducer block `B'`.
    dense_entries: u64,
    muladds: u64,
    /// Time spent on `B'`, and on the S-rows and their echelon.
    ms_reducers: f64,
    ms_residues: f64,
}

/// Forms row `k` of a set of rows on demand.
type FormRow<'a> = &'a (dyn Fn(usize) -> Row + Sync);

/// One step's matrix, eliminated in the manner of Faugère–Lachartre.
///
/// The pivot rows, formed by `piv_row`, have distinct, monic leads
/// `piv_leads` (`pivot_of[col]` indexes them): the `A|B` rows. The `n_s`
/// S-rows, formed by `s_row`, are the `C|D` rows. Rows are formed a block
/// at a time, when they are reduced. The columns no pivot row leads, `Q`,
/// are the ones without a divisor, and are handled densely:
/// 1. every pivot row is reduced to its lead plus a dense row over the `Q`
///    columns to its right, the rightmost lead first (`B' = A⁻¹B`), in
///    blocks whose rows are independent but for the few that point inside
///    the block;
/// 2. every S-row is reduced by those rows in one pass, leaving a dense row
///    over `Q` (`D − C·B'`), with no fill-in on the pivot columns;
/// 3. the residues are echelonized in chunks: each chunk is reduced in
///    parallel by the pivots found so far, then finished one row at a time.
///
/// Returns the pivots of the echelon as sparse rows over the step's
/// columns, monic, semi-reduced, leads ascending. `B'` larger than
/// `max_dense` entries stops it as oversize.
fn eliminate(
    fp: Fp,
    n_cols: usize,
    piv_leads: &[u32],
    piv_row: FormRow,
    pivot_of: &[u32],
    n_s: usize,
    s_row: FormRow,
    deadline: Option<Instant>,
    max_dense: Option<u64>,
    st: &mut ElimStats,
) -> Result<Vec<Row>, Stop> {
    let kern = Kernel::new(fp);
    // Q, ascending; `q_start[c]` is the first Q index at or after `c`.
    let mut q_of = vec![NONE; n_cols];
    let mut q_start = vec![0u32; n_cols];
    let mut q_col: Vec<u32> = Vec::new();
    for c in 0..n_cols {
        q_start[c] = q_col.len() as u32;
        if pivot_of[c] == NONE {
            q_of[c] = q_col.len() as u32;
            q_col.push(c as u32);
        }
    }
    let nq = q_col.len();
    st.q_cols = nq;
    let tail_len = |c: u32| nq - q_start[c as usize] as usize;
    st.dense_entries = piv_leads.iter().map(|&c| tail_len(c) as u64).sum();
    if max_dense.is_some_and(|cap| st.dense_entries > cap) {
        return Err(Stop::Oversize);
    }
    let expired = AtomicBool::new(false);
    let past = || {
        if expired.load(AtomicOrdering::Relaxed) {
            return true;
        }
        if deadline.is_some_and(|d| Instant::now() >= d) {
            expired.store(true, AtomicOrdering::Relaxed);
            return true;
        }
        false
    };

    // 1. B' = A⁻¹B, the rightmost lead first. A pivot row's tail points
    //    only at pivot rows further right, so at rows already reduced, or
    //    at rows earlier in its own block, which wait for the sequential
    //    pass over the block.
    let started = Instant::now();
    let n_piv = piv_leads.len();
    let mut order: Vec<u32> = (0..n_piv as u32).collect();
    order.sort_unstable_by_key(|&k| std::cmp::Reverse(piv_leads[k as usize]));
    let mut pos = vec![0u32; n_piv];
    for (i, &k) in order.iter().enumerate() {
        pos[k as usize] = i as u32;
    }
    let mut bred: Vec<Vec<u32>> = vec![Vec::new(); n_piv];
    const BLOCK: usize = 64;
    for (b, block) in order.chunks(BLOCK).enumerate() {
        let first = (b * BLOCK) as u32;
        type Partial = (Vec<u64>, Vec<(u32, u32)>, u64);
        let partial: Vec<Partial> = block
            .par_iter()
            .map(|&k| {
                let s0 = q_start[piv_leads[k as usize] as usize] as usize;
                let mut acc = vec![0u64; nq - s0];
                let mut later = Vec::new();
                let mut work = 0u64;
                if past() {
                    return (acc, later, work);
                }
                let row = piv_row(k as usize);
                debug_assert_eq!(row.cols[0], piv_leads[k as usize]);
                debug_assert_eq!(row.vals[0], 1, "a pivot row must be monic");
                // The row's own Q entries first: the subtractions below
                // write to Q columns anywhere to their right.
                for (&c, &v) in row.cols[1..].iter().zip(&row.vals[1..]) {
                    if q_of[c as usize] != NONE {
                        acc[q_of[c as usize] as usize - s0] = u64::from(v);
                    }
                }
                for (&c, &v) in row.cols[1..].iter().zip(&row.vals[1..]) {
                    let cu = c as usize;
                    if q_of[cu] != NONE {
                        continue;
                    }
                    let j = pivot_of[cu];
                    if pos[j as usize] < first {
                        let off = q_start[cu] as usize - s0;
                        work += kern.sub(&mut acc[off..], u64::from(v), &bred[j as usize]);
                    } else {
                        later.push((j, v));
                    }
                }
                (acc, later, work)
            })
            .collect();
        if expired.load(AtomicOrdering::Relaxed) {
            return Err(Stop::Deadline);
        }
        for (&k, (mut acc, later, work)) in block.iter().zip(partial) {
            st.muladds += work;
            let s0 = q_start[piv_leads[k as usize] as usize] as usize;
            for (j, v) in later {
                let off = q_start[piv_leads[j as usize] as usize] as usize - s0;
                st.muladds += kern.sub(&mut acc[off..], u64::from(v), &bred[j as usize]);
            }
            bred[k as usize] = acc.iter().map(|&x| fp.reduce(x) as u32).collect();
        }
    }
    let residues_started = Instant::now();
    st.ms_reducers = (residues_started - started).as_secs_f64() * 1e3;

    // 2 and 3. The S-rows, in chunks. `ech[l]` is the pivot with lead `l`
    // (a Q index), stored from `l` on, with 1 at `l`; empty when there is
    // none. `leads` is ascending.
    let mut ech: Vec<Vec<u32>> = vec![Vec::new(); nq];
    let mut leads: Vec<u32> = Vec::new();
    // A task reduces a block of rows together, one reducer at a time, so
    // that each dense row it reads is read once per block rather than once
    // per row. The block's accumulators are sized to stay in cache.
    let per_task = ((1usize << 18) / (8 * nq.max(1))).clamp(4, 64);
    let chunk = per_task * 2 * rayon::current_num_threads().max(1);
    type Reduced = (Vec<(Option<Vec<u64>>, bool)>, u64);
    let all: Vec<usize> = (0..n_s).collect();
    for rows in all.chunks(chunk) {
        let reduced: Vec<Reduced> = rows
            .par_chunks(per_task)
            .map(|ks| {
                if past() {
                    return (Vec::new(), 0);
                }
                let blk: Vec<Row> = ks.iter().map(|&k| s_row(k)).collect();
                let mut acc = vec![0u64; blk.len() * nq];
                let mut work = 0u64;
                // (column, row, coefficient) of the pivot-column entries,
                // grouped by column: every row that meets a reducer takes
                // it while it is in cache.
                let mut ents: Vec<(u32, u32, u32)> = Vec::new();
                for (r, row) in blk.iter().enumerate() {
                    for (&c, &v) in row.cols.iter().zip(&row.vals) {
                        let q = q_of[c as usize];
                        if q != NONE {
                            acc[r * nq + q as usize] = u64::from(v);
                        } else {
                            ents.push((c, r as u32, v));
                        }
                    }
                }
                ents.sort_unstable();
                for &(c, r, v) in &ents {
                    let (off, end) = (
                        r as usize * nq + q_start[c as usize] as usize,
                        (r as usize + 1) * nq,
                    );
                    work += kern.sub(
                        &mut acc[off..end],
                        u64::from(v),
                        &bred[pivot_of[c as usize] as usize],
                    );
                }
                let residual: Vec<bool> = (0..blk.len())
                    .map(|r| acc[r * nq..(r + 1) * nq].iter().any(|&x| fp.reduce(x) != 0))
                    .collect();
                let mut live: Vec<usize> = (0..blk.len()).filter(|&r| residual[r]).collect();
                for &l in &leads {
                    let l = l as usize;
                    for &r in &live {
                        let a = fp.reduce(acc[r * nq + l]);
                        if a != 0 {
                            work += kern.sub(&mut acc[r * nq + l..(r + 1) * nq], a, &ech[l]);
                        }
                    }
                }
                let mut out: Vec<(Option<Vec<u64>>, bool)> =
                    residual.iter().map(|&x| (None, x)).collect();
                live.retain(|&r| {
                    let row = &mut acc[r * nq..(r + 1) * nq];
                    for x in row.iter_mut() {
                        *x = fp.reduce(*x);
                    }
                    row.iter().any(|&x| x != 0)
                });
                for r in live {
                    out[r].0 = Some(acc[r * nq..(r + 1) * nq].to_vec());
                }
                (out, work)
            })
            .collect();
        if expired.load(AtomicOrdering::Relaxed) {
            return Err(Stop::Deadline);
        }
        // What this chunk adds, reduced one row at a time by the pivots it
        // added before it (ascending); every residue already vanishes on
        // the older leads.
        let mut new_leads: Vec<u32> = Vec::new();
        let mut residues: Vec<(Option<Vec<u64>>, bool)> = Vec::with_capacity(rows.len());
        for (out, work) in reduced {
            st.muladds += work;
            residues.extend(out);
        }
        for (acc, residual) in residues {
            st.residual_rows += usize::from(residual);
            let Some(mut acc) = acc else { continue };
            for &l in &new_leads {
                let l = l as usize;
                let a = fp.reduce(acc[l]);
                if a != 0 {
                    st.muladds += kern.sub(&mut acc[l..], a, &ech[l]);
                }
            }
            let Some(l) = acc.iter().position(|&x| fp.reduce(x) != 0) else {
                continue;
            };
            let inv = fp.inv(fp.reduce(acc[l]));
            ech[l] = acc[l..]
                .iter()
                .map(|&x| fp.mul(fp.reduce(x), inv) as u32)
                .collect();
            let at = new_leads.partition_point(|&m| m < l as u32);
            new_leads.insert(at, l as u32);
        }
        leads.extend(new_leads);
        leads.sort_unstable();
    }
    st.ms_residues = residues_started.elapsed().as_secs_f64() * 1e3;

    Ok(leads
        .iter()
        .map(|&l| {
            let e = &ech[l as usize];
            let mut row = Row::default();
            for (i, &v) in e.iter().enumerate() {
                if v != 0 {
                    row.cols.push(q_col[l as usize + i]);
                    row.vals.push(v);
                }
            }
            row
        })
        .collect())
}

// ── Pairs and the basis ──────────────────────────────────────────────

#[derive(Clone, Copy, Debug)]
enum PairKind {
    /// The S-polynomial of basis elements `i < j`.
    Critical(u32, u32),
    /// `y_v · g_i` for a tower variable `v` of `LM(g_i)`.
    Tower(u32, u8),
}

#[derive(Clone, Copy, Debug)]
struct Pair {
    kind: PairKind,
    /// The lcm of the leading monomials (critical pairs).
    lcm: Mono,
    deg: u32,
}

struct State {
    polys: Vec<RPoly>,
    lm: Vec<Mono>,
    active: Vec<bool>,
    /// Active leading monomial → element.
    lm_index: MonoMap<u32>,
    pairs: Vec<Pair>,
}

/// Every monomial `L'` with `lo | L' | L`, `L'` ≠ `L`, is passed to `f`
/// until it returns `true`; returns whether one did.
fn any_between(lo: Mono, l: Mono, mut f: impl FnMut(Mono) -> bool) -> bool {
    let (lo_mask, l_mask) = (mask_of(lo), mask_of(l));
    let extra = l_mask & !lo_mask;
    let (lo_f, l_f) = (free_of(lo), free_of(l));
    // enumerate submasks s of `extra` and free vectors in [lo_f, l_f]
    let mut s = extra;
    loop {
        let mut fv = lo_f;
        loop {
            let cand = mono(lo_mask | s, fv);
            if cand != l && f(cand) {
                return true;
            }
            // next free vector (odometer)
            let mut k = 0;
            loop {
                if k == MAX_FREE {
                    break;
                }
                if fv[k] < l_f[k] {
                    fv[k] += 1;
                    break;
                }
                fv[k] = lo_f[k];
                k += 1;
            }
            if k == MAX_FREE {
                break;
            }
        }
        if s == 0 {
            break;
        }
        s = (s - 1) & extra;
    }
    false
}

impl State {
    /// Becker–Weispfenning `UPDATE` for the critical pairs of a new
    /// element, plus its tower pairs.
    fn insert(&mut self, h_poly: RPoly, rep: &mut TowerF4Report) {
        let h = self.polys.len();
        let lh = h_poly.lm().expect("a new element is non-zero");
        self.polys.push(h_poly);
        self.lm.push(lh);
        self.active.push(false);

        let dh = degree_of(lh);
        let mut bits = mask_of(lh);
        while bits != 0 {
            let v = bits.trailing_zeros();
            bits &= bits - 1;
            self.pairs.push(Pair {
                kind: PairKind::Tower(h as u32, v as u8),
                lcm: lh,
                deg: dh + 1,
            });
        }

        // New pairs (g, h). Keep one per lcm that no other new lcm divides
        // strictly (criterion M), none for an lcm a coprime pair also has
        // (criterion F with the product criterion), and drop the coprime
        // ones: what `UPDATE`'s first two loops leave.
        // lcm → (the first element with it, whether any pair with it is
        // coprime). A group with a coprime pair is dropped whole, so its
        // representative never matters.
        let mut groups: MonoMap<(u32, bool)> = MonoMap::default();
        for g in 0..h {
            if !self.active[g] {
                continue;
            }
            let l = lcm(lh, self.lm[g]);
            let e = groups.entry(l).or_insert((g as u32, false));
            if coprime(lh, self.lm[g]) {
                e.1 = true;
            }
        }
        let mut kept: Vec<(u32, Mono)> = Vec::new();
        for (&l, &(g, has_coprime)) in &groups {
            if any_between(lh, l, |c| groups.contains_key(&c)) {
                rep.pairs_chain_skipped += 1;
                continue;
            }
            if has_coprime {
                rep.pairs_product_skipped += 1;
                continue;
            }
            kept.push((g, l));
        }
        // Old critical pairs whose lcm `LM(h)` divides, strictly on both
        // sides (criterion B).
        let lm = &self.lm;
        let mut dropped = 0u64;
        self.pairs.retain(|p| match p.kind {
            PairKind::Tower(..) => true,
            PairKind::Critical(i, j) => {
                let keep = !divides(lh, p.lcm)
                    || lcm(lm[i as usize], lh) == p.lcm
                    || lcm(lm[j as usize], lh) == p.lcm;
                if !keep {
                    dropped += 1;
                }
                keep
            }
        });
        rep.pairs_chain_skipped += dropped;
        kept.sort_unstable_by_key(|&(g, _)| g);
        for (g, l) in kept {
            self.pairs.push(Pair {
                kind: PairKind::Critical(g, h as u32),
                lcm: l,
                deg: degree_of(l),
            });
        }
        for g in 0..h {
            if self.active[g] && divides(lh, self.lm[g]) {
                self.active[g] = false;
                if self.lm_index.get(&self.lm[g]) == Some(&(g as u32)) {
                    self.lm_index.remove(&self.lm[g]);
                }
            }
        }
        self.active[h] = true;
        self.lm_index.insert(lh, h as u32);
    }

    /// An active element whose leading monomial divides `m`, the shortest.
    fn reducer_for(&self, m: Mono) -> Option<u32> {
        let mask = mask_of(m);
        let f = free_of(m);
        let mut best: Option<u32> = None;
        let mut s = mask;
        loop {
            let mut fv = [0u8; MAX_FREE];
            loop {
                if let Some(&g) = self.lm_index.get(&mono(s, fv)) {
                    if best
                        .is_none_or(|b| self.polys[g as usize].len() < self.polys[b as usize].len())
                    {
                        best = Some(g);
                    }
                }
                let mut k = 0;
                loop {
                    if k == MAX_FREE {
                        break;
                    }
                    if fv[k] < f[k] {
                        fv[k] += 1;
                        break;
                    }
                    fv[k] = 0;
                    k += 1;
                }
                if k == MAX_FREE {
                    break;
                }
            }
            if s == 0 {
                break;
            }
            s = (s - 1) & mask;
        }
        best
    }

    fn active_lms(&self) -> Vec<Mono> {
        (0..self.polys.len())
            .filter(|&g| self.active[g])
            .map(|g| self.lm[g])
            .collect()
    }
}

/// The number of standard monomials of `R / (lms)`, or `None` if it
/// exceeds `bound` or is infinite (a free variable without a pure power
/// among the leading monomials).
fn staircase_at_most(lms: &[Mono], n_tower: usize, n_free: usize, bound: usize) -> Option<usize> {
    let mut cap = [0u8; MAX_FREE];
    for (k, c) in cap.iter_mut().enumerate().take(n_free) {
        *c = lms
            .iter()
            .filter(|&&m| {
                mask_of(m) == 0
                    && free_of(m)
                        .iter()
                        .enumerate()
                        .all(|(i, &e)| (i == k) == (e > 0))
            })
            .map(|&m| free_of(m)[k])
            .min()?;
    }
    fn walk(
        k: usize,
        mask: u64,
        free: &mut [u8; MAX_FREE],
        ctx: (&[Mono], usize, usize, &[u8; MAX_FREE]),
        count: &mut usize,
        bound: usize,
    ) -> bool {
        let (lms, n_tower, n_free, cap) = ctx;
        let cur = mono(mask, *free);
        if lms.iter().any(|&l| divides(l, cur)) {
            return true;
        }
        if k == n_tower + n_free {
            *count += 1;
            return *count <= bound;
        }
        if k < n_tower {
            walk(k + 1, mask, free, ctx, count, bound)
                && walk(k + 1, mask | 1 << k, free, ctx, count, bound)
        } else {
            let f = k - n_tower;
            for e in 0..cap[f] {
                free[f] = e;
                if !walk(k + 1, mask, free, ctx, count, bound) {
                    free[f] = 0;
                    return false;
                }
            }
            free[f] = 0;
            true
        }
    }
    let mut count = 0usize;
    let mut free = [0u8; MAX_FREE];
    walk(
        0,
        0,
        &mut free,
        (lms, n_tower, n_free, &cap),
        &mut count,
        bound,
    )
    .then_some(count)
}

/// A row of a step's matrix, kept as the product that forms it.
#[derive(Clone, Copy, Debug)]
struct RowDesc {
    mult: Mono,
    g: u32,
    /// The product's leading monomial and number of terms.
    lead: Mono,
    len: u32,
}

/// Forms the products `mult · polys[g]` of `todo` a batch at a time and
/// records each non-empty one in `out`. Every monomial of a product, past
/// its first `skip`, that `examined` has not seen joins `frontier`. The
/// products themselves are dropped. Returns the number of terms formed.
fn scan_products(
    ring: &TowerRing,
    fp: Fp,
    polys: &[RPoly],
    todo: &[(Mono, u32)],
    skip: usize,
    out: &mut Vec<RowDesc>,
    examined: &mut MonoMap<()>,
    frontier: &mut Vec<Mono>,
) -> u64 {
    let mut terms = 0u64;
    for batch in todo.chunks(1024) {
        let prods: Vec<RPoly> = batch
            .par_iter()
            .map(|&(mult, g)| ring.mul_mono_fp(fp, &polys[g as usize], mult))
            .collect();
        for (&(mult, g), p) in batch.iter().zip(&prods) {
            let Some(lead) = p.lm() else { continue };
            terms += p.len() as u64;
            out.push(RowDesc {
                mult,
                g,
                lead,
                len: p.len() as u32,
            });
            for &m in p.monos.iter().skip(skip) {
                if examined.insert(m, ()).is_none() {
                    frontier.push(m);
                }
            }
        }
    }
    terms
}

// ── The algorithm ────────────────────────────────────────────────────

/// **F4 on `R`** for the ideal generated by `input` (tower normal forms),
/// with the normal selection strategy. See the module notes.
pub fn f4_tower(input: &[RPoly], ring: &TowerRing, opts: &TowerF4Options) -> TowerF4Report {
    ring.check();
    let started = Instant::now();
    let fp = Fp::new(ring.p);
    let mut rep = TowerF4Report::default();
    let finish = |mut rep: TowerF4Report| {
        rep.ms = started.elapsed().as_secs_f64() * 1e3;
        rep
    };
    let unit = || {
        vec![RPoly {
            monos: vec![ONE],
            coefs: vec![1],
        }]
    };

    let inputs: Vec<RPoly> = input.iter().filter(|p| !p.is_empty()).cloned().collect();
    if inputs.iter().any(|p| p.is_unit()) {
        rep.inconsistent = true;
        rep.basis = unit();
        return finish(rep);
    }

    // The initial echelon: distinct leading monomials to start from.
    let (start, _) = {
        let mut all: Vec<Mono> = inputs
            .iter()
            .flat_map(|p| p.monos.iter().copied())
            .collect();
        all.sort_unstable_by(|a, b| b.cmp(a));
        all.dedup();
        let col_of: MonoMap<u32> = all
            .iter()
            .enumerate()
            .map(|(i, &m)| (m, i as u32))
            .collect();
        let rows: Vec<Row> = inputs
            .iter()
            .map(|p| Row {
                cols: p.monos.iter().map(|m| col_of[m]).collect(),
                vals: p.coefs.clone(),
            })
            .collect();
        match echelon(fp, rows, all.len(), &mut rep.muladds, opts.deadline) {
            Some(piv) => (
                piv.into_iter()
                    .map(|r| RPoly {
                        monos: r.cols.iter().map(|&c| all[c as usize]).collect(),
                        coefs: r.vals,
                    })
                    .collect::<Vec<_>>(),
                (),
            ),
            None => {
                rep.timed_out = true;
                rep.basis = inputs;
                return finish(rep);
            }
        }
    };
    if start.iter().any(|p| p.is_unit()) {
        rep.inconsistent = true;
        rep.basis = unit();
        return finish(rep);
    }
    let mut start = start;
    start.sort_by_key(|p| std::cmp::Reverse(p.lm().unwrap()));

    let mut s = State {
        polys: Vec::new(),
        lm: Vec::new(),
        active: Vec::new(),
        lm_index: MonoMap::default(),
        pairs: Vec::new(),
    };
    for p in start {
        s.insert(p, &mut rep);
    }
    // (solving_degree_max, max_cols_to_solution, steps_to_solution)
    let mut learned = (0u32, 0usize, 0usize);
    let mut max_cols_so_far = 0usize;

    let active_basis = |s: &State| -> Vec<RPoly> {
        (0..s.polys.len())
            .filter(|&g| s.active[g])
            .map(|g| s.polys[g].clone())
            .collect()
    };
    let record = |rep: &mut TowerF4Report, learned: (u32, usize, usize)| {
        rep.solving_degree_max = learned.0;
        rep.max_cols_to_solution = learned.1;
        rep.steps_to_solution = learned.2;
    };

    while !s.pairs.is_empty() {
        if opts.deadline.is_some_and(|d| Instant::now() >= d) {
            rep.timed_out = true;
            break;
        }
        let d = s.pairs.iter().map(|p| p.deg).min().unwrap();
        if d > opts.max_degree {
            rep.pairs_above_bound = s.pairs.len();
            break;
        }
        let step_started = Instant::now();
        let (selected, rest): (Vec<Pair>, Vec<Pair>) = s.pairs.drain(..).partition(|p| p.deg == d);
        s.pairs = rest;
        rep.steps += 1;
        rep.degree_reached = rep.degree_reached.max(d);
        let mut tr = StepTrace {
            degree: d,
            ..Default::default()
        };

        // The rows the step reduces: both halves of every critical pair and
        // every tower product, each (multiplier, element) once.
        let mut seen: HashMap<(Mono, u32), (), BuildHasherDefault<MonoHasher>> = HashMap::default();
        let mut jobs: Vec<(Mono, u32)> = Vec::new();
        let mut lcm_cols: MonoMap<()> = MonoMap::default();
        for p in &selected {
            match p.kind {
                PairKind::Critical(i, j) => {
                    tr.critical_pairs += 1;
                    lcm_cols.insert(p.lcm, ());
                    for g in [i, j] {
                        let mult = quotient(p.lcm, s.lm[g as usize]);
                        if seen.insert((mult, g), ()).is_none() {
                            jobs.push((mult, g));
                        }
                    }
                }
                PairKind::Tower(g, v) => {
                    tr.tower_pairs += 1;
                    // A tower multiplier lies inside LM(g), a half's outside it.
                    let mult = mono(1u64 << v, [0; MAX_FREE]);
                    if seen.insert((mult, g), ()).is_none() {
                        jobs.push((mult, g));
                    }
                }
            }
        }
        rep.critical_pairs_reduced += tr.critical_pairs as u64;
        rep.tower_pairs_reduced += tr.tower_pairs as u64;

        // Symbolic preprocessing, one frontier at a time. A row is kept as
        // the product that makes it and formed again when it is eliminated:
        // the products of a large step do not fit in memory together, their
        // monomials do.
        let mut examined: MonoMap<()> = lcm_cols.clone();
        let mut no_divisor: MonoMap<()> = MonoMap::default();
        let mut frontier: Vec<Mono> = Vec::new();
        let mut s_desc: Vec<RowDesc> = Vec::with_capacity(jobs.len());
        let mut nnz = scan_products(
            ring,
            fp,
            &s.polys,
            &jobs,
            0,
            &mut s_desc,
            &mut examined,
            &mut frontier,
        );
        let mut r_desc: Vec<RowDesc> = Vec::new();
        let mut aborted = false;
        while !frontier.is_empty() {
            if opts.deadline.is_some_and(|dl| Instant::now() >= dl) {
                aborted = true;
                break;
            }
            let found: Vec<(Mono, Option<u32>)> = frontier
                .par_iter()
                .map(|&m| (m, s.reducer_for(m)))
                .collect();
            frontier.clear();
            let mut todo: Vec<(Mono, u32)> = Vec::new();
            for &(m, g) in &found {
                match g {
                    Some(g) => todo.push((quotient(m, s.lm[g as usize]), g)),
                    None => {
                        no_divisor.insert(m, ());
                    }
                }
            }
            let before = r_desc.len();
            nnz += scan_products(
                ring,
                fp,
                &s.polys,
                &todo,
                1,
                &mut r_desc,
                &mut examined,
                &mut frontier,
            );
            debug_assert!(
                r_desc[before..]
                    .iter()
                    .zip(found.iter().filter(|f| f.1.is_some()))
                    .all(|(d, f)| d.lead == f.0),
                "a reducer must lead with its monomial"
            );
            if opts.max_nnz.is_some_and(|cap| nnz > cap) {
                rep.oversize = true;
                aborted = true;
                break;
            }
        }
        if aborted {
            if !rep.oversize {
                rep.timed_out = true;
            }
            s.pairs.extend(selected);
            break;
        }
        rep.reducer_rows += r_desc.len() as u64;

        // Columns, descending.
        let mut cols: Vec<Mono> = examined.keys().copied().collect();
        drop(examined);
        cols.par_sort_unstable_by(|a, b| b.cmp(a));
        let col_of: MonoMap<u32> = cols
            .iter()
            .enumerate()
            .map(|(i, &m)| (m, i as u32))
            .collect();
        let n_cols = cols.len();
        let mut pivot_of = vec![NONE; n_cols];
        let mut piv: Vec<RowDesc> = r_desc;
        for (k, d) in piv.iter().enumerate() {
            pivot_of[col_of[&d.lead] as usize] = k as u32;
        }
        let n_reducers = piv.len();
        // The shortest S-row at each lcm column joins the reducers, made
        // monic, and the other rows there are reduced by it: the A|B and
        // C|D split. The residues then live on the columns without a
        // divisor alone, where every pivot is a new leading monomial. (The
        // sort is stable: ties keep the order of the jobs.)
        s_desc.sort_by_key(|d| (std::cmp::Reverse(d.lead), d.len));
        let mut s_list: Vec<RowDesc> = Vec::with_capacity(s_desc.len());
        for d in s_desc {
            let c = col_of[&d.lead] as usize;
            if pivot_of[c] == NONE && lcm_cols.contains_key(&d.lead) {
                pivot_of[c] = piv.len() as u32;
                piv.push(d);
            } else {
                s_list.push(d);
            }
        }
        tr.promoted_rows = piv.len() - n_reducers;
        tr.s_rows = s_list.len();
        tr.reducer_rows = n_reducers;
        tr.cols = n_cols;
        tr.nnz = nnz;
        rep.max_rows = rep.max_rows.max(s_list.len() + piv.len());
        rep.max_cols = rep.max_cols.max(n_cols);
        rep.max_nnz = rep.max_nnz.max(nnz);
        max_cols_so_far = max_cols_so_far.max(n_cols);

        tr.ms_rows = step_started.elapsed().as_secs_f64() * 1e3;

        // The elimination; the columns without a pivot row are exactly the
        // ones without a divisor, so every pivot it returns is new.
        debug_assert!(
            (0..n_cols).all(|c| (pivot_of[c] == NONE) == no_divisor.contains_key(&cols[c])),
            "the columns without a reducer must be those without a divisor"
        );
        let polys = &s.polys;
        let form = |d: &RowDesc| -> Row {
            let p = ring.mul_mono_fp(fp, &polys[d.g as usize], d.mult);
            debug_assert_eq!(
                p.len(),
                d.len as usize,
                "a row must be formed as it was scanned"
            );
            Row {
                cols: p.monos.iter().map(|m| col_of[m]).collect(),
                vals: p.coefs,
            }
        };
        let piv_row = |k: usize| -> Row {
            let mut r = form(&piv[k]);
            if r.vals[0] != 1 {
                // Only a promoted tower row can lead with another
                // coefficient: products of monic elements stay monic.
                debug_assert!(k >= n_reducers);
                let inv = fp.inv(u64::from(r.vals[0]));
                for v in &mut r.vals {
                    *v = fp.mul(u64::from(*v), inv) as u32;
                }
            }
            r
        };
        let s_row = |k: usize| form(&s_list[k]);
        let piv_leads: Vec<u32> = piv.iter().map(|d| col_of[&d.lead]).collect();
        let mut st = ElimStats::default();
        let result = eliminate(
            fp,
            n_cols,
            &piv_leads,
            &piv_row,
            &pivot_of,
            s_list.len(),
            &s_row,
            opts.deadline,
            opts.max_nnz,
            &mut st,
        );
        tr.muladds = st.muladds;
        rep.muladds += st.muladds;
        tr.residual_rows = st.residual_rows;
        tr.residual_cols = st.q_cols;
        tr.dense_entries = st.dense_entries;
        tr.ms_reduce = st.ms_reducers;
        tr.ms_echelon = st.ms_residues;
        rep.max_residual_rows = rep.max_residual_rows.max(st.residual_rows);
        rep.max_dense_entries = rep.max_dense_entries.max(st.dense_entries);
        let pivots = match result {
            Ok(pivots) => pivots,
            Err(stop) => {
                match stop {
                    Stop::Deadline => rep.timed_out = true,
                    Stop::Oversize => rep.oversize = true,
                }
                s.pairs.extend(selected);
                break;
            }
        };
        let update_started = Instant::now();

        let mut fresh: Vec<RPoly> = pivots
            .into_iter()
            .map(|r| RPoly {
                monos: r.cols.iter().map(|&c| cols[c as usize]).collect(),
                coefs: r.vals,
            })
            .collect();
        tr.fresh = fresh.len();
        tr.fresh_min_degree = fresh
            .iter()
            .map(|p| degree_of(p.monos[0]))
            .min()
            .unwrap_or(0);
        if !fresh.is_empty() {
            learned = (learned.0.max(d), max_cols_so_far, rep.steps);
            rep.last_productive_degree = d;
        }
        if fresh.iter().any(|p| p.is_unit()) {
            rep.inconsistent = true;
            rep.basis = unit();
            record(&mut rep, learned);
            tr.basis_active = s.active.iter().filter(|&&a| a).count();
            tr.pairs_left = s.pairs.len();
            tr.ms = step_started.elapsed().as_secs_f64() * 1e3;
            rep.trace.push(tr);
            return finish(rep);
        }
        // Largest leading monomial first, so that a later, smaller one
        // retires the earlier ones it divides (`UPDATE`'s G_new).
        fresh.sort_by_key(|p| std::cmp::Reverse(p.lm().unwrap()));
        for p in fresh {
            s.insert(p.monic(fp), &mut rep);
        }
        tr.basis_active = s.active.iter().filter(|&&a| a).count();
        tr.pairs_left = s.pairs.len();
        tr.ms_update = update_started.elapsed().as_secs_f64() * 1e3;
        tr.ms = step_started.elapsed().as_secs_f64() * 1e3;
        rep.trace.push(tr);

        if let Some(bound) = opts.stop_staircase {
            if !s.pairs.is_empty() {
                if let Some(count) =
                    staircase_at_most(&s.active_lms(), ring.n_tower(), ring.n_free, bound)
                {
                    rep.staircase_at_stop = Some(count);
                    break;
                }
            }
        }
    }
    record(&mut rep, learned);
    rep.basis = active_basis(&s);
    finish(rep)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn fp(p: u64) -> Fp {
        Fp::new(p)
    }

    /// grevlex on exponent vectors, variable 0 largest.
    fn grevlex_cmp(a: &[u32], b: &[u32]) -> std::cmp::Ordering {
        let (da, db): (u32, u32) = (a.iter().sum(), b.iter().sum());
        if da != db {
            return da.cmp(&db);
        }
        for i in (0..a.len()).rev() {
            if a[i] != b[i] {
                return b[i].cmp(&a[i]);
            }
        }
        std::cmp::Ordering::Equal
    }

    fn key_of(e: &[u32], n_tower: usize) -> Mono {
        let mut mask = 0u64;
        for (j, &x) in e.iter().take(n_tower).enumerate() {
            assert!(x <= 1);
            if x == 1 {
                mask |= 1 << j;
            }
        }
        let mut f = [0u8; MAX_FREE];
        for (k, &x) in e.iter().skip(n_tower).enumerate() {
            f[k] = x as u8;
        }
        mono(mask, f)
    }

    #[test]
    fn keys_order_like_grevlex() {
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(7);
        let (n_tower, n_free) = (9usize, 2usize);
        for _ in 0..20_000 {
            let mut e1 = vec![0u32; n_tower + n_free];
            let mut e2 = vec![0u32; n_tower + n_free];
            for e in [&mut e1, &mut e2] {
                for (i, x) in e.iter_mut().enumerate() {
                    *x = if i < n_tower {
                        rng.gen_range(0..2)
                    } else {
                        rng.gen_range(0..4)
                    };
                }
            }
            let (k1, k2) = (key_of(&e1, n_tower), key_of(&e2, n_tower));
            assert_eq!(k1.cmp(&k2), grevlex_cmp(&e1, &e2), "{e1:?} {e2:?}");
            assert_eq!(degree_of(k1), e1.iter().sum::<u32>());
            // lcm, divisibility and quotient agree with exponent vectors
            let l: Vec<u32> = e1.iter().zip(&e2).map(|(a, b)| *a.max(b)).collect();
            assert_eq!(lcm(k1, k2), key_of(&l, n_tower));
            let div = e1.iter().zip(&e2).all(|(a, b)| a <= b);
            assert_eq!(divides(k1, k2), div);
            if div {
                let q: Vec<u32> = e2.iter().zip(&e1).map(|(b, a)| b - a).collect();
                assert_eq!(quotient(k2, k1), key_of(&q, n_tower));
            }
        }
        assert_eq!(mono(0, [0; MAX_FREE]), ONE);
    }

    /// Every kernel this CPU can run against exact arithmetic, over enough
    /// steps that the lazy accumulators cross `2⁶³` many times.
    #[test]
    fn the_kernels_agree_with_exact_arithmetic() {
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(5);
        let mut lanes = vec![Lanes::Scalar];
        #[cfg(target_arch = "x86_64")]
        {
            if std::is_x86_feature_detected!("avx2") {
                lanes.push(Lanes::Avx2);
            }
            #[cfg(suite_avx512)]
            if std::is_x86_feature_detected!("avx512f") {
                lanes.push(Lanes::Avx512);
            }
        }
        for &p in &[
            3u64,
            786433,
            2013265921,
            (1 << 31) - 1,
            3221225473,
            4294967291,
        ] {
            let f = fp(p);
            for _ in 0..20 {
                let n = rng.gen_range(0..200usize);
                let init: Vec<u64> = (0..n).map(|_| rng.gen_range(0..p)).collect();
                let steps: Vec<(u32, Vec<u32>)> = (0..rng.gen_range(1..40))
                    .map(|_| {
                        let a = rng.gen_range(0..p) as u32;
                        (a, (0..n).map(|_| rng.gen_range(0..p) as u32).collect())
                    })
                    .collect();
                let mut exact: Vec<u128> = init.iter().map(|&x| u128::from(x)).collect();
                for (a, b) in &steps {
                    for (x, &y) in exact.iter_mut().zip(b) {
                        *x = (*x + u128::from(*a) * u128::from(y)) % u128::from(p);
                    }
                }
                for &l in &lanes {
                    let kern = Kernel::with_lanes(f, l);
                    let mut acc = init.clone();
                    for (a, b) in &steps {
                        kern.axpy(&mut acc, *a, b);
                    }
                    let got: Vec<u128> = acc.iter().map(|&x| u128::from(f.reduce(x))).collect();
                    assert_eq!(got, exact, "p = {p}, {l:?}");
                }
            }
        }
    }

    /// The step's elimination against the plain sequential echelon, on
    /// random matrices that cross its block and chunk boundaries, with both
    /// kernels (below and above `2³¹`).
    #[test]
    fn the_elimination_matches_a_plain_echelon() {
        use rand::seq::SliceRandom;
        use rand::{Rng, SeedableRng};
        use std::collections::BTreeSet;
        let mut rng = rand::rngs::StdRng::seed_from_u64(11);
        for &p in &[786433u64, 2013265921, 3221225473] {
            let f = fp(p);
            for _ in 0..6 {
                let n_cols = rng.gen_range(150..400usize);
                let density = rng.gen_range(0.02..0.15);
                let random_row = |lead: usize, rng: &mut rand::rngs::StdRng| {
                    let mut row = Row {
                        cols: vec![lead as u32],
                        vals: vec![rng.gen_range(1..p) as u32],
                    };
                    for c in lead + 1..n_cols {
                        if rng.gen_bool(density) {
                            row.cols.push(c as u32);
                            row.vals.push(rng.gen_range(1..p) as u32);
                        }
                    }
                    row
                };
                // Pivot rows: distinct, monic leads, in a shuffled order.
                let mut leads: Vec<usize> = (0..n_cols).filter(|_| rng.gen_bool(0.6)).collect();
                leads.shuffle(&mut rng);
                let mut pivot_of = vec![NONE; n_cols];
                let mut piv_rows = Vec::new();
                for &c in &leads {
                    let mut row = random_row(c, &mut rng);
                    row.vals[0] = 1;
                    pivot_of[c] = piv_rows.len() as u32;
                    piv_rows.push(row);
                }
                // Up to several chunks of S-rows (a chunk holds at most
                // 128 rows per thread).
                let s_rows: Vec<Row> = (0..rng.gen_range(50..2000))
                    .map(|_| {
                        let lead = rng.gen_range(0..n_cols);
                        random_row(lead, &mut rng)
                    })
                    .collect();
                let mut st = ElimStats::default();
                let piv_leads: Vec<u32> = piv_rows.iter().map(|r| r.cols[0]).collect();
                let Ok(got) = eliminate(
                    f,
                    n_cols,
                    &piv_leads,
                    &|k| piv_rows[k].clone(),
                    &pivot_of,
                    s_rows.len(),
                    &|k| s_rows[k].clone(),
                    None,
                    None,
                    &mut st,
                ) else {
                    panic!("no deadline and no cap were set");
                };
                let mut all = piv_rows.clone();
                all.extend(s_rows.iter().cloned());
                let mut w = 0;
                let reference = echelon(f, all.clone(), n_cols, &mut w, None).unwrap();
                let ref_leads: BTreeSet<u32> = reference.iter().map(|r| r.cols[0]).collect();
                let piv_leads: BTreeSet<u32> = leads.iter().map(|&c| c as u32).collect();
                let new_leads: BTreeSet<u32> = got.iter().map(|r| r.cols[0]).collect();
                assert_eq!(new_leads.len(), got.len(), "p = {p}: repeated leads");
                assert!(new_leads.is_disjoint(&piv_leads), "p = {p}");
                assert_eq!(
                    ref_leads,
                    piv_leads.union(&new_leads).copied().collect(),
                    "p = {p}: a different row space"
                );
                // The rows lie in the row space: adding them keeps the rank.
                all.extend(got.iter().cloned());
                assert_eq!(
                    echelon(f, all, n_cols, &mut w, None).unwrap().len(),
                    reference.len(),
                    "p = {p}: a row outside the row space"
                );
                for r in &got {
                    assert_eq!(r.vals[0], 1);
                    assert!(r.cols.windows(2).all(|w| w[0] < w[1]));
                    assert!(r.cols.iter().all(|&c| pivot_of[c as usize] == NONE));
                    assert!(r.vals.iter().all(|&v| v != 0 && u64::from(v) < p));
                }
            }
        }
    }

    /// Generic reduction by `y_j² − rule_j` on exponent vectors, as an
    /// independent reference for the rewriting.
    fn reference_nf(ring: &TowerRing, terms: &[(Vec<u32>, u64)]) -> BTreeMap<Vec<u32>, u64> {
        let p = ring.p;
        let f = fp(p);
        let mut work: BTreeMap<Vec<u32>, u64> = BTreeMap::new();
        for (e, c) in terms {
            let v = work.entry(e.clone()).or_insert(0);
            *v = f.add(*v, c % p);
        }
        loop {
            let hit = work
                .iter()
                .find(|(e, c)| **c != 0 && e.iter().take(ring.n_tower()).any(|&x| x >= 2))
                .map(|(e, c)| (e.clone(), *c));
            let Some((e, c)) = hit else { break };
            work.remove(&e);
            let j = e.iter().position(|&x| x >= 2).unwrap();
            let r = ring.rules[j];
            let mut base = e.clone();
            base[j] -= 2;
            let mut push = |add: &[(usize, u32)], coef: u64| {
                if coef == 0 {
                    return;
                }
                let mut t = base.clone();
                for &(v, k) in add {
                    t[v] += k;
                }
                let v = work.entry(t).or_insert(0);
                *v = f.add(*v, f.mul(c, coef));
            };
            push(&[], r.d);
            push(&[(j, 1)], r.c);
            if let Some(nx) = r.next {
                push(&[(nx as usize, 1)], r.b);
                push(&[(j, 1), (nx as usize, 1)], r.a);
            }
        }
        work.retain(|_, c| *c != 0);
        work
    }

    fn random_ring(
        rng: &mut impl rand::Rng,
        p: u64,
        blocks: usize,
        t: usize,
        n_free: usize,
        general: bool,
    ) -> TowerRing {
        let mut rules = Vec::new();
        for b in 0..blocks {
            for j in 0..t {
                let top = j + 1 == t;
                let r = if general {
                    SquareRule {
                        next: (!top).then_some((b * t + j + 1) as u8),
                        a: if top { 0 } else { rng.gen_range(0..p) },
                        b: if top { 0 } else { rng.gen_range(0..p) },
                        c: rng.gen_range(0..p),
                        d: rng.gen_range(0..p),
                    }
                } else {
                    SquareRule {
                        next: (!top).then_some((b * t + j + 1) as u8),
                        a: 0,
                        b: if top { 0 } else { 1 },
                        c: 0,
                        d: if top { rng.gen_range(1..p) } else { 0 },
                    }
                };
                rules.push(r);
            }
        }
        TowerRing { p, rules, n_free }
    }

    #[test]
    fn products_match_a_generic_reduction() {
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(11);
        let p = 1_000_003u64;
        for trial in 0..60 {
            let general = trial % 2 == 0;
            let ring = random_ring(&mut rng, p, 2, 4, 1, general);
            let n = ring.n_vars();
            // Sparse raw terms: the reference rewrites whole exponent
            // vectors, and a dense vector like (2, 2, 2, 2) on one tower
            // swells through millions of intermediate monomials before it
            // settles (the engine never sees them: it stays square-free
            // after every variable).
            let rand_raw =
                |rng: &mut rand::rngs::StdRng, terms: usize, max_e: u32| -> Vec<(Vec<u32>, u64)> {
                    (0..terms)
                        .map(|_| {
                            let mut e = vec![0u32; n];
                            let mut budget = 4u32;
                            for x in e.iter_mut() {
                                if budget > 0 && rng.gen_range(0..10) < 3 {
                                    *x = rng.gen_range(1..=max_e.min(budget));
                                    budget -= *x;
                                }
                            }
                            (e, rng.gen_range(1..p))
                        })
                        .collect()
                };
            // from_raw against the reference
            let raw = rand_raw(&mut rng, 6, 3);
            let got = ring.from_raw(&raw);
            let want = reference_nf(&ring, &raw);
            let got_map: BTreeMap<Vec<u32>, u64> = got
                .monos
                .iter()
                .zip(&got.coefs)
                .map(|(&m, &c)| {
                    let mut e = vec![0u32; n];
                    let mask = mask_of(m);
                    for (j, x) in e.iter_mut().enumerate().take(ring.n_tower()) {
                        *x = ((mask >> j) & 1) as u32;
                    }
                    for k in 0..ring.n_free {
                        e[ring.n_tower() + k] = u32::from(free_of(m)[k]);
                    }
                    (e, u64::from(c))
                })
                .collect();
            assert_eq!(got_map, want, "trial {trial}");
            // monomial × polynomial against from_raw of the raw product
            let g = ring.from_raw(&rand_raw(&mut rng, 5, 1));
            let u_raw: Vec<u32> = (0..n)
                .map(|i| {
                    if i < ring.n_tower() {
                        rng.gen_range(0..2)
                    } else {
                        rng.gen_range(0..3)
                    }
                })
                .collect();
            let u = key_of(&u_raw, ring.n_tower());
            let prod = ring.mul_mono(&g, u);
            let raw_prod: Vec<(Vec<u32>, u64)> = g
                .monos
                .iter()
                .zip(&g.coefs)
                .map(|(&m, &c)| {
                    let mut e = vec![0u32; n];
                    let mask = mask_of(m);
                    for (j, x) in e.iter_mut().enumerate().take(ring.n_tower()) {
                        *x = ((mask >> j) & 1) as u32 + u_raw[j];
                    }
                    for k in 0..ring.n_free {
                        e[ring.n_tower() + k] =
                            u32::from(free_of(m)[k]) + u_raw[ring.n_tower() + k];
                    }
                    (e, u64::from(c))
                })
                .collect();
            assert_eq!(prod, ring.from_raw(&raw_prod), "trial {trial}");
        }
    }

    // ── Small towers with points, for end-to-end checks ──

    /// A Kummer tower of `t` levels over `p` (needs `2^t | p − 1`): the
    /// rules, and every point `(y_0 … y_{t−1})` with `y_0` in `μ_{2^t}`.
    fn kummer_block(p: u64, t: usize, base: usize) -> (Vec<SquareRule>, Vec<Vec<u64>>) {
        let f = fp(p);
        let zeta = (2..p)
            .map(|h| f.pow(h, (p - 1) >> t))
            .find(|&z| f.pow(z, 1 << (t - 1)) != 1)
            .unwrap();
        let rules: Vec<SquareRule> = (0..t)
            .map(|j| SquareRule {
                next: (j + 1 < t).then_some((base + j + 1) as u8),
                a: 0,
                b: if j + 1 < t { 1 } else { 0 },
                c: 0,
                d: if j + 1 < t { 0 } else { 1 },
            })
            .collect();
        let points = (0..1u64 << t)
            .map(|k| {
                let mut y = vec![f.pow(zeta, k)];
                for j in 1..t {
                    y.push(f.mul(y[j - 1], y[j - 1]));
                }
                y
            })
            .collect();
        (rules, points)
    }

    /// A random polynomial of bidegree at most (2, 2) in `x_1 = y_{0,0}`,
    /// `x_2 = y_{1,0}`, the shape of `S₃`, in tower normal form.
    fn biquadratic(
        rng: &mut impl rand::Rng,
        ring: &TowerRing,
        t: usize,
        zero_at: Option<&[u64]>,
    ) -> RPoly {
        let n = ring.n_vars();
        let mut raw = Vec::new();
        for a in 0..3u32 {
            for b in 0..3u32 {
                let mut e = vec![0u32; n];
                e[0] = a;
                e[t] = b;
                raw.push((e, rng.gen_range(1..ring.p)));
            }
        }
        let mut g = ring.from_raw(&raw);
        if let Some(pt) = zero_at {
            let v = ring.eval(&g, pt);
            if v != 0 {
                g = ring.from_raw(&[raw, vec![(vec![0; n], ring.p - v)]].concat());
            }
        }
        g
    }

    #[test]
    fn refutes_exactly_the_empty_systems_and_counts_the_rest() {
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(2026);
        let p = 97u64; // 2^5 | 96
        for t in 1..=4usize {
            let (r0, pts) = kummer_block(p, t, 0);
            let (r1, _) = kummer_block(p, t, t);
            let ring = TowerRing {
                p,
                rules: [r0, r1].concat(),
                n_free: 0,
            };
            for trial in 0..12 {
                let plant: Option<Vec<u64>> = (trial % 3 == 0).then(|| {
                    let a = &pts[rng.gen_range(0..pts.len())];
                    let b = &pts[rng.gen_range(0..pts.len())];
                    [a.clone(), b.clone()].concat()
                });
                let g = biquadratic(&mut rng, &ring, t, plant.as_deref());
                // brute force over V × V
                let mut zeros = Vec::new();
                for a in &pts {
                    for b in &pts {
                        let x = [a.clone(), b.clone()].concat();
                        if ring.eval(&g, &x) == 0 {
                            zeros.push(x);
                        }
                    }
                }
                let rep = f4_tower(&[g], &ring, &TowerF4Options::new(64));
                assert!(!rep.timed_out && rep.pairs_above_bound == 0);
                assert_eq!(rep.inconsistent, zeros.is_empty(), "t {t} trial {trial}");
                if !rep.inconsistent {
                    for z in &zeros {
                        for b in &rep.basis {
                            assert_eq!(ring.eval(b, z), 0, "a solution was lost");
                        }
                    }
                    // A zero-dimensional radical ideal: its staircase counts
                    // its points.
                    let lms: Vec<Mono> = rep.basis.iter().map(|b| b.lm().unwrap()).collect();
                    assert_eq!(
                        staircase_at_most(&lms, ring.n_tower(), 0, 1 << 12),
                        Some(zeros.len())
                    );
                }
            }
        }
    }

    #[test]
    fn a_free_variable_is_eliminated_like_a_chain_link() {
        // x1 in a Kummer set V, u free: u² − x1 = 0 and u − c = 0 for a c
        // whose square is or is not in V.
        let p = 97u64;
        let t = 3usize;
        let (rules, pts) = kummer_block(p, t, 0);
        let ring = TowerRing {
            p,
            rules,
            n_free: 1,
        };
        let n = ring.n_vars();
        let f = fp(p);
        for c in 1..p {
            let sq = f.mul(c, c);
            let in_v = pts.iter().any(|y| y[0] == sq);
            let mut e_u2 = vec![0u32; n];
            e_u2[t] = 2;
            let mut e_x = vec![0u32; n];
            e_x[0] = 1;
            let mut e_u = vec![0u32; n];
            e_u[t] = 1;
            let g1 = ring.from_raw(&[(e_u2, 1), (e_x, p - 1)]);
            let g2 = ring.from_raw(&[(e_u, 1), (vec![0; n], p - c)]);
            let rep = f4_tower(&[g1, g2], &ring, &TowerF4Options::new(64));
            assert_eq!(rep.inconsistent, !in_v, "c = {c}");
        }
    }

    #[test]
    fn the_stop_keeps_every_solution() {
        use rand::{Rng, SeedableRng};
        let mut rng = rand::rngs::StdRng::seed_from_u64(99);
        let p = 97u64;
        let t = 4usize;
        let (r0, pts) = kummer_block(p, t, 0);
        let (r1, _) = kummer_block(p, t, t);
        let ring = TowerRing {
            p,
            rules: [r0, r1].concat(),
            n_free: 0,
        };
        for _ in 0..10 {
            let a = pts[rng.gen_range(0..pts.len())].clone();
            let b = pts[rng.gen_range(0..pts.len())].clone();
            let x = [a, b].concat();
            let g = biquadratic(&mut rng, &ring, t, Some(&x));
            let full = f4_tower(std::slice::from_ref(&g), &ring, &TowerF4Options::new(64));
            let stopped = f4_tower(&[g], &ring, &TowerF4Options::new(64).stopping_below(4));
            assert!(!stopped.inconsistent);
            for b in &stopped.basis {
                assert_eq!(ring.eval(b, &x), 0);
            }
            assert!(stopped.solving_degree_max <= full.solving_degree_max);
            if let Some(k) = stopped.staircase_at_stop {
                assert!((1..=4).contains(&k));
            }
        }
    }

    #[test]
    fn the_degree_bound_stops_and_reports() {
        use rand::SeedableRng;
        let mut rng = rand::rngs::StdRng::seed_from_u64(5);
        let p = 97u64;
        let t = 4usize;
        let (r0, _) = kummer_block(p, t, 0);
        let (r1, _) = kummer_block(p, t, t);
        let ring = TowerRing {
            p,
            rules: [r0, r1].concat(),
            n_free: 0,
        };
        let g = biquadratic(&mut rng, &ring, t, None);
        let rep = f4_tower(&[g], &ring, &TowerF4Options::new(2));
        assert!(rep.degree_reached <= 2);
        assert!(rep.inconsistent || rep.pairs_above_bound > 0);
    }
}
