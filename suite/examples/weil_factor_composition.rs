//! Frozen complete-cover experiment; truth tables are never supplied to solvers.
use cryptanalysis_suite::{
    binary_ecc::{BinaryPoint, F2mElement},
    cryptanalysis::{
        koblitz_factor_base_search::TargetSet,
        koblitz_fast::{FastCurve, FastPoint},
        koblitz_groebner::{FieldStructure, SolveOptions},
        koblitz_index_calculus::*,
        semaev_decomp::Gf2,
        weil_charts::{canonical_basis, WeilChartPlan, WeilSolveStats},
    },
};
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::{rngs::StdRng, Rng, SeedableRng};
use serde_json::{json, Value};
use std::{
    collections::{BTreeSet, HashMap, HashSet},
    sync::Arc,
    time::Instant,
};

fn bits(x: &F2mElement) -> u64 {
    x.raw_bits().first().copied().unwrap_or(0)
}
fn point_json(p: &BinaryPoint) -> Value {
    match p {
        BinaryPoint::Infinity => json!(null),
        BinaryPoint::Affine { x, y } => json!([bits(x), bits(y)]),
    }
}
fn fe(x: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(x), n)
}
fn digest<T: serde::Serialize>(x: &T) -> String {
    blake3::hash(&serde_json::to_vec(x).unwrap())
        .to_hex()
        .to_string()
}
fn stats(s: &WeilSolveStats) -> Value {
    json!({"component_pairs":s.component_pairs,"duplicate_pairs":s.duplicate_pairs,
    "algebraic_pairs":s.algebraic_pairs,"projection_refutations":s.projection_refutations,
    "linear_constraints":s.linear_constraints,"projection_word_xors":s.projection_word_xors,
    "coefficient_field_muls":s.coefficient_field_muls,"coefficient_field_squares":s.coefficient_field_squares,
    "reductions":s.solver.reductions,"exhausted":s.solver.exhausted})
}
fn seed_basis(kc: &KoblitzCurve, c: &Value, seed: u64) -> Vec<F2mElement> {
    let ell = c["ell"].as_u64().unwrap() as usize;
    let f = Gf2::new(&kc.curve.irreducible);
    let v: Vec<u64> = match c["family"].as_str().unwrap() {
        "power_span" => (0..ell).map(|i| 1 << i).collect(),
        "subfield_control" | "scaled_subfield" => {
            let b = linearised_kernel_basis(&[0, ell as u32], kc.n, &kc.curve.irreducible);
            assert_eq!(b.len(), ell);
            b.iter()
                .map(|x| {
                    if c["family"] == "scaled_subfield" {
                        f.mul(2, bits(x))
                    } else {
                        bits(x)
                    }
                })
                .collect()
        }
        "random" => {
            let mut rng = StdRng::seed_from_u64(seed ^ 0x564543544f5253);
            let mut v = Vec::new();
            while v.len() < ell {
                let x = rng.gen_range(1..1u64 << kc.n);
                let mut w = v.clone();
                w.push(x);
                if canonical_basis(w).len() > v.len() {
                    v.push(x);
                }
            }
            v
        }
        _ => panic!("unknown family"),
    };
    v.into_iter().map(|x| fe(x, kc.n)).collect()
}
fn point_truth(fc: &FastCurve, fb: &FrobeniusFactorBase) -> HashSet<FastPoint> {
    let p: Vec<_> = fb.points.iter().map(|p| fc.lift(p)).collect();
    let mut out = HashSet::new();
    for (i, &a) in p.iter().enumerate() {
        for &b in &p[i..] {
            out.insert(fc.add(a, b));
        }
    }
    out
}
fn algebraic_truth(f: &Gf2, fb: &FrobeniusFactorBase, r: u64, b: u64) -> BTreeSet<(u64, u64)> {
    let xs: Vec<_> = fb.subspace.iter().map(bits).collect();
    let mut out = BTreeSet::new();
    for (i, &x) in xs.iter().enumerate() {
        for &y in &xs[i..] {
            let p = f.mul(x, y);
            if f.sqr(p) ^ f.mul(r, p) ^ f.mul(f.sqr(r), f.sqr(x ^ y)) ^ b == 0 {
                out.insert((x.min(y), x.max(y)));
            }
        }
    }
    out
}
fn valid_witness(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    t: &BinaryPoint,
    w: &[usize],
) -> bool {
    w.len() == 2
        && w.iter().all(|&i| i < fb.points.len())
        && kc.add(&fb.points[w[0]], &fb.points[w[1]]) == *t
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let mode = &args[1];
    let ci: usize = args[2].parse().unwrap();
    let variant = &args[3];
    let seed: u64 = args[4].parse().unwrap();
    let contract: Value = serde_json::from_str(include_str!(
        "../fixtures/weil_factor_composition_contract.json"
    ))
    .unwrap();
    let c = &contract["stage_cases"][ci];
    let u = |k: &str| c[k].as_u64().unwrap() as u32;
    let cold = Instant::now();
    let Some(kc) = KoblitzCurve::subfield(u("k"), u("n"), u("a") as u64, u("b") as u64) else {
        println!(
            "{}",
            json!({"phase":"rejected_curve","case":ci,"configuration":c,"variant":variant,"seed":seed,"cold_ns":cold.elapsed().as_nanos()})
        );
        return;
    };
    let curve_ns = cold.elapsed().as_nanos();
    let started = Instant::now();
    let known = if mode == "dlp" || mode == "rho" {
        args[5].parse::<u64>().unwrap()
    } else {
        1
    };
    let q = kc.mul(kc.generator(), &BigUint::from(known));
    let target_ns = started.elapsed().as_nanos();
    if mode == "rho" {
        let opts = KoblitzSignedRhoOptions {
            seed,
            max_restarts: 16,
            max_iterations_per_restart: 100000,
            ..Default::default()
        };
        let r = koblitz_signed_frobenius_rho_with_progress(&kc, &q, &opts, &mut |_| {});
        let verified = r.verified
            && r.recovered_log == Some(BigUint::from(known))
            && kc.mul(kc.generator(), &r.recovered_log.clone().unwrap()) == q;
        println!(
            "{}",
            json!({"phase":"rho","case":ci,"seed":seed,"known_log":known,"curve_ns":curve_ns,"target_ns":target_ns,
            "cold_ns":cold.elapsed().as_nanos(),"verified":verified,"exhausted":r.exhausted,"iterations":r.iterations,
            "setup_ns":r.setup_ns,"walk_ns":r.walk_ns,"verification_ns":r.verification_ns,"charges":format!("{:?}",r.charges)})
        );
        return;
    }
    let started = Instant::now();
    let basis = seed_basis(&kc, c, seed);
    let fb = build_frobenius_union_factor_base(&kc, &basis).unwrap();
    let base_ns = started.elapsed().as_nanos();
    let started = Instant::now();
    let plan = if variant.starts_with("charts_") {
        Some(Arc::new(
            WeilChartPlan::new(&kc, &fb, &basis, variant == "charts_linear").unwrap(),
        ))
    } else {
        None
    };
    let plan_ns = started.elapsed().as_nanos();
    let index: HashMap<_, _> = fb
        .points
        .iter()
        .enumerate()
        .map(|(i, p)| (point_key(p), i))
        .collect();
    let setup_ns = cold.elapsed().as_nanos();
    println!(
        "{}",
        json!({"phase":"setup","case":ci,"configuration":c,"variant":variant,"seed":seed,"known_log":known,
        "curve_ns":curve_ns,"target_ns":target_ns,"base_ns":base_ns,"plan_ns":plan_ns,"setup_ns":setup_ns,
        "basis":basis.iter().map(bits).collect::<Vec<_>>(),"field_polynomial":kc.curve.irreducible.low_terms,
        "subgroup":kc.subgroup_order.to_string(),"cofactor":kc.cofactor.to_string(),"points":fb.points.len(),"signed_orbits":fb.signed_orbits.len(),
        "domain_size":fb.subspace.len(),"domain_hash":digest(&fb.subspace.iter().map(bits).collect::<Vec<_>>()),
        "target_hash":digest(&point_json(&q)),"total_calibrated_operations":null,"S":null,"rho_ratio":null,"floor_ratio":null})
    );
    if mode == "dlp" {
        let opts = KoblitzIcOptions {
            m: 2,
            extra_relations: 2,
            max_trials: 256,
            seed,
            node_budget: 20000,
            strategy: match variant.as_str() {
                "ambient_f4" | "charts_linear" => DecompositionStrategy::Groebner,
                "enumerate" => DecompositionStrategy::Enumerate,
                "pair_table" => DecompositionStrategy::PairTable,
                _ => panic!("variant"),
            },
            weil_charts: plan,
            allow_direct_relation: false,
            collapse_projected_orbits: true,
            crossbred: None,
            wdsat_binary: None,
            wdsat_timeout_ms: 5_000,
            relation_batch_size: 1,
            ..Default::default()
        };
        let run = Instant::now();
        let result = koblitz_index_calculus_dlp_with_factor_base(&kc, &q, &fb, &opts);
        let driver_ns = run.elapsed().as_nanos();
        let verify = Instant::now();
        let verified = result
            .as_ref()
            .and_then(|r| r.log.as_ref())
            .is_some_and(|log| *log == BigUint::from(known) && kc.mul(kc.generator(), log) == q);
        let verification_ns = verify.elapsed().as_nanos();
        let cold_ns = setup_ns + driver_ns + verification_ns;
        let verify = Instant::now();
        let fc = FastCurve::new(&kc.curve).unwrap();
        let truth = point_truth(&fc, &fb);
        if let Some(r) = result {
            let mut checks = Vec::new();
            for a in &r.attempt_records {
                let exists = truth.contains(&fc.lift(&a.target));
                let witness_ok = a
                    .decomposition_indices
                    .as_ref()
                    .is_none_or(|w| valid_witness(&kc, &fb, &a.target, w));
                let correct = witness_ok
                    && (!matches!(a.disposition, KoblitzRelationAttemptDisposition::Refuted)
                        || !exists);
                checks.push(json!({"trial":a.trial,"target":point_json(&a.target),"a":a.coefficient_a.to_string(),"b":a.coefficient_b.to_string(),
                    "disposition":format!("{:?}",a.disposition),"witness":a.decomposition_indices,"truth":exists,"correct":correct}));
                assert!(correct, "oracle disagrees with full pair truth");
            }
            assert_eq!(r.verification_failures, 0);
            assert_eq!(r.inconsistent_relations, 0);
            assert!(!r.direct_relation);
            if r.log.is_some() {
                assert!(verified);
            }
            println!(
                "{}",
                json!({"phase":"dlp","verified":verified,"cold_ns":cold_ns,"driver_ns":driver_ns,"verification_ns":verification_ns,
                "oracle_validation_ns":verify.elapsed().as_nanos(),"relations":r.relations,"independent_relations":r.independent_relations,
                "dependent_relations":r.dependent_relations,"trials":r.trials,"reductions":r.reductions,"matrix_columns":r.matrix_columns,
                "matrix_rank":r.terminal_matrix_rank,"relation_collection_ns":r.relation_collection_ns,"linear_algebra_ns":r.linear_algebra_ns,
                "projected_orbit_construction_ns":r.projected_orbit_construction_ns,"cofactor_admission_ns":r.cofactor_admission_ns,
                "pair_table_ns":r.pair_table_ns,"pair_table_entries":r.pair_table_entries,"direct_relations_skipped":r.direct_relations_skipped,
                "attempts":checks})
            );
        } else {
            println!(
                "{}",
                json!({"phase":"dlp","verified":false,"rejected":true,"cold_ns":cold_ns,"driver_ns":driver_ns})
            );
        }
        return;
    }
    // The following oracle/census work is validation, timed separately and withheld.
    let validation = Instant::now();
    let fc = FastCurve::new(&kc.curve).unwrap();
    let truth = point_truth(&fc, &fb);
    let diagnostic = WeilChartPlan::new(&kc, &fb, &basis, true).unwrap();
    let mut same = HashSet::new();
    for component in diagnostic.component_elements() {
        let set: HashSet<_> = component.into_iter().collect();
        let points: Vec<_> = fb
            .points
            .iter()
            .map(|p| fc.lift(p))
            .filter(|p| set.contains(&p.x))
            .collect();
        for (i, &a) in points.iter().enumerate() {
            for &b in &points[i..] {
                same.insert(fc.add(a, b));
            }
        }
    }
    let order = kc.subgroup_order.to_u64().unwrap();
    let subgroup_count = |s: &HashSet<FastPoint>| {
        s.iter()
            .filter(|p| !p.infinity && fc.mul_u64(**p, order).infinity)
            .count()
    };
    println!(
        "{}",
        json!({"phase":"census","component_count":diagnostic.component_count(),"tensor_bytes":diagnostic.tensor_bytes(),
        "relative_product_ranks":diagnostic.relative_product_ranks(),"pair_weighted_product_rank":diagnostic.pair_weighted_product_rank(),
        "projected_columns":projected_signed_orbit_count(&kc,&fb),"exact_pair_coverage":subgroup_count(&truth),
        "same_component_coverage":subgroup_count(&same),"coverage_denominator":order-1,"validation_ns":validation.elapsed().as_nanos()})
    );
    let started = Instant::now();
    let targets = TargetSet::new(&kc, 8, 0, seed);
    let targets_ns = started.elapsed().as_nanos();
    let started = Instant::now();
    let field = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let field_setup_ns = started.elapsed().as_nanos();
    println!(
        "{}",
        json!({"phase":"target_setup","target_generation_ns":targets_ns,"field_setup_ns":field_setup_ns})
    );
    for t in &targets.points {
        let opts = SolveOptions {
            node_budget: 20000,
            max_solutions: usize::MAX,
            ..Default::default()
        };
        let started = Instant::now();
        let (w, mut counter, exhausted) = match variant.as_str() {
            "charts_f4" | "charts_linear" => {
                let (w, s) = plan
                    .as_ref()
                    .unwrap()
                    .decompose(&kc, &fb, &index, t, &opts)
                    .unwrap();
                let ex = s.solver.exhausted;
                (w, stats(&s), ex)
            }
            "ambient_f4" => {
                let (w, s) = groebner_decompose(
                    &kc,
                    &fb,
                    &index,
                    &field,
                    t,
                    2,
                    opts.engine,
                    opts.node_budget,
                );
                (w, json!({"reductions":s.reductions}), s.exhausted)
            }
            "enumerate" => (
                enumerate_decompose(&kc, &fb, &index, t, 2),
                json!({}),
                false,
            ),
            _ => panic!("variant"),
        };
        let solve_ns = started.elapsed().as_nanos();
        let validation = Instant::now();
        let exists = truth.contains(&fc.lift(t));
        let correct = w.as_ref().is_none_or(|w| valid_witness(&kc, &fb, t, w))
            && (exhausted || w.is_some() == exists);
        assert!(correct);
        counter["phase"] = json!("target");
        counter["target"] = point_json(t);
        counter["witness"] = json!(w);
        counter["truth"] = json!(exists);
        counter["solve_ns"] = json!(solve_ns);
        counter["correct"] = json!(correct);
        counter["exhausted"] = json!(exhausted);
        counter["verification_ns"] = json!(validation.elapsed().as_nanos());
        println!("{}", counter);
        if let Some(p) = &plan {
            let x = fc.lift(t).x;
            let started = Instant::now();
            let mut got = BTreeSet::new();
            let s = p.visit_pairs(x, &opts, |a, b| {
                got.insert((a, b));
                false
            });
            let complete_ns = started.elapsed().as_nanos();
            let expected = algebraic_truth(&fc.field, &fb, x, bits(&kc.curve.b));
            assert!(got.is_subset(&expected));
            if !s.solver.exhausted {
                assert_eq!(got, expected);
            }
            println!(
                "{}",
                json!({"phase":"complete_roots","target":point_json(t),"root_hash":digest(&got),"truth_hash":digest(&expected),
                "roots":got,"complete_ns":complete_ns,"correct":got==expected,"stats":stats(&s)})
            );
        }
    }
}
