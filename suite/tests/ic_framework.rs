use serde_json::{json, Value};
use std::{
    path::PathBuf,
    process::Command,
    sync::atomic::{AtomicUsize, Ordering},
};
static NEXT: AtomicUsize = AtomicUsize::new(0);
fn path() -> PathBuf {
    std::env::temp_dir().join(format!(
        "ic-test-{}-{}.json",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ))
}
fn command(args: &[&str]) -> (bool, Value) {
    let output = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(args)
        .arg("--json")
        .output()
        .unwrap();
    let value = serde_json::from_slice(&output.stdout)
        .unwrap_or_else(|_| panic!("not JSON: {:?} {:?}", output.stdout, output.stderr));
    (output.status.success(), value)
}
fn inspect(value: &Value) -> (bool, Value) {
    let file = path();
    std::fs::write(&file, serde_json::to_vec(value).unwrap()).unwrap();
    let result = command(&["inspect", "--file", file.to_str().unwrap()]);
    std::fs::remove_file(file).unwrap();
    result
}
fn generated() -> Value {
    let (ok, v) = command(&["generate", "--degree", "9", "--seed", "41"]);
    assert!(ok);
    v
}
#[test]
fn named_profiles_report_inspection_only_and_missing_representation() {
    for name in ["ecc2k-130", "ecc2k-95", "sect163k1", "secp256k1"] {
        let (ok, v) = command(&[name]);
        assert!(ok, "{name}: {v}");
        assert_eq!(v["operation"], "inspect");
        assert_eq!(v["capabilities"]["imported_target_solving"], false);
        assert_eq!(v["capabilities"]["factor_base_built"], false);
        assert!(v["software"]["binary_blake3"].as_str().unwrap().len() == 64);
        if name == "ecc2k-130" {
            assert_eq!(v["parameters"]["field"]["degree"], 131);
            assert_eq!(v["capabilities"]["point_checks_attempted"], false);
            assert!(v["checks"]
                .as_array()
                .unwrap()
                .iter()
                .any(|c| c["name"] == "field_representation" && c["status"] == "not_checked"));
        }
    }
}
#[test]
fn generated_documents_round_trip_and_reproduce() {
    let v = generated();
    assert_eq!(v, generated());
    let (ok, report) = inspect(&v);
    assert!(ok, "{report}");
    assert!(report["checks"]
        .as_array()
        .unwrap()
        .iter()
        .any(|c| c["name"] == "known_answer" && c["status"] == "pass"));
}
#[test]
fn malformed_binary_parameters_fail_without_false_success() {
    let original = generated();
    let mut reducible = original.clone();
    reducible["field"]["polynomial_terms"] = json!([9, 0]);
    let mut duplicate = original.clone();
    duplicate["field"]["polynomial_terms"] = json!([9, 1, 1, 0]);
    let mut noncanonical = original.clone();
    noncanonical["generator"]["x"] = json!("0x200");
    let mut wrong_order = original.clone();
    wrong_order["subgroup_order"] = json!("6");
    let mut wrong_point = original.clone();
    wrong_point["point"] = json!({"x":"0","y":"0"});
    let mut wrong_answer = original;
    wrong_answer["fixture"]["known_log"] = json!("0");
    for value in [
        reducible,
        duplicate,
        noncanonical,
        wrong_order,
        wrong_point,
        wrong_answer,
    ] {
        let (ok, report) = inspect(&value);
        assert!(!ok, "accepted {report}");
        assert_eq!(report["status"], "invalid");
    }
}
#[test]
fn custom_prime_curve_checks_points_and_known_answer() {
    let v = json!({"schema_version":1,"name":"prime-toy","field":{"kind":"prime","modulus":"97"},
        "a":"2","b":"3","subgroup_order":"5","cofactor":"20",
        "generator":{"x":"3","y":"6"},"point":{"x":"3","y":"91"},"fixture":{"known_log":"4","seed":0}});
    let (ok, report) = inspect(&v);
    assert!(ok, "{report}");
    assert!(report["checks"]
        .as_array()
        .unwrap()
        .iter()
        .any(|c| c["name"] == "known_answer" && c["status"] == "pass"));
    let mut bad = v;
    bad["field"]["modulus"] = json!("91");
    assert!(!inspect(&bad).0);
}
#[test]
fn schema_unknown_fields_and_ambiguous_abstract_coordinates_are_rejected() {
    let mut v = generated();
    v["unrecognized"] = json!(true);
    assert!(!inspect(&v).0);
    let (_, normal) = command(&["ecc2k-130"]);
    let mut p = normal["parameters"].clone();
    p["generator"] = json!({"x":"1","y":"1"});
    let (ok, report) = inspect(&p);
    assert!(!ok);
    assert_eq!(report["status"], "invalid");
}
#[test]
fn supported_larger_fixture_completes_and_reports_resources() {
    // Control accounting: one column per Frobenius orbit, fixed surplus,
    // serial trials — the historical 91 + 4 relations.
    let (ok, v) = command(&[
        "run",
        "--degree",
        "11",
        "--curve-a",
        "1",
        "--known-log",
        "53",
        "--solver",
        "enumerate",
        "--control",
        "--batch",
        "1",
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["result"]["verified"], true);
    assert_eq!(v["result"]["recovered"], "53");
    assert_eq!(v["counts"]["relations"], 95);
    assert_eq!(v["mode"]["control"], true);
    assert_eq!(v["factor_base"]["spec"]["kind"], "factor");
    // Fast accounting: signed and cofactor-projected columns, and the
    // incremental solve stops as soon as the scalar is pinned.
    let (ok, fast) = command(&[
        "run",
        "--degree",
        "11",
        "--curve-a",
        "1",
        "--known-log",
        "53",
        "--solver",
        "enumerate",
        "--batch",
        "1",
    ]);
    assert!(ok, "{fast}");
    assert_eq!(fast["result"]["verified"], true);
    assert_eq!(fast["result"]["recovered"], "53");
    assert!(fast["counts"]["columns"].as_u64().unwrap() < v["counts"]["columns"].as_u64().unwrap());
    assert!(fast["counts"]["relations"].as_u64().unwrap() < 95);
    assert_eq!(fast["counts"]["inconsistent_relations"], 0);
    assert_eq!(fast["counts"]["verification_failures"], 0);
    assert_eq!(
        v["stages"].as_array().unwrap().last().unwrap()["status"],
        "pass"
    );
    #[cfg(any(target_os = "macos", target_os = "linux"))]
    {
        assert!(v["resources"]["peak_rss_bytes"].as_u64().unwrap() > 0);
        assert!(v["resources"]["cpu_seconds"].as_f64().unwrap() > 0.0);
    }
}
#[test]
fn synthetic_targets_are_reproducible_and_imports_are_not_run_arguments() {
    let args = [
        "run",
        "--random-target",
        "--seed",
        "17",
        "--solver",
        "enumerate",
    ];
    let (ok, a) = command(&args);
    let (ok2, b) = command(&args);
    assert!(ok && ok2);
    assert_eq!(a["parameters"], b["parameters"]);
    let status = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["run", "--file", "anything.json"])
        .output()
        .unwrap()
        .status;
    assert!(!status.success());
    let status = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["run", "--degree", "131"])
        .output()
        .unwrap()
        .status;
    assert!(!status.success());
}
#[test]
fn incomplete_comparisons_never_select_a_winner() {
    let (ok, v) = command(&[
        "compare",
        "--samples",
        "1",
        "--holdout",
        "1",
        "--max-trials",
        "1",
    ]);
    assert!(!ok);
    assert_eq!(v["status"], "inconclusive");
    assert!(v["selected_factor_index"].is_null());
    for c in v["candidates"].as_array().unwrap() {
        assert_eq!(c["eligible"], false);
        assert!(c["median_process_seconds"].is_null());
    }
}
#[test]
fn successful_comparison_has_same_training_inputs_and_separate_holdout() {
    let (ok, v) = command(&[
        "compare",
        "--samples",
        "2",
        "--holdout",
        "1",
        "--max-trials",
        "100",
    ]);
    assert!(ok, "{v}");
    let candidates = v["candidates"].as_array().unwrap();
    assert_eq!(candidates.len(), 2);
    assert_eq!(
        candidates[0]["training"][0]["parameters"],
        candidates[1]["training"][0]["parameters"]
    );
    let index = v["selected_factor_index"].as_u64().unwrap() as usize;
    assert_eq!(candidates[index]["eligible"], true);
    assert_eq!(v["holdout"][0]["result"]["verified"], true);
    assert_ne!(
        v["holdout"][0]["arguments"]["seed"],
        candidates[0]["training"][0]["arguments"]["seed"]
    );
}
#[test]
fn report_files_are_created_once_and_generated_reports_are_importable() {
    let file = path();
    let (ok, v) = command(&["generate", "--out", file.to_str().unwrap()]);
    assert!(ok);
    let bytes = std::fs::read(&file).unwrap();
    assert_eq!(serde_json::from_slice::<Value>(&bytes).unwrap(), v);
    let run = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["generate", "--out", file.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(!run.status.success());
    assert_eq!(std::fs::read(&file).unwrap(), bytes);
    assert!(command(&["inspect", "--file", file.to_str().unwrap()]).0);
    std::fs::remove_file(file).unwrap();
}

#[test]
fn point_only_input_reports_the_checks_that_were_attempted() {
    let value = json!({"schema_version":1,"name":"point-only","field":{"kind":"prime","modulus":"97"},
        "a":"2","b":"3","subgroup_order":"5","cofactor":"20","point":{"x":"3","y":"6"}});
    let (ok, report) = inspect(&value);
    assert!(ok, "{report}");
    assert_eq!(report["capabilities"]["point_checks_attempted"], true);
    assert!(report["checks"]
        .as_array()
        .unwrap()
        .iter()
        .any(|c| c["name"] == "generator" && c["status"] == "not_checked"));
    assert!(report["checks"]
        .as_array()
        .unwrap()
        .iter()
        .any(|c| c["name"] == "point_subgroup" && c["status"] == "pass"));
}

#[test]
fn search_finds_a_validated_base_where_the_legacy_family_yields_nothing() {
    // K_1 / GF(2^15) with factor index 0 collects no relation at all.
    let (ok, legacy) = command(&[
        "run",
        "--degree",
        "15",
        "--curve-a",
        "1",
        "--solver",
        "pair-table",
        "--max-trials",
        "500",
    ]);
    assert!(!ok);
    assert_eq!(legacy["status"], "incomplete");
    assert_eq!(legacy["counts"]["relations"], 0);

    let spec = path();
    let (ok, v) = command(&[
        "search",
        "--degree",
        "15",
        "--curve-a",
        "1",
        "--family",
        "divisor",
        "--max-dimension",
        "8",
        "--no-saturate",
        "--validate-top",
        "1",
        "--holdout",
        "1",
        "--spec-out",
        spec.to_str().unwrap(),
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "complete");
    assert_eq!(v["exhaustive_targets"], true);
    assert_eq!(v["targets"], 210);
    let candidates = v["candidates"].as_array().unwrap();
    assert!(!candidates.is_empty());
    // Ranked by expected trials, finite ones first.
    let scores: Vec<f64> = candidates
        .iter()
        .map(|c| c["expected_trials"].as_f64().unwrap_or(f64::INFINITY))
        .collect();
    assert!(scores.windows(2).all(|w| w[0] <= w[1]));
    assert!(candidates
        .iter()
        .all(|c| c["spec"]["kind"] == "divisor" || c["spec"]["kind"] == "pruned"));
    assert_eq!(v["validation"]["runs"][0]["eligible"], true);
    assert_eq!(v["selected"]["degree"], 15);
    assert_eq!(v["selected"]["curve_a"], 1);

    // The saved recipe solves a fresh known-answer fixture end to end.
    let (ok, run) = command(&[
        "run",
        "--degree",
        "15",
        "--curve-a",
        "1",
        "--solver",
        "pair-table",
        "--factor-base",
        spec.to_str().unwrap(),
        "--known-log",
        "97",
    ]);
    assert!(ok, "{run}");
    assert_eq!(run["result"]["verified"], true);
    assert_eq!(run["result"]["recovered"], "97");
    assert_eq!(run["factor_base"]["spec"], v["selected"]["spec"]);
    assert_eq!(run["counts"]["inconsistent_relations"], 0);

    // A recipe is bound to its curve.
    let (ok, wrong) = command(&[
        "run",
        "--degree",
        "9",
        "--curve-a",
        "0",
        "--factor-base",
        spec.to_str().unwrap(),
    ]);
    assert!(!ok);
    assert_eq!(wrong["operation"], "error");
    // The recipe file is never overwritten.
    let (ok, _) = command(&[
        "search",
        "--degree",
        "15",
        "--curve-a",
        "1",
        "--family",
        "factor",
        "--validate-top",
        "0",
        "--spec-out",
        spec.to_str().unwrap(),
    ]);
    assert!(!ok);
    std::fs::remove_file(spec).unwrap();
}

#[test]
fn every_solver_recovers_the_same_scalar_with_three_summands() {
    for solver in ["pair-table", "enumerate", "groebner", "sat"] {
        let (ok, v) = command(&[
            "run",
            "--degree",
            "9",
            "--curve-a",
            "0",
            "--known-log",
            "77",
            "--summands",
            "3",
            "--solver",
            solver,
        ]);
        assert!(ok, "{solver}: {v}");
        assert_eq!(v["result"]["verified"], true, "{solver}");
        assert_eq!(v["result"]["recovered"], "77", "{solver}");
        assert_eq!(v["counts"]["sat_invalid_models"], 0);
        assert_eq!(v["counts"]["inconsistent_relations"], 0);
    }
}

#[test]
fn factor_base_logarithm_database_precomputes_then_descends() {
    // Precompute the database once, then recover several targets by
    // descent reusing it — the CADO-style split.
    let db = path();
    let (ok, logs) = command(&[
        "logs",
        "--degree",
        "9",
        "--curve-a",
        "0",
        "--solver",
        "pair-table",
        "--database",
        db.to_str().unwrap(),
    ]);
    assert!(ok, "{logs}");
    assert_eq!(logs["status"], "complete");
    assert_eq!(logs["verified"], true);
    assert_eq!(logs["counts"]["columns"], 3);
    assert_eq!(logs["linear_algebra"]["mode"], "sparse");
    assert!(logs["linear_algebra"]["attempts"].as_u64().unwrap() >= 1);

    // The dense path certifies the very same database.
    let dense_db = path();
    let (ok, dense) = command(&[
        "logs",
        "--degree",
        "9",
        "--curve-a",
        "0",
        "--solver",
        "pair-table",
        "--linear-algebra",
        "dense",
        "--database",
        dense_db.to_str().unwrap(),
    ]);
    assert!(ok, "{dense}");
    assert_eq!(dense["linear_algebra"]["mode"], "dense");
    assert!(dense["linear_algebra"]["sparse"].is_null());
    let a: Value = serde_json::from_slice(&std::fs::read(&db).unwrap()).unwrap();
    let b: Value = serde_json::from_slice(&std::fs::read(&dense_db).unwrap()).unwrap();
    assert_eq!(
        a["columns"], b["columns"],
        "sparse and dense databases differ"
    );
    std::fs::remove_file(dense_db).unwrap();

    for k in ["1", "53", "126"] {
        let (ok, solve) = command(&[
            "solve",
            "--degree",
            "9",
            "--curve-a",
            "0",
            "--logs",
            db.to_str().unwrap(),
            "--known-log",
            k,
            "--solver",
            "pair-table",
        ]);
        assert!(ok, "{solve}");
        assert_eq!(solve["status"], "complete");
        assert_eq!(solve["result"]["verified"], true);
        assert_eq!(solve["result"]["recovered"], k);
        assert_eq!(solve["database"]["reverified"], true);
    }

    // A database is bound to its curve.
    let (ok, wrong) = command(&[
        "solve",
        "--degree",
        "11",
        "--curve-a",
        "1",
        "--logs",
        db.to_str().unwrap(),
        "--known-log",
        "5",
    ]);
    assert!(!ok);
    assert_eq!(wrong["operation"], "error");

    // The database file is never overwritten.
    let (ok, _) = command(&[
        "logs",
        "--degree",
        "9",
        "--curve-a",
        "0",
        "--database",
        db.to_str().unwrap(),
    ]);
    assert!(!ok);
    std::fs::remove_file(db).unwrap();
}

/// The solve-cost objective prices one oracle over one kind of base.
/// A workflow that asks for it while collecting with a different oracle,
/// or while most of its candidates cannot be priced at all, is selecting
/// on a number that does not describe the run it will do; refuse it, and
/// name what to change.
#[test]
fn workflow_rejects_a_solve_cost_objective_that_does_not_match_the_run() {
    let base = json!({
        "schema_version":1,"name":"k1n15","curve":{"degree":15,"curve_a":1},
        "summands":2,"solver":"groebner","seed":1,"max_trials":100000,
        "collection":{"unit_trials":64,"units":1,"max_units":2},
        "factor_base":{"mode":"search","family":"divisor","min_dimension":3,"max_dimension":6,
            "prune":false,"saturate":false,"solve_cost_targets":4},
        "targets":[{"known_log":"53"}]
    });
    let cases: [(&str, Value, &str); 5] = [
        ("wrong oracle", json!({"solver":"pair_table"}), "groebner"),
        (
            "pruned candidates",
            json!({"prune":true}),
            "prune and saturate",
        ),
        (
            "saturated candidates",
            json!({"saturate":true}),
            "prune and saturate",
        ),
        ("out of range", json!({"solve_cost_targets":0}), "1..=4096"),
        ("unpriceable family", json!({"family":"union"}), "factor"),
    ];
    for (name, patch, expected) in cases {
        let mut params = base.clone();
        for (key, value) in patch.as_object().unwrap() {
            if key == "solver" {
                params["solver"] = value.clone();
            } else {
                params["factor_base"][key] = value.clone();
            }
        }
        let file = path();
        std::fs::write(&file, serde_json::to_vec(&params).unwrap()).unwrap();
        let dir = std::env::temp_dir().join(format!(
            "ic-solve-cost-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let _ = std::fs::remove_dir_all(&dir);
        let (ok, v) = command(&[
            "workflow",
            "--params",
            file.to_str().unwrap(),
            "--dir",
            dir.to_str().unwrap(),
            "--stop-after",
            "select",
        ]);
        assert!(!ok, "{name} was accepted: {v}");
        let message = v["message"].as_str().unwrap_or_default();
        assert!(
            message.contains(expected),
            "{name}: {message:?} does not say what to change ({expected:?})"
        );
        let _ = std::fs::remove_dir_all(&dir);
    }
}

#[test]
fn workflow_runs_in_stages_and_resumes_without_redoing_work() {
    let dir = std::env::temp_dir().join(format!(
        "ic-workflow-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    let _ = std::fs::remove_dir_all(&dir);
    let params = path();
    std::fs::write(
        &params,
        serde_json::to_vec(&json!({
            "schema_version":1,"name":"k0n9","curve":{"degree":9,"curve_a":0},
            "summands":2,"solver":"pair_table","seed":1,"max_trials":100000000,
            "linear_algebra":{"mode":"sparse","sparse":{"wiedemann":{"block_m":2,"block_n":2}}},
            "collection":{"unit_trials":128,"units":2,"max_units":8},
            "baseline":{"rho":true,"rho_max_iterations":100000},
            "factor_base":{"mode":"spec","spec":{"kind":"factor","index":0}},
            "targets":[{"known_log":"53"},{"random_seed":7},{"known_log":"126"},{"public_hash_seed":29}]
        }))
        .unwrap(),
    )
    .unwrap();
    let p = params.to_str().unwrap();
    let d = dir.to_str().unwrap();

    // Stage by stage: each rerun reuses what the previous one produced.
    let (ok, v) = command(&[
        "workflow",
        "--params",
        p,
        "--dir",
        d,
        "--stop-after",
        "select",
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "stopped");
    assert_eq!(v["run_number"], 1);
    assert!(dir.join("factor_base.json").exists());
    assert!(!dir.join("logs.json").exists());
    assert!(!dir.join("relations").join("unit-00000.json").exists());

    // A collection worker (another process, possibly another machine)
    // runs one work unit and stops; running it again does nothing.
    let unit1 = dir.join("relations").join("unit-00001.json");
    let (ok, v) = command(&[
        "workflow",
        "--params",
        p,
        "--dir",
        d,
        "--collect-units",
        "1",
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "stopped");
    assert_eq!(v["stages"][1]["stage"], "collect");
    assert_eq!(v["stages"][1]["worker"], true);
    assert_eq!(v["stages"][1]["units"]["ran_now"], 1);
    assert_eq!(v["stages"][1]["units"]["present"], 1);
    assert_eq!(
        v["stages"][1]["status"], "partial",
        "unit 0 is still missing"
    );
    assert!(unit1.exists() && !dir.join("logs.json").exists());
    let (ok, v) = command(&[
        "workflow",
        "--params",
        p,
        "--dir",
        d,
        "--collect-units",
        "1",
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["stages"][1]["units"]["ran_now"], 0);
    let (ok, v) = command(&[
        "workflow",
        "--params",
        p,
        "--dir",
        d,
        "--collect-units",
        "99",
    ]);
    assert!(!ok, "a unit beyond max_units is refused: {v}");

    // Forge one relation in the worker's file and drop in a file from
    // another run: the forgery is rejected, the foreign file ignored.
    let mut unit: Value = serde_json::from_slice(&std::fs::read(&unit1).unwrap()).unwrap();
    let relations_in_unit1 = unit["relations"].as_array().unwrap().len();
    assert!(relations_in_unit1 > 0);
    let a: u64 = unit["relations"][0]["a"].as_u64().unwrap();
    unit["relations"][0]["a"] = json!(if a == 1 { 2 } else { a - 1 });
    std::fs::write(&unit1, serde_json::to_vec(&unit).unwrap()).unwrap();
    let mut foreign = unit.clone();
    foreign["params_digest"] = json!("0".repeat(64));
    foreign["unit"] = json!(7);
    std::fs::write(
        dir.join("relations").join("unit-00007.json"),
        serde_json::to_vec(&foreign).unwrap(),
    )
    .unwrap();

    let (ok, v) = command(&[
        "workflow",
        "--params",
        p,
        "--dir",
        d,
        "--stop-after",
        "logs",
    ]);
    assert!(ok, "{v}");
    assert_eq!(v["resumed"], true);
    let stages = v["stages"].as_array().unwrap();
    assert_eq!(stages[0]["stage"], "select");
    assert_eq!(stages[0]["ran"], false, "select must be reused");
    assert_eq!(stages[1]["stage"], "collect");
    assert_eq!(stages[1]["units"]["ran_now"], 1, "only unit 0 was missing");
    assert_eq!(stages[1]["units"]["present"], 2);
    assert_eq!(stages[1]["units"]["ignored"], 1);
    assert_eq!(stages[1]["status"], "complete");
    assert_eq!(stages[2]["stage"], "logs");
    assert_eq!(stages[2]["ran"], true);
    assert_eq!(stages[2]["rejected"], 1, "the forged relation");
    assert_eq!(stages[2]["units_used"], 2);
    assert_eq!(stages[2]["linear_algebra"]["mode"], "sparse");
    // Three columns; the filtering statistics are reported and whatever
    // the merge leaves (at most the three) goes to block Wiedemann.
    assert_eq!(
        stages[2]["linear_algebra"]["sparse"]["filter"]["columns_in"],
        3
    );
    assert!(
        stages[2]["linear_algebra"]["sparse"]["core_dimension"]
            .as_u64()
            .unwrap()
            <= 3
    );
    assert!(dir.join("logs.json").exists());
    assert!(dir.join("relations").join("unit-00000.json").exists());

    let (ok, v) = command(&["workflow", "--params", p, "--dir", d]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "complete");
    assert_eq!(v["summands"], 2);
    assert_eq!(v["descent_summands"], 2);
    assert_eq!(
        v["evidence_scope"],
        "mixed_synthetic_known_answer_and_public_hash_unknown_scalar"
    );
    assert_eq!(v["solutions"]["verified"], 4);
    assert_eq!(v["solutions"]["count"], 4);
    let stages = v["stages"].as_array().unwrap();
    assert_eq!(stages[1]["ran"], false, "collection must be reused");
    assert_eq!(stages[2]["ran"], false, "logs must be reused");
    assert_eq!(stages[3]["stage"], "solve");
    assert_eq!(stages[3]["solved_now"], 4);
    // The rho baseline ran on the same four targets in this process.
    assert_eq!(stages[4]["stage"], "baseline");
    let vs = &stages[4]["vs_rho"];
    assert_eq!(vs["targets"], 4);
    assert_eq!(vs["rho"]["verified"], 4);
    assert_eq!(vs["ic"]["verified"], 4);
    assert_eq!(vs["claim_boundary"], "public_hash_unknown_scalar");
    assert!(vs["rho"]["seconds_per_target"].as_f64().unwrap() > 0.0);
    assert!(vs["ratio"]["charged"].as_f64().unwrap() > 0.0);
    assert!(vs["verdict"]["charged_crossover"].is_boolean());
    assert!(dir.join("baseline.json").exists());
    for item in v["solutions"]["items"].as_array().unwrap() {
        assert_eq!(item["verified"], true);
        if item["target"]["kind"] == "public_hash_to_curve_cofactor" {
            assert_eq!(item["expected"], "not_constructed");
            assert_eq!(item["target"]["target_scalar_constructed"], false);
            assert!(item["recovered"].as_str().is_some());
        } else {
            assert_eq!(item["expected"], item["recovered"]);
            assert_eq!(item["target"]["target_scalar_constructed"], true);
        }
    }

    // A full rerun does no new work.
    let (ok, v) = command(&["workflow", "--params", p, "--dir", d]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "complete");
    assert_eq!(
        v["run_number"], 6,
        "the refused worker run persisted nothing"
    );
    assert_eq!(v["stages"][3]["solved_now"], 0);
    assert_eq!(v["stages"][3]["already_solved"], 4);
    assert_eq!(v["state"]["units_collected"], 2);

    // A different parameter set is refused in the same directory.
    let other = path();
    std::fs::write(
        &other,
        serde_json::to_vec(&json!({
            "schema_version":1,"name":"k0n9","curve":{"degree":9,"curve_a":0},
            "summands":2,"solver":"pair_table","seed":2,
            "factor_base":{"mode":"spec","spec":{"kind":"factor","index":0}},
            "targets":[{"known_log":"53"}]
        }))
        .unwrap(),
    )
    .unwrap();
    let (ok, v) = command(&["workflow", "--params", other.to_str().unwrap(), "--dir", d]);
    assert!(!ok);
    assert_eq!(v["operation"], "error");

    // A tampered logarithm database is rejected on resume, not trusted.
    let logs_path = dir.join("logs.json");
    let mut doc: Value = serde_json::from_slice(&std::fs::read(&logs_path).unwrap()).unwrap();
    let log: u64 = doc["columns"][0]["log"].as_str().unwrap().parse().unwrap();
    doc["columns"][0]["log"] = json!(((log + 1) % 127).to_string());
    std::fs::write(&logs_path, serde_json::to_vec(&doc).unwrap()).unwrap();
    let (ok, v) = command(&["workflow", "--params", p, "--dir", d]);
    assert!(!ok);
    assert_eq!(v["operation"], "error");

    std::fs::remove_dir_all(&dir).unwrap();
    std::fs::remove_file(params).unwrap();
    std::fs::remove_file(other).unwrap();
}

#[test]
fn subfield_curves_run_precompute_and_descend_with_bound_documents() {
    // E_{0,2}/GF(4) over GF(2^14): the 4-power Frobenius family.
    let (ok, run) = command(&[
        "run",
        "--degree",
        "14",
        "--subfield",
        "2",
        "--curve-a",
        "0",
        "--curve-b",
        "2",
        "--solver",
        "pair-table",
        "--known-log",
        "53",
    ]);
    assert!(ok, "{run}");
    assert_eq!(run["result"]["verified"], true);
    assert_eq!(run["result"]["recovered"], "53");

    let db = path();
    let (ok, logs) = command(&[
        "logs",
        "--degree",
        "14",
        "--subfield",
        "2",
        "--curve-a",
        "0",
        "--curve-b",
        "2",
        "--solver",
        "pair-table",
        "--database",
        db.to_str().unwrap(),
    ]);
    assert!(ok, "{logs}");
    assert_eq!(logs["status"], "complete");
    assert_eq!(logs["verified"], true);
    let doc: Value = serde_json::from_slice(&std::fs::read(&db).unwrap()).unwrap();
    assert_eq!(doc["subfield"], 2);
    assert_eq!(doc["curve_b"], 2);
    assert_eq!(doc["degree"], 14);

    let (ok, solve) = command(&[
        "solve",
        "--degree",
        "14",
        "--subfield",
        "2",
        "--curve-a",
        "0",
        "--curve-b",
        "2",
        "--logs",
        db.to_str().unwrap(),
        "--known-log",
        "4000",
        "--solver",
        "pair-table",
    ]);
    assert!(ok, "{solve}");
    assert_eq!(solve["result"]["verified"], true);
    assert_eq!(solve["result"]["recovered"], "4000");

    // The database is bound to the subfield curve: a Koblitz reading of
    // the same degree is refused, and so is another b.
    let (ok, v) = command(&[
        "solve",
        "--degree",
        "14",
        "--curve-a",
        "0",
        "--logs",
        db.to_str().unwrap(),
        "--known-log",
        "5",
    ]);
    assert!(!ok, "{v}");
    let (ok, v) = command(&[
        "solve",
        "--degree",
        "14",
        "--subfield",
        "2",
        "--curve-a",
        "0",
        "--curve-b",
        "3",
        "--logs",
        db.to_str().unwrap(),
        "--known-log",
        "5",
    ]);
    assert!(!ok, "{v}");
    std::fs::remove_file(db).unwrap();

    // Koblitz documents are unchanged: no subfield fields are written.
    let db = path();
    let (ok, _) = command(&[
        "logs",
        "--degree",
        "9",
        "--curve-a",
        "0",
        "--solver",
        "pair-table",
        "--database",
        db.to_str().unwrap(),
    ]);
    assert!(ok);
    let doc: Value = serde_json::from_slice(&std::fs::read(&db).unwrap()).unwrap();
    assert!(doc.get("subfield").is_none() && doc.get("curve_b").is_none());
    std::fs::remove_file(db).unwrap();

    // Parameter validation: n/k must be odd, coefficients below q.
    let (ok, _) = command(&["run", "--degree", "12", "--subfield", "2", "--curve-b", "2"]);
    assert!(!ok);
    let (ok, _) = command(&[
        "run",
        "--degree",
        "14",
        "--subfield",
        "2",
        "--curve-a",
        "4",
        "--curve-b",
        "2",
    ]);
    assert!(!ok);
}

#[test]
fn budget_charges_a_degree_far_past_the_curve_constructors_reach() {
    // Nothing is constructed, so the 63 cap on the run commands does not apply.
    let (ok, v) = command(&["budget", "--degree", "571", "--max-arity", "5"]);
    assert!(ok, "{v}");
    assert_eq!(v["operation"], "budget");
    assert_eq!(v["status"], "complete");
    assert_eq!(v["evidence_scope"], "analytic_cost_model");
    let degrees = v["degrees"].as_array().unwrap();
    assert_eq!(degrees.len(), 1);
    assert_eq!(degrees[0]["degree"], 571);
    assert!(!degrees[0]["cells"].as_array().unwrap().is_empty());
}

#[test]
fn budget_reports_arity_two_as_losing_even_to_a_free_decomposition_oracle() {
    let (ok, v) = command(&["budget", "--standard", "--summands", "2"]);
    assert!(ok, "{v}");
    for degree in v["degrees"].as_array().unwrap() {
        let cell = &degree["cells"].as_array().unwrap()[0];
        assert_eq!(
            cell["free_oracle_loses"], true,
            "degree {} unexpectedly left an arity-2 budget",
            degree["degree"]
        );
        assert!(cell["log2_budget"].as_f64().unwrap() < 0.0);
    }
}

#[test]
fn budget_separates_a_system_too_large_to_build_from_one_merely_hard_to_solve() {
    // ECC2K-130's degree: arity 4 has a positive budget and is still blocked,
    // because forming the descended system already exceeds it.
    let (ok, v) = command(&["budget", "--degree", "131", "--summands", "4"]);
    assert!(ok, "{v}");
    let cell = &v["degrees"].as_array().unwrap()[0]["cells"]
        .as_array()
        .unwrap()[0];
    assert!(cell["log2_budget"].as_f64().unwrap() > 0.0);
    assert_eq!(cell["free_oracle_loses"], false);
    assert_eq!(cell["anf_blocks"], true);
    assert_eq!(cell["viable"], false);
    assert!(cell["log2_anf_deficit"].as_f64().unwrap() > 0.0);
}

#[test]
fn budget_finds_the_two_degrees_where_the_system_fits_inside_the_budget() {
    let (ok, v) = command(&["budget", "--standard", "--summands", "4"]);
    assert!(ok, "{v}");
    let fitting: Vec<u64> = v["degrees"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|d| d["cells"].as_array().unwrap()[0]["viable"] == true)
        .map(|d| d["degree"].as_u64().unwrap())
        .collect();
    assert_eq!(fitting, vec![409, 571]);
}

#[test]
fn budget_shows_what_the_orbit_quotient_buys_by_withholding_it() {
    // Crediting the quotient may only help; at 113 it is what moves the
    // smallest viable arity from 4 down to 3.
    let (ok, with) = command(&["budget", "--degree", "113"]);
    assert!(ok, "{with}");
    let (ok, without) = command(&["budget", "--degree", "113", "--no-frobenius"]);
    assert!(ok, "{without}");
    assert_eq!(with["frobenius_orbit_quotient_credited"], true);
    assert_eq!(without["frobenius_orbit_quotient_credited"], false);
    assert_eq!(with["degrees"][0]["minimum_viable_arity"], 3);
    assert_eq!(without["degrees"][0]["minimum_viable_arity"], 4);
}

#[test]
fn budget_refuses_a_factor_base_spanning_the_whole_field() {
    let (ok, v) = command(&[
        "budget",
        "--degree",
        "131",
        "--summands",
        "4",
        "--dimension",
        "131",
    ]);
    assert!(!ok);
    assert_eq!(v["operation"], "error");
}

#[test]
fn budget_refuses_a_degree_it_was_not_given() {
    let (ok, v) = command(&["budget", "--summands", "4"]);
    assert!(!ok);
    assert_eq!(v["operation"], "error");
    assert!(v["message"].as_str().unwrap().contains("--degree"));
}
