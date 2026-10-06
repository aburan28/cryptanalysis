use serde_json::Value;
use std::{
    fs,
    path::PathBuf,
    process::Command,
    sync::atomic::{AtomicU64, Ordering},
};

static NEXT: AtomicU64 = AtomicU64::new(0);
fn directory() -> PathBuf {
    let path = std::env::temp_dir().join(format!(
        "ic-fixed-test-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&path).unwrap();
    path
}
fn run(path: &PathBuf, stage: &str, pairs: u32) -> (bool, Value) {
    let output = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["fixed", "--params"])
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("docs/ic/params/k0n9-fixed.json"))
        .arg("--dir")
        .arg(path)
        .args([
            "--stage",
            stage,
            "--pair-budget",
            &pairs.to_string(),
            "--attempts",
            "256",
            "--query-seconds",
            "2",
            "--json",
        ])
        .output()
        .unwrap();
    let report = serde_json::from_slice(&output.stdout)
        .unwrap_or_else(|_| panic!("{}", String::from_utf8_lossy(&output.stderr)));
    (output.status.success(), report)
}

#[test]
fn fixed_cli_preserves_incomplete_then_resumes_and_reuses() {
    let path = directory();
    let (success, partial) = run(&path, "pairs", 7);
    assert!(!success);
    assert_eq!(partial["status"], "pair_budget");
    let (success, complete) = run(&path, "all", 10000);
    assert!(success, "{complete}");
    assert_eq!(complete["status"], "complete");
    assert!(complete["targets"]
        .as_object()
        .unwrap()
        .values()
        .all(|v| v["verified"] == true));
    let (success, replay) = run(&path, "all", 0);
    assert!(success, "{replay}");
    assert!(replay["reuse"]["new_attempts"].is_null());
    assert!(replay["reuse"]["pair_candidates_built"].is_null());
    assert_eq!(replay["relations_saved"], complete["relations_saved"]);
    fs::remove_dir_all(path).unwrap();
}

#[test]
fn fixed_cli_reports_missing_interpreter() {
    let path = directory();
    let output = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args([
            "fixed",
            "--params",
            "unused.json",
            "--python",
            "/nonexistent/ic-python",
            "--dir",
        ])
        .arg(&path)
        .arg("--json")
        .output()
        .unwrap();
    assert!(!output.status.success());
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["status"], "error");
    assert!(report["message"]
        .as_str()
        .unwrap()
        .contains("could not run fixed workflow"));
    fs::remove_dir_all(path).unwrap();
}

#[test]
fn fixed_cli_routes_with_json_model_and_checks_missing_model() {
    let path = directory();
    let model = path.join("selector model.json");
    let mut domains = serde_json::Map::new();
    domains.insert(
        "b".repeat(64),
        serde_json::json!({
            "x_weight": [0, 9], "x_frobenius_distance": [0, 9],
            "rank_fraction": [0, 1], "direct_target": [0, 1]
        }),
    );
    fs::write(
        &model,
        serde_json::to_vec(&serde_json::json!({
            "format": "fixed-ic-selector-v1",
            "arms": {"pairs": 0.0, "sat-short": 0.1, "sat-medium": 0.5},
            "features": ["x_weight", "x_frobenius_distance", "rank_fraction", "direct_target"],
            "fallback": "pairs", "tree": {"arm": "sat-short"}, "domains": domains
        }))
        .unwrap(),
    )
    .unwrap();
    let mut command = Command::new(env!("CARGO_BIN_EXE_ca-ic"));
    command
        .args(["fixed", "--params"])
        .arg(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("docs/ic/params/k0n9-fixed.json"))
        .arg("--dir")
        .arg(path.join("campaign"))
        .args(["--solver", "learned", "--attempts", "256", "--json"]);
    let missing = command.output().unwrap();
    assert!(!missing.status.success());
    let error: Value = serde_json::from_slice(&missing.stdout).unwrap();
    assert!(error["message"]
        .as_str()
        .unwrap()
        .contains("selector-model"));
    let output = command
        .arg("--selector-model")
        .arg(&model)
        .output()
        .unwrap();
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(output.status.success(), "{report}");
    assert_eq!(report["status"], "complete");
    assert!(report["selector_model_sha256"].is_string());
    assert!(
        report["reuse"]["selector_reason_unseen_parameters_or_budget"]
            .as_u64()
            .unwrap()
            > 0
    );
    fs::remove_dir_all(path).unwrap();
}
