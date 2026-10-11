//! Paired raw-system benchmark. JSON lines; UNKNOWN is never a refutation.
//! cargo run --release --example koblitz_sat_ablation -- 15 4 20000
//! Arguments: extension degree, target count, conflict cap per solve.
use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::invariant_subspace_basis;
use cryptanalysis_suite::cryptanalysis::sat::SolveResult;
use cryptanalysis_suite::cryptanalysis::semaev_sat::{encode_boolean_system_with, XorEncoding};
use num_bigint::BigUint;
use rand::{Rng, SeedableRng};
use serde_json::json;
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = args.get(1).map(|s| s.parse().unwrap()).unwrap_or(15);
    let count: usize = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(4);
    let budget: u64 = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(20_000);
    let (irr, basis) = invariant_subspace_basis(n, 0).expect("invariant subspace");
    let st = FieldStructure::new(n, &irr);
    let b = F2mElement::from_biguint(&BigUint::from(1u8), n);
    let mut rng = rand::rngs::StdRng::seed_from_u64(0x534154);
    for sample in 0..count {
        let x: u64 = rng.gen_range(0..(1u64 << n));
        let xr = F2mElement::from_biguint(&BigUint::from(x), n);
        let start = Instant::now();
        let sys = build_decomposition_system(&basis, &xr, &b, 3, &st).expect("system capacity");
        let build_ms = start.elapsed().as_secs_f64() * 1000.;
        let mut verdict = None;
        // Alternate order to reduce systematic warm-cache/order effects.
        let arms = if sample % 2 == 0 {
            [
                (XorEncoding::Cnf, false),
                (XorEncoding::Native, false),
                (XorEncoding::Native, true),
            ]
        } else {
            [
                (XorEncoding::Native, true),
                (XorEncoding::Native, false),
                (XorEncoding::Cnf, false),
            ]
        };
        for (mode, priority) in arms {
            let start = Instant::now();
            let mut enc = encode_boolean_system_with(sys.n_vars, &sys.equations, &[], mode);
            if priority {
                // These summand coordinates determine the chain up to finite
                // ambiguity; remaining coordinates are still legal decisions.
                enc.solver
                    .set_branch_priority(&(1..=(3 * basis.len()) as u32).collect::<Vec<_>>());
            }
            enc.solver.conflict_budget = budget;
            let encode_ms = start.elapsed().as_secs_f64() * 1000.;
            let vars = enc.solver.n_vars();
            let clauses = enc.solver.n_clauses();
            let xors = enc.solver.n_xors();
            let start = Instant::now();
            let result = enc.solver.solve();
            let solve_ms = start.elapsed().as_secs_f64() * 1000.;
            if result == SolveResult::Sat {
                assert!(sys
                    .equations
                    .iter()
                    .all(|e| e.eval(enc.model_assignment()) == 0));
            }
            if result != SolveResult::Unknown {
                if let Some(previous) = verdict {
                    assert_eq!(previous, result);
                }
                verdict = Some(result);
            }
            println!(
                "{}",
                json!({"kind":"raw_semaev_system", "n":n,"ell":basis.len(),
                "m":3,"sample":sample,"x_r":x,"mode":format!("{mode:?}"),"priority":priority,
                "variables":vars,"clauses":clauses,"xors":xors,"result":format!("{result:?}"),
                "build_ms":build_ms,"encode_ms":encode_ms,"solve_ms":solve_ms,
                "conflicts":enc.solver.conflicts(),"conflict_cap":budget})
            );
        }
    }
}
