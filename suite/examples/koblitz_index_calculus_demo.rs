//! Index calculus on Koblitz curves with Frobenius-invariant factor
//! bases (Galbraith–Granger–Merz–Petit, SAC 2020).
//!
//! ```bash
//! cargo run --release --example koblitz_index_calculus_demo
//! ```

use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, factor_x_n_minus_1, koblitz_index_calculus_dlp,
    koblitz_speedup_model, order_of_2_mod_n, KoblitzCurve, KoblitzIcOptions,
};
use num_bigint::BigUint;

fn main() {
    println!();
    println!("=== Koblitz curve parameters K_a: y² + xy = x³ + a x² + 1 ===");
    println!();
    println!(
        "{:>2}  {:>1}  {:>3}  {:>10}  {:>9}  {:>3}  {:>6}  {:>7}",
        "n", "a", "ℓ", "#E(F_2^n)", "r", "h", "|F|", "signed"
    );
    for n in [7u32, 9, 11, 13, 15, 21] {
        for a in [0u8, 1] {
            let kc = match KoblitzCurve::new(a, n) {
                Some(kc) => kc,
                None => continue,
            };
            let fb = match build_frobenius_factor_base(&kc, 0) {
                Some(fb) => fb,
                None => continue,
            };
            println!(
                "{:>2}  {:>1}  {:>3}  {:>10}  {:>9}  {:>3}  {:>6}  {:>7}",
                n,
                a,
                fb.ell,
                kc.group_order,
                kc.subgroup_order,
                kc.cofactor,
                fb.points.len(),
                fb.unknowns()
            );
        }
    }

    println!();
    println!("=== Frobenius-invariant factor base for K_0 / F_2^9 ===");
    println!();
    let kc = KoblitzCurve::new(0, 9).expect("K_0 over F_2^9");
    let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
    println!(
        "x^9 − 1 non-trivial irreducible factors : {:?}",
        factor_x_n_minus_1(9)
            .iter()
            .map(|f| format!("{f:#b}"))
            .collect::<Vec<_>>()
    );
    println!(
        "ℓ = ord_9(2)                            : {:?}",
        order_of_2_mod_n(9)
    );
    println!(
        "linearised polynomial F(X)              : {}",
        fb.linearised_exponents
            .iter()
            .map(|k| format!("X^(2^{k})"))
            .collect::<Vec<_>>()
            .join(" + ")
    );
    println!(
        "|ker F| (an F_2-subspace, dim ℓ)        : {}",
        fb.subspace.len()
    );
    println!(
        "|F| (points with x ∈ ker F)             : {}",
        fb.points.len()
    );
    println!(
        "signed π-orbits (= relation unknowns)     : {}",
        fb.unknowns()
    );
    println!("λ with π(Q) = [λ]Q on ⟨G⟩               : {}", kc.lambda);

    println!();
    println!("=== Solving Q = [d]G by index calculus ===");
    println!();
    for d in [7u32, 53, 101] {
        let g = kc.generator().clone();
        let q = kc.mul(&g, &BigUint::from(d));
        let report =
            koblitz_index_calculus_dlp(&kc, &q, &KoblitzIcOptions::default()).expect("run");
        println!(
            "d = {:>3}  recovered = {:>5}  relations = {:>2}/{:<2}  (a,b) trials = {}",
            d,
            report
                .log
                .as_ref()
                .map(|v| v.to_string())
                .unwrap_or_else(|| "—".into()),
            report.relations,
            report.orbit_count,
            report.trials
        );
    }

    println!();
    println!("=== Speed-up from the Frobenius structure ===");
    println!();
    println!(
        "{:>2}{:>3}  {:>6}  {:>7}  {:>10}  {:>10}  {:>8}",
        "n", "a", "|F|", "signed", "relations", "lin. alg.", "rho"
    );
    for n in [9u32, 11, 13] {
        // Whichever of K_0 / K_1 has a usable prime-order subgroup at
        // this n (for n = 11 that is K_1, for n = 13 it is K_0).
        let Some((kc, fb)) = [0u8, 1].iter().find_map(|&a| {
            let kc = KoblitzCurve::new(a, n)?;
            let fb = build_frobenius_factor_base(&kc, 0)?;
            Some((kc, fb))
        }) else {
            continue;
        };
        let model = koblitz_speedup_model(n, fb.points.len(), fb.unknowns(), 2);
        println!(
            "{:>2}{:>3}  {:>6}  {:>7}  {:>9.2}×  {:>9.2}×  {:>7.2}×",
            n,
            kc.a,
            model.factor_base_size,
            model.unknowns,
            model.relation_collection_speedup,
            model.linear_algebra_speedup,
            model.rho_speedup
        );
    }
    println!();
    println!("Frobenius saves ≈ n and negation removes the opposite columns;");
    println!("the observed relation ratio can approach 2n and its square in");
    println!("the linear algebra. These remain larger structural savings than");
    println!("the √(2n) that Pollard rho already gets from the same");
    println!("endomorphism — yet index calculus stays the worse attack at the");
    println!("sizes anyone deploys (GGMP, SAC 2020, conclusion).");
    println!();
}
