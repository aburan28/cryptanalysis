//! Assumption 1 measured **on its own diagonal**, with an arbitrary subspace.
//!
//! Semaev 2015 (ePrint 2015/310) Assumption 1 asserts `d_F4 <= 4` for a Boolean
//! system equivalent to his eq. (5), where `V` is a subspace of `F_{2^n}` of
//! dimension `k = ceil(n/m)`.  Two words there are load-bearing and the
//! repository's existing instrument honours neither:
//!
//!   * **`k = ceil(n/m)`** — `koblitz_bench::subspace_ladder` sets the
//!     dimension to `ord_n(2)` instead.  Across `n = 5..49` odd those two
//!     never coincide at `m = 2` and coincide twice at `m = 3`.
//!   * **"a subspace"** — `invariant_subspace_basis` returns a *Frobenius
//!     invariant* subspace (a linearised-polynomial kernel from a factor of
//!     `x^n - 1`).  Assumption 1 quantifies over subspaces, not over the very
//!     special invariant ones.
//!
//! So `GOAL-DREG-001`'s ladder measures a different object family from the one
//! Assumption 1 is about, independently of the separate `d_F4`-versus-`d_reg`
//! definitional gap of `KN-OPEN-d218ec`.  This example measures the object the
//! assumption actually names: a **uniformly random** `F_2`-subspace of
//! dimension exactly `ceil(n/m)`, on the diagonal, with a matched random-system
//! control.
//!
//! What it reports is the **first fall degree** and, where the Macaulay matrix
//! fits, the **solving degree**.  Neither is Semaev's `d_F4`; that is the point
//! of `KN-OPEN-d218ec` and is NOT settled here.  What is settled is which
//! subspaces the numbers were taken on.
//!
//! ```sh
//! cargo run --release --example diagonal_assumption1 -- --m 2 --n-max 31 --trials 4
//! ```

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::koblitz_bench::random_control_system;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, first_fall_degree, solving_degree, system_degree, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

/// A uniformly random `F_2`-subspace basis of dimension `k` in `F_{2^n}`,
/// built by rejection on rank so the dimension is exactly `k`.
fn random_subspace_basis(n: u32, k: u32, rng: &mut StdRng) -> Option<Vec<F2mElement>> {
    for _ in 0..4096 {
        let mut basis: Vec<F2mElement> = Vec::new();
        let mut pivots: Vec<(u32, u64)> = Vec::new();
        for _ in 0..(4 * k + 32) {
            if basis.len() == k as usize {
                break;
            }
            let bits: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
            if bits == 0 {
                continue;
            }
            // reduce against known pivots to test independence
            let mut v = bits;
            for (p, row) in &pivots {
                if (v >> p) & 1 == 1 {
                    v ^= row;
                }
            }
            if v == 0 {
                continue;
            }
            let p = 63 - v.leading_zeros();
            pivots.push((p, v));
            pivots.sort_by_key(|a| std::cmp::Reverse(a.0));
            basis.push(F2mElement::from_bit_positions(
                &(0..n).filter(|i| (bits >> i) & 1 == 1).collect::<Vec<_>>(),
                n,
            ));
        }
        if basis.len() == k as usize {
            return Some(basis);
        }
    }
    None
}

fn random_element(n: u32, rng: &mut StdRng) -> F2mElement {
    let bits: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
    F2mElement::from_bit_positions(
        &(0..n).filter(|i| (bits >> i) & 1 == 1).collect::<Vec<_>>(),
        n,
    )
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str, default: i64| -> i64 {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    };
    let m = flag("--m", 2) as usize;
    let n_max = flag("--n-max", 31) as u32;
    let trials = flag("--trials", 4) as usize;
    let d_max = flag("--d-max", 6) as u32;
    let seed = flag("--seed", 0x0D1A6) as u64;

    println!("# Assumption 1 on its own diagonal: V a RANDOM subspace, dim k = ceil(n/m)");
    println!();
    println!("m = {m}, trials = {trials}, d_max = {d_max}, seed = {seed:#x}");
    println!();
    println!("Assumption 1 (Semaev 2015) asserts d_F4 <= 4 here. FFD and D_solve are");
    println!("NOT d_F4 (KN-OPEN-d218ec); this fixes the SUBSPACE, not the definition.");
    println!();
    println!(
        "| n | k=ceil(n/m) | vars | eqs | deg | FFD | D_solve | gap | null FFD | null D_solve |"
    );
    println!(
        "|--:|------------:|-----:|----:|----:|----:|--------:|----:|---------:|-------------:|"
    );

    let mut rng = StdRng::seed_from_u64(seed);
    for n in (5..=n_max).step_by(2) {
        let k = n.div_ceil(m as u32); // ceil(n/m)
        let irr: IrreduciblePoly = match find_irreducible_sparse(n) {
            Some(i) => i,
            None => continue,
        };
        let st = FieldStructure::new(n, &irr);
        let b = F2mElement::one(n);

        let mut ffds: Vec<u32> = Vec::new();
        let mut sols: Vec<u32> = Vec::new();
        let mut cf: Vec<u32> = Vec::new();
        let mut cs: Vec<u32> = Vec::new();
        let mut shape: Option<(usize, usize, u32)> = None;

        for _ in 0..trials {
            let basis = match random_subspace_basis(n, k, &mut rng) {
                Some(b) => b,
                None => break,
            };
            let x_r = random_element(n, &mut rng);
            let sys = match build_decomposition_system(&basis, &x_r, &b, m, &st) {
                Some(s) => s,
                None => break,
            };
            let deg = system_degree(&sys.equations);
            shape = Some((sys.n_vars, sys.equations.len(), deg));
            let (ffd, _) = first_fall_degree(&sys.equations, sys.n_vars, d_max);
            if let Some(v) = ffd {
                ffds.push(v);
            }
            let (sol, _) = solving_degree(&sys.equations, sys.n_vars, d_max);
            if let Some(v) = sol {
                sols.push(v);
            }
            // NULL OBJECT, not a replicate: a random Boolean system of matched
            // shape (vars, eqs, degree, mean monomial count). If the Semaev
            // system resolves at the same degree as this, its algebraic
            // structure is buying nothing and we measured the shape alone.
            let terms: usize = (sys.equations.iter().map(|e| e.terms.len()).sum::<usize>()
                / sys.equations.len().max(1))
            .max(1);
            let ctrl = random_control_system(
                sys.n_vars,
                sys.equations.len(),
                deg,
                terms,
                rng.gen::<u64>(),
            );
            if let (Some(v), _) = first_fall_degree(&ctrl, sys.n_vars, d_max) {
                cf.push(v);
            }
            if let (Some(v), _) = solving_degree(&ctrl, sys.n_vars, d_max) {
                cs.push(v);
            }
        }
        let mean = |v: &Vec<u32>| -> String {
            if v.is_empty() {
                "—".to_string()
            } else {
                format!("{:.2}", v.iter().sum::<u32>() as f64 / v.len() as f64)
            }
        };
        let gap = if ffds.is_empty() || sols.is_empty() {
            "—".to_string()
        } else {
            let a = sols.iter().sum::<u32>() as f64 / sols.len() as f64;
            let b2 = ffds.iter().sum::<u32>() as f64 / ffds.len() as f64;
            format!("{:+.2}", a - b2)
        };
        if let Some((vars, eqs, deg)) = shape {
            println!(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |",
                n,
                k,
                vars,
                eqs,
                deg,
                mean(&ffds),
                mean(&sols),
                gap,
                mean(&cf),
                mean(&cs)
            );
        }
    }
    println!();
    println!("Assumption 1 is about d_F4, which is measured by NEITHER column here.");
    println!("A FFD or D_solve above 4 is not by itself a refutation of it.");
}
