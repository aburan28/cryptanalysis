//! **X6′ identification: X5′'s hidden linear equation is Kosters–Yeo's trace.**
//!
//! Companion to §X6′ of `research/notes/ecc2k130/RESEARCH_ECC2K130_ROUTE_TARGETS.md`,
//! which registered this check and its predicted outcome before it ran.
//!
//! Kosters–Yeo (arXiv 1503.08001, Prop. 4.9): for an ordinary curve over
//! `F_{2ⁿ}` and `T = S₃(X₁, X₂, x(P))`, `Tr(T/b²)` is linear in `X₁, X₂`, with
//! `b = a₁(a₁x(P) + a₃)`.  On `K₀` (`a₁ = 1`, `a₂ = a₃ = 0`) that is `b = x_R`.
//! Writing `T = Σ_j [T]_j z^j`, the functional is `c_j = Tr(z^j·x_R⁻²)`, and
//! `T/x_R² = (e + x_m)² + s² + s + a₆/x_R²` with `s = e·x_m/x_R` gives
//! `Σ_j c_j [T]_j = Tr(e + x_m) + Tr(a₆·x_R⁻²)` for every `x_R ≠ 0`.
//!
//! On every draw of X5′'s quadratic-rank protocol and of H1's own protocol,
//! this checks (a) that the quadratic parts of the `x`-chain's degree-2
//! equations have a one-dimensional left null space spanned by `c`, and (b)
//! that `Σ_j c_j f_j` is exactly that linear polynomial.  It also prints the
//! same null space for the symmetrised chain's degree-2 equations.  A negative
//! control compares the null vector with the wrong functional `Tr(z^j·x_R⁻¹)`,
//! which differs from `c` unless `x_R = 1` (excluded), and must match nowhere.
//!
//! ```text
//! cargo run --release --example koblitz_x5_trace_identity > experiments/28_koblitz_x5_trace_identity.log
//! ```

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure, SymElement,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    find_irreducible_sparse, invariant_subspace_basis,
};
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_chained_symmetrised_system, random_subspace_containing_one_in,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::{BTreeSet, HashMap};

fn degree(p: &F2BoolPoly) -> u32 {
    p.terms
        .iter()
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

fn trace(e: &F2mElement, n: u32, irr: &IrreduciblePoly) -> bool {
    let (mut acc, mut s) = (e.clone(), e.clone());
    for _ in 1..n {
        s = s.square(irr);
        acc = acc.add(&s);
    }
    debug_assert!(acc.is_zero() || acc == F2mElement::one(n));
    !acc.is_zero()
}

// Left null space of the quadratic parts of `eqs`, as coefficient vectors.
fn quad_null_space(eqs: &[&F2BoolPoly]) -> Vec<Vec<bool>> {
    let mut cols: HashMap<u64, usize> = HashMap::new();
    for e in eqs {
        for t in e.terms.iter().filter(|t| t.mask.count_ones() == 2) {
            let k = cols.len();
            cols.entry(t.mask).or_insert(k);
        }
    }
    let nc = cols.len();
    let nr = eqs.len();
    let mut mat: Vec<Vec<bool>> = eqs
        .iter()
        .enumerate()
        .map(|(i, e)| {
            let mut v = vec![false; nc + nr];
            for t in e.terms.iter().filter(|t| t.mask.count_ones() == 2) {
                v[cols[&t.mask]] ^= true;
            }
            v[nc + i] = true;
            v
        })
        .collect();
    let mut rank = 0;
    for col in 0..nc {
        if let Some(p) = (rank..nr).find(|&r| mat[r][col]) {
            mat.swap(rank, p);
            let pr = mat[rank].clone();
            for (r, row) in mat.iter_mut().enumerate() {
                if r != rank && row[col] {
                    for (a, b) in row.iter_mut().zip(&pr) {
                        *a ^= *b;
                    }
                }
            }
            rank += 1;
        }
    }
    mat[rank..].iter().map(|r| r[nc..].to_vec()).collect()
}

fn term_set(p: &F2BoolPoly) -> BTreeSet<u64> {
    p.terms.iter().map(|t| t.mask).collect()
}

struct Check {
    null_dim: usize,
    null_is_trace: bool,
    // Negative control: the wrong functional, Tr(z^j·x_R⁻¹), must not match.
    null_is_wrong_trace: bool,
    linear_matches: bool,
    sym_null_dim: Option<usize>,
}

// The two checks on the x-chained system (last link closes on x_R), and the
// null-space dimension of the symmetrised chain's degree-2 equations.
fn check(
    basis: &[F2mElement],
    irr: &IrreduciblePoly,
    x_r: &F2mElement,
    m: usize,
    with_symmetrised: bool,
) -> Option<Check> {
    let n = irr.degree;
    let st = FieldStructure::new(n, irr);
    let a6 = F2mElement::one(n);
    let sys = build_decomposition_system(basis, x_r, &a6, m, &st)?;
    let nn = n as usize;
    let quads: Vec<&F2BoolPoly> = sys.equations.iter().filter(|e| degree(e) == 2).collect();
    // The degree-2 equations are exactly the last link's n coordinates.
    assert_eq!(quads.len(), nn);
    let last = &sys.equations[sys.equations.len() - nn..];
    assert!(last
        .iter()
        .zip(&quads)
        .all(|(a, b)| term_set(a) == term_set(b)));

    let inv2 = x_r.flt_inverse(irr)?.square(irr);
    let c: Vec<bool> = (0..n)
        .map(|j| {
            trace(
                &F2mElement::from_bit_positions(&[j], n).mul(&inv2, irr),
                n,
                irr,
            )
        })
        .collect();
    let null = quad_null_space(&quads);
    let null_is_trace = null.len() == 1 && null[0] == c;
    let inv1 = x_r.flt_inverse(irr)?;
    let wrong: Vec<bool> = (0..n)
        .map(|j| {
            trace(
                &F2mElement::from_bit_positions(&[j], n).mul(&inv1, irr),
                n,
                irr,
            )
        })
        .collect();
    let null_is_wrong_trace = null.len() == 1 && null[0] == wrong;

    let mut lhs = F2BoolPoly::zero(sys.n_vars);
    for (j, f) in last.iter().enumerate() {
        if c[j] {
            lhs = lhs.add(f);
        }
    }
    let ell = basis.len();
    let e = SymElement::from_free_vars(m * ell + (m - 3) * nn, n, sys.n_vars);
    let xm = SymElement::from_subspace_vars(basis, (m - 1) * ell, n, sys.n_vars);
    let mut rhs = F2BoolPoly::zero(sys.n_vars);
    for j in 0..n {
        if trace(&F2mElement::from_bit_positions(&[j], n), n, irr) {
            rhs = rhs.add(&e.coords[j as usize]).add(&xm.coords[j as usize]);
        }
    }
    if trace(&a6.mul(&inv2, irr), n, irr) {
        rhs = rhs.add(&F2BoolPoly::one(sys.n_vars));
    }
    let linear_matches = term_set(&lhs) == term_set(&rhs) && degree(&lhs) <= 1;

    let sym_null_dim = if with_symmetrised {
        let sy = build_chained_symmetrised_system(basis, irr, x_r, &st)?;
        let q: Vec<&F2BoolPoly> = sy.equations.iter().filter(|e| degree(e) == 2).collect();
        Some(quad_null_space(&q).len())
    } else {
        None
    };
    Some(Check {
        null_dim: null.len(),
        null_is_trace,
        null_is_wrong_trace,
        linear_matches,
        sym_null_dim,
    })
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

fn report(tag: &str, checks: &[Option<Check>]) -> bool {
    let done: Vec<&Check> = checks.iter().flatten().collect();
    let ok = done
        .iter()
        .all(|c| c.null_dim == 1 && c.null_is_trace && c.linear_matches && !c.null_is_wrong_trace);
    let sym: Vec<String> = done
        .iter()
        .filter_map(|c| c.sym_null_dim.map(|d| d.to_string()))
        .collect();
    println!(
        "{tag}  draws {}/{}  null dim {:?}  (a) null vector = Tr(z^j x_R^-2): {}/{}  (b) sum = Tr(e + x_m) + Tr(a6 x_R^-2): {}/{}  control Tr(z^j x_R^-1): {}/{}{}",
        done.len(),
        checks.len(),
        done.iter().map(|c| c.null_dim).collect::<Vec<_>>(),
        done.iter().filter(|c| c.null_is_trace).count(),
        done.len(),
        done.iter().filter(|c| c.linear_matches).count(),
        done.len(),
        done.iter().filter(|c| c.null_is_wrong_trace).count(),
        done.len(),
        if sym.is_empty() {
            String::new()
        } else {
            format!("  | symmetrised chain null dim {:?}", sym)
        }
    );
    ok && done.len() == checks.len()
}

fn main() {
    let mut all = true;
    println!("== X5' quadratic-rank protocol: random V, m = 4, seed 0x5EED0005, 8 draws per rung");
    for n in [9u32, 11, 13, 15, 17, 19] {
        let ell = ((n as f64 + 24f64.log2()) / 4.0).ceil() as usize;
        let irr = find_irreducible_sparse(n).unwrap();
        let mut rng = StdRng::seed_from_u64(0x5EED_0005u64 ^ ((n as u64) << 32));
        let v = random_subspace_containing_one_in(n, &irr, ell, &mut rng);
        let checks: Vec<Option<Check>> = draws_for(n, &mut rng, 8)
            .iter()
            .map(|x| check(&v, &irr, x, 4, true))
            .collect();
        all &= report(&format!("n={n:>2} m=4 l={ell}"), &checks);
    }
    println!();
    println!(
        "== H1's own protocol: invariant V (factor index 0), x(R) from seed 0x5EED + t, 8 draws"
    );
    for (n, m) in [(9u32, 3usize), (15, 3), (21, 3), (31, 3), (9, 4), (15, 4)] {
        let (irr, basis) = invariant_subspace_basis(n, 0).unwrap();
        let checks: Vec<Option<Check>> = (0..8u64)
            .map(|t| {
                let mut rng = StdRng::seed_from_u64(0x5EED + t);
                let x = F2mElement::from_biguint(&BigUint::from(rng.gen::<u64>()), n);
                check(&basis, &irr, &x, m, false)
            })
            .collect();
        all &= report(&format!("n={n:>2} m={m} l={}", basis.len()), &checks);
    }
    println!();
    println!(
        "{}",
        if all {
            "RESULT: (a) and (b) hold on every draw: the x-chain's hidden linear equation is Kosters-Yeo Prop. 4.9."
        } else {
            "RESULT: MISMATCH on some draw (see the rows above)."
        }
    );
}
