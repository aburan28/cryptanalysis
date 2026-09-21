//! Native matched S3 benchmark; run via research/polynomial_reuse_20260914/run.py.
use cryptanalysis_suite::{
    binary_ecc::F2mElement,
    cryptanalysis::{
        koblitz_groebner::{
            build_decomposition_system, matrix_f4_f2_counted, solve_boolean_system, FieldStructure,
            SolveOptions,
        },
        koblitz_index_calculus::find_irreducible,
        polynomial_reuse::DecompositionTemplate,
        pq_groebner_f2::{groebner_basis_f2, F2BoolPoly},
        sat::SolveResult,
        semaev_sat::encode_boolean_system,
    },
};
use num_bigint::BigUint;
use serde_json::json;
use std::time::Instant;
fn fe(x: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(x), n)
}
fn roots(e: &[F2BoolPoly], nv: usize) -> Vec<u64> {
    (0..1u64 << nv)
        .filter(|&x| e.iter().all(|p| p.eval(x) == 0))
        .collect()
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let n: u32 = args[1].parse().unwrap();
    let ell: usize = args[2].parse().unwrap();
    let m: usize = args[3].parse().unwrap();
    let variant = &args[4];
    let start = Instant::now();
    let st = FieldStructure::new(n, &find_irreducible(n).unwrap());
    let basis: Vec<_> = (0..ell).map(|k| fe(1 << k, n)).collect();
    let b = fe(1, n);
    let field_setup_ns = start.elapsed().as_nanos();
    println!(
        "{}",
        json!({"phase":"begin","n":n,"ell":ell,"m":m,"variant":variant,"field_setup_ns":field_setup_ns})
    );
    let start = Instant::now();
    let template = if variant == "baseline" {
        None
    } else {
        Some(DecompositionTemplate::build(&basis, &b, m, &st).unwrap())
    };
    let template_setup_ns = start.elapsed().as_nanos();
    let start = Instant::now();
    let param = if variant == "parameterized" {
        let t = template.as_ref().unwrap();
        Some(groebner_basis_f2(
            t.parameterized_generators().unwrap(),
            t.n_vars + n as usize,
        ))
    } else {
        None
    };
    let parameter_basis_setup_ns = start.elapsed().as_nanos();
    println!(
        "{}",
        json!({"phase":"setup","template_setup_ns":template_setup_ns,"parameter_basis_setup_ns":parameter_basis_setup_ns,
        "template_bytes":template.as_ref().map(|t|serde_json::to_vec(t).unwrap().len()).unwrap_or(0),
        "parameter_basis_bytes":param.as_ref().map(|t|serde_json::to_vec(t).unwrap().len()).unwrap_or(0),
        "parameter_basis_polynomials":param.as_ref().map(Vec::len).unwrap_or(0)})
    );
    let count = if n <= 5 { 1u64 << n } else { 32 };
    for index in 0..count {
        // odd multiplier is a permutation modulo 2^n: no duplicate targets.
        let r = (index * 13 + 3) % (1u64 << n);
        let start = Instant::now();
        let (eq, nv) = if variant == "baseline" {
            let s = build_decomposition_system(&basis, &fe(r, n), &b, m, &st).unwrap();
            (s.equations, s.n_vars)
        } else {
            let t = template.as_ref().unwrap();
            let e = if let Some(p) = &param {
                t.specialize_parameter_basis(p, r)
            } else {
                t.instantiate(&fe(r, n)).equations
            };
            (e, t.n_vars)
        };
        let instantiate_ns = start.elapsed().as_nanos();
        let start = Instant::now();
        let (mut found, stats) = solve_boolean_system(
            &eq,
            nv,
            &SolveOptions {
                max_solutions: usize::MAX,
                node_budget: 100000,
                ..Default::default()
            },
        );
        let solve_ns = start.elapsed().as_nanos();
        found.sort_unstable();
        let start = Instant::now();
        let mut enc = encode_boolean_system(nv, &eq, &[]);
        let mut sat = Vec::new();
        if !enc.trivially_unsat {
            loop {
                match enc.solver.solve() {
                    SolveResult::Unsat => break,
                    SolveResult::Unknown => panic!("unexpected unknown"),
                    SolveResult::Sat => {
                        let a = enc.model_assignment();
                        sat.push(a);
                        enc.solver.reset_search();
                        if !enc.solver.add_clause(
                            (0..nv)
                                .map(|k| {
                                    if a & (1 << k) != 0 {
                                        -((k + 1) as i32)
                                    } else {
                                        (k + 1) as i32
                                    }
                                })
                                .collect(),
                        ) {
                            break;
                        }
                    }
                }
            }
        }
        let sat_ns = start.elapsed().as_nanos();
        sat.sort_unstable();
        let start = Instant::now();
        let original = build_decomposition_system(&basis, &fe(r, n), &b, m, &st).unwrap();
        let truth = roots(&original.equations, nv);
        let equivalent = roots(&eq, nv) == truth;
        let correct = equivalent && found == truth && sat == truth && !stats.exhausted;
        let verification_ns = start.elapsed().as_nanos();
        let root_xors = matrix_f4_f2_counted(&eq, nv, 3).map(|(_, ops)| ops);
        println!(
            "{}",
            json!({"phase":"target","target":r,"split":if index%2==0 {"development"}else{"holdout"},
            "n_vars":nv,"input_hash":blake3::hash(&serde_json::to_vec(&original).unwrap()).to_hex().to_string(),
            "instantiate_ns":instantiate_ns,"solve_ns":solve_ns,"sat_ns":sat_ns,"verification_ns":verification_ns,
            "f4_root_elimination_word_xors":root_xors,"sat_conflicts":enc.solver.conflicts(),"reductions":stats.reductions,
            "solutions":truth,"correct":correct,"exhausted":stats.exhausted})
        );
        assert!(correct, "specialization or solver lost/introduced roots");
    }
}
