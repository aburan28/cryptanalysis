//! **X5′ diagnostic: what the `x`-chain's fall at `D = 3` is.**
//!
//! Companion to §X5′ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`.
//! The `x`-chained systems lose rank at `D = 3` by exactly one on every draw.
//! With `x_R` known, the last link is `S₃ = t² + x_R·t + x_R²(a + b) + 1` with
//! `t = ab + x_R(a + b)`, and `t ↦ t² + x_R·t` is `F₂`-linear with kernel
//! `{0, x_R}`: one functional of the link's `n` quadratic equations kills every
//! quadratic term and leaves a linear equation `λ`, whose Boolean identity
//! `λ(λ + 1) = 0` is the rank loss at `D = 3`.  This prints the rank of the
//! degree-2 equations' quadratic parts (`n − 1` if the hidden linear equation
//! is there), the left kernels at `D = 3`, and the kernels at `D = 4` against
//! the trivial syzygies `f(f + 1)` and `f_i f_j = f_j f_i`.
//!
//! ```text
//! cargo run --release --example koblitz_x5_syzygy > experiments/27_koblitz_x5_syzygy.log
//! ```

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    find_irreducible_sparse, invariant_subspace_basis,
};
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_chained_symmetrised_system, random_subspace_containing_one_in,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::HashMap;

// Left kernel of the degree-d Macaulay matrix: returns, per kernel vector,
// its support as (equation index, multiplier mask).
fn left_kernel(
    eqs: &[F2BoolPoly],
    n_vars: usize,
    d: u32,
) -> (usize, usize, Vec<Vec<(usize, u64)>>) {
    let mut rows: Vec<(usize, u64, Vec<u64>)> = Vec::new();
    for (i, e) in eqs.iter().enumerate() {
        let de = e
            .terms
            .iter()
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        let mut mults = vec![0u64];
        if de < d {
            for v in 0..n_vars {
                mults.push(1u64 << v);
            }
        }
        if de + 2 <= d {
            for a in 0..n_vars {
                for b in a + 1..n_vars {
                    mults.push((1u64 << a) | (1u64 << b));
                }
            }
        }
        for m in mults {
            let p = e.mul_mono(F2BoolMono::from_mask(m));
            if p.is_zero() {
                continue;
            }
            rows.push((i, m, p.terms.iter().map(|t| t.mask).collect()));
        }
    }
    let mut colidx: HashMap<u64, usize> = HashMap::new();
    for r in &rows {
        for &c in &r.2 {
            let k = colidx.len();
            colidx.entry(c).or_insert(k);
        }
    }
    let nc = colidx.len();
    let nr = rows.len();
    let wc = nc.div_ceil(64);
    let wr = nr.div_ceil(64);
    let mut mat: Vec<Vec<u64>> = rows
        .iter()
        .enumerate()
        .map(|(ri, r)| {
            let mut v = vec![0u64; wc + wr];
            for c in &r.2 {
                let j = colidx[c];
                v[j / 64] ^= 1u64 << (j % 64);
            }
            v[wc + ri / 64] |= 1u64 << (ri % 64);
            v
        })
        .collect();
    let mut pivot_row = 0;
    for col in 0..nc {
        let w = col / 64;
        let b = 1u64 << (col % 64);
        if let Some(p) = (pivot_row..nr).find(|&r| mat[r][w] & b != 0) {
            mat.swap(pivot_row, p);
            let pr = mat[pivot_row].clone();
            for r in 0..nr {
                if r != pivot_row && mat[r][w] & b != 0 {
                    for k in 0..wc + wr {
                        mat[r][k] ^= pr[k];
                    }
                }
            }
            pivot_row += 1;
        }
    }
    let mut kernel = Vec::new();
    for r in pivot_row..nr {
        let mut sup = Vec::new();
        for ri in 0..nr {
            if mat[r][wc + ri / 64] >> (ri % 64) & 1 == 1 {
                sup.push((rows[ri].0, rows[ri].1));
            }
        }
        kernel.push(sup);
    }
    (nr, nc, kernel)
}

// Rank over F2 of the degree-2 homogeneous parts of the degree-2 equations,
// and the number of linear combinations whose quadratic part vanishes.
fn quad_rank(eqs: &[F2BoolPoly]) -> (usize, usize) {
    let quads: Vec<Vec<u64>> = eqs
        .iter()
        .filter(|e| {
            e.terms
                .iter()
                .map(|t| t.mask.count_ones())
                .max()
                .unwrap_or(0)
                == 2
        })
        .map(|e| {
            e.terms
                .iter()
                .filter(|t| t.mask.count_ones() == 2)
                .map(|t| t.mask)
                .collect()
        })
        .collect();
    let mut cols: HashMap<u64, usize> = HashMap::new();
    for q in &quads {
        for &m in q {
            let k = cols.len();
            cols.entry(m).or_insert(k);
        }
    }
    let w = cols.len().div_ceil(64).max(1);
    let mut mat: Vec<Vec<u64>> = quads
        .iter()
        .map(|q| {
            let mut v = vec![0u64; w];
            for m in q {
                let j = cols[m];
                v[j / 64] ^= 1u64 << (j % 64);
            }
            v
        })
        .collect();
    let mut rank = 0;
    for col in 0..cols.len() {
        let (wi, b) = (col / 64, 1u64 << (col % 64));
        if let Some(p) = (rank..mat.len()).find(|&r| mat[r][wi] & b != 0) {
            mat.swap(rank, p);
            let pr = mat[rank].clone();
            for r in 0..mat.len() {
                if r != rank && mat[r][wi] & b != 0 {
                    for k in 0..w {
                        mat[r][k] ^= pr[k];
                    }
                }
            }
            rank += 1;
        }
    }
    (quads.len(), rank)
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
    println!("== quadratic-part rank of the degree-2 equations (the last link), X5' protocol: random V, seed 0x5EED0005");
    for n in [9u32, 11, 13, 15, 17, 19] {
        let ell = ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
        let irr = find_irreducible_sparse(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let mut rng = StdRng::seed_from_u64(0x5EED_0005u64 ^ ((n as u64) << 32));
        let v = random_subspace_containing_one_in(n, &irr, ell, &mut rng);
        let (mut xr, mut sr) = (Vec::new(), Vec::new());
        for x in draws_for(n, &mut rng, 8) {
            let xs = build_decomposition_system(&v, &x, &F2mElement::one(n), 4, &st).unwrap();
            let sy = build_chained_symmetrised_system(&v, &irr, &x, &st).unwrap();
            let (q, r) = quad_rank(&xs.equations);
            xr.push(format!("{r}/{q}"));
            let (q, r) = quad_rank(&sy.equations);
            sr.push(format!("{r}/{q}"));
        }
        println!(
            "n={n:>2} m=4  x-chained {:?}  symmetrised chain {:?}",
            xr, sr
        );
    }
    println!();
    println!("== the same, on H1's own protocol: invariant V (factor index 0), x(R) from seed 0x5EED + t");
    for (n, m) in [(9u32, 3usize), (15, 3), (21, 3), (31, 3), (9, 4), (15, 4)] {
        let (irr, basis) = invariant_subspace_basis(n, 0).unwrap();
        let st = FieldStructure::new(n, &irr);
        let mut out = Vec::new();
        for t in 0..8u64 {
            let mut rng = StdRng::seed_from_u64(0x5EED + t);
            let x = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);
            let sys = build_decomposition_system(&basis, &x, &F2mElement::one(n), m, &st).unwrap();
            let (q, r) = quad_rank(&sys.equations);
            out.push(format!("{r}/{q}"));
        }
        println!("n={n:>2} m={m} l={}  x-chained {:?}", basis.len(), out);
    }
    println!();
    for (n, d, k) in [(11u32, 3u32, 4usize), (9, 4, 2)] {
        let ell = ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
        let irr = find_irreducible_sparse(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let mut rng = StdRng::seed_from_u64(0x5EED_0005u64 ^ ((n as u64) << 32));
        let v = random_subspace_containing_one_in(n, &irr, ell, &mut rng);
        println!("== left kernels of the Macaulay matrix at D = {d}, n = {n} (the trivial syzygies f(f+1) and f_i f_j = f_j f_i of the n degree-2 equations first appear at D = 4: n + C(n,2) = {} of them, if independent)", n + n * (n - 1) / 2);
        for (i, x) in draws_for(n, &mut rng, k).into_iter().enumerate() {
            let xs = build_decomposition_system(&v, &x, &F2mElement::one(n), 4, &st).unwrap();
            let sy = build_chained_symmetrised_system(&v, &irr, &x, &st).unwrap();
            for (name, eqs, nv) in [
                ("x-chained", &xs.equations, xs.n_vars),
                ("symmetrised chain", &sy.equations, sy.n_vars),
            ] {
                let (nr, nc, kern) = left_kernel(eqs, nv, d);
                let detail: Vec<String> = kern
                    .iter()
                    .take(4)
                    .map(|s| {
                        let e: std::collections::BTreeSet<usize> = s.iter().map(|p| p.0).collect();
                        format!(
                            "{} rows over equations {}..={}",
                            s.len(),
                            e.iter().next().unwrap(),
                            e.iter().last().unwrap()
                        )
                    })
                    .collect();
                println!(
                    "draw {i} {name:<17} rows {nr} cols {nc} kernel dim {}{}",
                    kern.len(),
                    if d == 3 && !detail.is_empty() {
                        format!(": {}", detail.join("; "))
                    } else {
                        String::new()
                    }
                );
            }
        }
    }
}
