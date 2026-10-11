//! **Decomposition systems past 64 unknowns** — plan target C of
//! `docs/ic/perf/OPTIMIZATION_PLAN.md`.
//!
//! Every `F_2` solver in [`crate::cryptanalysis::koblitz_groebner`] keeps a
//! monomial in a `u64`, so the chained `S₃` system of an `m`-point
//! decomposition — `m·ℓ + (m − 2)·n` unknowns — cannot be written down
//! once that exceeds 64: already at `m = 4`, `n = 31`, `ℓ = 6` (86
//! unknowns), and at every `m ≥ 4` rung the index-calculus family cares
//! about.  This module is the same system in `u128` monomials (up to 128
//! unknowns) and a solver for it, kept separate so the 64-bit engines,
//! their counters and their frozen benchmarks are untouched.
//!
//! ## The solver
//!
//! A root of the system is wanted only for its summand abscissae: once
//! those `m·ℓ` bits are fixed, `lift_candidate` settles in the group
//! whether signs exist that make the summands add to the target.  So the
//! search branches on summand bits only, lowest first — which fixes one
//! summand at a time — and never on the `(m − 2)·n` intermediate
//! unknowns.  By default a node fixes a whole summand at once, branching
//! over the coordinate vectors whose abscissa is a factor-base point's
//! (`valid_coordinates`): a twist abscissa, or a point outside the
//! base, is never a child.  At every node the equations, with the branch's assignment
//! substituted, are **linearised**: their Macaulay matrix at their own
//! degree, columns in descending degree, reduced to row echelon form by
//! [`crate::cryptanalysis::gf2_elim`].  A reduced row equal to `1`
//! closes the branch; a row of degree `≤ 1` is a linear consequence,
//! eliminated by substitution, and the step repeats until nothing new
//! falls out.  That is the degree-`d` Macaulay step of the 64-bit
//! engines' default `max_degree = 3` on cubic systems, without the
//! splitting on intermediate unknowns that their measured failure at
//! `n = 31, m = 3` traced to.
//!
//! What this does not claim: that it is fast.  Its purpose is to make
//! the `m ≥ 4` cells of `examples/pdp_bench.rs` *measurable*, so the
//! Gröbner route's frontier at `m = 4, 5, 6` is a table rather than a
//! "not buildable".

use std::collections::HashMap;

use num_bigint::BigUint;

use crate::binary_ecc::{BinaryPoint, F2mElement};
use crate::cryptanalysis::fx_hash::FxMap;
use crate::cryptanalysis::gf2_elim;
use crate::cryptanalysis::koblitz_groebner::FieldStructure;
use crate::cryptanalysis::koblitz_index_calculus::{
    lift_candidate, point_key, points_with_x, FrobeniusFactorBase, KoblitzCurve,
};

/// Most unknowns a [`WPoly`] can carry.
pub const MAX_WIDE_VARS: usize = 128;

/// A monomial: bit `v` set means variable `v` divides it.
pub type Mono = u128;

/// A polynomial over `F_2` in Boolean variables (`v² = v`): its
/// monomials, ascending as integers, no repeats.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct WPoly {
    pub terms: Vec<Mono>,
}

impl WPoly {
    pub fn zero() -> Self {
        Self { terms: Vec::new() }
    }

    pub fn one() -> Self {
        Self { terms: vec![0] }
    }

    pub fn var(v: usize) -> Self {
        Self {
            terms: vec![1u128 << v],
        }
    }

    pub fn is_zero(&self) -> bool {
        self.terms.is_empty()
    }

    pub fn is_one(&self) -> bool {
        self.terms == [0]
    }

    /// Highest monomial degree (0 for constants and zero).
    pub fn degree(&self) -> u32 {
        self.terms.iter().map(|m| m.count_ones()).max().unwrap_or(0)
    }

    /// From any list of monomials: sorted, and pairs cancelled.
    pub fn from_monos(mut monos: Vec<Mono>) -> Self {
        monos.sort_unstable();
        let mut terms = Vec::with_capacity(monos.len());
        let mut i = 0;
        while i < monos.len() {
            let mut j = i;
            while j < monos.len() && monos[j] == monos[i] {
                j += 1;
            }
            if (j - i) % 2 == 1 {
                terms.push(monos[i]);
            }
            i = j;
        }
        Self { terms }
    }

    /// Sum: the symmetric difference of the term sets.
    pub fn add(&self, other: &Self) -> Self {
        let (a, b) = (&self.terms, &other.terms);
        let mut out = Vec::with_capacity(a.len() + b.len());
        let (mut i, mut j) = (0, 0);
        while i < a.len() && j < b.len() {
            match a[i].cmp(&b[j]) {
                std::cmp::Ordering::Less => {
                    out.push(a[i]);
                    i += 1;
                }
                std::cmp::Ordering::Greater => {
                    out.push(b[j]);
                    j += 1;
                }
                std::cmp::Ordering::Equal => {
                    i += 1;
                    j += 1;
                }
            }
        }
        out.extend_from_slice(&a[i..]);
        out.extend_from_slice(&b[j..]);
        Self { terms: out }
    }

    /// Product in the Boolean quotient: monomials multiply by union.
    pub fn mul(&self, other: &Self) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero();
        }
        let mut monos = Vec::with_capacity(self.terms.len() * other.terms.len());
        for &a in &self.terms {
            for &b in &other.terms {
                monos.push(a | b);
            }
        }
        Self::from_monos(monos)
    }

    /// Substitute the affine form `form` for variable `v`.
    pub fn substitute(&self, v: usize, form: &WPoly) -> Self {
        let bit = 1u128 << v;
        if self.terms.iter().all(|m| m & bit == 0) {
            return self.clone();
        }
        // The branching step substitutes constants, and those need no
        // multiplication: v := 0 drops the terms v divides, v := 1 strips
        // v from them (terms that then coincide cancel in pairs).
        if form.is_zero() {
            return Self {
                terms: self
                    .terms
                    .iter()
                    .copied()
                    .filter(|m| m & bit == 0)
                    .collect(),
            };
        }
        if form.is_one() {
            return Self::from_monos(self.terms.iter().map(|m| m & !bit).collect());
        }
        let (with, without): (Vec<Mono>, Vec<Mono>) =
            self.terms.iter().partition(|&&m| m & bit != 0);
        let cofactor = Self::from_monos(with.into_iter().map(|m| m & !bit).collect());
        Self { terms: without }.add(&cofactor.mul(form))
    }

    /// Substitute `forms[v]` (a term list) for every variable `v` of
    /// `mask` at once.  No form may mention a variable of `mask`.
    pub fn substitute_all(&self, mask: u128, forms: &[&[Mono]]) -> Self {
        if self.terms.iter().all(|m| m & mask == 0) {
            return self.clone();
        }
        let mut out: Vec<Mono> = Vec::with_capacity(self.terms.len() * 2);
        let mut expand: Vec<Mono> = Vec::new();
        let mut next: Vec<Mono> = Vec::new();
        for &m in &self.terms {
            let mut hit = m & mask;
            if hit == 0 {
                out.push(m);
                continue;
            }
            expand.clear();
            expand.push(m & !mask);
            while hit != 0 {
                let v = hit.trailing_zeros() as usize;
                hit &= hit - 1;
                next.clear();
                for &a in &expand {
                    for &b in forms[v] {
                        next.push(a | b);
                    }
                }
                std::mem::swap(&mut expand, &mut next);
            }
            out.extend_from_slice(&expand);
        }
        Self::from_monos(out)
    }

    /// Set the variables of `zeros` to 0 and those of `ones` to 1, in one
    /// pass: the terms a zero divides drop, the ones are stripped, and
    /// only then is the result sorted (and coinciding terms cancelled).
    pub fn assign_constants(&self, zeros: u128, ones: u128) -> Self {
        let touched = zeros | ones;
        if self.terms.iter().all(|m| m & touched == 0) {
            return self.clone();
        }
        let kept = self.terms.iter().copied().filter(|m| m & zeros == 0);
        if self.terms.iter().all(|m| m & ones == 0) {
            // Filtering keeps the order and adds no repeats.
            return Self {
                terms: kept.collect(),
            };
        }
        Self::from_monos(kept.map(|m| m & !ones).collect())
    }

    /// Evaluate at a full assignment (`bits` bit `v` = value of variable `v`).
    pub fn eval(&self, bits: u128) -> bool {
        self.terms.iter().filter(|&&m| m & !bits == 0).count() % 2 == 1
    }
}

/// A field element whose `n` coordinates are [`WPoly`]s.
#[derive(Clone, Debug)]
pub struct WSym {
    pub coords: Vec<WPoly>,
}

impl WSym {
    fn constant(v: &F2mElement, n: u32) -> Self {
        let bits = v.raw_bits().first().copied().unwrap_or(0);
        Self {
            coords: (0..n)
                .map(|k| {
                    if bits >> k & 1 == 1 {
                        WPoly::one()
                    } else {
                        WPoly::zero()
                    }
                })
                .collect(),
        }
    }

    fn from_subspace_vars(basis: &[F2mElement], offset: usize, n: u32) -> Self {
        let mut coords = vec![Vec::new(); n as usize];
        for (t, b) in basis.iter().enumerate() {
            let bits = b.raw_bits().first().copied().unwrap_or(0);
            for (k, c) in coords.iter_mut().enumerate() {
                if bits >> k & 1 == 1 {
                    c.push(1u128 << (offset + t));
                }
            }
        }
        Self {
            coords: coords.into_iter().map(WPoly::from_monos).collect(),
        }
    }

    fn from_free_vars(offset: usize, n: u32) -> Self {
        Self {
            coords: (0..n as usize).map(|k| WPoly::var(offset + k)).collect(),
        }
    }

    fn add(&self, other: &Self) -> Self {
        Self {
            coords: self
                .coords
                .iter()
                .zip(&other.coords)
                .map(|(a, b)| a.add(b))
                .collect(),
        }
    }

    fn mul(&self, other: &Self, st: &FieldStructure) -> Self {
        let n = st.n as usize;
        let mut acc: Vec<Vec<Mono>> = vec![Vec::new(); n];
        for (i, a) in self.coords.iter().enumerate() {
            if a.is_zero() {
                continue;
            }
            for (j, b) in other.coords.iter().enumerate() {
                if b.is_zero() {
                    continue;
                }
                let prod = a.mul(b);
                let red = st.reduced[i][j];
                for (k, slot) in acc.iter_mut().enumerate() {
                    if red >> k & 1 == 1 {
                        slot.extend_from_slice(&prod.terms);
                    }
                }
            }
        }
        Self {
            coords: acc.into_iter().map(WPoly::from_monos).collect(),
        }
    }

    fn square(&self, st: &FieldStructure) -> Self {
        let n = st.n as usize;
        let mut acc: Vec<Vec<Mono>> = vec![Vec::new(); n];
        for (k, c) in self.coords.iter().enumerate() {
            let sq = st.squares[k];
            for (t, slot) in acc.iter_mut().enumerate() {
                if sq >> t & 1 == 1 {
                    slot.extend_from_slice(&c.terms);
                }
            }
        }
        Self {
            coords: acc.into_iter().map(WPoly::from_monos).collect(),
        }
    }
}

/// `S₃(x₁, x₂, x₃) = (x₁+x₂)² x₃² + x₁x₂x₃ + (x₁x₂)² + b`, coordinatewise.
fn s3(x1: &WSym, x2: &WSym, x3: &WSym, b: &F2mElement, st: &FieldStructure) -> Vec<WPoly> {
    let prod = x1.mul(x2, st);
    x1.add(x2)
        .square(st)
        .mul(&x3.square(st), st)
        .add(&prod.mul(x3, st))
        .add(&prod.square(st))
        .add(&WSym::constant(b, st.n))
        .coords
}

/// The chained `S₃` system of an `m`-point decomposition of a target with
/// abscissa `x_r`, summands in the span of `basis` — the layout of
/// `koblitz_groebner::build_decomposition_system`: summand `i` owns
/// variables `[i·ℓ, (i+1)·ℓ)`, then `(m − 2)·n` intermediate unknowns.
#[derive(Clone, Debug)]
pub struct WideSystem {
    pub equations: Vec<WPoly>,
    pub n_vars: usize,
    pub ell: usize,
    pub m: usize,
}

impl WideSystem {
    pub fn build(
        basis: &[F2mElement],
        x_r: &F2mElement,
        b: &F2mElement,
        m: usize,
        st: &FieldStructure,
    ) -> Option<Self> {
        if m < 2 || st.n > 64 {
            return None;
        }
        let n = st.n;
        let ell = basis.len();
        let n_vars = m * ell + (m - 2) * n as usize;
        if n_vars > MAX_WIDE_VARS {
            return None;
        }
        let xs: Vec<WSym> = (0..m)
            .map(|i| WSym::from_subspace_vars(basis, i * ell, n))
            .collect();
        let inter: Vec<WSym> = (0..m - 2)
            .map(|i| WSym::from_free_vars(m * ell + i * n as usize, n))
            .collect();
        let target = WSym::constant(x_r, n);
        let mut equations = Vec::new();
        if m == 2 {
            equations.extend(s3(&xs[0], &xs[1], &target, b, st));
        } else {
            equations.extend(s3(&xs[0], &xs[1], &inter[0], b, st));
            for i in 0..m - 3 {
                equations.extend(s3(&inter[i], &xs[i + 2], &inter[i + 1], b, st));
            }
            equations.extend(s3(&inter[m - 3], &xs[m - 1], &target, b, st));
        }
        equations.retain(|p| !p.is_zero());
        Some(Self {
            equations,
            n_vars,
            ell,
            m,
        })
    }

    /// The last `k` links of an `m`-point chain, `m > k`, starting from a
    /// **free** abscissa: `w_0` stands for `x(P_1 + … + P_{m−k})`, and the
    /// links are `S₃(w_0, y_1, w_1), …, S₃(w_{k−1}, y_k, x_R)`.  Summand
    /// `y_i` owns variables `[(i−1)·ℓ, i·ℓ)`, then the `k` intermediates
    /// `w_0 … w_{k−1}`: `k·(ℓ + n)` unknowns.  Every decomposition of the
    /// target satisfies it, whatever the first `m − k` summands are, so
    /// it prunes soundly; it cannot finish a decomposition on its own.
    pub fn build_suffix(
        basis: &[F2mElement],
        x_r: &F2mElement,
        b: &F2mElement,
        k: usize,
        st: &FieldStructure,
    ) -> Option<Self> {
        if k == 0 || st.n > 64 {
            return None;
        }
        let n = st.n;
        let ell = basis.len();
        let n_vars = k * (ell + n as usize);
        if n_vars > MAX_WIDE_VARS {
            return None;
        }
        let ys: Vec<WSym> = (0..k)
            .map(|i| WSym::from_subspace_vars(basis, i * ell, n))
            .collect();
        let ws: Vec<WSym> = (0..k)
            .map(|i| WSym::from_free_vars(k * ell + i * n as usize, n))
            .collect();
        let target = WSym::constant(x_r, n);
        let mut equations = Vec::new();
        for i in 0..k {
            let next = if i + 1 < k { &ws[i + 1] } else { &target };
            equations.extend(s3(&ws[i], &ys[i], next, b, st));
        }
        equations.retain(|p| !p.is_zero());
        Some(Self {
            equations,
            n_vars,
            ell,
            m: k,
        })
    }
}

/// What a wide solve did.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct WideStats {
    /// Search nodes visited.
    pub nodes: usize,
    /// Linearisation passes (one Macaulay reduction each).
    pub reductions: usize,
    /// Branches closed by a reduced `1`.
    pub refuted: usize,
    /// Leaves whose summands were lifted in the group.
    pub leaves: usize,
    /// Largest linearisation matrix, rows × columns.
    pub max_rows: usize,
    pub max_cols: usize,
    /// The node budget ran out: a `None` then says nothing.
    pub exhausted: bool,
}

/// Columns above which a node skips linearisation and just splits: a
/// dense matrix that wide would cost more than the branch it might close.
const MAX_LINEARISATION_COLS: usize = 1 << 20;

/// Linearise `eqs` to a fixpoint: reduce their Macaulay matrix at their
/// own degree, substitute every linear consequence, repeat.  Returns
/// `false` when a reduction yields `1` (the branch has no root), and
/// otherwise the substitutions made (variable, affine form) in order.
fn linearise(eqs: &mut Vec<WPoly>, stats: &mut WideStats, subs: &mut Vec<(usize, WPoly)>) -> bool {
    loop {
        eqs.retain(|p| !p.is_zero());
        if eqs.iter().any(WPoly::is_one) {
            return false;
        }
        if eqs.is_empty() {
            return true;
        }
        // Columns: every monomial, by descending degree (any fixed order
        // within a degree serves), so a reduced row whose pivot column
        // has degree ≤ 1 is linear.
        //
        // Deduplicated through the index map, then laid out by degree
        // with a counting pass: no sort of every term of every equation
        // (sorting was most of a search).
        let mut index: FxMap<Mono, usize> = FxMap::default();
        index.reserve(eqs.iter().map(|p| p.terms.len()).max().unwrap_or(0) * 2);
        let mut all: Vec<Mono> = Vec::new();
        for p in eqs.iter() {
            for &m in &p.terms {
                index.entry(m).or_insert_with(|| {
                    all.push(m);
                    0
                });
            }
        }
        if all.len() > MAX_LINEARISATION_COLS {
            return true;
        }
        // Ascending within a degree, so that a reduced row read in column
        // order is one ascending run a degree (see `to_poly`): one sort of
        // the distinct monomials here instead of one of every row there.
        all.sort_unstable();
        let max_deg = all.iter().map(|m| m.count_ones()).max().unwrap_or(0) as usize;
        let mut start = vec![0usize; max_deg + 2];
        for m in &all {
            // Descending degree: degree d goes after every higher one.
            start[max_deg - m.count_ones() as usize + 1] += 1;
        }
        for d in 1..start.len() {
            start[d] += start[d - 1];
        }
        // Where each degree's columns end: a row read in column order is
        // one ascending run between consecutive ends.
        let degree_ends: Vec<usize> = start[1..].to_vec();
        let mut cols = vec![0 as Mono; all.len()];
        for &m in &all {
            let slot = &mut start[max_deg - m.count_ones() as usize];
            cols[*slot] = m;
            *index.get_mut(&m).expect("indexed") = *slot;
            *slot += 1;
        }
        let words = cols.len().div_ceil(64);
        let mut matrix: Vec<Vec<u64>> = eqs
            .iter()
            .map(|p| {
                let mut row = vec![0u64; words];
                for m in &p.terms {
                    let c = index[m];
                    row[c / 64] |= 1 << (c % 64);
                }
                row
            })
            .collect();
        stats.reductions += 1;
        stats.max_rows = stats.max_rows.max(matrix.len());
        stats.max_cols = stats.max_cols.max(cols.len());
        let mut ops = 0;
        let rank = gf2_elim::eliminate(
            &mut matrix,
            cols.len(),
            true,
            gf2_elim::Config::from_env(),
            &mut ops,
        );
        let to_poly = |row: &Vec<u64>| {
            let weight: u32 = row.iter().map(|w| w.count_ones()).sum();
            let mut terms: Vec<Mono> = Vec::with_capacity(weight as usize);
            let mut runs: Vec<usize> = Vec::with_capacity(degree_ends.len());
            let mut d = 0;
            for (w, &word) in row.iter().enumerate() {
                let mut bits = word;
                while bits != 0 {
                    let c = w * 64 + bits.trailing_zeros() as usize;
                    bits &= bits - 1;
                    while c >= degree_ends[d] {
                        runs.push(terms.len());
                        d += 1;
                    }
                    terms.push(cols[c]);
                }
            }
            runs.push(terms.len());
            WPoly {
                terms: merge_degree_runs(terms, &runs),
            }
        };
        let reduced: Vec<WPoly> = matrix[..rank].iter().map(to_poly).collect();
        if reduced.iter().any(WPoly::is_one) {
            return false;
        }
        // Linear rows: pivot (first, highest-degree) column of degree 1.
        // The reduced form clears each pivot column from every other
        // row, so each has a distinct leading variable that no other
        // row's form mentions.
        let mut linear: Vec<(usize, WPoly)> = Vec::new();
        for (row, p) in matrix[..rank].iter().zip(&reduced) {
            let first = row
                .iter()
                .enumerate()
                .find(|(_, &w)| w != 0)
                .map(|(w, &word)| w * 64 + word.trailing_zeros() as usize)
                .expect("nonzero row");
            let pivot = cols[first];
            if pivot.count_ones() == 1 {
                let v = pivot.trailing_zeros() as usize;
                let form = p.add(&WPoly::var(v)); // v = rest
                linear.push((v, form));
            }
        }
        if linear.is_empty() {
            *eqs = reduced;
            // Optional prolongation (`KIC_WIDE_PROLONG=D`): the degree-D
            // Macaulay matrix — every equation of degree < D times every
            // variable still present — may hold linear consequences, or a
            // `1`, that the equations' own degree does not.
            let d = prolong_degree();
            if d == 0 {
                return true;
            }
            match prolong(eqs, d, stats) {
                Prolonged::Refuted => return false,
                Prolonged::Nothing => return true,
                Prolonged::Linear(extra) => {
                    eqs.extend(extra);
                    continue;
                }
            }
        }
        *eqs = reduced;
        // The reduced form clears every pivot column from every other
        // row, so no linear row's form mentions another's leading
        // variable: the whole batch substitutes at once, one pass (and
        // one sort) a polynomial instead of one a variable.
        let mut batch: Vec<(usize, WPoly)> = Vec::with_capacity(linear.len());
        let mut mask = 0u128;
        for (v, form) in linear {
            // Earlier substitutions may already mention `v` in `form`'s
            // variables' place; apply them to the form first.
            let mut f = form;
            for (u, g) in subs.iter() {
                f = f.substitute(*u, g);
            }
            if f.terms.iter().any(|m| m >> v & 1 == 1 || m & mask != 0) {
                // `v = … + v …`, or a form naming another leading
                // variable, cannot happen in reduced form; guard anyway
                // and leave it for the next pass.
                continue;
            }
            if batch
                .iter()
                .any(|(_, g)| g.terms.iter().any(|m| m >> v & 1 == 1))
            {
                continue;
            }
            mask |= 1u128 << v;
            batch.push((v, f));
        }
        let mut forms: Vec<&[Mono]> = vec![&[]; MAX_WIDE_VARS];
        for (v, f) in &batch {
            forms[*v] = &f.terms;
        }
        for p in eqs.iter_mut() {
            *p = p.substitute_all(mask, &forms);
        }
        for (_, g) in subs.iter_mut() {
            *g = g.substitute_all(mask, &forms);
        }
        subs.extend(batch);
    }
}

/// Monomials in column order — descending degree, ascending within a
/// degree, no repeats — as the ascending list a [`WPoly`] keeps.  `runs`
/// are the per-degree segments' ends in `terms`; they are merged two at
/// a time (a plain merge each), not sorted.
fn merge_degree_runs(terms: Vec<Mono>, runs: &[usize]) -> Vec<Mono> {
    let mut bounds: Vec<(usize, usize)> = Vec::with_capacity(runs.len());
    let mut lo = 0;
    for &hi in runs {
        if hi > lo {
            bounds.push((lo, hi));
        }
        lo = hi;
    }
    if bounds.len() <= 1 {
        return terms;
    }
    let mut cur = terms;
    let mut next: Vec<Mono> = Vec::with_capacity(cur.len());
    while bounds.len() > 1 {
        next.clear();
        let mut merged = Vec::with_capacity(bounds.len().div_ceil(2));
        for pair in bounds.chunks(2) {
            let start = next.len();
            if let [(a0, a1), (b0, b1)] = *pair {
                let (a, b) = (&cur[a0..a1], &cur[b0..b1]);
                let (mut i, mut j) = (0, 0);
                while i < a.len() && j < b.len() {
                    if a[i] < b[j] {
                        next.push(a[i]);
                        i += 1;
                    } else {
                        next.push(b[j]);
                        j += 1;
                    }
                }
                next.extend_from_slice(&a[i..]);
                next.extend_from_slice(&b[j..]);
            } else {
                let (a0, a1) = pair[0];
                next.extend_from_slice(&cur[a0..a1]);
            }
            merged.push((start, next.len()));
        }
        std::mem::swap(&mut cur, &mut next);
        bounds = merged;
    }
    cur
}

fn prolong_degree() -> u32 {
    static D: std::sync::OnceLock<u32> = std::sync::OnceLock::new();
    *D.get_or_init(|| {
        std::env::var("KIC_WIDE_PROLONG")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0)
    })
}

enum Prolonged {
    Refuted,
    Nothing,
    Linear(Vec<WPoly>),
}

/// Most columns a prolongation may build before it is skipped.
const MAX_PROLONG_COLS: usize = 1 << 18;

/// Reduce the degree-`d` Macaulay matrix of `eqs` and return what it
/// adds: a `1`, or its linear rows, or nothing.
fn prolong(eqs: &[WPoly], d: u32, stats: &mut WideStats) -> Prolonged {
    let vars: u128 = eqs
        .iter()
        .flat_map(|p| p.terms.iter())
        .fold(0, |acc, &m| acc | m);
    let mut rows: Vec<WPoly> = eqs.to_vec();
    for p in eqs {
        if p.degree() >= d {
            continue;
        }
        let mut v = vars;
        while v != 0 {
            let b = v.trailing_zeros() as usize;
            v &= v - 1;
            let q = p.mul(&WPoly::var(b));
            if !q.is_zero() && q.degree() <= d {
                rows.push(q);
            }
        }
    }
    let mut all: Vec<Mono> = rows.iter().flat_map(|p| p.terms.iter().copied()).collect();
    all.sort_unstable();
    all.dedup();
    if all.len() > MAX_PROLONG_COLS {
        return Prolonged::Nothing;
    }
    let max_deg = all.iter().map(|m| m.count_ones()).max().unwrap_or(0) as usize;
    let mut start = vec![0usize; max_deg + 2];
    for m in &all {
        start[max_deg - m.count_ones() as usize + 1] += 1;
    }
    for i in 1..start.len() {
        start[i] += start[i - 1];
    }
    let mut cols = vec![0 as Mono; all.len()];
    let mut index: FxMap<Mono, usize> = FxMap::default();
    index.reserve(all.len());
    for &m in all.iter().rev() {
        let slot = &mut start[max_deg - m.count_ones() as usize];
        cols[*slot] = m;
        index.insert(m, *slot);
        *slot += 1;
    }
    let words = cols.len().div_ceil(64);
    let mut matrix: Vec<Vec<u64>> = rows
        .iter()
        .map(|p| {
            let mut row = vec![0u64; words];
            for m in &p.terms {
                let c = index[m];
                row[c / 64] |= 1 << (c % 64);
            }
            row
        })
        .collect();
    stats.reductions += 1;
    stats.max_rows = stats.max_rows.max(matrix.len());
    stats.max_cols = stats.max_cols.max(cols.len());
    let mut ops = 0;
    let rank = gf2_elim::eliminate(
        &mut matrix,
        cols.len(),
        true,
        gf2_elim::Config::from_env(),
        &mut ops,
    );
    let mut linear = Vec::new();
    for row in &matrix[..rank] {
        // Leading column: the first set bit; linear or constant rows
        // have it among the trailing (degree ≤ 1) columns.
        let lead = row
            .iter()
            .enumerate()
            .find(|(_, &w)| w != 0)
            .map(|(i, w)| i * 64 + w.trailing_zeros() as usize)
            .expect("rank row is nonzero");
        let deg = cols[lead].count_ones();
        if deg > 1 {
            continue;
        }
        let mut terms = Vec::new();
        for (w, &word) in row.iter().enumerate() {
            let mut bits = word;
            while bits != 0 {
                let b = bits.trailing_zeros() as usize;
                bits &= bits - 1;
                terms.push(cols[w * 64 + b]);
            }
        }
        let p = WPoly::from_monos(terms);
        if p.is_one() {
            return Prolonged::Refuted;
        }
        linear.push(p);
    }
    // Only rows the equations themselves did not already carry are news;
    // the caller's own-degree pass found no linear row, so any is.
    if linear.is_empty() {
        Prolonged::Nothing
    } else {
        Prolonged::Linear(linear)
    }
}

/// Decompose `target` into `m` factor-base points through the wide
/// chained system; `None` with `stats.exhausted` unset is a complete
/// search that found nothing, with it set says nothing.
///
/// When the whole chain needs more than [`MAX_WIDE_VARS`] unknowns, the
/// search takes the largest `k` trailing summands whose chain suffix
/// ([`WideSystem::build_suffix`]) fits, branches on those with the suffix
/// as the pruning system, and at each of its leaves decomposes the
/// remainder `target − ΣP_i` into the other `m − k` summands, by the
/// same function.
pub fn wide_groebner_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    node_budget: usize,
) -> (Option<Vec<usize>>, WideStats) {
    let mut stats = WideStats::default();
    let opts = SearchOptions::from_env();
    let valid = if opts.points {
        valid_coordinates(kc, fb, index_of)
    } else {
        Vec::new()
    };
    let found = decompose_rec(
        kc,
        fb,
        index_of,
        st,
        target,
        m,
        node_budget,
        &opts,
        &valid,
        &mut stats,
    );
    (found, stats)
}

/// Widest subspace whose coordinate vectors are listed for whole-summand
/// branching; past it the search branches bit by bit.
const MAX_POINT_BRANCH_ELL: usize = 20;

/// Every coordinate vector `c` of the factor-base subspace, ascending,
/// whose abscissa `Σ c_t·v_t` is a factor-base point's.  The rest — a
/// twist abscissa, or a point outside the base — can never be a summand.
fn valid_coordinates(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
) -> Vec<u32> {
    let ell = fb.subspace_basis.len();
    if ell > MAX_POINT_BRANCH_ELL {
        return Vec::new();
    }
    (0..1u32 << ell)
        .filter(|&c| {
            let x = summand_x(&fb.subspace_basis, ell, c as u128, 0, kc.n);
            points_with_x(&kc.curve, &x)
                .iter()
                .any(|p| index_of.contains_key(&point_key(p)))
        })
        .collect()
}

/// The search's switches, each a same-binary control read once per call.
#[derive(Clone, Copy)]
struct SearchOptions {
    /// Only summands in non-decreasing order (`KIC_WIDE_ORDER=0` off).
    order: bool,
    /// Each summand from its highest coordinate (`KIC_WIDE_BRANCH=low` off).
    high_first: bool,
    /// Look the last summand up instead of branching (`KIC_WIDE_FINISH=0` off).
    finish: bool,
    /// Branch on a whole summand at a time, over the coordinate vectors
    /// whose abscissa is a factor-base point's (`KIC_WIDE_POINTS=0` off:
    /// one summand bit at a time).
    points: bool,
    /// Widest system built in one piece; above it the suffix recursion
    /// takes over.  [`MAX_WIDE_VARS`] except in tests, which lower it to
    /// reach the recursion on small curves.
    max_vars: usize,
}

impl SearchOptions {
    fn from_env() -> Self {
        Self {
            order: std::env::var("KIC_WIDE_ORDER").as_deref() != Ok("0"),
            high_first: std::env::var("KIC_WIDE_BRANCH").as_deref() != Ok("low"),
            finish: std::env::var("KIC_WIDE_FINISH").as_deref() != Ok("0"),
            points: std::env::var("KIC_WIDE_POINTS").as_deref() != Ok("0"),
            max_vars: MAX_WIDE_VARS,
        }
    }
}

fn decompose_rec(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    node_budget: usize,
    opts: &SearchOptions,
    valid: &[u32],
    stats: &mut WideStats,
) -> Option<Vec<usize>> {
    if m == 0 {
        return (*target == BinaryPoint::Infinity).then(Vec::new);
    }
    if m == 1 {
        return index_of.get(&point_key(target)).map(|&i| vec![i]);
    }
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return None,
    };
    let ell = fb.subspace_basis.len();
    let full_vars = m * ell + (m - 2) * st.n as usize;
    let whole = if full_vars <= opts.max_vars {
        WideSystem::build(&fb.subspace_basis, &x_r, &kc.curve.b, m, st)
    } else {
        None
    };
    if let Some(sys) = whole {
        // The whole chain fits: its leaves finish the decomposition.
        let ell = sys.ell;
        let finish_head = opts.finish.then_some(m - 1);
        return search(
            &sys,
            m,
            finish_head,
            node_budget,
            opts,
            valid,
            stats,
            &|values, is_head, _stats| {
                let count = if is_head { m - 1 } else { m };
                let xs: Vec<F2mElement> = (0..count)
                    .map(|i| summand_x(&fb.subspace_basis, ell, values, i, kc.n))
                    .collect();
                if is_head {
                    finish_last(kc, fb, index_of, &xs, target)
                } else {
                    lift_candidate(kc, fb, index_of, &xs, target)
                }
            },
        );
    }
    // Too wide: prune with the longest chain suffix that fits.
    let k = (1..m - 1)
        .rev()
        .find(|&k| k * (ell + st.n as usize) <= opts.max_vars)?;
    let sys = WideSystem::build_suffix(&fb.subspace_basis, &x_r, &kc.curve.b, k, st)?;
    search(
        &sys,
        k,
        None,
        node_budget,
        opts,
        valid,
        stats,
        &|values, _is_head, stats| {
            // The k trailing summands are known up to sign: for each
            // choice of base points, decompose what is left.  In order,
            // they are the k largest, so the rest are at most the least
            // of them (summand 0, when the order test is on).
            let head_valid = if opts.order && !valid.is_empty() {
                let least = (values & ((1u128 << ell) - 1)) as u32;
                &valid[..valid.partition_point(|&c| c <= least)]
            } else {
                valid
            };
            if !valid.is_empty() && head_valid.is_empty() {
                return None;
            }
            let choices: Vec<Vec<usize>> = (0..k)
                .map(|i| {
                    let x = summand_x(&fb.subspace_basis, ell, values, i, kc.n);
                    points_with_x(&kc.curve, &x)
                        .iter()
                        .filter_map(|p| index_of.get(&point_key(p)).copied())
                        .collect()
                })
                .collect();
            if choices.iter().any(Vec::is_empty) {
                return None;
            }
            let mut pick = vec![0usize; k];
            loop {
                let chosen: Vec<usize> = (0..k).map(|i| choices[i][pick[i]]).collect();
                let rest = chosen.iter().fold(target.clone(), |acc, &i| {
                    kc.add(&acc, &negate(&fb.points[i]))
                });
                if let Some(mut head) = decompose_rec(
                    kc,
                    fb,
                    index_of,
                    st,
                    &rest,
                    m - k,
                    node_budget,
                    opts,
                    head_valid,
                    stats,
                ) {
                    head.extend(chosen);
                    return Some(head);
                }
                if stats.exhausted {
                    return None;
                }
                // Next sign pattern.
                let mut i = 0;
                loop {
                    if i == k {
                        return None;
                    }
                    pick[i] += 1;
                    if pick[i] < choices[i].len() {
                        break;
                    }
                    pick[i] = 0;
                    i += 1;
                }
            }
        },
    )
}

/// `−P` on a binary curve: `(x, x + y)`.
fn negate(p: &BinaryPoint) -> BinaryPoint {
    match p {
        BinaryPoint::Affine { x, y } => BinaryPoint::Affine {
            x: x.clone(),
            y: x.add(y),
        },
        BinaryPoint::Infinity => BinaryPoint::Infinity,
    }
}

/// Summand `i`'s abscissa under an assignment of the summand bits.
fn summand_x(basis: &[F2mElement], ell: usize, bits: u128, i: usize, n: u32) -> F2mElement {
    let mut acc = 0u64;
    for t in 0..ell {
        if bits >> (i * ell + t) & 1 == 1 {
            acc ^= basis[t].raw_bits().first().copied().unwrap_or(0);
        }
    }
    let positions: Vec<u32> = (0..n).filter(|&k| acc >> k & 1 == 1).collect();
    F2mElement::from_bit_positions(&positions, n)
}

/// One search frame: the node's system, its substitutions, and which
/// summand bits it has fixed to which values.
struct Frame {
    eqs: Vec<WPoly>,
    subs: Vec<(usize, WPoly)>,
    fixed: u128,
    values: u128,
}

/// What processing one node gave.
enum Step {
    /// No root below: refuted by the linearisation or the order test.
    Closed,
    /// A leaf: `is_head` for the last-summand shortcut.
    Leaf { values: u128, is_head: bool },
    /// Children, pushed in this order (the last is explored first).
    Split(Vec<Frame>),
}

/// The search's fixed shape, shared by every thread.
struct Shape<'a> {
    count: usize,
    ell: usize,
    head_mask: Option<u128>,
    opts: &'a SearchOptions,
    /// [`valid_coordinates`]; empty for bit-by-bit branching.
    valid: &'a [u32],
}

impl Shape<'_> {
    fn step(&self, mut f: Frame, stats: &mut WideStats) -> Step {
        let (count, ell) = (self.count, self.ell);
        let summand_vars = count * ell;
        if !linearise(&mut f.eqs, stats, &mut f.subs) {
            stats.refuted += 1;
            return Step::Closed;
        }
        // Summand bits fixed by substitution to constants count as fixed.
        let mut fixed = f.fixed;
        let mut values = f.values;
        for (v, form) in &f.subs {
            if *v < summand_vars && form.terms.iter().all(|&m| m == 0) {
                fixed |= 1u128 << v;
                if form.is_one() {
                    values |= 1u128 << v;
                }
            }
        }
        if self.opts.order && !summands_ordered(fixed, values, count, ell) {
            stats.refuted += 1;
            return Step::Closed;
        }
        let summand_mask = (1u128 << ell) - 1;
        let valid = !self.valid.is_empty();
        if valid {
            // A summand the linearisation fixed outright must be a base
            // point's abscissa.
            let bad = (0..count).any(|i| {
                fixed >> (i * ell) & summand_mask == summand_mask
                    && self
                        .valid
                        .binary_search(&((values >> (i * ell) & summand_mask) as u32))
                        .is_err()
            });
            if bad {
                stats.refuted += 1;
                return Step::Closed;
            }
        }
        if let Some(mask) = self.head_mask {
            if fixed & mask == mask {
                return Step::Leaf {
                    values,
                    is_head: true,
                };
            }
        }
        // Each summand from its highest coordinate down, so the order
        // test above decides as early as it can.
        if valid {
            let Some(i) = (0..count).find(|&i| fixed >> (i * ell) & summand_mask != summand_mask)
            else {
                return Step::Leaf {
                    values,
                    is_head: false,
                };
            };
            let fixed_i = (fixed >> (i * ell) & summand_mask) as u32;
            let values_i = (values >> (i * ell) & summand_mask) as u32;
            // Summands are in non-decreasing order: at least the previous.
            let low = if self.opts.order && i > 0 {
                (values >> ((i - 1) * ell) & summand_mask) as u32
            } else {
                0
            };
            let start = self.valid.partition_point(|&c| c < low);
            let children: Vec<Frame> = self.valid[start..]
                .iter()
                .rev()
                .filter(|&&c| c & fixed_i == values_i & fixed_i)
                .map(|&c| {
                    let free = !fixed_i & summand_mask as u32;
                    let assignment: Vec<(usize, bool)> = (0..ell)
                        .filter(|&t| free >> t & 1 == 1)
                        .map(|t| (i * ell + t, c >> t & 1 == 1))
                        .collect();
                    assign(&f, fixed, values, &assignment)
                })
                .collect();
            if children.is_empty() {
                stats.refuted += 1;
                return Step::Closed;
            }
            return Step::Split(children);
        }
        let next = if self.opts.high_first {
            (0..count)
                .flat_map(|i| (0..ell).rev().map(move |t| i * ell + t))
                .find(|&v| fixed >> v & 1 == 0)
        } else {
            (0..summand_vars).find(|&v| fixed >> v & 1 == 0)
        };
        let Some(v) = next else {
            return Step::Leaf {
                values,
                is_head: false,
            };
        };
        Step::Split(vec![
            assign(&f, fixed, values, &[(v, true)]),
            assign(&f, fixed, values, &[(v, false)]),
        ])
    }
}

/// `f` with each summand bit `(v, value)` set to a constant.  A bit the
/// linearisation already eliminated as `v = g` keeps that constraint as
/// the equation `g + value`, rather than dropping it.
fn assign(f: &Frame, mut fixed: u128, mut values: u128, assignment: &[(usize, bool)]) -> Frame {
    let (mut zeros, mut ones) = (0u128, 0u128);
    for &(v, value) in assignment {
        if value {
            ones |= 1u128 << v;
        } else {
            zeros |= 1u128 << v;
        }
    }
    let mut eqs: Vec<WPoly> = f
        .eqs
        .iter()
        .map(|p| p.assign_constants(zeros, ones))
        .collect();
    let mut subs: Vec<(usize, WPoly)> = f
        .subs
        .iter()
        .map(|(u, g)| (*u, g.assign_constants(zeros, ones)))
        .collect();
    for &(v, value) in assignment {
        let form = if value { WPoly::one() } else { WPoly::zero() };
        if let Some((_, g)) = subs.iter().find(|(u, _)| *u == v) {
            eqs.push(g.add(&form));
        }
    }
    for &(v, value) in assignment {
        subs.push((v, if value { WPoly::one() } else { WPoly::zero() }));
        fixed |= 1u128 << v;
        if value {
            values |= 1u128 << v;
        }
    }
    eqs.retain(|p| !p.is_zero());
    Frame {
        eqs,
        subs,
        fixed,
        values,
    }
}

/// Subtrees handed to each thread, about: the tree is expanded breadth
/// first until it has this many per thread, then searched in parallel.
const SUBTREES_PER_THREAD: usize = 16;

type Leaf<'a> = dyn Fn(u128, bool, &mut WideStats) -> Option<Vec<usize>> + Sync + 'a;

/// Depth-first over the summand bits of `sys` (`count` summands), each
/// node linearised.  A node whose first `head` summands are all fixed is
/// handed to `leaf` with `is_head = true` (the last-summand shortcut); a
/// node with every summand fixed, with `false`.  `leaf` returning `Some`
/// ends the search.
///
/// The tree is first expanded breadth-first, serially, into a frontier of
/// about [`SUBTREES_PER_THREAD`] subtrees a thread; the subtrees are then
/// searched in parallel, sharing the node budget and a stop flag.  The
/// first decomposition any thread finds is returned — which one, when
/// several exist, can differ between runs; every one is verified.
fn search(
    sys: &WideSystem,
    count: usize,
    head: Option<usize>,
    node_budget: usize,
    opts: &SearchOptions,
    valid: &[u32],
    stats: &mut WideStats,
    leaf: &Leaf<'_>,
) -> Option<Vec<usize>> {
    use rayon::prelude::*;
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

    let ell = sys.ell;
    let shape = Shape {
        count,
        ell,
        head_mask: head.map(|h| {
            let bits = h * ell;
            if bits >= 128 {
                u128::MAX
            } else {
                (1u128 << bits) - 1
            }
        }),
        opts,
        valid: if ell <= MAX_POINT_BRANCH_ELL {
            valid
        } else {
            &[]
        },
    };
    let nodes = AtomicUsize::new(stats.nodes);
    let stop = AtomicBool::new(false);
    // Serial breadth-first expansion into a frontier.
    let want = SUBTREES_PER_THREAD * rayon::current_num_threads().max(1);
    let mut frontier = vec![Frame {
        eqs: sys.equations.clone(),
        subs: Vec::new(),
        fixed: 0,
        values: 0,
    }];
    while !frontier.is_empty() && frontier.len() < want {
        let mut next = Vec::with_capacity(frontier.len() * 2);
        for f in frontier {
            if nodes.fetch_add(1, Ordering::Relaxed) >= node_budget {
                stats.exhausted = true;
                stats.nodes = nodes.load(Ordering::Relaxed);
                return None;
            }
            match shape.step(f, stats) {
                Step::Closed => {}
                Step::Leaf { values, is_head } => {
                    stats.leaves += 1;
                    if let Some(found) = leaf(values, is_head, stats) {
                        stats.nodes = nodes.load(Ordering::Relaxed);
                        return Some(found);
                    }
                    if stats.exhausted {
                        return None;
                    }
                }
                Step::Split(children) => next.extend(children.into_iter().rev()),
            }
        }
        frontier = next;
    }
    // Each subtree depth-first, in parallel.
    let results: Vec<(Option<Vec<usize>>, WideStats)> = frontier
        .into_par_iter()
        .with_max_len(1)
        .map(|root| {
            let mut local = WideStats::default();
            let mut stack = vec![root];
            while let Some(f) = stack.pop() {
                if stop.load(Ordering::Relaxed) {
                    break;
                }
                if nodes.fetch_add(1, Ordering::Relaxed) >= node_budget {
                    local.exhausted = true;
                    stop.store(true, Ordering::Relaxed);
                    break;
                }
                match shape.step(f, &mut local) {
                    Step::Closed => {}
                    Step::Leaf { values, is_head } => {
                        local.leaves += 1;
                        if let Some(found) = leaf(values, is_head, &mut local) {
                            stop.store(true, Ordering::Relaxed);
                            return (Some(found), local);
                        }
                        if local.exhausted {
                            stop.store(true, Ordering::Relaxed);
                            break;
                        }
                    }
                    Step::Split(children) => stack.extend(children),
                }
            }
            (None, local)
        })
        .collect();
    let mut found = None;
    for (r, local) in results {
        stats.reductions += local.reductions;
        stats.refuted += local.refuted;
        stats.leaves += local.leaves;
        stats.max_rows = stats.max_rows.max(local.max_rows);
        stats.max_cols = stats.max_cols.max(local.max_cols);
        stats.exhausted |= local.exhausted;
        if found.is_none() {
            found = r;
        }
    }
    stats.nodes = nodes.load(Ordering::Relaxed);
    if found.is_some() {
        // A decomposition was found: the budget running out elsewhere
        // does not make this answer incomplete.
        stats.exhausted = false;
    }
    found
}

/// With the abscissae of all but the last summand known, find the last:
/// for every choice of factor-base points with those abscissae (each is
/// one of `±P`), the remainder `target − ΣP_i` must itself be a base
/// point.  Returns the indices, last summand included.
fn finish_last(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    xs: &[F2mElement],
    target: &BinaryPoint,
) -> Option<Vec<usize>> {
    let choices: Vec<Vec<usize>> = xs
        .iter()
        .map(|x| {
            points_with_x(&kc.curve, x)
                .iter()
                .filter_map(|p| index_of.get(&point_key(p)).copied())
                .collect()
        })
        .collect();
    if choices.iter().any(Vec::is_empty) {
        return None;
    }
    fn walk(
        kc: &KoblitzCurve,
        fb: &FrobeniusFactorBase,
        index_of: &HashMap<(BigUint, BigUint), usize>,
        choices: &[Vec<usize>],
        depth: usize,
        rest: &BinaryPoint,
        chosen: &mut Vec<usize>,
    ) -> bool {
        if depth == choices.len() {
            if let Some(&last) = index_of.get(&point_key(rest)) {
                chosen.push(last);
                return true;
            }
            return false;
        }
        for &i in &choices[depth] {
            let neg = negate(&fb.points[i]);
            chosen.push(i);
            if walk(
                kc,
                fb,
                index_of,
                choices,
                depth + 1,
                &kc.add(rest, &neg),
                chosen,
            ) {
                return true;
            }
            chosen.pop();
        }
        false
    }
    let mut chosen = Vec::with_capacity(xs.len() + 1);
    walk(kc, fb, index_of, &choices, 0, target, &mut chosen).then_some(chosen)
}

/// Whether the fixed bits already contradict `x_0 ≤ x_1 ≤ … ≤ x_{m−1}`,
/// comparing each adjacent pair from its highest coordinate down:
/// `false` only on a definite violation — the first coordinate where both
/// are fixed and differ has the earlier summand's bit set and the later
/// one's clear, with every higher coordinate fixed and equal in both.
fn summands_ordered(fixed: u128, values: u128, m: usize, ell: usize) -> bool {
    for i in 1..m {
        let (lo, hi) = ((i - 1) * ell, i * ell);
        for t in (0..ell).rev() {
            let (a, b) = (lo + t, hi + t);
            if fixed >> a & 1 == 0 || fixed >> b & 1 == 0 {
                break;
            }
            let (va, vb) = (values >> a & 1, values >> b & 1);
            if va != vb {
                if va > vb {
                    return false;
                }
                break;
            }
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::build_decomposition_system;
    use crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base;
    use rand::{rngs::StdRng, Rng, SeedableRng};

    #[test]
    fn wide_system_matches_the_64_bit_builder() {
        // Where both fit, the equations are the same polynomials.
        for (a, n, m) in [
            (0u8, 9u32, 2usize),
            (0, 9, 3),
            (1, 17, 2),
            (0, 13, 3),
            (0, 9, 4),
        ] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let x = match kc.mul(kc.generator(), &BigUint::from(4242u32)) {
                BinaryPoint::Affine { x, .. } => x,
                _ => unreachable!(),
            };
            let Some(narrow) =
                build_decomposition_system(&fb.subspace_basis, &x, &kc.curve.b, m, &st)
            else {
                continue;
            };
            let wide = WideSystem::build(&fb.subspace_basis, &x, &kc.curve.b, m, &st).unwrap();
            assert_eq!(wide.n_vars, narrow.n_vars);
            let mut want: Vec<Vec<Mono>> = narrow
                .equations
                .iter()
                .filter(|p| !p.terms.is_empty())
                .map(|p| {
                    let mut t: Vec<Mono> = p.terms.iter().map(|m| u128::from(m.mask)).collect();
                    t.sort_unstable();
                    t
                })
                .collect();
            let mut got: Vec<Vec<Mono>> = wide.equations.iter().map(|p| p.terms.clone()).collect();
            want.sort();
            got.sort();
            assert_eq!(got, want, "K_{a}/2^{n} m={m}");
        }
    }

    #[test]
    fn substitution_and_arithmetic_agree_with_evaluation() {
        let mut rng = StdRng::seed_from_u64(5);
        for _ in 0..200 {
            let rand_poly = |rng: &mut StdRng| {
                WPoly::from_monos(
                    (0..rng.gen_range(0..8))
                        .map(|_| {
                            (0..3).fold(0u128, |m, _| {
                                if rng.gen_bool(0.7) {
                                    m | 1u128 << rng.gen_range(0..100)
                                } else {
                                    m
                                }
                            })
                        })
                        .collect(),
                )
            };
            let (p, q) = (rand_poly(&mut rng), rand_poly(&mut rng));
            let v = rng.gen_range(0..100);
            let form = WPoly::from_monos(vec![0, 1u128 << rng.gen_range(0..100)]);
            for _ in 0..20 {
                let bits: u128 = rng.gen();
                assert_eq!(p.add(&q).eval(bits), p.eval(bits) ^ q.eval(bits));
                assert_eq!(p.mul(&q).eval(bits), p.eval(bits) & q.eval(bits));
                // Substituting then evaluating is evaluating with v set to form(bits).
                let fv = form.eval(bits);
                let with = if fv {
                    bits | 1u128 << v
                } else {
                    bits & !(1u128 << v)
                };
                assert_eq!(p.substitute(v, &form).eval(bits), p.eval(with));
                // The constant fast paths.
                for (c, set) in [(WPoly::zero(), false), (WPoly::one(), true)] {
                    let with = if set {
                        bits | 1u128 << v
                    } else {
                        bits & !(1u128 << v)
                    };
                    assert_eq!(p.substitute(v, &c).eval(bits), p.eval(with));
                }
                // Several affine forms at once, none naming a substituted
                // variable.
                {
                    let (u, w) = (rng.gen_range(100..110), rng.gen_range(110..120));
                    let fu = WPoly::from_monos(vec![0, 1u128 << rng.gen_range(0..100)]);
                    let fw = WPoly::from_monos(vec![1u128 << rng.gen_range(0..100)]);
                    let mut forms: Vec<&[Mono]> = vec![&[]; MAX_WIDE_VARS];
                    forms[u] = &fu.terms;
                    forms[w] = &fw.terms;
                    let r = WPoly::from_monos(
                        p.terms
                            .iter()
                            .map(|&m| {
                                m | if m & 1 == 1 { 1u128 << u } else { 0 }
                                    | if m & 2 == 2 { 1u128 << w } else { 0 }
                            })
                            .collect(),
                    );
                    let expect = r.substitute(u, &fu).substitute(w, &fw);
                    assert_eq!(r.substitute_all(1u128 << u | 1u128 << w, &forms), expect);
                }
                // Several constants at once.
                let (zeros, ones) = {
                    let a: u128 = rng.gen::<u128>() & rng.gen::<u128>();
                    let z: u128 = rng.gen::<u128>() & rng.gen::<u128>() & !a;
                    (z, a)
                };
                assert_eq!(
                    p.assign_constants(zeros, ones).eval(bits),
                    p.eval((bits | ones) & !zeros)
                );
            }
        }
    }

    #[test]
    fn degree_runs_merge_to_ascending_order() {
        let mut rng = StdRng::seed_from_u64(9);
        for _ in 0..200 {
            let mut monos: Vec<Mono> = (0..rng.gen_range(0..40))
                .map(|_| {
                    (0..rng.gen_range(0..4)).fold(0u128, |m, _| m | 1u128 << rng.gen_range(0..128))
                })
                .collect();
            monos.sort_unstable();
            monos.dedup();
            let mut column_order = monos.clone();
            column_order.sort_by_key(|m| (std::cmp::Reverse(m.count_ones()), *m));
            let mut runs: Vec<usize> = (1..column_order.len())
                .filter(|&i| column_order[i].count_ones() != column_order[i - 1].count_ones())
                .collect();
            runs.push(column_order.len());
            assert_eq!(merge_degree_runs(column_order, &runs), monos);
        }
    }

    #[test]
    fn the_order_test_refuses_only_definite_violations() {
        let ell = 3;
        // Summand 0 = 0b101, summand 1 = 0b011: 5 > 3, a violation.
        let all = 0b111_111u128;
        assert!(!summands_ordered(all, 0b011_101, 2, ell));
        assert!(summands_ordered(all, 0b101_011, 2, ell));
        assert!(summands_ordered(all, 0b101_101, 2, ell)); // equal is allowed
                                                           // Top bits differ in the violating direction but a lower bit is
                                                           // unfixed: still a violation, the top bit decides.
        assert!(!summands_ordered(0b100_100, 0b000_100, 2, ell));
        // Top bit of the later summand unfixed: undecided, not refused.
        assert!(summands_ordered(0b000_111, 0b000_101, 2, ell));
    }

    #[test]
    fn the_suffix_recursion_finds_planted_decompositions() {
        // Force the recursion on a small curve by lowering the one-piece
        // cap below the whole chain: at n = 9, m = 4 the chain has
        // 4l + 18 unknowns, the suffix k(l + 9).
        for (a, n, m) in [(0u8, 9u32, 4usize), (0, 9, 5), (1, 17, 3)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let index_of = fb.index_map();
            let ell = fb.subspace_basis.len();
            let opts = SearchOptions {
                max_vars: m * ell + (m - 2) * n as usize - 1,
                ..SearchOptions::from_env()
            };
            let mut rng = StdRng::seed_from_u64(91 + n as u64 + m as u64);
            for _ in 0..4 {
                let t = (0..m).fold(BinaryPoint::Infinity, |acc, _| {
                    kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
                });
                if t == BinaryPoint::Infinity {
                    continue;
                }
                let mut stats = WideStats::default();
                let valid = valid_coordinates(&kc, &fb, &index_of);
                let idxs = decompose_rec(
                    &kc,
                    &fb,
                    &index_of,
                    &st,
                    &t,
                    m,
                    1 << 22,
                    &opts,
                    &valid,
                    &mut stats,
                )
                .unwrap_or_else(|| panic!("K_{a}/2^{n} m={m}: missed, {stats:?}"));
                assert_eq!(idxs.len(), m);
                let sum = idxs
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(sum, t, "K_{a}/2^{n} m={m}");
            }
        }
    }

    #[test]
    fn finds_planted_decompositions_on_small_curves() {
        for (a, n, m) in [(0u8, 9u32, 2usize), (0, 9, 3), (1, 17, 2)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            let index_of = fb.index_map();
            let mut rng = StdRng::seed_from_u64(77 + n as u64);
            for _ in 0..6 {
                let t = (0..m).fold(BinaryPoint::Infinity, |acc, _| {
                    kc.add(&acc, &fb.points[rng.gen_range(0..fb.points.len())])
                });
                if t == BinaryPoint::Infinity {
                    continue;
                }
                let (found, stats) =
                    wide_groebner_decompose(&kc, &fb, &index_of, &st, &t, m, 1 << 20);
                let idxs = found.unwrap_or_else(|| panic!("K_{a}/2^{n} m={m}: missed, {stats:?}"));
                let sum = idxs
                    .iter()
                    .fold(BinaryPoint::Infinity, |s, &i| kc.add(&s, &fb.points[i]));
                assert_eq!(sum, t);
            }
        }
    }
}
