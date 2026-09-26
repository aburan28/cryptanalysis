//! **X5″: the symmetrised chain's `D = 4` kernel, split.**
//!
//! Companion to §X5″ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`,
//! which registered the systems, the draws and all three measurements before
//! this driver existed.  On X5′'s chained `m = 4` systems (both arms), per
//! draw:
//!
//! - **(G)** the literature's first fall degree: for `D = 2, 3, 4` the
//!   top-degree Macaulay matrix in `F₂[x]/(x_k²)`, its left kernel `K^h_D`, the
//!   span `T^h_D` of the trivial syzygies of the top parts, and
//!   `R^h_D = dim K^h_D − dim T^h_D`;
//! - **(L)** `L_D`, the linear polynomials in the row space of the full
//!   Boolean Macaulay matrix of degree `≤ D`;
//! - **(F)** H1's rank-loss kernel `K_4`, against the degree-`≤ 4` span `T_4`
//!   of Koszul and field syzygies and the span `Λ_4` of the Boolean identities
//!   `(h + 1)·g`, `h_b·g_a + h_a·g_b` of the linear polynomials `h = Σ g_i f_i`
//!   derivable at `D ≤ 3`; monomial multiples of `K_3` are reported beside it.
//!
//! Every generator is checked to lie in the kernel before it is counted.
//!
//! ```text
//! cargo run --release --example koblitz_x5_syzygy_split -- --json experiments/29_koblitz_x5_syzygy_split.json > experiments/29_koblitz_x5_syzygy_split.log
//! ```

use std::collections::HashMap;
use std::env;
use std::fs;
use std::time::Instant;

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_chained_symmetrised_system, random_subspace_containing_one_in,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rayon::prelude::*;
use serde::Serialize;

type Poly = Vec<u64>; // sorted monomial masks, constant = 0

fn popc(m: u64) -> u32 {
    m.count_ones()
}

fn deg(p: &Poly) -> u32 {
    p.iter().map(|&m| popc(m)).max().unwrap_or(0)
}

fn canon(mut v: Vec<u64>) -> Poly {
    v.sort_unstable();
    let mut out: Vec<u64> = Vec::with_capacity(v.len());
    for m in v {
        if out.last() == Some(&m) {
            out.pop();
        } else {
            out.push(m);
        }
    }
    out
}

// Product with a monomial in B = F₂[x]/(x_k² + x_k): monomials multiply by OR.
fn bool_mul(p: &Poly, s: u64) -> Poly {
    canon(p.iter().map(|&m| m | s).collect())
}

// Product with a monomial in F₂[x]/(x_k²): overlapping monomials vanish.
fn graded_mul(p: &Poly, s: u64) -> Poly {
    canon(p.iter().filter(|&&m| m & s == 0).map(|&m| m | s).collect())
}

fn top(p: &Poly) -> Poly {
    let d = deg(p);
    p.iter().copied().filter(|&m| popc(m) == d).collect()
}

fn monos_exact(nv: usize, k: u32) -> Vec<u64> {
    let mut out = Vec::new();
    fn rec(nv: usize, start: usize, k: u32, acc: u64, out: &mut Vec<u64>) {
        if k == 0 {
            out.push(acc);
            return;
        }
        for v in start..nv {
            rec(nv, v + 1, k - 1, acc | (1u64 << v), out);
        }
    }
    rec(nv, 0, k, 0, &mut out);
    out
}

fn monos_upto(nv: usize, k: i64) -> Vec<u64> {
    (0..=k.max(-1))
        .filter(|&d| d >= 0)
        .flat_map(|d| monos_exact(nv, d as u32))
        .collect()
}

// A Macaulay matrix: rows are (equation, multiplier) with their polynomial.
struct Mac {
    keys: Vec<(usize, u64)>,
    index: HashMap<(usize, u64), usize>,
    polys: Vec<Poly>,
}

impl Mac {
    fn push(&mut self, key: (usize, u64), p: Poly) {
        if p.is_empty() {
            return;
        }
        self.index.insert(key, self.keys.len());
        self.keys.push(key);
        self.polys.push(p);
    }
    fn full(eqs: &[Poly], nv: usize, d: u32) -> Self {
        let mut m = Mac {
            keys: Vec::new(),
            index: HashMap::new(),
            polys: Vec::new(),
        };
        for (i, f) in eqs.iter().enumerate() {
            for t in monos_upto(nv, d as i64 - deg(f) as i64) {
                m.push((i, t), bool_mul(f, t));
            }
        }
        m
    }
    fn graded(eqs: &[Poly], nv: usize, d: u32) -> Self {
        let mut m = Mac {
            keys: Vec::new(),
            index: HashMap::new(),
            polys: Vec::new(),
        };
        for (i, f) in eqs.iter().enumerate() {
            let df = deg(f);
            if df > d {
                continue;
            }
            let ft = top(f);
            for t in monos_exact(nv, d - df) {
                m.push((i, t), graded_mul(&ft, t));
            }
        }
        m
    }
}

// Forward elimination with the row-identity attached.  Columns are ordered
// by degree, highest first, so rows pivoting in the degree-≤1 block span the
// linear part of the row space.
struct Elim {
    // The pivots in the degree-≤1 block: (column poly, combination of the
    // original rows).  Only these are kept; the others are counted.
    linear: Vec<(Poly, Vec<usize>)>,
    kernel: Vec<Vec<usize>>,
}

fn eliminate(mac: &Mac) -> Elim {
    let mut cols: Vec<u64> = mac.polys.iter().flatten().copied().collect();
    cols.sort_unstable_by(|a, b| popc(*b).cmp(&popc(*a)).then(a.cmp(b)));
    cols.dedup();
    let colidx: HashMap<u64, usize> = cols.iter().enumerate().map(|(i, &c)| (c, i)).collect();
    let first_linear_col = cols
        .iter()
        .position(|&c| popc(c) <= 1)
        .unwrap_or(cols.len());
    let nc = cols.len();
    let nr = mac.polys.len();
    let (wc, wr) = (nc.div_ceil(64), nr.div_ceil(64));
    let w = wc + wr;
    let mut rows: Vec<Vec<u64>> = mac
        .polys
        .par_iter()
        .enumerate()
        .map(|(ri, p)| {
            let mut v = vec![0u64; w];
            for c in p {
                let j = colidx[c];
                v[j / 64] ^= 1u64 << (j % 64);
            }
            v[wc + ri / 64] |= 1u64 << (ri % 64);
            v
        })
        .collect();
    let mut rank = 0usize;
    let mut pivot_cols = Vec::new();
    for col in 0..nc {
        let (wi, b) = (col / 64, 1u64 << (col % 64));
        let Some(p) = (rank..nr).find(|&r| rows[r][wi] & b != 0) else {
            continue;
        };
        rows.swap(rank, p);
        let (head, tail) = rows.split_at_mut(rank + 1);
        let pr = &head[rank];
        tail.par_iter_mut().for_each(|r| {
            if r[wi] & b != 0 {
                for k in wi..w {
                    r[k] ^= pr[k];
                }
            }
        });
        pivot_cols.push(col);
        rank += 1;
    }
    let ident = |v: &Vec<u64>| -> Vec<usize> {
        (0..nr)
            .filter(|&ri| v[wc + ri / 64] >> (ri % 64) & 1 == 1)
            .collect()
    };
    let linear = (0..rank)
        .filter(|&r| pivot_cols[r] >= first_linear_col)
        .map(|r| {
            let poly: Poly = (first_linear_col..nc)
                .filter(|&j| rows[r][j / 64] >> (j % 64) & 1 == 1)
                .map(|j| cols[j])
                .collect();
            (canon(poly), ident(&rows[r]))
        })
        .collect();
    let kernel = (rank..nr).map(|r| ident(&rows[r])).collect();
    Elim { linear, kernel }
}

// Rank over F₂ of vectors given as sets of indices below `n`.
fn rank_of(vecs: &[Vec<u64>]) -> usize {
    let mut m: Vec<Vec<u64>> = vecs
        .iter()
        .filter(|v| v.iter().any(|&x| x != 0))
        .cloned()
        .collect();
    let Some(w) = m.first().map(|v| v.len()) else {
        return 0;
    };
    let mut rank = 0;
    for col in 0..w * 64 {
        let (wi, b) = (col / 64, 1u64 << (col % 64));
        let Some(p) = (rank..m.len()).find(|&r| m[r][wi] & b != 0) else {
            continue;
        };
        m.swap(rank, p);
        let pr = m[rank].clone();
        for r in m.iter_mut().skip(rank + 1) {
            if r[wi] & b != 0 {
                for k in wi..w {
                    r[k] ^= pr[k];
                }
            }
        }
        rank += 1;
    }
    rank
}

// Accumulates a row-combination over `mac` from (equation, multiplier) terms.
struct Acc<'a> {
    mac: &'a Mac,
    v: Vec<u64>,
    missing: usize,
}

impl<'a> Acc<'a> {
    fn new(mac: &'a Mac) -> Self {
        Acc {
            mac,
            v: vec![0u64; mac.polys.len().div_ceil(64).max(1)],
            missing: 0,
        }
    }
    // A key absent from `mac` is a row whose product vanished (dropped) or a
    // degree overflow; the builders below never produce the latter, and the
    // count is reported.
    fn toggle(&mut self, key: (usize, u64), max_deg: &[u32], d: u32) {
        match self.mac.index.get(&key) {
            Some(&r) => self.v[r / 64] ^= 1u64 << (r % 64),
            None => {
                if popc(key.1) + max_deg[key.0] > d {
                    self.missing += 1;
                }
            }
        }
    }
}

// v · M = 0 ?
fn in_kernel(mac: &Mac, v: &[u64]) -> bool {
    let mut acc: Vec<u64> = Vec::new();
    for (r, p) in mac.polys.iter().enumerate() {
        if v[r / 64] >> (r % 64) & 1 == 1 {
            acc.extend_from_slice(p);
        }
    }
    canon(acc).is_empty()
}

#[derive(Serialize, Default, Clone)]
struct Graded {
    d: u32,
    rows: usize,
    kernel: usize,
    trivial: usize,
    residual: usize,
}

#[derive(Serialize, Default, Clone)]
struct Arm {
    arm: String,
    n_vars: usize,
    eq_degrees: Vec<(u32, usize)>,
    graded: Vec<Graded>,
    first_fall_degree: Option<u32>,
    linear: Vec<(u32, usize)>,
    constant_derived: Vec<(u32, bool)>,
    rows_4: usize,
    cols_4: usize,
    kernel_3: usize,
    kernel_4: usize,
    trivial_4: usize,
    trivial_plus_identities_4: usize,
    plus_k3_multiples_4: usize,
    residual_4: usize,
    residual_4_with_k3: usize,
    generator_failures: usize,
    /// Unregistered localisation, computed after the registered quantities:
    /// per link alone, `(label, D = 4 kernel, graded R^h_3)`.
    link_kernels_4: Vec<(String, usize, usize)>,
    /// Unregistered: the last (degree-2) link alone at `D = 4`.  Its two
    /// unknown blocks are the chain unknown (`n` bits) and the summand
    /// (`small_block` bits).  `small_mult_kernel` is the kernel with
    /// multipliers restricted to the summand's variables, and
    /// `trivial_plus_small` the span of `T_4` and that kernel, against
    /// `last_link_kernel`.
    small_block: usize,
    last_link_kernel: usize,
    last_link_trivial: usize,
    small_mult_kernel: usize,
    trivial_plus_small: usize,
    ms: f64,
}

#[derive(Serialize)]
struct Draw {
    n: u32,
    ell: usize,
    draw: usize,
    x_r: String,
    arms: Vec<Arm>,
}

fn graded_cell(eqs: &[Poly], nv: usize, d: u32, fails: &mut usize) -> Graded {
    let mac = Mac::graded(eqs, nv, d);
    let el = eliminate(&mac);
    let degs: Vec<u32> = eqs.iter().map(deg).collect();
    let tops: Vec<Poly> = eqs.iter().map(top).collect();
    let mut triv: Vec<Vec<u64>> = Vec::new();
    for i in 0..eqs.len() {
        for j in i..eqs.len() {
            let dd = degs[i] as i64 + degs[j] as i64;
            if dd > d as i64 {
                continue;
            }
            for s in monos_exact(nv, (d as i64 - dd) as u32) {
                let mut a = Acc::new(&mac);
                if i == j {
                    // field: s·f_i^h·e_i
                    for m in graded_mul(&tops[i], s) {
                        a.toggle((i, m), &degs, d);
                    }
                } else {
                    for m in graded_mul(&tops[j], s) {
                        a.toggle((i, m), &degs, d);
                    }
                    for m in graded_mul(&tops[i], s) {
                        a.toggle((j, m), &degs, d);
                    }
                }
                *fails += a.missing;
                if !in_kernel(&mac, &a.v) {
                    *fails += 1;
                }
                triv.push(a.v);
            }
        }
    }
    let kernel = el.kernel.len();
    let trivial = rank_of(&triv);
    Graded {
        d,
        rows: mac.polys.len(),
        kernel,
        trivial,
        residual: kernel.saturating_sub(trivial),
    }
}

fn e_deg(ps: &[F2BoolPoly]) -> u32 {
    ps.iter()
        .flat_map(|p| p.terms.iter().map(|t| t.mask.count_ones()))
        .max()
        .unwrap_or(0)
}

fn analyse(name: &str, raw: &[F2BoolPoly], nv: usize) -> Arm {
    let t0 = Instant::now();
    let eqs: Vec<Poly> = raw
        .iter()
        .map(|p| canon(p.terms.iter().map(|t| t.mask).collect()))
        .filter(|p| !p.is_empty())
        .collect();
    let degs: Vec<u32> = eqs.iter().map(deg).collect();
    let mut hist: HashMap<u32, usize> = HashMap::new();
    for &d in &degs {
        *hist.entry(d).or_default() += 1;
    }
    let mut eq_degrees: Vec<(u32, usize)> = hist.into_iter().collect();
    eq_degrees.sort();
    let mut fails = 0usize;

    let graded: Vec<Graded> = (2..=4)
        .map(|d| graded_cell(&eqs, nv, d, &mut fails))
        .collect();
    let first_fall_degree = graded.iter().find(|g| g.residual > 0).map(|g| g.d);

    let mut linear = Vec::new();
    let mut constant_derived = Vec::new();
    let mut e2: Option<(Mac, Elim)> = None;
    let mut e3: Option<(Mac, Elim)> = None;
    let mut e4: Option<(Mac, Elim)> = None;
    for d in 2..=4u32 {
        let mac = Mac::full(&eqs, nv, d);
        let el = eliminate(&mac);
        let lin = el.linear.len();
        let konst = el.linear.iter().any(|p| p.0 == vec![0u64]);
        linear.push((d, lin));
        constant_derived.push((d, konst));
        match d {
            2 => e2 = Some((mac, el)),
            3 => e3 = Some((mac, el)),
            _ => e4 = Some((mac, el)),
        }
    }
    let (m2, el2) = e2.unwrap();
    let (m3, el3) = e3.unwrap();
    let (m4, el4) = e4.unwrap();
    let nr4 = m4.polys.len();
    let cols_4 = {
        let mut c: Vec<u64> = m4.polys.iter().flatten().copied().collect();
        c.sort_unstable();
        c.dedup();
        c.len()
    };

    // T_4: degree-≤4 monomial multiples of Koszul and field syzygies.
    let mut triv: Vec<Vec<u64>> = Vec::new();
    for i in 0..eqs.len() {
        for j in i..eqs.len() {
            let dd = degs[i] as i64 + degs[j] as i64;
            if dd > 4 {
                continue;
            }
            for s in monos_upto(nv, 4 - dd) {
                let mut a = Acc::new(&m4);
                if i == j {
                    let mut f1 = eqs[i].clone();
                    f1.push(0);
                    for m in bool_mul(&canon(f1), s) {
                        a.toggle((i, m), &degs, 4);
                    }
                } else {
                    for m in bool_mul(&eqs[j], s) {
                        a.toggle((i, m), &degs, 4);
                    }
                    for m in bool_mul(&eqs[i], s) {
                        a.toggle((j, m), &degs, 4);
                    }
                }
                fails += a.missing;
                if !in_kernel(&m4, &a.v) {
                    fails += 1;
                }
                triv.push(a.v);
            }
        }
    }
    let trivial_4 = rank_of(&triv);

    // Λ_4: Boolean identities of the linear polynomials derivable at D ≤ 3.
    // Each is taken from the lowest degree it appears at (the linear pivots
    // of M_2, then of M_3), so the multiples `s` that fit are not lost to a
    // higher-degree representation.
    let lin3: Vec<(Poly, Vec<(usize, u64)>, u32)> = [(&m2, &el2), (&m3, &el3)]
        .into_iter()
        .flat_map(|(m, el)| {
            el.linear.iter().map(move |p| {
                let g: Vec<(usize, u64)> = p.1.iter().map(|&r| m.keys[r]).collect();
                (p.0.clone(), g)
            })
        })
        .map(|(h, g)| {
            let delta = g.iter().map(|&(i, t)| popc(t) + degs[i]).max().unwrap_or(0);
            (h, g, delta)
        })
        .collect();
    let mut lam: Vec<Vec<u64>> = Vec::new();
    let push_mult =
        |g: &[(usize, u64)], mult: &Poly, s: u64, lam: &mut Vec<Vec<u64>>, fails: &mut usize| {
            let mut a = Acc::new(&m4);
            for &(i, t) in g {
                for u in bool_mul(mult, s | t) {
                    a.toggle((i, u), &degs, 4);
                }
            }
            *fails += a.missing;
            if !in_kernel(&m4, &a.v) {
                *fails += 1;
            }
            lam.push(a.v);
        };
    for (h, g, delta) in &lin3 {
        let mut h1 = h.clone();
        h1.push(0);
        let h1 = canon(h1);
        for s in monos_upto(nv, 3 - *delta as i64) {
            push_mult(g, &h1, s, &mut lam, &mut fails);
        }
    }
    for a in 0..lin3.len() {
        for b in a + 1..lin3.len() {
            let (ha, ga, da) = &lin3[a];
            let (hb, gb, db) = &lin3[b];
            for s in monos_upto(nv, 3 - (*da).max(*db) as i64) {
                let mut acc = Acc::new(&m4);
                for (g, mult) in [(ga, hb), (gb, ha)] {
                    for &(i, t) in g.iter() {
                        for u in bool_mul(mult, s | t) {
                            acc.toggle((i, u), &degs, 4);
                        }
                    }
                }
                fails += acc.missing;
                if !in_kernel(&m4, &acc.v) {
                    fails += 1;
                }
                lam.push(acc.v);
            }
        }
    }
    let mut tl = triv.clone();
    tl.extend(lam.iter().cloned());
    let trivial_plus_identities_4 = rank_of(&tl);

    // Monomial multiples of the D = 3 kernel.
    let mut k3m: Vec<Vec<u64>> = Vec::new();
    for kv in &el3.kernel {
        let g: Vec<(usize, u64)> = kv.iter().map(|&r| m3.keys[r]).collect();
        let delta = g.iter().map(|&(i, t)| popc(t) + degs[i]).max().unwrap_or(0);
        for s in monos_upto(nv, 4 - delta as i64) {
            let mut a = Acc::new(&m4);
            for &(i, t) in &g {
                a.toggle((i, t | s), &degs, 4);
            }
            fails += a.missing;
            if !in_kernel(&m4, &a.v) {
                fails += 1;
            }
            k3m.push(a.v);
        }
    }
    let mut tlk = tl;
    tlk.extend(k3m);
    let plus_k3 = rank_of(&tlk);
    let kernel_4 = el4.kernel.len();

    // Unregistered: where the D = 4 kernel lives.  The builders emit n
    // equations per S₃ link, in link order.
    let nlinks = 3usize;
    let per = raw.len() / nlinks;
    let link_eqs = |ls: &[usize]| -> Vec<Poly> {
        ls.iter()
            .flat_map(|&l| {
                raw[l * per..(l + 1) * per]
                    .iter()
                    .map(|p| canon(p.terms.iter().map(|t| t.mask).collect()))
            })
            .filter(|p: &Poly| !p.is_empty())
            .collect()
    };
    let mut link_kernels_4 = Vec::new();
    for ls in [vec![0usize], vec![1], vec![2]] {
        let e = link_eqs(&ls);
        let label = ls
            .iter()
            .map(|&l| {
                let d = e_deg(&raw[l * per..(l + 1) * per]);
                format!("L{l}(deg {d})")
            })
            .collect::<Vec<_>>()
            .join("+");
        let k = eliminate(&Mac::full(&e, nv, 4)).kernel.len();
        let g3 = graded_cell(&e, nv, 3, &mut fails).residual;
        link_kernels_4.push((label, k, g3));
    }

    // Unregistered: the last link, and multipliers on its small block only.
    let last = (0..nlinks)
        .find(|&l| e_deg(&raw[l * per..(l + 1) * per]) == 2)
        .expect("one degree-2 link");
    let le = link_eqs(&[last]);
    let support: u64 = le.iter().flatten().fold(0, |a, &m| a | m);
    let vars: Vec<usize> = (0..nv).filter(|&v| support >> v & 1 == 1).collect();
    // The largest run of consecutive indices is the chain unknown; the rest
    // is the summand.
    let mut runs: Vec<Vec<usize>> = Vec::new();
    for &v in &vars {
        match runs.last_mut() {
            Some(r) if *r.last().unwrap() + 1 == v => r.push(v),
            _ => runs.push(vec![v]),
        }
    }
    let big = runs
        .iter()
        .max_by_key(|r| r.len())
        .cloned()
        .unwrap_or_default();
    let small_mask: u64 = vars
        .iter()
        .filter(|v| !big.contains(v))
        .fold(0, |a, &v| a | (1u64 << v));
    let ml = Mac::full(&le, nv, 4);
    let ell_last = eliminate(&ml);
    let ldeg: Vec<u32> = le.iter().map(deg).collect();
    let mut ltriv: Vec<Vec<u64>> = Vec::new();
    for i in 0..le.len() {
        for j in i..le.len() {
            let dd = ldeg[i] as i64 + ldeg[j] as i64;
            for sm in monos_upto(nv, 4 - dd) {
                let mut a = Acc::new(&ml);
                if i == j {
                    let mut f1 = le[i].clone();
                    f1.push(0);
                    for m in bool_mul(&canon(f1), sm) {
                        a.toggle((i, m), &ldeg, 4);
                    }
                } else {
                    for m in bool_mul(&le[j], sm) {
                        a.toggle((i, m), &ldeg, 4);
                    }
                    for m in bool_mul(&le[i], sm) {
                        a.toggle((j, m), &ldeg, 4);
                    }
                }
                fails += a.missing;
                ltriv.push(a.v);
            }
        }
    }
    let last_link_trivial = rank_of(&ltriv);
    // Rows of `ml` whose multiplier lies in the summand's variables.
    let small_rows: Vec<usize> = (0..ml.keys.len())
        .filter(|&r| ml.keys[r].1 & !small_mask == 0)
        .collect();
    let sub = Mac {
        keys: small_rows.iter().map(|&r| ml.keys[r]).collect(),
        index: HashMap::new(),
        polys: small_rows.iter().map(|&r| ml.polys[r].clone()).collect(),
    };
    let sk = eliminate(&sub).kernel;
    let mut tps = ltriv.clone();
    for kv in &sk {
        let mut v = vec![0u64; ml.polys.len().div_ceil(64).max(1)];
        for &r in kv {
            let rr = small_rows[r];
            v[rr / 64] ^= 1u64 << (rr % 64);
        }
        if !in_kernel(&ml, &v) {
            fails += 1;
        }
        tps.push(v);
    }
    let trivial_plus_small = rank_of(&tps);
    Arm {
        arm: name.into(),
        n_vars: nv,
        eq_degrees,
        graded,
        first_fall_degree,
        linear,
        constant_derived,
        rows_4: nr4,
        cols_4,
        kernel_3: el3.kernel.len(),
        kernel_4,
        trivial_4,
        trivial_plus_identities_4,
        plus_k3_multiples_4: plus_k3,
        residual_4: kernel_4.saturating_sub(trivial_plus_identities_4),
        residual_4_with_k3: kernel_4.saturating_sub(plus_k3),
        generator_failures: fails,
        link_kernels_4,
        small_block: small_mask.count_ones() as usize,
        last_link_kernel: ell_last.kernel.len(),
        last_link_trivial,
        small_mult_kernel: sk.len(),
        trivial_plus_small,
        ms: t0.elapsed().as_secs_f64() * 1e3,
    }
}

// Same draws as examples/koblitz_x5_syzygy.rs.
fn draws_for(n: u32, rng: &mut StdRng, k: usize) -> Vec<F2mElement> {
    let mut xs = Vec::new();
    while xs.len() < k {
        let x = F2mElement::from_biguint(&BigUint::from(rng.gen_range(0..(1u64 << n))), n);
        if !x.is_zero() && x != F2mElement::one(n) {
            xs.push(x);
        }
    }
    xs
}

fn print_arm(n: u32, i: usize, a: &Arm) {
    let g: Vec<String> = a
        .graded
        .iter()
        .map(|g| format!("D={}: K {} T {} R {}", g.d, g.kernel, g.trivial, g.residual))
        .collect();
    println!(
        "n={n:>2} draw {i} {:<17} vars {} eqs {:?} | (G) {} -> first fall {} | (L) {:?}{} | (F) rows {} cols {} K3 {} K4 {} T4 {} T4+L4 {} (+K3 mult {}) residual {} ({} with K3) | failures {} | unregistered: per link (D=4 kernel, graded R3) {:?}; last link: small block {} bits, K {} T {} small-multiplier K {} T+small {} | {:.0} ms",
        a.arm,
        a.n_vars,
        a.eq_degrees,
        g.join(", "),
        a.first_fall_degree.map(|d| d.to_string()).unwrap_or_else(|| "none <= 4".into()),
        a.linear,
        if a.constant_derived.iter().any(|c| c.1) {
            format!(" constant at {:?}", a.constant_derived.iter().filter(|c| c.1).map(|c| c.0).collect::<Vec<_>>())
        } else {
            String::new()
        },
        a.rows_4,
        a.cols_4,
        a.kernel_3,
        a.kernel_4,
        a.trivial_4,
        a.trivial_plus_identities_4,
        a.plus_k3_multiples_4,
        a.residual_4,
        a.residual_4_with_k3,
        a.generator_failures,
        a.link_kernels_4,
        a.small_block,
        a.last_link_kernel,
        a.last_link_trivial,
        a.small_mult_kernel,
        a.trivial_plus_small,
        a.ms
    );
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut json: Option<String> = None;
    let mut plan: Vec<(u32, usize)> = vec![(9, 8), (11, 8), (13, 2)];
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            "--plan" => {
                i += 1;
                plan = args[i]
                    .split(',')
                    .map(|c| {
                        let (n, k) = c.split_once(':').expect("--plan n:draws,...");
                        (n.parse().unwrap(), k.parse().unwrap())
                    })
                    .collect();
            }
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let mut out: Vec<Draw> = Vec::new();
    let mut failures = 0usize;
    let mut control_ok = true;
    for (n, k) in plan {
        let ell = ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
        let irr = find_irreducible_sparse(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let mut rng = StdRng::seed_from_u64(0x5EED_0005u64 ^ ((n as u64) << 32));
        let v = random_subspace_containing_one_in(n, &irr, ell, &mut rng);
        for (di, x) in draws_for(n, &mut rng, 8).into_iter().enumerate().take(k) {
            let xs = build_decomposition_system(&v, &x, &F2mElement::one(n), 4, &st).unwrap();
            let sy = build_chained_symmetrised_system(&v, &irr, &x, &st).unwrap();
            let mut arms = Vec::new();
            for (name, eqs, nv) in [
                ("symmetrised chain", &sy.equations, sy.n_vars),
                ("x-chained", &xs.equations, xs.n_vars),
            ] {
                let a = analyse(name, eqs, nv);
                print_arm(n, di, &a);
                failures += a.generator_failures;
                if name == "x-chained" && a.graded[0].residual != 1 {
                    control_ok = false;
                }
                arms.push(a);
            }
            out.push(Draw {
                n,
                ell,
                draw: di,
                x_r: x.to_biguint().to_string(),
                arms,
            });
            if let Some(p) = &json {
                fs::write(p, serde_json::to_string_pretty(&out).unwrap()).expect("write json");
            }
        }
    }
    println!();
    println!(
        "positive control (x-chain R^h_2 = 1 on every draw): {}",
        if control_ok { "PASS" } else { "FAIL" }
    );
    println!(
        "generator failures (a generator outside its kernel, or a row out of range): {failures}"
    );
}
