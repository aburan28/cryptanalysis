//! Uncached degree-3 Macaulay/RREF microbenchmark for the retained
//! public-synthetic Koblitz n=31, dimension-16 decomposition cell.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, f4_word_ops_total, macaulay_profile, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base_from_divisor, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::koblitz_symmetrised::{
    build_symmetrised_factor_base, build_symmetrised_system, divisor_for_dimension,
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;

fn median(mut samples: Vec<f64>) -> f64 {
    samples.sort_by(|left, right| left.total_cmp(right));
    samples[samples.len() / 2]
}

fn main() {
    let repeats: usize = std::env::args()
        .nth(1)
        .map(|value| value.parse().expect("repeats"))
        .unwrap_or(5);
    let system_kind = std::env::args().nth(2).unwrap_or_else(|| "x".to_owned());
    assert!(matches!(system_kind.as_str(), "x" | "sym"));
    assert!(repeats > 0);
    let n = 31u32;
    let curve = KoblitzCurve::new(0, n).expect("K_0/F_2^31");
    let divisor = divisor_for_dimension(n, 16).expect("dimension-16 divisor");
    let structure = FieldStructure::new(n, &curve.curve.irreducible);
    let target = curve.mul(curve.generator(), &BigUint::from(66_142u64));
    let (equations, n_vars, dimension) = if system_kind == "x" {
        let base = build_frobenius_factor_base_from_divisor(&curve, &divisor)
            .expect("Frobenius factor base");
        assert_eq!(base.subspace_basis.len(), 16);
        let BinaryPoint::Affine { x: target_x, .. } = &target else {
            panic!("fixture target must be affine");
        };
        let system = build_decomposition_system(
            &base.subspace_basis,
            target_x,
            &curve.curve.b,
            2,
            &structure,
        )
        .expect("quadratic S3 system");
        (system.equations, system.n_vars, 16usize)
    } else {
        let base =
            build_symmetrised_factor_base(&curve, &divisor).expect("symmetrised factor base");
        let system = build_symmetrised_system(&curve, &base, &target, 2, &structure)
            .expect("symmetrised quadratic system");
        (system.equations, system.n_vars, base.ell)
    };
    assert_eq!(equations.len(), 31);

    let mut elapsed_ms = Vec::with_capacity(repeats);
    let mut word_ops = Vec::with_capacity(repeats);
    let mut retained_profile = None;
    for _ in 0..repeats {
        let started = Instant::now();
        let operations_before = f4_word_ops_total();
        let profile = macaulay_profile(&equations, n_vars, 3).expect("degree-3 matrix under cap");
        word_ops.push(f4_word_ops_total() - operations_before);
        elapsed_ms.push(started.elapsed().as_secs_f64() * 1000.0);
        match retained_profile {
            Some(previous) => assert_eq!(previous, profile),
            None => retained_profile = Some(profile),
        }
    }
    let profile = retained_profile.unwrap();
    let median_ms = median(elapsed_ms.clone());
    let rref_kernel = if std::env::var("KIC_F4_RREF_SUFFIX").as_deref() == Ok("1")
        || profile.rows < 128
        || profile.cols < 256
        || profile.cols > profile.rows.saturating_mul(4)
    {
        "active_suffix"
    } else {
        "m4ri_auto"
    };
    println!(
        "{}",
        json!({
            "schema_version":"1.0",
            "task_id":"TASK-KIC-GROEBNER-HYPEROPT-KERNEL-N31-20260921",
            "kind":"koblitz_boolean_f4_kernel_benchmark",
            "n":n,
            "system":system_kind,
            "dimension":dimension,
            "variables":n_vars,
            "equations":equations.len(),
            "degree":3,
            "rows":profile.rows,
            "cols":profile.cols,
            "rank":profile.rank,
            "syzygies":profile.syzygies(),
            "repeats":repeats,
            "rref_kernel":rref_kernel,
            "samples_ms":elapsed_ms,
            "word_ops":word_ops,
            "median_ms":median_ms,
            "claim_boundary":"Uncached public-synthetic degree-3 Macaulay kernel timing only; no decomposition, relation, DLP, or sub-rho claim"
        })
    );
}
