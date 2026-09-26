//! End-to-end checks of `ca-ic` on prime-field curves: the named-curve
//! catalog, and `ic prime` on each curve type with both solvers.
use serde_json::Value;
use std::process::Command;

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

fn prime(args: &[&str]) -> (bool, Value) {
    let mut all = vec!["prime"];
    all.extend_from_slice(args);
    command(&all)
}

#[test]
fn the_catalog_covers_every_prime_field_family() {
    let (ok, v) = command(&["list"]);
    assert!(ok);
    let names: Vec<&str> = v["curves"]
        .as_array()
        .unwrap()
        .iter()
        .map(|n| n.as_str().unwrap())
        .collect();
    for want in [
        "secp160k1",
        "secp192k1",
        "secp224k1",
        "secp256k1",
        "p192",
        "p224",
        "p256",
        "p384",
        "p521",
        "brainpoolp256r1",
        "sm2",
        "frp256v1",
        "gost-tc26-256-a",
    ] {
        assert!(names.contains(&want), "{want} missing from ic list");
    }
}

#[test]
fn named_prime_curves_inspect_cleanly() {
    // The GOST 256-bit paramSetA row is the regression: its cofactor is 4.
    for name in [
        "p192",
        "p224",
        "secp256r1",
        "secp224k1",
        "brainpoolp192r1",
        "gost-tc26-256-a",
    ] {
        let (ok, v) = command(&["inspect", "--curve", name]);
        assert!(ok, "{name}: {v}");
        assert_eq!(v["status"], "checks_passed", "{name}");
        assert_eq!(v["parameters"]["field"]["kind"], "prime", "{name}");
        assert!(v["checks"]
            .as_array()
            .unwrap()
            .iter()
            .any(|c| c["name"] == "generator_subgroup" && c["status"] == "pass"));
    }
    let (_, gost) = command(&["inspect", "--curve", "gost-tc26-256-a"]);
    assert_eq!(gost["parameters"]["cofactor"], "4");
}

#[test]
fn secp256k1_is_reported_as_a_j0_curve_and_its_shape_is_kept() {
    let (ok, v) = prime(&["--curve", "secp256k1", "--bits", "20", "--targets", "4"]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "complete");
    assert_eq!(v["curve_type"], "j0");
    let named = &v["named_curve"];
    assert_eq!(named["automorphism_order"], 6);
    assert_eq!(named["s3_zeta_equivariant"], true);
    assert!(named["glv_lambda"].is_string());
    assert_eq!(named["evidence_scope"], "structure_only");
    // The scaled curve is y² = x³ + 7, as secp256k1 is.
    assert_eq!(v["instance"]["a"], "0");
    assert_eq!(v["instance"]["b"], "7");
    assert_eq!(v["instance"]["cofactor"], 1);
    assert_eq!(v["factor_base"]["automorphism_order"], 6);
    assert_eq!(v["vs_rho"]["verdict"]["all_verified"], true);
    assert_eq!(v["result"]["expected"], "53");
    assert_eq!(v["result"]["verified"], true);
}

#[test]
fn a_nist_curve_scales_with_a_equal_to_minus_three() {
    let (ok, v) = prime(&["--curve", "p224", "--bits", "20", "--targets", "4"]);
    assert!(ok, "{v}");
    assert_eq!(v["curve_type"], "generic");
    assert_eq!(v["named_curve"]["automorphism_order"], 2);
    assert!(v["named_curve"]["glv_lambda"].is_null());
    assert_eq!(v["shape"]["a"], -3);
    let p: u64 = v["instance"]["p"].as_str().unwrap().parse().unwrap();
    let a: u64 = v["instance"]["a"].as_str().unwrap().parse().unwrap();
    assert_eq!(p - a, 3);
    assert_eq!(v["descent"]["verified"], 4);
    assert_eq!(v["rho"]["verified"], 4);
}

#[test]
fn j1728_runs_on_its_certified_cofactor() {
    let (ok, v) = prime(&["--type", "j1728", "--bits", "20", "--targets", "4"]);
    assert!(ok, "{v}");
    assert_eq!(v["status"], "complete");
    assert_eq!(v["instance"]["b"], "0");
    assert!(v["instance"]["cofactor"].as_u64().unwrap() >= 2);
    assert_eq!(v["factor_base"]["automorphism_order"], 4);
    let order: u64 = v["instance"]["group_order"]
        .as_str()
        .unwrap()
        .parse()
        .unwrap();
    let r: u64 = v["instance"]["subgroup_order"]
        .as_str()
        .unwrap()
        .parse()
        .unwrap();
    assert_eq!(order, r * v["instance"]["cofactor"].as_u64().unwrap());
}

#[test]
fn every_target_is_recovered_and_the_accounting_adds_up() {
    let (ok, v) = prime(&["--type", "j0", "--bits", "22", "--targets", "8"]);
    assert!(ok, "{v}");
    let logs = &v["logs"];
    assert_eq!(logs["rejected_relations"], 0);
    assert_eq!(logs["uncertified_columns"], 0);
    assert_eq!(logs["inconsistent_components"], 0);
    let per = v["descent"]["per_target"].as_array().unwrap();
    assert_eq!(per.len(), 8);
    assert_eq!(v["configuration"]["solver"], "orbit");
    assert_eq!(v["configuration"]["seed"], 1);
    assert!(logs["rank"].as_u64().unwrap() <= v["factor_base"]["orbits"].as_u64().unwrap());
    assert!(logs["solved_columns"].as_u64().unwrap() <= v["factor_base"]["orbits"].as_u64().unwrap());
    for t in per {
        assert_eq!(t["verified"], true);
        assert_eq!(t["expected"], t["recovered"]);
        assert!(t["target"]["x"].is_string() && t["target"]["y"].is_string());
        assert_eq!(t["ops"].as_u64().unwrap(),
                   t["oracle_ops"].as_u64().unwrap() + t["probe_ops"].as_u64().unwrap());
    }
    for t in v["rho"]["per_target"].as_array().unwrap() {
        assert_eq!(t["expected"], t["recovered"]);
    }
    let total: u64 = per.iter().map(|t| t["ops"].as_u64().unwrap()).sum();
    assert_eq!(v["descent"]["total_ops"], total);
    let whole = &v["vs_rho"]["whole_process"];
    let pre = logs["oracle_ops"].as_f64().unwrap() + logs["probe_ops"].as_f64().unwrap();
    assert!((whole["ic_ops"].as_f64().unwrap() - (pre + total as f64)).abs() < 1.0);
    // The batch-rho opponent is charged against the same whole process.
    let batch = &v["vs_rho"]["whole_process_vs_batch_rho"];
    assert_eq!(batch["ic_ops"], whole["ic_ops"]);
    let plain = batch["rho_ops_expected"].as_f64().unwrap();
    let folded = batch["rho_ops_expected_folded"].as_f64().unwrap();
    assert!(0.0 < folded && folded < plain, "{batch}");
}

#[test]
fn large_primes_are_the_default_and_cut_the_precompute() {
    let args = ["--type", "j0", "--bits", "22", "--targets", "4"];
    let (ok, default) = prime(&args);
    assert!(ok, "{default}");
    assert_eq!(default["logs"]["collection"], "large_primes");
    assert_eq!(default["factor_base"]["sizing"], "batch");
    assert_eq!(default["descent"]["learn"], true);
    // Against the control on the same base (the default would size the
    // large-prime base to the batch, trading descent for precompute), and
    // with descents that do not learn, so that each database is only what
    // its collection found.
    let mut same_base = args.to_vec();
    same_base.extend(["--width", "2", "--no-learn"]);
    let (ok, lp) = prime(&same_base);
    assert!(ok, "{lp}");
    assert!(lp["logs"]["combined_relations"].as_u64().unwrap() > 0);
    let mut control = same_base.clone();
    control.push("--no-large-primes");
    let (ok, full) = prime(&control);
    assert!(ok, "{full}");
    assert_eq!(full["logs"]["collection"], "full_decompositions");
    let pre = |v: &Value| {
        v["logs"]["oracle_ops"].as_u64().unwrap() + v["logs"]["probe_ops"].as_u64().unwrap()
    };
    assert!(
        pre(&lp) * 10 < pre(&full),
        "large primes {} against full {}",
        pre(&lp),
        pre(&full)
    );
    assert_eq!(lp["descent"]["verified"], 4);
    assert_eq!(full["descent"]["verified"], 4);
    // The large primes the collection met are a second, much larger base
    // for the descent; the full collection has none.
    let known = lp["logs"]["known_large_primes"].as_u64().unwrap();
    assert!(known > 10 * lp["factor_base"]["certified_orbits"].as_u64().unwrap());
    assert_eq!(full["logs"]["known_large_primes"], 0);
    assert_eq!(full["descent"]["through_large_primes"], 0);
    let mean = |v: &Value| v["descent"]["mean_ops"].as_f64().unwrap();
    assert!(
        mean(&lp) * 5.0 < mean(&full),
        "descent {} with large primes against {} without",
        mean(&lp),
        mean(&full)
    );
}

#[test]
fn the_base_is_sized_to_the_batch_unless_a_width_is_given() {
    let base = [
        "--type",
        "j0",
        "--bits",
        "22",
        "--targets",
        "40",
        "--no-rho",
    ];
    let (ok, batch) = prime(&base);
    assert!(ok, "{batch}");
    assert_eq!(batch["factor_base"]["sizing"], "batch");
    // Learning descents build the database, so the base only bootstraps.
    assert_eq!(batch["factor_base"]["orbits"], 8);
    let with = |extra: &[&'static str]| {
        let mut args = base.to_vec();
        args.extend_from_slice(extra);
        let (ok, v) = prime(&args);
        assert!(ok, "{extra:?}: {v}");
        v
    };
    // Without learning the base is sized to the batch, T/2 by default.
    assert_eq!(with(&["--no-learn"])["factor_base"]["orbits"], 20);
    assert_eq!(
        with(&["--orbits-per-target", "2", "--no-learn"])["factor_base"]["orbits"],
        80
    );
    let wide = with(&["--width", "2"]);
    assert_eq!(wide["factor_base"]["sizing"], "width");
    assert!(wide["factor_base"]["orbits"].as_u64().unwrap() > 200);
    let both = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["prime", "--width", "2", "--orbits-per-target", "1"])
        .output()
        .unwrap();
    assert!(!both.status.success());
}

#[test]
fn runs_are_reproducible() {
    let args = [
        "--type",
        "generic",
        "--bits",
        "20",
        "--targets",
        "3",
        "--seed",
        "5",
    ];
    let (_, a) = prime(&args);
    let (_, b) = prime(&args);
    for key in ["p", "a", "b", "subgroup_order"] {
        assert_eq!(a["instance"][key], b["instance"][key], "{key}");
    }
    assert_eq!(a["logs"]["oracle_ops"], b["logs"]["oracle_ops"]);
    assert_eq!(a["descent"]["total_ops"], b["descent"]["total_ops"]);
    assert_eq!(a["rho"]["mean_steps"], b["rho"]["mean_steps"]);
}

#[test]
fn the_semaev_reference_solver_cross_checks_both_prime_order_types() {
    for args in [
        vec!["--curve", "p192", "--bits", "14", "--solver", "semaev"],
        vec!["--curve", "secp256k1", "--bits", "14", "--solver", "semaev"],
        vec![
            "--type",
            "j0",
            "--bits",
            "14",
            "--solver",
            "semaev",
            "--eisenstein",
        ],
    ] {
        let (ok, v) = prime(&args);
        assert!(ok, "{args:?}: {v}");
        assert_eq!(v["status"], "complete");
        assert_eq!(v["solver"], "semaev");
        assert_eq!(v["result"]["verified"], true);
        assert_eq!(v["rho"]["solver"]["verified"], true);
    }
}

#[test]
fn impossible_requests_are_refused_with_a_reason() {
    for (args, needle) in [
        (
            vec!["--type", "j1728", "--solver", "semaev", "--bits", "14"],
            "2-torsion",
        ),
        (vec!["--curve", "ecc2k-130"], "not a built-in prime-field"),
        (vec!["--type", "j0", "--eisenstein"], "--eisenstein"),
        (vec!["--solver", "semaev", "--bits", "30"], "at most 24"),
        (
            vec!["--bits", "8", "--known-log", "100000"],
            "below the subgroup order",
        ),
    ] {
        let (ok, v) = prime(&args);
        assert!(!ok, "{args:?} was accepted: {v}");
        assert_eq!(v["status"], "error");
        let msg = v["message"].as_str().unwrap_or_default();
        assert!(msg.contains(needle), "{args:?}: {msg}");
    }
}
