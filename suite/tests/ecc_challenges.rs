//! Inspector check of one published challenge file.

use std::path::PathBuf;
use std::process::Command;

use serde_json::Value;

fn corpus() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../challenges/ecc")
}

#[test]
fn inspector_accepts_a_small_koblitz_challenge() {
    let path = corpus().join("inspect/f2-koblitz-a1-m7.json");
    let output = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["inspect", "--file", path.to_str().unwrap(), "--json"])
        .output()
        .expect("run ca-ic");
    let report: Value = serde_json::from_slice(&output.stdout).unwrap_or_else(|_| {
        panic!(
            "not JSON\nstdout: {}\nstderr: {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        )
    });
    assert!(
        output.status.success(),
        "inspect failed: {}",
        serde_json::to_string_pretty(&report).unwrap()
    );
    assert_eq!(report["status"], "checks_passed");
}

#[test]
fn inspector_accepts_a_small_prime_field_challenge() {
    let catalog: Value = serde_json::from_str(
        &std::fs::read_to_string(corpus().join("catalog.json")).expect("catalog"),
    )
    .expect("catalog json");
    let id = catalog["curves"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| {
            c["inspect"] == true
                && c["field_type"] == "prime"
                && c["cardinality_bits"].as_u64().unwrap_or(999) <= 24
                && c["tier"] == "check"
        })
        .map(|c| c["id"].as_str().unwrap().to_string())
        .expect("a small prime-field inspect file");
    let path = corpus().join(format!("inspect/{id}.json"));
    let output = Command::new(env!("CARGO_BIN_EXE_ca-ic"))
        .args(["inspect", "--file", path.to_str().unwrap(), "--json"])
        .output()
        .expect("run ca-ic");
    let report: Value = serde_json::from_slice(&output.stdout).expect("json");
    assert!(
        output.status.success(),
        "{} inspect failed: {}",
        id,
        serde_json::to_string_pretty(&report).unwrap()
    );
    assert_eq!(report["status"], "checks_passed");
}
