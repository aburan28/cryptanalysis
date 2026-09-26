//! What would a full parametric Gröbner basis cost to build?
//!
//! `algebra_cache` has three layers. `Preprocessing` is the one on the
//! relation-search path and it is cheap -- see `preprocessing_cost.rs`, which
//! measures it. `Parameterized` was the other extreme: a cached Gröbner basis
//! of the template with the target bits as `n` extra Boolean variables, capped
//! at 16. That cache was removed after it was measured never to pay for itself
//! (see `polynomial_reuse.rs`); this probe still prices the basis it would have
//! stored, because the cost is the reason it went.
//!
//! **Run every point under an external `timeout`.** A point past the feasible
//! edge does not come back:
//!
//!     for pt in "3 2 2" "5 2 2" "5 3 2"; do
//!       timeout 45 cargo run --release --example gb_probe -- $pt
//!     done
//!
//! `b = 1` throughout: the Koblitz coefficient, and the case the engine left
//! unclosed before it paired basis elements with the field equations. Three
//! engines, one row each; a superseded figure moves, it does not vanish.
//! 4-core x86_64 container, rustc 1.94.1, release, one run per point:
//!
//!                     vars   2026-09-21   340a8379    this engine
//!     n=3 ell=2 m=2     7       49 ms      10.5 ms       12.8 ms
//!     n=5 ell=2 m=2     9     5340 ms      1174 ms       1347 ms
//!     n=5 ell=3 m=2    11     did not finish in 45 s, on every engine
//!     n=7 ell=2 m=2, n=5 ell=2 m=3, n=7 ell=3 m=2, n=9 ell=2 m=2
//!                             did not finish in 45 s (2026-09-21)
//!
//! Read the columns as three different computations, not one getting faster.
//! 2026-09-21 is the engine before the chain criterion (b8eca515), which
//! accounts for the 4.6x to 340a8379. Neither of those returned a Gröbner
//! basis here: at n=5 the 340a8379 output has 28 elements and is not closed.
//! This engine adds the field-equation pairs, finds two new generators at each
//! point, and returns the 16- and 23-element reduced bases. It costs +22% and
//! +15% over 340a8379 at those points, the price of a correct answer on a
//! system that needs the pairs. Scoped to these points on this machine;
//! nothing here is a claim about any attack's cost.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::FieldStructure;
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible;
use cryptanalysis_suite::cryptanalysis::polynomial_reuse::DecompositionTemplate;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::groebner_basis_f2_stats;
use num_bigint::BigUint;
use std::time::Instant;

fn fe(x: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(x), n)
}

fn main() {
    // One point per process, so a point that does not terminate bounds only
    // itself. With no arguments, the smallest known-feasible point.
    let a: Vec<u32> = std::env::args()
        .skip(1)
        .filter_map(|x| x.parse().ok())
        .collect();
    let (n, ell, m) = if a.len() == 3 {
        (a[0], a[1] as usize, a[2] as usize)
    } else {
        println!("usage: gb_probe <n> <ell> <m>   (run under `timeout`; defaulting to 3 2 2)");
        (3, 2, 2)
    };

    println!(
        "{:>4} {:>4} {:>3} {:>7} {:>7}  {:>14}",
        "n", "ell", "m", "n_vars", "total", "groebner"
    );

    let Some(irr) = find_irreducible(n) else {
        println!("{n:>4} {ell:>4} {m:>3}   no irreducible of that degree");
        return;
    };
    let st = FieldStructure::new(n, &irr);
    let basis: Vec<_> = (0..ell).map(|k| fe(1u64 << k, n)).collect();
    let Some(t) = DecompositionTemplate::build(&basis, &fe(1, n), m, &st) else {
        println!("{n:>4} {ell:>4} {m:>3}   layout refused (MAX_VARS, or n > 64)");
        return;
    };
    let total = t.n_vars + n as usize;
    if total > 16 {
        println!(
            "{n:>4} {ell:>4} {m:>3} {:>7} {total:>7}   over the 16-var cap",
            t.n_vars
        );
        return;
    }

    let Some(generators) = t.parameterized_generators() else {
        println!(
            "{n:>4} {ell:>4} {m:>3} {:>7} {total:>7}   refused",
            t.n_vars
        );
        return;
    };
    let start = Instant::now();
    let (g, stats) = groebner_basis_f2_stats(generators, total);
    let ns = start.elapsed().as_nanos();
    println!(
        "{n:>4} {ell:>4} {m:>3} {:>7} {total:>7}  {:>11.1} ms   ({} generators, {} from field pairs, {:.3e} mono ops)",
        t.n_vars,
        ns as f64 / 1e6,
        g.len(),
        stats.field_generators,
        stats.mono_ops as f64,
    );
}
