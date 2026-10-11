//! **A RECORDED DEAD END.** This is not a working degree instrument. It is kept
//! because the reason it fails is a design requirement for the next one.
//!
//! ## What was attempted
//!
//! `IMP-SEMBIN-ENGINE` records that no available engine reports a statistic
//! definitionally commensurable with Semaev's `d_F4`. The idea here was to
//! sidestep the definition by testing the **binary predicate** Assumption 1
//! actually asserts -- does a degree-<= 4 computation resolve the system? --
//! via the degree-4 closure: multiply the generators by every monomial keeping
//! total degree <= 4, row-reduce, feed the degree falls back, repeat to a fixed
//! point. The refutation direction looked rigorous: if the full degree-<= 4 part
//! of the ideal does not resolve the system, no algorithm restricted to degree
//! <= 4 can, F4 included.
//!
//! ## Why it does not measure degree
//!
//! The resolution criterion was "refuted, OR every occurring variable pinned by
//! a linear row". Measured verdicts at m = 2 varied WITHIN a fixed n, which is
//! the tell. The diagnostic says why:
//!
//! ```text
//!   verdict       refuted   vars pinned
//!   SUFFICIENT    true      14/14
//!   STALLS        false     0/10, 2/10, 8/10, 10/12
//! ```
//!
//! Every "sufficient" is a refutation; every "stall" is a non-refuted system.
//! So the predicate tracks **whether the target is decomposable**, not the
//! degree -- and the cause is structural, not a patchable bug:
//!
//! > For `m = 2` the decomposition `x_R = x(P1 + P2)` carries the swap symmetry
//! > `(P1, P2) <-> (P2, P1)`. Every decomposable target therefore has at least
//! > TWO solutions, so no variable is pinned by a linear row at ANY degree.
//! > "Unresolved" is guaranteed for every consistent instance a priori.
//!
//! The inference `STALLS => d_F4 >= 5` is therefore invalid, and the verdict
//! strings below are renamed to what the run actually distinguishes.
//!
//! ## The design requirement this leaves
//!
//! A closure- or solving-degree predicate on this system family needs EITHER
//! symmetry-breaking constraints (an ordering on the summand blocks), OR a
//! target set independently verified non-decomposable -- where "resolved" means
//! "refuted" and a stall IS a degree fact. The second is only checkable while
//! the pair search is affordable (about n <= 25 at m = 2, k = ceil(n/2)), which
//! sits inside the n <= 21 region Semaev already measured and does not reach the
//! disputed n = 40 versus n = 45 boundary.
//!
//! So `IMP-SEMBIN-ENGINE` is genuinely binding and this route does not clear it.
//! Nothing here asserts anything about `d_F4`, Assumption 1, or any curve.
//!
//! ```sh
//! F4_F2_MAX_ROWS=300000 F4_F2_MAX_COLS=600000 \
//!   cargo run --release --example assumption1_closure -- --m 2 --n-max 21
//! ```

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, matrix_f4_f2, solving_profile, system_degree, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

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

/// Signature of a reduced set, for fixed-point detection.
fn signature(
    polys: &[cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly],
) -> Vec<Vec<u64>> {
    let mut s: Vec<Vec<u64>> = polys
        .iter()
        .map(|p| {
            let mut m: Vec<u64> = p.terms.iter().map(|t| t.mask).collect();
            m.sort_unstable();
            m
        })
        .filter(|m: &Vec<u64>| !m.is_empty())
        .collect();
    s.sort();
    s
}

/// Degree-`d` closure: feed degree falls back until the reduced set is stable.
/// Why a degree-`d` closure stopped. A degree verdict may only be drawn from
/// `Converged`; a set still changing when the round budget ran out supports no
/// claim about degree.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Closure {
    Converged,
    SizeCap,
    RoundsExhausted,
}

fn degree_closure(
    polys: &[cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly],
    n_vars: usize,
    d: u32,
    max_rounds: usize,
) -> (
    Vec<cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly>,
    usize,
    Closure,
) {
    let mut gens = polys.to_vec();
    let mut prev = signature(&gens);
    for round in 1..=max_rounds {
        let reduced = match matrix_f4_f2(&gens, n_vars, d) {
            Some(r) => r,
            None => return (gens, round - 1, Closure::SizeCap),
        };
        let mut next: Vec<_> = reduced
            .into_iter()
            .filter(|p| !p.terms.is_empty())
            .collect();
        next.sort_by_key(|p| system_degree(std::slice::from_ref(p)));
        let sig = signature(&next);
        if sig == prev {
            return (next, round, Closure::Converged);
        }
        prev = sig;
        gens = next;
    }
    (gens, max_rounds, Closure::RoundsExhausted)
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
    let n_min = flag("--n-min", 5) as u32;
    let n_max = flag("--n-max", 31) as u32;
    let trials = flag("--trials", 2) as usize;
    let d = flag("--degree", 4) as u32;
    let rounds = flag("--rounds", 8) as usize;
    let seed = flag("--seed", 0xA55E7) as u64;

    println!("# Assumption 1's predicate: does a degree-<= {d} computation resolve the system?");
    println!();
    println!("m = {m}, trials = {trials}, max rounds = {rounds}, seed = {seed:#x}");
    println!();
    println!("CONFOUNDED: see the module docs. REFUTED-AT-{d} vs NOT-REFUTED tracks target");
    println!("decomposability, NOT degree: the m=2 swap symmetry makes every decomposable");
    println!("target unresolvable at any degree. No d_F4 claim follows from any row.");
    println!("CAP     => matrix exceeded F4_F2_MAX_ROWS/COLS; no verdict, not a negative.");
    println!();
    println!("| n | k | vars | eqs | rounds | closure size | resolved | verdict |");
    println!("|--:|--:|-----:|----:|-------:|-------------:|:--------:|:--------|");

    let mut rng = StdRng::seed_from_u64(seed);
    for n in (n_min..=n_max).step_by(2) {
        let k = n.div_ceil(m as u32);
        let irr: IrreduciblePoly = match find_irreducible_sparse(n) {
            Some(i) => i,
            None => continue,
        };
        let st = FieldStructure::new(n, &irr);
        let b = F2mElement::one(n);

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
            let (closure, used, outcome) = degree_closure(&sys.equations, sys.n_vars, d, rounds);
            let (resolved, verdict) = if outcome == Closure::SizeCap {
                ("—".to_string(), "SIZE CAP (no verdict)".to_string())
            } else if outcome == Closure::RoundsExhausted {
                ("—".to_string(), "NOT CONVERGED (no verdict)".to_string())
            } else {
                match solving_profile(&closure, sys.n_vars, d) {
                    Some(p) => {
                        let done = p.refuted || (p.vars_determined == p.vars_occurring);
                        eprintln!(
                            "   DIAG n={} refuted={} pinned={}/{}",
                            n, p.refuted, p.vars_determined, p.vars_occurring
                        );
                        (
                            if done { "yes" } else { "no" }.to_string(),
                            if done {
                                format!("REFUTED-at-degree-{d}")
                            } else {
                                "not-refuted (target likely decomposable; NOT a degree verdict)"
                                    .to_string()
                            },
                        )
                    }
                    None => ("—".to_string(), "CAP".to_string()),
                }
            };
            println!(
                "| {} | {} | {} | {} | {} | {} | {} | {} |",
                n,
                k,
                sys.n_vars,
                sys.equations.len(),
                used,
                closure.len(),
                resolved,
                verdict
            );
        }
    }
}
