#!/usr/bin/env python3
"""Audit the Q1415 matched N53 XOR-Gauss negative method gate."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

from run_probe import HERE, sha
from run_q1415_gauss_n53 import identity_hash
from build_q1415_stage_comparison import build as build_comparison


def main():
    protocol_path = HERE / "q1415_gauss_n53_protocol.json"
    parent_protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    parent_path = HERE / "runs/n53_q1410_ordinary.json"
    parent_stdout_path = HERE / "runs/n53_q1410_ordinary.attempt0.stdout.txt"
    formula_path = HERE / "runs/n53_q1410_ordinary.xcnf.gz"
    runtime_path = HERE / "q1415_sage_runtime_info.json"
    receipt_path = HERE / "runs/n53_q1415_gauss_ordinary.json"
    stdout_path = HERE / "runs/n53_q1415_gauss_ordinary.stdout.txt"
    stderr_path = HERE / "runs/n53_q1415_gauss_ordinary.stderr.txt"
    protocol = json.loads(protocol_path.read_text())
    parent_protocol = json.loads(parent_protocol_path.read_text())
    parent = json.loads(parent_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    stdout = stdout_path.read_text()
    assert protocol["proposal_id"] == receipt["proposal_id"] == "Q1415"
    assert protocol["candidate_id"] is receipt["candidate_id"] is None
    assert receipt["run_id"] is None and receipt["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(HERE / "run_q1415_gauss_n53.py")
    assert protocol["parent_protocol_sha256"] == sha(parent_protocol_path)
    assert protocol["parent_run_sha256"] == sha(parent_path)
    assert protocol["formula_archive_sha256"] == sha(formula_path)
    assert protocol["runtime_info_sha256"] == sha(runtime_path)
    assert protocol["solver_binary_sha256"] == sha(
        Path(shutil.which("cryptominisat5")))
    assert receipt["protocol_sha256"] == sha(protocol_path)
    assert receipt["runtime_info_sha256"] == sha(runtime_path)
    assert receipt["source_sha256"] == protocol["source_sha256"]
    assert receipt["solver_stdout_sha256"] == sha(stdout_path)
    assert receipt["solver_stderr_sha256"] == sha(stderr_path)
    assert receipt["formula_raw_sha256"] == parent["attempts"][0][
        "xcnf_sha256"]
    assert parent["attempts"][0]["solver_stdout_sha256"] == sha(
        parent_stdout_path)
    parent_stdout = parent_stdout_path.read_text()
    assert "212 x 8586" in parent_stdout
    assert "Using 0 matrices recovered" in parent_stdout
    assert "Too many columns in matrix: 8586" in parent_stdout
    digest = hashlib.sha256()
    size = 0
    with gzip.open(formula_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    assert digest.hexdigest() == protocol["formula_raw_sha256"]
    assert size == protocol["formula_raw_bytes"]
    for name in ("curve_id", "factor_base_actual_B",
                 "factor_base_folded_columns",
                 "factor_base_enumerated_set_sha256"):
        assert receipt[name] == protocol[name] == parent[name]
    assert receipt["workload_id"] == protocol["ordinary_workload_id"]
    assert receipt["same_ordinary_target_and_formula_as_q1410"] is True
    identity = receipt["stage_config_hash_input"]
    assert identity["factor_base"] == parent_protocol["factor_base"]
    assert identity["point_decomposition"]["solver_flags"] == protocol[
        "solver_flags"]
    full_digest = identity_hash(identity)
    assert receipt["stage_config_sha256_full"] == full_digest
    stage_id = f"PS1N53Ckb1fb24062PDP4sath{full_digest[:12]}"
    assert receipt["stage_config_id"] == stage_id
    assert receipt["stage_run_id"] == (
        f"{stage_id}W{receipt['workload_id']}R1")
    assert receipt["solver_status"] == "external_timeout"
    assert receipt["solver_return_code"] is None
    assert receipt["solver_wall_seconds_exploratory"] >= 120
    assert receipt["observed_verified_relation_count"] == 0
    assert receipt["complete_solve_work_log2"] is None
    assert receipt["gaussian_matrix_reported_active"] is True
    assert re.search(r"Using [1-9][0-9]* matrices recovered", stdout)
    assert not re.search(r"^s SATISFIABLE", stdout, re.MULTILINE)
    assert not re.search(r"^s UNSATISFIABLE", stdout, re.MULTILINE)
    comparison_path = HERE / "runs/n53_q1410_q1415_named_stage_comparison.json"
    comparison = json.loads(comparison_path.read_text())
    assert comparison == build_comparison()
    canonical = comparison["stage_profiles"][1]
    assert canonical["legacy_stage_config_id"] == stage_id
    assert canonical["legacy_stage_run_id"] == receipt["stage_run_id"]
    assert canonical["stage_config_id"] != stage_id
    assert canonical["stage_run_id"] == (
        f"{canonical['stage_config_id']}W{receipt['workload_id']}R1")
    print(json.dumps({"status": "PASS",
                      "canonical_stage_config_id": canonical["stage_config_id"],
                      "legacy_stage_config_id": stage_id,
                      "solver_status": receipt["solver_status"],
                      "matrix_active": True,
                      "verified_relations": 0}))


if __name__ == "__main__":
    main()
