//! Degree-bounded F4 over a small prime field `F_p`.
//!
//! The coordinate thread (`research/notes/index-calculus/RESEARCH_EXOTIC_COORDINATES.md` §12.4, §13.5)
//! ended on systems the repo's Buchberger (`groebner_f4::buchberger`, a
//! textbook Buchberger over `BigUint` field elements) could not finish:
//! three or four unknowns over `F₂₉` or `F₃₁`, equations of total degree
//! 4 to 12 with up to 125 terms.  This module is the tool that row of the
//! table asked for.
//!
//! ## What it is
//!
//! Faugère's F4 with the normal (degree-by-degree) selection strategy and
//! a **degree bound** `D`: critical pairs whose lcm has degree above `D`
//! are never formed, so the result is the degree-`D` truncation of the
//! Gröbner basis — enough to decide consistency and, for a zero-
//! dimensional ideal, to solve, whenever the solving degree is at most
//! `D`.  Each step builds one matrix by symbolic preprocessing (the pair
//! multiples plus one reducer per reducible monomial) and keeps the rows
//! of its reduced echelon form whose leading monomial is new.  The
//! reducers already have distinct leading monomials, so the step reduces
//! each (sparse) pair row by them alone and takes the dense reduced
//! echelon form of only what is left, on the columns no reducer leads —
//! the same rows the whole matrix's echelon form would give, from a much
//! smaller dense block.  Rows run in parallel once a step is large enough
//! to repay the dispatch.  The product criterion prunes pairs;
//! polynomials whose leading monomial becomes divisible by a new one are
//! dropped.
//!
//! Solving ([`solve`]) is by substitution: after a basis at degree `D`,
//! a univariate element (when the basis has one) is factored by root
//! finding over `F_p`, each root substituted, and the smaller system run
//! again; without a univariate element every value of the first variable
//! is tried (`p` small).  Each run reports the degree at which the
//! system resolved — the number to compare across coordinate systems —
//! and stops cooperatively at a deadline, so a budget never leaves a
//! thread behind.
//!
//! ## Honest scope
//!
//! Small primes (`p < 2³²`), a few unknowns, degrees in the tens: the
//! residual matrices are dense.  No Gebauer–Möller chain criterion, no F5
//! signatures, no sugar; this is the plain algorithm, written so that
//! the descent systems of the coordinate thread can be timed at `m = 3`.

use std::collections::{BTreeMap, HashSet};
use std::time::{Duration, Instant};

use rayon::prelude::*;

use super::fx_hash::{FxMap, FxSet};
use super::groebner_f4::cmp_monomial;
pub use super::groebner_f4::Ordering;

/// A polynomial over `F_p`: `(exponent vector, coefficient)` terms with
/// non-zero coefficients, sorted with the leading term first.
pub type Poly = Vec<(Vec<u32>, u64)>;

// ── Field arithmetic ───────────────────────────────────────────────

#[inline]
fn mulmod(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn invmod(a: u64, p: u64) -> u64 {
    // p prime, a != 0
    let mut r = 1u64;
    let mut base = a % p;
    let mut e = p - 2;
    while e > 0 {
        if e & 1 == 1 {
            r = mulmod(r, base, p);
        }
        base = mulmod(base, base, p);
        e >>= 1;
    }
    r
}

/// Reduction modulo a fixed `p < 2³²` by Barrett's method: a precomputed
/// `⌊2⁶⁴/p⌋` turns each remainder in the eliminations into a high
/// multiply and at most one subtraction, instead of a hardware division
/// by a `p` known only at run time.
#[derive(Clone, Copy)]
struct Barrett {
    p: u64,
    m: u64,
}

impl Barrett {
    fn new(p: u64) -> Self {
        assert!(
            (2..1 << 32).contains(&p),
            "f4_fp: the prime must be below 2^32"
        );
        Barrett {
            p,
            m: (u128::from(u64::MAX) + 1).div_euclid(u128::from(p)) as u64,
        }
    }
    /// `x mod p` for any `x < 2⁶⁴`: `q = ⌊x·m/2⁶⁴⌋` undershoots `⌊x/p⌋`
    /// by at most one.
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
}

// ── Polynomial helpers ─────────────────────────────────────────────

fn total_degree(m: &[u32]) -> u32 {
    m.iter().sum()
}

/// Normalise: merge duplicate monomials, drop zeros, sort leading-first,
/// make monic.
pub fn normalise(terms: &[(Vec<u32>, u64)], p: u64, ord: Ordering) -> Poly {
    let mut map: BTreeMap<Vec<u32>, u64> = BTreeMap::new();
    for (e, c) in terms {
        let c = c % p;
        if c == 0 {
            continue;
        }
        let v = map.entry(e.clone()).or_insert(0);
        *v = (*v + c) % p;
    }
    let mut out: Poly = map.into_iter().filter(|(_, c)| *c != 0).collect();
    out.sort_by(|(a, _), (b, _)| cmp_monomial(b, a, ord));
    if let Some((_, lc)) = out.first() {
        let inv = invmod(*lc, p);
        for (_, c) in out.iter_mut() {
            *c = mulmod(*c, inv, p);
        }
    }
    out
}

fn divides(a: &[u32], b: &[u32]) -> bool {
    a.iter().zip(b).all(|(x, y)| x <= y)
}

/// Render a polynomial with variable names.
pub fn render(f: &Poly, names: &[String], p: u64) -> String {
    if f.is_empty() {
        return "0".to_string();
    }
    f.iter()
        .map(|(e, c)| {
            let mono: Vec<String> = e
                .iter()
                .enumerate()
                .filter(|(_, &k)| k > 0)
                .map(|(i, &k)| {
                    if k == 1 {
                        names[i].clone()
                    } else {
                        format!("{}^{}", names[i], k)
                    }
                })
                .collect();
            let cs = if *c > p / 2 {
                format!("−{}", p - c)
            } else {
                c.to_string()
            };
            if mono.is_empty() {
                cs
            } else if *c == 1 {
                mono.join("·")
            } else {
                format!("{cs}·{}", mono.join("·"))
            }
        })
        .collect::<Vec<_>>()
        .join(" + ")
}

// ── The algorithm ──────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct F4Options {
    pub order: Ordering,
    /// Critical pairs with lcm degree above this are never formed.
    pub max_degree: u32,
    /// Cooperative stop: the run returns `timed_out` once past it.
    pub deadline: Option<Instant>,
}

impl F4Options {
    pub fn new(order: Ordering, max_degree: u32) -> Self {
        F4Options {
            order,
            max_degree,
            deadline: None,
        }
    }
    pub fn with_budget(mut self, budget: Duration) -> Self {
        self.deadline = Some(Instant::now() + budget);
        self
    }
}

#[derive(Clone, Debug)]
pub struct F4Report {
    /// The (interreduced) degree-bounded basis, `[1]` when inconsistent.
    pub basis: Vec<Poly>,
    pub inconsistent: bool,
    /// Highest pair degree processed.
    pub degree_reached: u32,
    /// Degree of the step at which `1` appeared, or at which the last
    /// new basis element was found.
    pub solving_degree: u32,
    pub steps: usize,
    pub max_rows: usize,
    pub max_cols: usize,
    pub ms: f64,
    pub timed_out: bool,
    /// Pairs dropped because their lcm degree exceeded the bound: `> 0`
    /// means the basis may be a strict truncation.
    pub pairs_above_bound: usize,
}

struct Pair {
    i: usize,
    j: usize,
    lcm: Vec<u32>,
    degree: u32,
}

/// Rows × columns of remaining elimination work below which a pivot's
/// elimination runs on one thread: under it, rayon's dispatch costs more
/// than the arithmetic it spreads.
const PAR_WORK: usize = 1 << 15;

/// Subtract `f · pivot` from `row` over the columns `from..`, with
/// `f = row[col]`.  `p < 2³²`, so `x + (p − f)·y < 2⁶⁴` fits a `u64`
/// and one Barrett reduction replaces the `u128` remainder of [`mulmod`].
#[inline]
fn eliminate(row: &mut [u64], pivot: &[u64], col: usize, fp: Barrett) {
    let f = row[col];
    if f == 0 {
        return;
    }
    let neg = fp.p - f;
    for (x, &y) in row[col..].iter_mut().zip(&pivot[col..]) {
        if y != 0 {
            *x = fp.reduce(*x + neg * y);
        }
    }
}

/// Row-reduce `rows` (dense, entries in `[0, p)`) to reduced echelon form
/// in place: zero rows are dropped, the rest sorted by pivot column, whose
/// list is returned.  `None` when the deadline passed first.
fn rref(rows: &mut Vec<Vec<u64>>, fp: Barrett, deadline: Option<Instant>) -> Option<Vec<usize>> {
    let p = fp.p;
    let n_cols = rows.first().map_or(0, |r| r.len());
    let mut pivots: Vec<usize> = Vec::new();
    let mut pr = 0usize;
    // forward: echelon form
    for c in 0..n_cols {
        if pr >= rows.len() {
            break;
        }
        if c % 32 == 0 && deadline.is_some_and(|d| Instant::now() > d) {
            return None;
        }
        let Some(r) = (pr..rows.len()).find(|&r| rows[r][c] != 0) else {
            continue;
        };
        rows.swap(pr, r);
        let inv = invmod(rows[pr][c], p);
        for x in rows[pr][c..].iter_mut() {
            if *x != 0 {
                *x = fp.reduce(*x * inv);
            }
        }
        let (head, tail) = rows.split_at_mut(pr + 1);
        let prow = &head[pr];
        if tail.len() * (n_cols - c) > PAR_WORK {
            tail.par_iter_mut()
                .for_each(|row| eliminate(row, prow, c, fp));
        } else {
            tail.iter_mut().for_each(|row| eliminate(row, prow, c, fp));
        }
        pivots.push(c);
        pr += 1;
    }
    rows.truncate(pr);
    // backward: clear each pivot column above its pivot
    for i in (1..pr).rev() {
        if deadline.is_some_and(|d| Instant::now() > d) {
            return None;
        }
        let c = pivots[i];
        let (head, tail) = rows.split_at_mut(i);
        let prow = &tail[0];
        if head.len() * (n_cols - c) > PAR_WORK {
            head.par_iter_mut()
                .for_each(|row| eliminate(row, prow, c, fp));
        } else {
            head.iter_mut().for_each(|row| eliminate(row, prow, c, fp));
        }
    }
    Some(pivots)
}

/// Degree-bounded F4.
pub fn f4(input: &[Poly], n_vars: usize, p: u64, opts: &F4Options) -> F4Report {
    let t0 = Instant::now();
    let debug = std::env::var("F4_DEBUG").is_ok();
    if debug {
        eprintln!(
            "f4: {} polys in {n_vars} vars over F_{p}, degrees {:?}",
            input.len(),
            input
                .iter()
                .map(|f| f.iter().map(|(e, _)| total_degree(e)).max().unwrap_or(0))
                .collect::<Vec<_>>()
        );
    }
    let fp = Barrett::new(p);
    let ord = opts.order;
    let mut basis: Vec<Poly> = Vec::new();
    let mut alive: Vec<bool> = Vec::new();
    let mut pairs: Vec<Pair> = Vec::new();
    let mut pairs_above_bound = 0usize;
    let report = |basis: &[Poly], alive: &[bool], inconsistent, dr, sd, steps, mr, mc, to, pab| {
        let b: Vec<Poly> = if inconsistent {
            vec![vec![(vec![0; n_vars], 1)]]
        } else {
            basis
                .iter()
                .zip(alive)
                .filter(|(_, &a)| a)
                .map(|(f, _)| f.clone())
                .collect()
        };
        F4Report {
            basis: b,
            inconsistent,
            degree_reached: dr,
            solving_degree: sd,
            steps,
            max_rows: mr,
            max_cols: mc,
            ms: t0.elapsed().as_secs_f64() * 1e3,
            timed_out: to,
            pairs_above_bound: pab,
        }
    };

    // add a polynomial to the basis: pairs with the product criterion
    // and the degree bound; drop basis elements it makes redundant
    fn add(
        f: Poly,
        basis: &mut Vec<Poly>,
        alive: &mut Vec<bool>,
        pairs: &mut Vec<Pair>,
        max_degree: u32,
        pairs_above_bound: &mut usize,
    ) {
        let lm = f[0].0.clone();
        let k = basis.len();
        for i in 0..k {
            if !alive[i] {
                continue;
            }
            let lmi = &basis[i][0].0;
            if divides(&lm, lmi) {
                // `basis[i]` is redundant in the final basis, but its pair
                // with `f` must still be processed (Buchberger's criterion
                // is about the generating set, not the reduced one); only
                // its role as an output element ends here.
                alive[i] = false;
            }
            // product criterion: coprime leading monomials
            if lm.iter().zip(lmi).all(|(a, b)| *a == 0 || *b == 0) {
                continue;
            }
            let l: Vec<u32> = lm.iter().zip(lmi).map(|(a, b)| *a.max(b)).collect();
            let d = total_degree(&l);
            if d > max_degree {
                *pairs_above_bound += 1;
                continue;
            }
            pairs.push(Pair {
                i,
                j: k,
                lcm: l,
                degree: d,
            });
        }
        basis.push(f);
        alive.push(true);
    }

    for f in input {
        let f = normalise(f, p, ord);
        if f.is_empty() {
            continue;
        }
        if total_degree(&f[0].0) == 0 {
            return report(&basis, &alive, true, 0, 0, 0, 0, 0, false, 0);
        }
        add(
            f,
            &mut basis,
            &mut alive,
            &mut pairs,
            opts.max_degree,
            &mut pairs_above_bound,
        );
    }
    // interreduce the input (tails included) so the first matrix is small
    let mut steps = 0usize;
    let mut max_rows = 0usize;
    let mut max_cols = 0usize;
    let mut degree_reached = 0u32;
    let mut solving_degree = 0u32;

    while !pairs.is_empty() {
        if debug {
            eprintln!("f4: {} pairs pending, basis {}", pairs.len(), basis.len());
        }
        if let Some(d) = opts.deadline {
            if Instant::now() > d {
                return report(
                    &basis,
                    &alive,
                    false,
                    degree_reached,
                    solving_degree,
                    steps,
                    max_rows,
                    max_cols,
                    true,
                    pairs_above_bound,
                );
            }
        }
        let d = pairs.iter().map(|pr| pr.degree).min().unwrap();
        degree_reached = degree_reached.max(d);
        let (selected, rest): (Vec<Pair>, Vec<Pair>) =
            pairs.drain(..).partition(|pr| pr.degree == d);
        pairs = rest;
        // symbolic preprocessing
        let mut rows_poly: Vec<(usize, Vec<u32>)> = Vec::new(); // (basis index, multiplier)
        let mut seen: FxSet<(usize, Vec<u32>)> = FxSet::default();
        for pr in &selected {
            for &idx in &[pr.i, pr.j] {
                let m: Vec<u32> = pr
                    .lcm
                    .iter()
                    .zip(&basis[idx][0].0)
                    .map(|(a, b)| a - b)
                    .collect();
                if seen.insert((idx, m.clone())) {
                    rows_poly.push((idx, m));
                }
            }
        }
        let n_pair_rows = rows_poly.len();
        let mut monomials: FxSet<Vec<u32>> = FxSet::default();
        let mut done: FxSet<Vec<u32>> = FxSet::default();
        let mut queue: Vec<Vec<u32>> = Vec::new();
        for (idx, m) in &rows_poly {
            for (e, _) in &basis[*idx] {
                let em: Vec<u32> = e.iter().zip(m).map(|(x, y)| x + y).collect();
                if monomials.insert(em.clone()) {
                    queue.push(em);
                }
            }
            let lm: Vec<u32> = basis[*idx][0].0.iter().zip(m).map(|(x, y)| x + y).collect();
            done.insert(lm);
        }
        while let Some(mono) = queue.pop() {
            if done.contains(&mono) {
                continue;
            }
            done.insert(mono.clone());
            // one reducer: the alive basis element with the largest leading
            // monomial dividing it (any would do)
            if let Some(idx) =
                (0..basis.len()).find(|&i| alive[i] && divides(&basis[i][0].0, &mono))
            {
                let m: Vec<u32> = mono
                    .iter()
                    .zip(&basis[idx][0].0)
                    .map(|(a, b)| a - b)
                    .collect();
                if seen.insert((idx, m.clone())) {
                    for (e, _) in &basis[idx] {
                        let em: Vec<u32> = e.iter().zip(&m).map(|(x, y)| x + y).collect();
                        if monomials.insert(em.clone()) {
                            queue.push(em);
                        }
                    }
                    rows_poly.push((idx, m));
                }
            }
        }
        // matrix: columns in decreasing monomial order, rows sparse
        let mut cols: Vec<Vec<u32>> = monomials.into_iter().collect();
        cols.sort_unstable_by(|a, b| cmp_monomial(b, a, ord));
        let col_of: FxMap<&[u32], u32> = cols
            .iter()
            .enumerate()
            .map(|(i, m)| (m.as_slice(), i as u32))
            .collect();
        let n_cols = cols.len();
        // `(column, coefficient)` in increasing column order, so the
        // leading term first; every row is monic
        let to_sparse = |(idx, m): &(usize, Vec<u32>)| -> Vec<(u32, u64)> {
            let mut em = vec![0u32; n_vars];
            basis[*idx]
                .iter()
                .map(|(e, c)| {
                    for (k, x) in em.iter_mut().enumerate() {
                        *x = e[k] + m[k];
                    }
                    (col_of[em.as_slice()], *c)
                })
                .collect()
        };
        // small steps (most of them, and all of `solve`'s specialised
        // runs) are cheaper on one thread than dispatched
        let parallel = rows_poly.len() * n_cols > PAR_WORK;
        let sparse: Vec<Vec<(u32, u64)>> = if parallel {
            rows_poly.par_iter().map(to_sparse).collect()
        } else {
            rows_poly.iter().map(to_sparse).collect()
        };
        let mut input_lm = vec![false; n_cols];
        for r in &sparse {
            input_lm[r[0].0 as usize] = true;
        }
        max_rows = max_rows.max(sparse.len());
        max_cols = max_cols.max(n_cols);
        steps += 1;
        // The reducer rows of symbolic preprocessing have distinct leading
        // columns, none of them an lcm: they are already an echelon form.
        // Reduce each pair row by them alone, column by column, then take
        // the reduced echelon form of what is left, which lives on the
        // other columns only.  Its rows are exactly the rows of the whole
        // matrix's reduced echelon form whose pivot is not a reducer's
        // leading monomial — the only ones that can be new.
        let (pair_rows, reducers) = sparse.split_at(n_pair_rows);
        const NONE: u32 = u32::MAX;
        let mut reducer_at = vec![NONE; n_cols];
        for (k, r) in reducers.iter().enumerate() {
            reducer_at[r[0].0 as usize] = k as u32;
        }
        let free_cols: Vec<usize> = (0..n_cols).filter(|&c| reducer_at[c] == NONE).collect();
        let deadline = opts.deadline;
        let reduce_pair_row = |r: &Vec<(u32, u64)>| -> Option<Vec<u64>> {
            if deadline.is_some_and(|d| Instant::now() > d) {
                return None;
            }
            let mut acc = vec![0u64; n_cols];
            for &(c, v) in r {
                acc[c as usize] = v;
            }
            for c in r[0].0 as usize..n_cols {
                let f = acc[c];
                if f == 0 || reducer_at[c] == NONE {
                    continue;
                }
                acc[c] = 0;
                let neg = p - f;
                for &(cc, v) in &reducers[reducer_at[c] as usize][1..] {
                    let x = &mut acc[cc as usize];
                    *x = fp.reduce(*x + neg * v);
                }
            }
            let row: Vec<u64> = free_cols.iter().map(|&c| acc[c]).collect();
            Some(row)
        };
        let reduced: Option<Vec<Vec<u64>>> = if parallel {
            pair_rows.par_iter().map(reduce_pair_row).collect()
        } else {
            pair_rows.iter().map(reduce_pair_row).collect()
        };
        let pivots = reduced.and_then(|mut rows| {
            rows.retain(|r| r.iter().any(|&v| v != 0));
            rref(&mut rows, fp, deadline).map(|piv| (rows, piv))
        });
        if debug {
            eprintln!(
                "f4 step {steps}: degree {d}, {} pairs, {} rows × {n_cols} cols, {} pivots, basis {}",
                selected.len(),
                sparse.len(),
                reducers.len() + pivots.as_ref().map_or(0, |(_, pv)| pv.len()),
                basis.len()
            );
        }
        let Some((rows, pivots)) = pivots else {
            return report(
                &basis,
                &alive,
                false,
                degree_reached,
                solving_degree,
                steps,
                max_rows,
                max_cols,
                true,
                pairs_above_bound,
            );
        };
        // new polynomials: rows whose pivot column is not an input leading monomial
        let mut new_polys: Vec<Poly> = Vec::new();
        for (row, &c) in rows.iter().zip(&pivots) {
            if input_lm[free_cols[c]] {
                continue;
            }
            let poly: Poly = row
                .iter()
                .enumerate()
                .filter(|(_, &v)| v != 0)
                .map(|(j, &v)| (cols[free_cols[j]].clone(), v))
                .collect();
            if total_degree(&poly[0].0) == 0 {
                return report(
                    &basis,
                    &alive,
                    true,
                    degree_reached,
                    d,
                    steps,
                    max_rows,
                    max_cols,
                    false,
                    pairs_above_bound,
                );
            }
            new_polys.push(poly);
        }
        if !new_polys.is_empty() {
            solving_degree = d;
        }
        for f in new_polys {
            add(
                f,
                &mut basis,
                &mut alive,
                &mut pairs,
                opts.max_degree,
                &mut pairs_above_bound,
            );
        }
    }
    // final interreduction of the alive basis (tails)
    let mut reduced: Vec<Poly> = basis
        .iter()
        .zip(&alive)
        .filter(|(_, &a)| a)
        .map(|(f, _)| f.clone())
        .collect();
    reduced = interreduce(&reduced, p, ord);
    F4Report {
        basis: reduced,
        inconsistent: false,
        degree_reached,
        solving_degree,
        steps,
        max_rows,
        max_cols,
        ms: t0.elapsed().as_secs_f64() * 1e3,
        timed_out: false,
        pairs_above_bound,
    }
}

/// A monomial ordered by `cmp_monomial` under a fixed ordering, for the
/// work heap of [`reduce`].
struct Keyed<'a>(Vec<u32>, &'a Ordering);

impl PartialEq for Keyed<'_> {
    fn eq(&self, other: &Self) -> bool {
        self.0 == other.0
    }
}
impl Eq for Keyed<'_> {}
impl PartialOrd for Keyed<'_> {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Keyed<'_> {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        cmp_monomial(&self.0, &other.0, *self.1)
    }
}

/// Reduce `f` by `basis` (full reduction of every term).
pub fn reduce(f: &Poly, basis: &[Poly], p: u64, ord: Ordering) -> Poly {
    reduce_skipping(f, basis, usize::MAX, p, ord)
}

/// [`reduce`] by every element of `basis` except `basis[skip]`.
fn reduce_skipping(f: &Poly, basis: &[Poly], skip: usize, p: u64, ord: Ordering) -> Poly {
    // coefficients of the pending terms, and a max-heap of their
    // monomials; a reduction only adds monomials below the one it
    // removes, so each monomial leaves the heap once
    let mut work: FxMap<Vec<u32>, u64> = FxMap::default();
    let mut heap: std::collections::BinaryHeap<Keyed> = std::collections::BinaryHeap::new();
    for (e, c) in f {
        let v = work.entry(e.clone()).or_insert_with(|| {
            heap.push(Keyed(e.clone(), &ord));
            0
        });
        *v = (*v + c % p) % p;
    }
    let mut out: Vec<(Vec<u32>, u64)> = Vec::new();
    while let Some(Keyed(mono, _)) = heap.pop() {
        let Some(c) = work.remove(&mono) else {
            continue;
        };
        if c == 0 {
            continue;
        }
        let g = basis
            .iter()
            .enumerate()
            .find(|&(j, g)| j != skip && divides(&g[0].0, &mono));
        if let Some((_, g)) = g {
            // `g` is monic: `mono − c·m·g` cancels the leading term (already
            // removed from `work`) and adds the shifted tail
            let neg = p - c;
            for (e, gc) in &g[1..] {
                let em: Vec<u32> = e
                    .iter()
                    .zip(&mono)
                    .zip(&g[0].0)
                    .map(|((x, a), b)| x + a - b)
                    .collect();
                let v = work.entry(em).or_insert_with_key(|k| {
                    heap.push(Keyed(k.clone(), &ord));
                    0
                });
                *v = (*v + mulmod(neg, *gc, p)) % p;
            }
        } else {
            out.push((mono, c));
        }
    }
    // popped in decreasing order: already leading-first
    out
}

/// Interreduce a basis: drop elements whose leading monomial another
/// divides, then reduce every tail by the others.
pub fn interreduce(basis: &[Poly], p: u64, ord: Ordering) -> Vec<Poly> {
    let mut keep: Vec<Poly> = Vec::new();
    for (i, f) in basis.iter().enumerate() {
        let redundant = basis
            .iter()
            .enumerate()
            .any(|(j, g)| j != i && divides(&g[0].0, &f[0].0) && (g[0].0 != f[0].0 || j < i));
        if !redundant {
            keep.push(f.clone());
        }
    }
    let mut out = keep;
    for i in 0..out.len() {
        let r = reduce_skipping(&out[i], &out, i, p, ord);
        if !r.is_empty() {
            out[i] = normalise(&r, p, ord);
        }
    }
    out.sort_by(|a, b| cmp_monomial(&a[0].0, &b[0].0, ord));
    out
}

/// Autoreduce a *generating set* (not a Gröbner basis): reduce every
/// element by the others until nothing changes, dropping the ones that
/// reduce to zero.  Two generators with the same leading monomial are
/// not redundant — their difference is a new generator with a smaller
/// one — which is what distinguishes this from [`interreduce`].
pub fn autoreduce(polys: &[Poly], p: u64, ord: Ordering) -> Vec<Poly> {
    let mut set: Vec<Poly> = polys
        .iter()
        .map(|f| normalise(f, p, ord))
        .filter(|f| !f.is_empty())
        .collect();
    loop {
        let mut changed = false;
        let mut i = 0;
        while i < set.len() {
            let r = normalise(&reduce_skipping(&set[i], &set, i, p, ord), p, ord);
            if r != set[i] {
                changed = true;
                if r.is_empty() {
                    set.remove(i);
                    continue;
                }
                set[i] = r;
            }
            i += 1;
        }
        if !changed {
            break;
        }
    }
    set.sort_by(|a, b| cmp_monomial(&b[0].0, &a[0].0, ord));
    set
}

// ── Solving ────────────────────────────────────────────────────────

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Verdict {
    Inconsistent,
    Solutions(Vec<Vec<u64>>),
    /// The degree bound (or the deadline) was reached before the system
    /// resolved.
    Undetermined,
}

#[derive(Clone, Debug)]
pub struct SolveReport {
    pub verdict: Verdict,
    /// Solving degree of the top-level run.
    pub solving_degree: u32,
    pub degree_reached: u32,
    pub max_rows: usize,
    pub max_cols: usize,
    pub f4_runs: usize,
    pub ms: f64,
    pub timed_out: bool,
}

/// Roots in `F_p` of a univariate polynomial given as `(degree, coeff)`.
fn roots_univariate(coeffs: &[(u32, u64)], p: u64) -> Vec<u64> {
    (0..p)
        .filter(|&x| {
            let mut v = 0u64;
            for (k, c) in coeffs {
                v = (v + mulmod(*c, powmod(x, *k as u64, p), p)) % p;
            }
            v == 0
        })
        .collect()
}

fn powmod(mut a: u64, mut e: u64, p: u64) -> u64 {
    let mut r = 1u64;
    a %= p;
    while e > 0 {
        if e & 1 == 1 {
            r = mulmod(r, a, p);
        }
        a = mulmod(a, a, p);
        e >>= 1;
    }
    r
}

/// Substitute `x_i = a` and drop variable `i`.
fn specialise(f: &Poly, i: usize, a: u64, p: u64) -> Vec<(Vec<u32>, u64)> {
    f.iter()
        .map(|(e, c)| {
            let mut e2 = e.clone();
            let k = e2.remove(i);
            (e2, mulmod(*c, powmod(a, k as u64, p), p))
        })
        .collect()
}

/// Solve a zero-dimensional system over `F_p` by degree-bounded F4 and
/// substitution.  Solutions are full assignments `(x_0, …, x_{n−1})`.
pub fn solve(input: &[Poly], n_vars: usize, p: u64, opts: &F4Options) -> SolveReport {
    let t0 = Instant::now();
    let mut runs = 0usize;
    let mut max_rows = 0;
    let mut max_cols = 0;
    let mut top: Option<(u32, u32)> = None;
    let mut timed_out = false;
    let verdict = solve_rec(
        input,
        n_vars,
        p,
        opts,
        &mut runs,
        &mut max_rows,
        &mut max_cols,
        &mut top,
        &mut timed_out,
    );
    let (solving_degree, degree_reached) = top.unwrap_or((0, 0));
    SolveReport {
        verdict,
        solving_degree,
        degree_reached,
        max_rows,
        max_cols,
        f4_runs: runs,
        ms: t0.elapsed().as_secs_f64() * 1e3,
        timed_out,
    }
}

#[allow(clippy::too_many_arguments)]
fn solve_rec(
    input: &[Poly],
    n_vars: usize,
    p: u64,
    opts: &F4Options,
    runs: &mut usize,
    max_rows: &mut usize,
    max_cols: &mut usize,
    top: &mut Option<(u32, u32)>,
    timed_out: &mut bool,
) -> Verdict {
    if n_vars == 0 {
        // constants only: consistent iff all zero
        let bad = input.iter().any(|f| f.iter().any(|(_, c)| *c % p != 0));
        return if bad {
            Verdict::Inconsistent
        } else {
            Verdict::Solutions(vec![vec![]])
        };
    }
    let r = f4(input, n_vars, p, opts);
    *runs += 1;
    *max_rows = (*max_rows).max(r.max_rows);
    *max_cols = (*max_cols).max(r.max_cols);
    if top.is_none() {
        *top = Some((r.solving_degree, r.degree_reached));
    }
    if r.timed_out {
        *timed_out = true;
        return Verdict::Undetermined;
    }
    if r.inconsistent {
        return Verdict::Inconsistent;
    }
    // a univariate element?  prefer the variable with the fewest roots
    let mut best: Option<(usize, Vec<u64>)> = None;
    for g in &r.basis {
        let vars: HashSet<usize> = g
            .iter()
            .flat_map(|(e, _)| e.iter().enumerate().filter(|(_, &k)| k > 0).map(|(i, _)| i))
            .collect();
        if vars.len() == 1 {
            let i = *vars.iter().next().unwrap();
            let coeffs: Vec<(u32, u64)> = g.iter().map(|(e, c)| (e[i], *c)).collect();
            let roots = roots_univariate(&coeffs, p);
            if best.as_ref().is_none_or(|(_, rs)| roots.len() < rs.len()) {
                best = Some((i, roots));
            }
        }
    }
    let (var, values): (usize, Vec<u64>) = match best {
        Some(b) => b,
        None => {
            if r.pairs_above_bound > 0 && r.basis.len() < n_vars {
                // the truncation may have hidden the univariate element;
                // brute force on the first variable is still sound
            }
            (0, (0..p).collect())
        }
    };
    let mut sols: Vec<Vec<u64>> = Vec::new();
    for a in values {
        if let Some(d) = opts.deadline {
            if Instant::now() > d {
                *timed_out = true;
                return Verdict::Undetermined;
            }
        }
        let sub: Vec<Poly> = r
            .basis
            .iter()
            .map(|g| normalise(&specialise(g, var, a, p), p, opts.order))
            .filter(|g| !g.is_empty())
            .collect();
        match solve_rec(
            &sub,
            n_vars - 1,
            p,
            opts,
            runs,
            max_rows,
            max_cols,
            top,
            timed_out,
        ) {
            Verdict::Inconsistent => {}
            Verdict::Undetermined => return Verdict::Undetermined,
            Verdict::Solutions(ss) => {
                for mut s in ss {
                    s.insert(var, a);
                    sols.push(s);
                }
            }
        }
    }
    if sols.is_empty() {
        Verdict::Inconsistent
    } else {
        Verdict::Solutions(sols)
    }
}

/// Evaluate a polynomial at a point.
pub fn eval(f: &Poly, x: &[u64], p: u64) -> u64 {
    let mut v = 0u64;
    for (e, c) in f {
        let mut t = *c;
        for (i, &k) in e.iter().enumerate() {
            if k > 0 {
                t = mulmod(t, powmod(x[i], k as u64, p), p);
            }
        }
        v = (v + t) % p;
    }
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    fn poly(terms: &[(&[u32], u64)]) -> Poly {
        terms.iter().map(|(e, c)| (e.to_vec(), *c)).collect()
    }

    #[test]
    fn circle_and_line_over_f7_match_buchberger() {
        // x² + y² − 1, x − y over F_7: y² = 4 → y = ±2
        let p = 7;
        let f = poly(&[(&[2, 0], 1), (&[0, 2], 1), (&[0, 0], 6)]);
        let g = poly(&[(&[1, 0], 1), (&[0, 1], 6)]);
        let r = f4(
            &[f.clone(), g.clone()],
            2,
            p,
            &F4Options::new(Ordering::Grevlex, 8),
        );
        assert!(!r.inconsistent);
        for b in &r.basis {
            for x in 0..p {
                for y in 0..p {
                    if eval(&f, &[x, y], p) == 0 && eval(&g, &[x, y], p) == 0 {
                        assert_eq!(eval(b, &[x, y], p), 0);
                    }
                }
            }
        }
        let s = solve(&[f, g], 2, p, &F4Options::new(Ordering::Grevlex, 8));
        let mut sols = match s.verdict {
            Verdict::Solutions(v) => v,
            other => panic!("{other:?}"),
        };
        sols.sort();
        assert_eq!(sols, vec![vec![2, 2], vec![5, 5]]);
    }

    #[test]
    fn autoreduce_keeps_generators_with_equal_leading_monomials() {
        // x² + y and x² + 2y generate (x², y): interreduce would wrongly
        // drop one of them, autoreduce must keep two generators
        let p = 31;
        let f = poly(&[(&[2, 0], 1), (&[0, 1], 1)]);
        let g = poly(&[(&[2, 0], 1), (&[0, 1], 2)]);
        let a = autoreduce(&[f.clone(), g.clone()], p, Ordering::Grevlex);
        assert_eq!(a.len(), 2, "{a:?}");
        assert!(a.iter().any(|h| h == &poly(&[(&[2, 0], 1)])), "{a:?}");
        assert!(a.iter().any(|h| h == &poly(&[(&[0, 1], 1)])), "{a:?}");
        // multiples of a generator are dropped
        let m = poly(&[(&[3, 1], 1), (&[1, 2], 1)]); // x·y·(x² + y)
        let a = autoreduce(&[f.clone(), m], p, Ordering::Grevlex);
        assert_eq!(a.len(), 1, "{a:?}");
    }

    #[test]
    fn inconsistent_system_is_refuted() {
        let p = 31;
        let f = poly(&[(&[1, 0], 1), (&[0, 0], 1)]); // x + 1
        let g = poly(&[(&[1, 0], 1), (&[0, 0], 2)]); // x + 2
        let r = f4(&[f, g], 2, p, &F4Options::new(Ordering::Grevlex, 4));
        assert!(r.inconsistent);
    }

    #[test]
    fn degree_bound_truncates_and_reports_it() {
        // x³ − y, y³ − x, x·y − 1 over F_101 has finitely many solutions;
        // a bound of 2 cannot form the degree-3 pairs.
        let p = 101;
        let f = poly(&[(&[3, 0], 1), (&[0, 1], p - 1)]);
        let g = poly(&[(&[0, 3], 1), (&[1, 0], p - 1)]);
        let h = poly(&[(&[1, 1], 1), (&[0, 0], p - 1)]);
        let r = f4(
            &[f.clone(), g.clone(), h.clone()],
            2,
            p,
            &F4Options::new(Ordering::Grevlex, 2),
        );
        assert!(r.pairs_above_bound > 0);
        let s = solve(
            &[f.clone(), g.clone(), h.clone()],
            2,
            p,
            &F4Options::new(Ordering::Grevlex, 8),
        );
        let sols = match s.verdict {
            Verdict::Solutions(v) => v,
            other => panic!("{other:?}"),
        };
        for x in 0..p {
            for y in 0..p {
                let on = [&f, &g, &h].iter().all(|q| eval(q, &[x, y], p) == 0);
                assert_eq!(on, sols.contains(&vec![x, y]), "({x}, {y})");
            }
        }
    }

    #[test]
    fn random_zero_dimensional_systems_agree_with_brute_force() {
        // three random quadrics in three unknowns over F_13, plus the
        // field equations' role played by brute force
        let p = 13;
        let mut seed = 0x1234_5678u64;
        let mut rnd = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed % p
        };
        let monos: Vec<Vec<u32>> = {
            let mut v = Vec::new();
            for a in 0..=2 {
                for b in 0..=2 - a {
                    for c in 0..=2 - a - b {
                        v.push(vec![a, b, c]);
                    }
                }
            }
            v
        };
        for _ in 0..6 {
            let sys: Vec<Poly> = (0..3)
                .map(|_| monos.iter().map(|m| (m.clone(), rnd())).collect())
                .collect();
            let s = solve(&sys, 3, p, &F4Options::new(Ordering::Grevlex, 10));
            let mut expected: Vec<Vec<u64>> = Vec::new();
            for x in 0..p {
                for y in 0..p {
                    for z in 0..p {
                        if sys.iter().all(|q| eval(q, &[x, y, z], p) == 0) {
                            expected.push(vec![x, y, z]);
                        }
                    }
                }
            }
            let mut got = match s.verdict {
                Verdict::Solutions(v) => v,
                Verdict::Inconsistent => vec![],
                Verdict::Undetermined => panic!("undetermined"),
            };
            got.sort();
            expected.sort();
            assert_eq!(got, expected);
        }
    }

    #[test]
    fn barrett_matches_the_hardware_remainder() {
        let mut x = 0x0123_4567_89ab_cdefu64;
        for p in [2u64, 3, 31, 65_521, 2_147_483_647, 4_294_967_291] {
            let fp = Barrett::new(p);
            for probe in [0, 1, p - 1, p, p + 1, p * p - 1, u64::MAX, u64::MAX - 1] {
                assert_eq!(fp.reduce(probe), probe % p, "{probe} mod {p}");
            }
            for _ in 0..10_000 {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                assert_eq!(fp.reduce(x), x % p, "{x} mod {p}");
            }
        }
    }

    /// `S(f, g)` of two monic polynomials.
    fn spoly(f: &Poly, g: &Poly, p: u64, ord: Ordering) -> Poly {
        let l: Vec<u32> = f[0].0.iter().zip(&g[0].0).map(|(a, b)| *a.max(b)).collect();
        let mut terms: Vec<(Vec<u32>, u64)> = Vec::new();
        for (h, sign) in [(f, 1), (g, p - 1)] {
            for (e, c) in h {
                let em = e
                    .iter()
                    .zip(&l)
                    .zip(&h[0].0)
                    .map(|((x, a), b)| x + a - b)
                    .collect();
                terms.push((em, mulmod(*c, sign, p)));
            }
        }
        let mut map: BTreeMap<Vec<u32>, u64> = BTreeMap::new();
        for (e, c) in terms {
            let v = map.entry(e).or_insert(0);
            *v = (*v + c) % p;
        }
        let mut out: Poly = map.into_iter().filter(|(_, c)| *c != 0).collect();
        out.sort_by(|(a, _), (b, _)| cmp_monomial(b, a, ord));
        out
    }

    #[test]
    fn basis_from_the_parallel_path_is_a_reduced_groebner_basis() {
        // six random quadrics in six unknowns over F_65521: the larger
        // steps exceed `PAR_WORK` and run the row reductions in parallel
        let (n, p, ord) = (6usize, 65_521u64, Ordering::Grevlex);
        let mut seed = 0x0bad_c0de_1234_5678u64;
        let mut rnd = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed % p
        };
        let mut monos: Vec<Vec<u32>> = Vec::new();
        for m in 0u32..(3u32.pow(n as u32)) {
            let e: Vec<u32> = (0..n).map(|i| (m / 3u32.pow(i as u32)) % 3).collect();
            if e.iter().sum::<u32>() <= 2 {
                monos.push(e);
            }
        }
        let sys: Vec<Poly> = (0..n)
            .map(|_| monos.iter().map(|m| (m.clone(), rnd())).collect())
            .collect();
        let r = f4(&sys, n, p, &F4Options::new(ord, 20));
        assert!(!r.inconsistent && !r.timed_out);
        assert_eq!(r.pairs_above_bound, 0);
        assert!(r.max_rows * r.max_cols > PAR_WORK, "not the parallel path");
        let g = &r.basis;
        for f in &sys {
            assert!(reduce(&normalise(f, p, ord), g, p, ord).is_empty());
        }
        for i in 0..g.len() {
            for j in i + 1..g.len() {
                let s = spoly(&g[i], &g[j], p, ord);
                assert!(reduce(&s, g, p, ord).is_empty(), "S({i}, {j})");
            }
            // reduced: no term of g[i] is divisible by another leading monomial
            for (e, _) in &g[i] {
                for (j, h) in g.iter().enumerate() {
                    assert!(
                        j == i || !divides(&h[0].0, e),
                        "g[{i}] not reduced by g[{j}]"
                    );
                }
            }
        }
    }
}
