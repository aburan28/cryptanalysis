//! **X5‴: what the symmetrised last link's residual syzygies are.**
//!
//! Companion to §X5‴ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`,
//! which registered the hypothesis, the gates and the draws before this
//! driver existed.
//!
//! The chain's last link, with the target's coordinate known, is for each
//! value `σ` of its small block (the summand's bits and, symmetrised, `ε`) an
//! `F₂`-linear system in the chain unknown `U`, with a one-dimensional
//! cokernel killed by a trace functional `ψ_σ`:
//!
//! - symmetrised: `Φ = a(U² + U) + U² + d`, `a = w_R·AS(v)`,
//!   `ψ_σ(z) = Tr(z·(1 + a)/a²)` (zero if `a ∈ {0, 1}`);
//! - `x`-chained: `T = αe² + βe + c`, `α = x_m² + x_R²`, `β = x_R x_m`,
//!   `ψ_σ(z) = Tr(z·α/β²)` (zero if `αβ = 0`).
//!
//! `P_4` is the set of degree-4 syzygies whose value at every point lies in
//! `span(ψ_σ)`.  H: `T_4 + P_4` (with the `x`-link's trace identities and
//! `K_3` multiples) spans the link's whole degree-4 left kernel `K_4`.
//!
//! ```text
//! cargo run --release --example koblitz_x5_residual -- --json experiments/30_koblitz_x5_residual.json > experiments/30_koblitz_x5_residual.log
//! ```

use std::collections::HashMap;
use std::env;
use std::fs;
use std::time::Instant;

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_chained_symmetrised_system, random_subspace_containing_one_in,
};
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

fn bool_mul(p: &Poly, s: u64) -> Poly {
    canon(p.iter().map(|&m| m | s).collect())
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

fn eval(p: &Poly, x: u64) -> bool {
    p.iter().filter(|&&m| m & x == m).count() % 2 == 1
}

struct Mac {
    keys: Vec<(usize, u64)>,
    index: HashMap<(usize, u64), usize>,
    polys: Vec<Poly>,
}

impl Mac {
    fn full(eqs: &[Poly], nv: usize, d: u32, allow: impl Fn(u64) -> bool) -> Self {
        let mut m = Mac {
            keys: Vec::new(),
            index: HashMap::new(),
            polys: Vec::new(),
        };
        for (i, f) in eqs.iter().enumerate() {
            for t in monos_upto(nv, d as i64 - deg(f) as i64) {
                if !allow(t) {
                    continue;
                }
                let p = bool_mul(f, t);
                if p.is_empty() {
                    continue;
                }
                m.index.insert((i, t), m.keys.len());
                m.keys.push((i, t));
                m.polys.push(p);
            }
        }
        m
    }
}

struct Elim {
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

fn in_kernel(mac: &Mac, v: &[u64]) -> bool {
    let mut acc: Vec<u64> = Vec::new();
    for (r, p) in mac.polys.iter().enumerate() {
        if v[r / 64] >> (r % 64) & 1 == 1 {
            acc.extend_from_slice(p);
        }
    }
    canon(acc).is_empty()
}

fn rowvec(
    mac: &Mac,
    keys: impl IntoIterator<Item = (usize, u64)>,
    missing: &mut usize,
) -> Vec<u64> {
    let mut v = vec![0u64; mac.polys.len().div_ceil(64).max(1)];
    for key in keys {
        match mac.index.get(&key) {
            Some(&r) => v[r / 64] ^= 1u64 << (r % 64),
            None => {
                // Dropped rows are zero products.  Every link equation has
                // degree 2, so a multiplier above degree 2 is an error.
                if popc(key.1) > 2 {
                    *missing += 1;
                }
            }
        }
    }
    v
}

// An incremental echelon basis of vectors in F₂^k (k ≤ 64·w).
struct Echelon {
    w: usize,
    rows: Vec<Option<Vec<u64>>>,
    rank: usize,
}

impl Echelon {
    fn new(k: usize) -> Self {
        Echelon {
            w: k.div_ceil(64).max(1),
            rows: vec![None; k],
            rank: 0,
        }
    }
    fn insert(&mut self, mut v: Vec<u64>) {
        loop {
            let Some(p) = (0..self.w)
                .find_map(|i| (v[i] != 0).then(|| i * 64 + v[i].trailing_zeros() as usize))
            else {
                return;
            };
            match &self.rows[p] {
                Some(r) => {
                    for (a, b) in v.iter_mut().zip(r) {
                        *a ^= *b;
                    }
                }
                None => {
                    self.rows[p] = Some(v);
                    self.rank += 1;
                    return;
                }
            }
        }
    }
    // Basis of { α : ⟨α, row⟩ = 0 for every inserted row }.
    fn null_space(&self, k: usize) -> Vec<Vec<u64>> {
        // Reduce to RREF over the pivots.
        let mut rows: Vec<(usize, Vec<u64>)> = self
            .rows
            .iter()
            .enumerate()
            .filter_map(|(p, r)| r.clone().map(|r| (p, r)))
            .collect();
        for i in (0..rows.len()).rev() {
            let (pi, ri) = rows[i].clone();
            for (_, rj) in rows.iter_mut().take(i) {
                if rj[pi / 64] >> (pi % 64) & 1 == 1 {
                    for (a, b) in rj.iter_mut().zip(&ri) {
                        *a ^= *b;
                    }
                }
            }
        }
        let pivots: Vec<usize> = rows.iter().map(|r| r.0).collect();
        (0..k)
            .filter(|c| !pivots.contains(c))
            .map(|free| {
                let mut a = vec![0u64; self.w];
                a[free / 64] |= 1u64 << (free % 64);
                for (p, r) in &rows {
                    if r[free / 64] >> (free % 64) & 1 == 1 {
                        a[p / 64] |= 1u64 << (p % 64);
                    }
                }
                a
            })
            .collect()
    }
}

fn trace(e: &F2mElement, n: u32, irr: &IrreduciblePoly) -> bool {
    let (mut acc, mut s) = (e.clone(), e.clone());
    for _ in 1..n {
        s = s.square(irr);
        acc = acc.add(&s);
    }
    !acc.is_zero()
}

fn field_from_bits(bits: u64, basis: &[F2mElement], n: u32) -> F2mElement {
    let mut acc = F2mElement::zero(n);
    for (i, b) in basis.iter().enumerate() {
        if bits >> i & 1 == 1 {
            acc = acc.add(b);
        }
    }
    acc
}

#[derive(Serialize, Default, Clone)]
struct Arm {
    arm: String,
    n_vars: usize,
    small_bits: usize,
    kernel_4: usize,
    trivial_4: usize,
    identities_4: usize,
    p4: usize,
    explained: usize,
    residual_unexplained: usize,
    /// Descriptive: `dim(T_4 + K_4(S)) − dim T_4` for multiplier classes S.
    residual_u_deg0: usize,
    residual_u_deg_le1: usize,
    residual_small_deg0: usize,
    residual_small_deg_le1: usize,
    /// Added after the registered run (same draws, descriptive): multipliers
    /// of bidegree ≤ (1, 1), i.e. {1, U_k, σ_l, U_k σ_l}.
    residual_both_le1: usize,
    /// Added after the registered run: the span of the U-deg ≤ 1 and the
    /// small-deg ≤ 1 kernels together.
    residual_union_le1: usize,
    /// Descriptive: small-block points with ψ_σ = 0, and consistent ones.
    points_psi_zero: usize,
    points_consistent: usize,
    gate_constant_in_u: bool,
    gate_x5pp: Option<bool>,
    generator_failures: usize,
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

struct Link {
    eqs: Vec<Poly>,
    nv: usize,
    n: usize,
    small: usize,
    // ψ_σ for each small-block value σ (bits of the small block), as a bit
    // vector over the equations; and the field-level constant check needs
    // nothing else.
    psi: Vec<Vec<bool>>,
}

fn remap(p: &Poly, map: &HashMap<usize, usize>) -> Poly {
    let known: u64 = map.keys().fold(0, |a, &k| a | (1u64 << k));
    assert!(
        p.iter().all(|&m| m & !known == 0),
        "a link equation uses a variable outside its block"
    );
    canon(
        p.iter()
            .map(|&m| {
                let mut out = 0u64;
                for (&from, &to) in map {
                    if m >> from & 1 == 1 {
                        out |= 1u64 << to;
                    }
                }
                out
            })
            .collect(),
    )
}

fn analyse(name: &str, link: &Link, x5pp: Option<(usize, usize)>) -> Arm {
    let t0 = Instant::now();
    let (eqs, nv, n) = (&link.eqs, link.nv, link.n);
    let degs: Vec<u32> = eqs.iter().map(deg).collect();
    let mut fails = 0usize;
    let u_mask: u64 = (1u64 << n) - 1;

    // Gate (i): Σ_j ψ_{σ,j} f_j is constant in U at every σ.
    let mut gate_constant = true;
    let mut psi_zero = 0usize;
    let mut consistent = 0usize;
    for (sig, psi) in link.psi.iter().enumerate() {
        if psi.iter().all(|&b| !b) {
            psi_zero += 1;
            continue;
        }
        let val = |u: u64| -> bool {
            let x = u | ((sig as u64) << n);
            eqs.iter()
                .zip(psi)
                .filter(|(_, &c)| c)
                .fold(false, |a, (f, _)| a ^ eval(f, x))
        };
        let k0 = val(0);
        if (0..1u64 << n).any(|u| val(u) != k0) {
            gate_constant = false;
        }
        if !k0 {
            consistent += 1;
        }
    }

    let m4 = Mac::full(eqs, nv, 4, |_| true);
    let el4 = eliminate(&m4);
    let kernel_4 = el4.kernel.len();
    let kvecs: Vec<Vec<u64>> = el4
        .kernel
        .iter()
        .map(|kv| rowvec(&m4, kv.iter().map(|&r| m4.keys[r]), &mut fails))
        .collect();

    // T_4.
    let mut triv: Vec<Vec<u64>> = Vec::new();
    for i in 0..eqs.len() {
        for j in i..eqs.len() {
            let dd = degs[i] as i64 + degs[j] as i64;
            for s in monos_upto(nv, 4 - dd) {
                let keys: Vec<(usize, u64)> = if i == j {
                    let mut f1 = eqs[i].clone();
                    f1.push(0);
                    bool_mul(&canon(f1), s)
                        .into_iter()
                        .map(|m| (i, m))
                        .collect()
                } else {
                    bool_mul(&eqs[j], s)
                        .into_iter()
                        .map(|m| (i, m))
                        .chain(bool_mul(&eqs[i], s).into_iter().map(|m| (j, m)))
                        .collect()
                };
                let v = rowvec(&m4, keys, &mut fails);
                if !in_kernel(&m4, &v) {
                    fails += 1;
                }
                triv.push(v);
            }
        }
    }
    let trivial_4 = rank_of(&triv);

    // Λ_4 and K_3 multiples (the x-link's trace identities), as in X5″.
    let mut ident: Vec<Vec<u64>> = Vec::new();
    let m2 = Mac::full(eqs, nv, 2, |_| true);
    let m3 = Mac::full(eqs, nv, 3, |_| true);
    let (el2, el3) = (eliminate(&m2), eliminate(&m3));
    let lin: Vec<(Poly, Vec<(usize, u64)>, u32)> = [(&m2, &el2), (&m3, &el3)]
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
    for (h, g, delta) in &lin {
        let mut h1 = h.clone();
        h1.push(0);
        let h1 = canon(h1);
        for s in monos_upto(nv, 3 - *delta as i64) {
            let keys: Vec<(usize, u64)> = g
                .iter()
                .flat_map(|&(i, t)| bool_mul(&h1, s | t).into_iter().map(move |u| (i, u)))
                .collect();
            ident.push(rowvec(&m4, keys, &mut fails));
        }
    }
    for a in 0..lin.len() {
        for b in a + 1..lin.len() {
            let (ha, ga, da) = &lin[a];
            let (hb, gb, db) = &lin[b];
            for s in monos_upto(nv, 3 - (*da).max(*db) as i64) {
                let keys: Vec<(usize, u64)> =
                    ga.iter()
                        .flat_map(|&(i, t)| bool_mul(hb, s | t).into_iter().map(move |u| (i, u)))
                        .chain(gb.iter().flat_map(|&(i, t)| {
                            bool_mul(ha, s | t).into_iter().map(move |u| (i, u))
                        }))
                        .collect();
                ident.push(rowvec(&m4, keys, &mut fails));
            }
        }
    }
    for kv in &el3.kernel {
        let g: Vec<(usize, u64)> = kv.iter().map(|&r| m3.keys[r]).collect();
        let delta = g.iter().map(|&(i, t)| popc(t) + degs[i]).max().unwrap_or(0);
        for s in monos_upto(nv, 4 - delta as i64) {
            ident.push(rowvec(&m4, g.iter().map(|&(i, t)| (i, t | s)), &mut fails));
        }
    }
    for v in &ident {
        if !in_kernel(&m4, v) {
            fails += 1;
        }
    }
    let mut ti = triv.clone();
    ti.extend(ident.iter().cloned());
    let with_identities = rank_of(&ti);

    // P_4: combinations α of the kernel basis whose multipliers lie in
    // span(ψ_σ) at every point.  Multipliers have degree ≤ 2 (every
    // equation has degree 2), so G_j(x) = c_j + Σ_i l_{j,i}x_i +
    // Σ_{i<k} q_{j,ik} x_i x_k, each coefficient a k-bit vector over α.
    let k = kernel_4;
    let kw = k.div_ceil(64).max(1);
    let neq = eqs.len();
    let mut coef_c = vec![vec![0u64; kw]; neq];
    let mut coef_l = vec![vec![vec![0u64; kw]; nv]; neq];
    let mut coef_q = vec![vec![vec![0u64; kw]; nv * nv]; neq];
    for (r, kv) in el4.kernel.iter().enumerate() {
        for &row in kv {
            let (j, t) = m4.keys[row];
            let bits: Vec<usize> = (0..nv).filter(|&b| t >> b & 1 == 1).collect();
            let slot = match bits.len() {
                0 => &mut coef_c[j],
                1 => &mut coef_l[j][bits[0]],
                2 => &mut coef_q[j][bits[0] * nv + bits[1]],
                _ => {
                    fails += 1;
                    continue;
                }
            };
            slot[r / 64] ^= 1u64 << (r % 64);
        }
    }
    let nsig = link.psi.len();
    let partial: Vec<Echelon> = (0..nsig)
        .into_par_iter()
        .map(|sig| {
            let mut ech = Echelon::new(k);
            let psi = &link.psi[sig];
            let p = psi.iter().position(|&b| b);
            let mut g = vec![vec![0u64; kw]; neq];
            for u in 0..1u64 << n {
                let x = u | ((sig as u64) << n);
                let bits: Vec<usize> = (0..nv).filter(|&b| x >> b & 1 == 1).collect();
                for (j, gj) in g.iter_mut().enumerate() {
                    gj.copy_from_slice(&coef_c[j]);
                    for &a in &bits {
                        for (d, s) in gj.iter_mut().zip(&coef_l[j][a]) {
                            *d ^= *s;
                        }
                    }
                    for (ai, &a) in bits.iter().enumerate() {
                        for &b in &bits[ai + 1..] {
                            for (d, s) in gj.iter_mut().zip(&coef_q[j][a * nv + b]) {
                                *d ^= *s;
                            }
                        }
                    }
                }
                for j in 0..neq {
                    let row: Vec<u64> = match p {
                        Some(pp) if j == pp => continue,
                        Some(pp) if psi[j] => g[j].iter().zip(&g[pp]).map(|(a, b)| a ^ b).collect(),
                        _ => g[j].clone(),
                    };
                    ech.insert(row);
                }
                if ech.rank == k {
                    break;
                }
            }
            ech
        })
        .collect();
    let mut ech = Echelon::new(k);
    for e in partial {
        for r in e.rows.into_iter().flatten() {
            ech.insert(r);
        }
    }
    let alphas = ech.null_space(k);
    let pvecs: Vec<Vec<u64>> = alphas
        .iter()
        .map(|a| {
            let mut v = vec![0u64; m4.polys.len().div_ceil(64).max(1)];
            for (r, kv) in kvecs.iter().enumerate() {
                if a[r / 64] >> (r % 64) & 1 == 1 {
                    for (d, s) in v.iter_mut().zip(kv) {
                        *d ^= *s;
                    }
                }
            }
            if !in_kernel(&m4, &v) {
                fails += 1;
            }
            v
        })
        .collect();
    let p4 = rank_of(&pvecs);
    let mut all = ti.clone();
    all.extend(pvecs);
    let explained = rank_of(&all);

    // Descriptive: the residual realised with restricted multipliers.
    let small_mask = !u_mask;
    let kernel_in = |allow: &dyn Fn(u64) -> bool| -> Vec<Vec<u64>> {
        let m = Mac::full(eqs, nv, 4, allow);
        eliminate(&m)
            .kernel
            .iter()
            .map(|kv| rowvec(&m4, kv.iter().map(|&r| m.keys[r]), &mut 0))
            .collect()
    };
    let realised = |ks: &[&Vec<Vec<u64>>]| -> usize {
        let mut vs = triv.clone();
        for k in ks {
            vs.extend(k.iter().cloned());
        }
        rank_of(&vs) - trivial_4
    };
    let k_u0 = kernel_in(&|t| t & u_mask == 0);
    let k_u1 = kernel_in(&|t| popc(t & u_mask) <= 1);
    let k_s0 = kernel_in(&|t| t & small_mask == 0);
    let k_s1 = kernel_in(&|t| popc(t & small_mask) <= 1);
    let k_b1 = kernel_in(&|t| popc(t & u_mask) <= 1 && popc(t & small_mask) <= 1);
    let residual_u_deg0 = realised(&[&k_u0]);
    let residual_u_deg_le1 = realised(&[&k_u1]);
    let residual_small_deg0 = realised(&[&k_s0]);
    let residual_small_deg_le1 = realised(&[&k_s1]);
    let residual_both_le1 = realised(&[&k_b1]);
    let residual_union_le1 = realised(&[&k_u1, &k_s1]);

    Arm {
        arm: name.into(),
        n_vars: nv,
        small_bits: link.small,
        kernel_4,
        trivial_4,
        identities_4: with_identities - trivial_4,
        p4,
        explained,
        residual_unexplained: kernel_4.saturating_sub(explained),
        residual_u_deg0,
        residual_u_deg_le1,
        residual_small_deg0,
        residual_small_deg_le1,
        residual_both_le1,
        residual_union_le1,
        points_psi_zero: psi_zero,
        points_consistent: consistent,
        gate_constant_in_u: gate_constant,
        gate_x5pp: x5pp.map(|(k4, t4)| k4 == kernel_4 && t4 == trivial_4),
        generator_failures: fails,
        ms: t0.elapsed().as_secs_f64() * 1e3,
    }
}

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

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mut json: Option<String> = None;
    let mut x5pp_path = "experiments/29_koblitz_x5_syzygy_split.json".to_string();
    let mut plan: Vec<(u32, usize)> = vec![(9, 8), (11, 8), (13, 2)];
    // Diagnostic for gate (ii) on the x-arm: X5″ built its last-link matrix
    // with multipliers over the whole chain's variables.  With this flag the
    // x-link's K_4 is recomputed that way and printed; nothing else runs.
    let mut pad_check = false;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--json" => {
                i += 1;
                json = Some(args[i].clone());
            }
            "--x5pp" => {
                i += 1;
                x5pp_path = args[i].clone();
            }
            "--pad-check" => pad_check = true,
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
    // X5″'s last-link values, for gate (ii).
    let x5pp: HashMap<(u32, usize, String), (usize, usize)> = fs::read_to_string(&x5pp_path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .map(|v| {
            v.as_array()
                .unwrap()
                .iter()
                .flat_map(|d| {
                    let n = d["n"].as_u64().unwrap() as u32;
                    let di = d["draw"].as_u64().unwrap() as usize;
                    d["arms"].as_array().unwrap().iter().map(move |a| {
                        (
                            (n, di, a["arm"].as_str().unwrap().to_string()),
                            (
                                a["last_link_kernel"].as_u64().unwrap() as usize,
                                a["last_link_trivial"].as_u64().unwrap() as usize,
                            ),
                        )
                    })
                })
                .collect()
        })
        .unwrap_or_default();

    let mut out: Vec<Draw> = Vec::new();
    let mut ok = true;
    for (n, k) in plan {
        let ell = ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
        let irr = find_irreducible_sparse(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let mut rng = StdRng::seed_from_u64(0x5EED_0005u64 ^ ((n as u64) << 32));
        let v = random_subspace_containing_one_in(n, &irr, ell, &mut rng);
        let nn = n as usize;
        let as_ = |e: &F2mElement| e.square(&irr).add(e);
        for (di, x) in draws_for(n, &mut rng, 8).into_iter().enumerate().take(k) {
            let mut arms = Vec::new();
            // Symmetrised: last link = equations[2n..3n]; unknowns U₂, the
            // fourth summand's ℓ − 1 bits, ε.
            let sy = build_chained_symmetrised_system(&v, &irr, &x, &st).unwrap();
            let ell_w = sy.ell_w;
            let eps = 4 * ell_w;
            let off2 = eps + 1 + nn;
            let mut map: HashMap<usize, usize> = HashMap::new();
            for b in 0..nn {
                map.insert(off2 + b, b);
            }
            for b in 0..ell_w {
                map.insert(3 * ell_w + b, nn + b);
            }
            map.insert(eps, nn + ell_w);
            let eqs: Vec<Poly> = sy.equations[2 * nn..3 * nn]
                .iter()
                .map(|p| remap(&canon(p.terms.iter().map(|t| t.mask).collect()), &map))
                .collect();
            let w_r = as_(&sy.u_r);
            let small = ell_w + 1;
            let psi: Vec<Vec<bool>> = (0..1usize << small)
                .map(|sig| {
                    let vv = field_from_bits(sig as u64 & ((1 << ell_w) - 1), &v[1..], n);
                    let a = w_r.mul(&as_(&vv), &irr);
                    if a.is_zero() || a == F2mElement::one(n) {
                        return vec![false; nn];
                    }
                    let one_a = a.add(&F2mElement::one(n));
                    let coef = one_a.mul(&a.square(&irr).flt_inverse(&irr).unwrap(), &irr);
                    (0..n)
                        .map(|j| {
                            trace(
                                &F2mElement::from_bit_positions(&[j], n).mul(&coef, &irr),
                                n,
                                &irr,
                            )
                        })
                        .collect()
                })
                .collect();
            let link = Link {
                eqs,
                nv: nn + small,
                n: nn,
                small,
                psi,
            };
            let a = analyse(
                "symmetrised chain",
                &link,
                x5pp.get(&(n, di, "symmetrised chain".into())).copied(),
            );
            arms.push(a);

            // x-chained: last link = the last n equations; unknowns e (the
            // second intermediate, n bits) and the fourth summand's ℓ bits.
            let xs = build_decomposition_system(&v, &x, &F2mElement::one(n), 4, &st).unwrap();
            let e_off = 4 * ell + nn;
            let mut map: HashMap<usize, usize> = HashMap::new();
            for b in 0..nn {
                map.insert(e_off + b, b);
            }
            for b in 0..ell {
                map.insert(3 * ell + b, nn + b);
            }
            let len = xs.equations.len();
            let eqs: Vec<Poly> = xs.equations[len - nn..]
                .iter()
                .map(|p| remap(&canon(p.terms.iter().map(|t| t.mask).collect()), &map))
                .collect();
            if pad_check {
                let raw: Vec<Poly> = xs.equations[len - nn..]
                    .iter()
                    .map(|p| canon(p.terms.iter().map(|t| t.mask).collect()))
                    .collect();
                let k4 = eliminate(&Mac::full(&raw, xs.n_vars, 4, |_| true))
                    .kernel
                    .len();
                let k3 = eliminate(&Mac::full(&raw, xs.n_vars, 3, |_| true))
                    .kernel
                    .len();
                let x5 = x5pp.get(&(n, di, "x-chained".into())).map(|v| v.0);
                println!(
                    "pad-check n={n:>2} draw {di} x-link over the chain's {} variables: K4 {k4} (X5'' {:?}), K3 {k3}",
                    xs.n_vars, x5
                );
                continue;
            }
            let x2 = x.square(&irr);
            let psi: Vec<Vec<bool>> = (0..1usize << ell)
                .map(|sig| {
                    let xm = field_from_bits(sig as u64, &v, n);
                    let alpha = xm.square(&irr).add(&x2);
                    let beta = x.mul(&xm, &irr);
                    if alpha.is_zero() || beta.is_zero() {
                        return vec![false; nn];
                    }
                    let coef = alpha.mul(&beta.square(&irr).flt_inverse(&irr).unwrap(), &irr);
                    (0..n)
                        .map(|j| {
                            trace(
                                &F2mElement::from_bit_positions(&[j], n).mul(&coef, &irr),
                                n,
                                &irr,
                            )
                        })
                        .collect()
                })
                .collect();
            let link = Link {
                eqs,
                nv: nn + ell,
                n: nn,
                small: ell,
                psi,
            };
            let b = analyse(
                "x-chained",
                &link,
                x5pp.get(&(n, di, "x-chained".into())).copied(),
            );
            arms.push(b);

            for a in &arms {
                println!(
                    "n={n:>2} draw {di} {:<17} N {} (small {}) | K4 {} T4 {} +identities {} | P4 {} explained {} unexplained {} | residual by multiplier class: U-deg0 {} U-deg<=1 {} small-deg0 {} small-deg<=1 {} both<=1 {} union {} | psi=0 at {} points, consistent at {} | gates: constant-in-U {} X5'' {:?} failures {} | {:.0} ms",
                    a.arm, a.n_vars, a.small_bits, a.kernel_4, a.trivial_4, a.identities_4, a.p4, a.explained,
                    a.residual_unexplained, a.residual_u_deg0, a.residual_u_deg_le1, a.residual_small_deg0,
                    a.residual_small_deg_le1, a.residual_both_le1, a.residual_union_le1, a.points_psi_zero, a.points_consistent, a.gate_constant_in_u,
                    a.gate_x5pp, a.generator_failures, a.ms
                );
                ok &=
                    a.gate_constant_in_u && a.gate_x5pp != Some(false) && a.generator_failures == 0;
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
        "gates (constant in U, X5'' agreement, no generator failures): {}",
        if ok { "PASS" } else { "FAIL" }
    );
}
