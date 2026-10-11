//! Which Frobenius-invariant factor bases exist, and which are fruitful.
//!
//! ```bash
//! cargo run --release --example koblitz_factor_base_survey
//! ```

use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{FieldStructure, SolverEngine};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    available_subspace_dimensions, build_frobenius_factor_base_from_divisor, cyclotomic_cosets,
    enumerate_decompose, groebner_decompose, koblitz_index_calculus_dlp_with_factor_base,
    sat_decompose, DecompositionStrategy, KoblitzCurve, KoblitzIcOptions,
};
use num_bigint::BigUint;
use std::time::Instant;

fn main() {
    println!();
    println!("=== Every invariant subspace dimension, by cyclotomic coset ===");
    println!();
    println!(
        "{:>5} {:>7} {:>28}  available dimensions",
        "n", "cosets", "coset sizes"
    );
    for n in [7u32, 9, 15, 21, 31, 63, 127, 131, 163] {
        let mut sizes: Vec<usize> = cyclotomic_cosets(n).iter().map(|c| c.len()).collect();
        sizes.sort_unstable();
        let dims = available_subspace_dimensions(n);
        let shown: Vec<String> = dims.iter().take(9).map(|d| d.to_string()).collect();
        println!(
            "{:>5} {:>7} {:>28}  {}{}",
            n,
            sizes.len(),
            format!("{sizes:?}"),
            shown.join(","),
            if dims.len() > 9 { ", …" } else { "" }
        );
    }
    println!();
    println!("A stable subspace is a divisor of x^n − 1, so these are all of them.");
    println!("At n = 131 and 163 — where 2 is primitive — only 0, 1, n−1, n exist:");
    println!("the construction is empty exactly at the sizes that matter.");

    println!();
    println!("=== Divisor bases on toy curves ===");
    println!();
    println!(
        "{:>10} {:>4} {:>7} {:>7} {:>10} {:>3} {:>6} {:>10} {:>10} {:>10}",
        "curve", "dim", "|F|", "orbits", "m ok", "m", "vars", "search", "F4", "SAT"
    );
    for (a, n, sets) in [
        (1u8, 7u32, vec![vec![1usize], vec![1, 2]]),
        (0, 9, vec![vec![1], vec![2], vec![1, 2]]),
        (1, 15, vec![vec![2], vec![2, 3], vec![1, 2, 3]]),
    ] {
        let kc = match KoblitzCurve::new(a, n) {
            Some(k) => k,
            None => continue,
        };
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let g = kc.generator().clone();
        for indices in sets {
            let fb = match build_frobenius_factor_base_from_divisor(&kc, &indices) {
                Some(f) => f,
                None => continue,
            };
            let ok = fb.admissible_summand_counts(&kc, 4);
            // Smallest admissible m that also fits the variable budget.
            let m = match ok
                .iter()
                .copied()
                .find(|&m| m * fb.ell as usize + m.saturating_sub(2) * n as usize <= 64)
            {
                Some(m) => m,
                None => continue,
            };
            let n_vars = m * fb.ell as usize + m.saturating_sub(2) * n as usize;
            let index_of = fb.index_map();
            let target = kc.mul(&g, &BigUint::from(11u32));

            let t = Instant::now();
            let s = enumerate_decompose(&kc, &fb, &index_of, &target, m);
            let t_s = t.elapsed();
            let t = Instant::now();
            let (f, _) = groebner_decompose(
                &kc,
                &fb,
                &index_of,
                &st,
                &target,
                m,
                SolverEngine::default(),
                20_000,
            );
            let t_f = t.elapsed();
            let t = Instant::now();
            let (x, _) = sat_decompose(&kc, &fb, &index_of, &st, &target, m, 16, Some(2));
            let t_x = t.elapsed();
            assert_eq!(s.is_some(), f.is_some(), "search vs F4 disagree");
            assert_eq!(s.is_some(), x.is_some(), "search vs SAT disagree");

            println!(
                "{:>10} {:>4} {:>7} {:>7} {:>10} {m:>3} {n_vars:>6} {:>10.2?} {:>10.2?} {:>10.2?}",
                format!("K_{a}/2^{n}"),
                fb.ell,
                fb.points.len(),
                fb.orbits.len(),
                format!("{ok:?}"),
                t_s,
                t_f,
                t_x
            );
        }
    }
    println!();
    println!("=== The payoff: a curve the single-factor base cannot reach ===");
    println!();
    let kc = KoblitzCurve::new(0, 31).expect("K_0 over F_2^31");
    let g = kc.generator().clone();
    let d = BigUint::from(123_456u32);
    let q = kc.mul(&g, &d);
    println!("K_0/F_2^31, r = {}, target d = {d}", kc.subgroup_order);
    println!();
    println!(
        "{:>18} {:>4} {:>7} {:>7} {:>2} {:>6} {:>10} {:>9}",
        "base", "dim", "|F|", "orbits", "m", "vars", "log", "time"
    );
    for (label, indices, m) in [
        ("single factor", vec![1usize], 2usize),
        ("single factor", vec![1], 4),
        ("divisor [1,2]", vec![1, 2], 2),
        ("divisor [0,1,2]", vec![0, 1, 2], 2),
    ] {
        let fb = match build_frobenius_factor_base_from_divisor(&kc, &indices) {
            Some(f) => f,
            None => continue,
        };
        let vars = fb.n_vars_for_summands(31, m);
        if vars > 64 {
            println!(
                "{label:>18} {:>4} {:>7} {:>7} {m:>2} {vars:>6} {:>10} {:>9}",
                fb.ell,
                fb.points.len(),
                fb.orbits.len(),
                "—",
                "over cap"
            );
            continue;
        }
        let opts = KoblitzIcOptions {
            m,
            strategy: DecompositionStrategy::Enumerate,
            extra_relations: 8,
            max_trials: 60_000,
            ..KoblitzIcOptions::default()
        };
        let t = Instant::now();
        let got =
            koblitz_index_calculus_dlp_with_factor_base(&kc, &q, &fb, &opts).and_then(|r| r.log);
        println!(
            "{label:>18} {:>4} {:>7} {:>7} {m:>2} {vars:>6} {:>10} {:>9.1?}",
            fb.ell,
            fb.points.len(),
            fb.orbits.len(),
            got.map(|v| v.to_string()).unwrap_or_else(|| "none".into()),
            t.elapsed()
        );
    }
    println!();
    println!("One irreducible factor gives dim 5: at m = 2 its 63 points pair into");
    println!("~2 000 of 1.4M group elements so nothing decomposes, and m = 4 needs");
    println!("82 unknowns — past the 64-variable cap.  That base cannot reach this");
    println!("curve at all.  A divisor of x^31 − 1 gives dim 10 and solves it at");
    println!("m = 2 in seconds: 20 unknowns, quadratic, no chaining.");

    println!();
    println!("`m ok` is the cofactor-class predicate: a sum of m factor-base points");
    println!("reaches ⟨G⟩ only when their h-torsion classes cancel.  On a cofactor-2");
    println!("curve whose base misses ⟨G⟩ entirely, odd m decomposes nothing at all —");
    println!("independent of |F|.  Checking that first is one scalar multiplication");
    println!("per point, against a search that would otherwise find nothing.");
    println!();
}
