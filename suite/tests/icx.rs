//! Integration tests for the `icx` binary: they run the actual executable
//! across the whole standardized-curve catalog, which is the completion
//! criterion for the engine ("you can run this against every curve").

use std::process::Command;

fn icx() -> Command {
    Command::new(env!("CARGO_BIN_EXE_ca-icx"))
}

/// Parse the top-level JSON object printed by an `icx --json` invocation.
fn run_json(args: &[&str]) -> serde_json::Value {
    let out = icx().args(args).arg("--json").output().expect("run icx");
    assert!(
        out.status.success(),
        "icx {:?} exited with failure: {}",
        args,
        String::from_utf8_lossy(&out.stderr)
    );
    serde_json::from_slice(&out.stdout)
        .unwrap_or_else(|e| panic!("icx {args:?} did not print valid JSON: {e}"))
}

#[test]
fn list_reports_every_family() {
    let v = run_json(&["list"]);
    assert_eq!(v["operation"], "list");
    let curves = v["curves"].as_array().expect("curves array");
    assert!(
        curves.len() >= 35,
        "catalog unexpectedly small: {}",
        curves.len()
    );
    // Every named field family is represented.
    let families: std::collections::HashSet<&str> =
        curves.iter().filter_map(|c| c["family"].as_str()).collect();
    for fam in ["prime", "binary", "koblitz"] {
        assert!(families.contains(fam), "family {fam} missing from listing");
    }
    // A provenance block records the dispatched field backend.
    assert!(v["software"]["field_backend"].is_string());
}

#[test]
fn inspect_verifies_every_catalog_curve() {
    // The load-bearing gate: run `icx inspect` on EVERY curve the catalog
    // lists, and require each to verify. This is what "run icx against every
    // standardized curve" means for the inspect front door.
    let list = run_json(&["list"]);
    let curves = list["curves"].as_array().unwrap().clone();
    assert!(!curves.is_empty());
    let mut checked = 0;
    for c in &curves {
        let name = c["name"].as_str().unwrap();
        let rep = run_json(&["inspect", name]);
        assert_eq!(
            rep["status"], "checks_passed",
            "curve {name} failed inspect"
        );
        assert_eq!(rep["verified"], true, "curve {name} not verified");
        checked += 1;
    }
    assert!(checked >= 35, "only {checked} curves checked");
}

#[test]
fn estimate_labels_prime_as_not_ic_relevant() {
    let v = run_json(&["estimate", "p256"]);
    assert_eq!(v["index_calculus"]["relevant"], false);
    // ~128-bit generic security.
    let sec = v["generic_attack"]["security_bits"].as_f64().unwrap();
    assert!((120.0..132.0).contains(&sec), "p256 security {sec}");
}

#[test]
fn estimate_labels_koblitz_as_ic_relevant() {
    let v = run_json(&["estimate", "sect163k1"]);
    assert_eq!(v["index_calculus"]["relevant"], true);
    assert_eq!(v["family"], "koblitz");
}

#[test]
fn aliases_resolve() {
    // NIST/SEC aliases must map to the canonical curve.
    for (alias, canonical) in [("nistp256", "p256"), ("k-163", "sect163k1")] {
        let v = run_json(&["inspect", alias]);
        assert_eq!(v["curve"]["name"], canonical, "alias {alias}");
    }
}

#[test]
fn unknown_curve_errors_cleanly() {
    let out = icx().args(["inspect", "no-such-curve"]).output().unwrap();
    assert!(!out.status.success());
}

#[test]
fn fes_cpu_backend_solves() {
    // The in-process CPU FES backend recovers the planted solution.
    let v = run_json(&[
        "fes",
        "--n",
        "16",
        "--m",
        "20",
        "--seed",
        "1",
        "--backend",
        "cpu",
    ]);
    assert_eq!(v["operation"], "fes");
    assert_eq!(v["backend"], "cpu");
    assert_eq!(
        v["planted_found"], true,
        "cpu FES missed the planted solution"
    );
}

#[test]
fn fes_worker_path_when_available() {
    // When a worker executable is provided (CI builds the host-emulation worker
    // and sets ICX_FES_WORKER; a GPU machine would point this at fes_cuda /
    // fes_metal), the binary drives it as a subprocess, re-verifies, and finds
    // the planted solution. Skipped where no worker is configured.
    let worker = match std::env::var("ICX_FES_WORKER") {
        Ok(w) if std::path::Path::new(&w).is_file() => w,
        _ => {
            eprintln!("no ICX_FES_WORKER configured; skipping worker-path test");
            return;
        }
    };
    let v = run_json(&[
        "fes",
        "--n",
        "18",
        "--m",
        "20",
        "--seed",
        "1",
        "--backend",
        "gpu",
    ]);
    assert_eq!(
        v["planted_found"], true,
        "worker FES missed the planted solution"
    );
    assert_ne!(v["backend"], "cpu", "expected the worker backend, got cpu");
    assert!(v["backend"].as_str().unwrap().contains(
        std::path::Path::new(&worker)
            .file_name()
            .unwrap()
            .to_str()
            .unwrap()
    ));
    // The worker's proposals must all verify (a worker can only propose).
    assert_eq!(v["verified"], v["solutions"]);
}

#[test]
fn run_koblitz_analogue_recovers_a_logarithm() {
    // `icx run` on a Koblitz curve executes a small same-family analogue and
    // must recover a verified logarithm, labelled as scaled.
    let v = run_json(&["run", "sect163k1", "--degree", "13", "--rho-runs", "0"]);
    assert_eq!(v["operation"], "run");
    assert_eq!(v["verified"], true, "koblitz analogue did not verify");
    assert_eq!(v["result"]["analogue"]["family"], "koblitz");
    assert_eq!(v["result"]["analogue"]["is_named_curve"], false);
    assert!(v["result"]["extrapolation_note"].is_string());
}

#[test]
fn run_prime_analogue_recovers_a_logarithm() {
    let v = run_json(&["run", "p256", "--bits", "14", "--rho-runs", "0"]);
    assert_eq!(v["verified"], true, "prime analogue did not verify");
    assert_eq!(v["result"]["ic_relevant"], false);
}

#[test]
fn char3_curves_are_present_and_verify() {
    // Characteristic-three coverage: the catalog carries verified F_3^m curves.
    let list = run_json(&["list", "--family", "char3"]);
    let curves = list["curves"].as_array().expect("curves");
    assert!(
        !curves.is_empty(),
        "no characteristic-three curves in catalog"
    );
    let name = curves[0]["name"].as_str().unwrap();
    let rep = run_json(&["inspect", name]);
    assert_eq!(
        rep["status"], "checks_passed",
        "char3 curve {name} failed inspect"
    );
    assert_eq!(rep["verified"], true);
    assert_eq!(rep["curve"]["family"], "char3");
    // Estimate works; the runnable pipeline is not available for char-3 yet.
    let est = run_json(&["estimate", name]);
    assert_eq!(est["family"], "char3");
}

#[test]
fn run_with_gray_code_fes_solver() {
    // The Gray-code FES solver plugs into the descent-algebraic oracle.
    let v = run_json(&[
        "run",
        "sect163k1",
        "--degree",
        "11",
        "--oracle",
        "descent-algebraic",
        "--solver",
        "fes-f2",
        "--rho-runs",
        "0",
    ]);
    assert_eq!(v["verified"], true, "FES-solved analogue did not verify");
}
