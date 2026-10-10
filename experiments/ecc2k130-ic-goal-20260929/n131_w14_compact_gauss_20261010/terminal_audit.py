#!/usr/bin/env python3
"""Audit the Gaussian preflight and full run against the frozen XCNF."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_compact_columns_20261010"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def last_conflicts(path):
    lines = [line for line in Path(path).read_text(errors="replace").splitlines()
             if line.startswith("c rst ")]
    return lines[-1].split()[6] if lines else None


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    preflight = json.loads((HERE / "preflight/result.json").read_text())
    full = json.loads((HERE / "full/result.json").read_text())
    baseline = json.loads((SOURCE / "public_query/result.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_MODERATE_GAUSS_COMPONENT_PREFLIGHT"
    assert protocol["target_q"] == preflight["target_q"] == full["target_q"] == baseline["target_q"]
    assert protocol["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert protocol["source_sha256"]["compact_formula_gzip"] == sha(
        SOURCE / "public_query/system.xcnf.gz")
    assert preflight["source_sha256"]["protocol"] == full["source_sha256"]["protocol"] == sha(
        HERE / "protocol.json")
    assert preflight["gaussian_matrix_admitted"] and full["gaussian_matrix_admitted"]
    assert preflight["status"] == "CENSORED_TIME"
    assert 5 in preflight["gaussian_matrices_used_observations"]
    assert 5 in full["gaussian_matrices_used_observations"]
    assert preflight["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert full["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    assert full["solver_wall_seconds"] <= protocol["full_solver_wall_cap_seconds"] + 1
    assert protocol["prior_formula_build_seconds"] + full["solver_wall_seconds"] <= 600
    assert full["status"] in ("CENSORED_TIME", "SAT_MODEL_PENDING_CHECK", "UNSAT_FORMULA")
    if full["status"] == "CENSORED_TIME":
        assert full["solver_status_lines"] == [] and full["model_lines"] == 0
    assert preflight["source_sha256"]["stdout"] == sha(HERE / "preflight/solver.stdout.txt")
    assert full["source_sha256"]["stdout"] == sha(HERE / "full/solver.stdout.txt")
    assert full["source_sha256"]["stderr"] == sha(HERE / "full/solver.stderr.txt")
    digest = hashlib.sha256()
    size = 0
    with gzip.open(SOURCE / "public_query/system.xcnf.gz", "rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
            size += len(block)
    assert digest.hexdigest() == protocol["input_formula_uncompressed_sha256"]
    assert size == protocol["input_formula_uncompressed_bytes"]
    receipt = {
        "status": "PASS_N131_GAUSSIAN_GATE_TERMINAL_AUDIT",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "target_q": protocol["target_q"],
        "same_formula_uncompressed_sha256": digest.hexdigest(),
        "preflight_status": preflight["status"], "full_status": full["status"],
        "preflight_matrices_used": preflight["gaussian_matrices_used_observations"],
        "full_matrices_used": full["gaussian_matrices_used_observations"],
        "last_logged_conflicts": {
            "zero_matrix_baseline": last_conflicts(SOURCE / "public_query/solver.stdout.txt"),
            "gaussian_full": last_conflicts(HERE / "full/solver.stdout.txt")},
        "solver_wall_seconds": full["solver_wall_seconds"],
        "prior_formula_build_seconds": protocol["prior_formula_build_seconds"],
        "sampled_peak_rss_bytes": full["sampled_peak_combined_rss_bytes"],
        "source_sha256": {name: sha(path) for name,path in {
            "script": __file__, "protocol": HERE / "protocol.json",
            "preflight_result": HERE / "preflight/result.json",
            "full_result": HERE / "full/result.json",
            "full_stdout": HERE / "full/solver.stdout.txt",
            "full_stderr": HERE / "full/solver.stderr.txt",
            "compact_formula_gzip": SOURCE / "public_query/system.xcnf.gz",
        }.items()},
    }
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "full_status": full["status"],
                      "last_logged_conflicts": receipt["last_logged_conflicts"]}))


if __name__ == "__main__":
    main()
