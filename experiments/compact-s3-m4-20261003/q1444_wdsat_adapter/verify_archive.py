#!/usr/bin/env python3
"""Audit Q1444's frozen inputs and every bounded WDSat run receipt."""

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

from verify_factor_xcnf import audit


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(scratch=None):
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1444"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["challenge_run_admitted"] is False
    assert protocol["complete_n131_log2_work"] is None
    assert protocol["source_sha256"] == {
        name: sha(HERE / name) for name in protocol["source_sha256"]}
    assert protocol["sage_runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert protocol["solver_validation_sha256"] == sha(
        HERE / "solver_validation.json")
    validation = json.loads((HERE / "solver_validation.json").read_text())
    assert validation["status"] == "pass" and len(validation["cases"]) == 7
    for n in (53, 83):
        build = protocol["binaries"][str(n)]
        assert build["upstream_commit"] == protocol["wdsat_upstream_commit"]
        assert build["patch_sha256"] == protocol["wdsat_patch_sha256"]
        assert build["patch_sha256"] == sha(HERE / "wdsat_adapter.patch")
        if scratch:
            binary = scratch / f"n{n}_wdsat_build" / "wdsat_solver"
            assert sha(binary) == build["binary_sha256"]
    rows = {}
    for cell in protocol["run_order"]:
        frozen = protocol["cells"][cell]
        output = HERE / "runs" / cell
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1444"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["cell"] == cell
        assert receipt["curve_id"] == frozen["curve_id"]
        assert receipt["factor_base_actual_B"] == frozen[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == frozen["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == frozen[
            "factor_base_enumerated_set_sha256"]
        assert receipt["workload_id"] == frozen["workload_id"]
        assert receipt["ordinary_query"] == frozen["ordinary_query"]
        assert receipt["solver_binary_sha256"] == protocol["binaries"][frozen[
            "degree"]]["binary_sha256"]
        assert receipt["source_formula_gzip_sha256"] == frozen[
            "source_gzip_sha256"]
        source = REPO / frozen["source_formula"]
        assert sha(source) == frozen["source_gzip_sha256"]
        formula_archive = output / "system.factored.xcnf.gz"
        assert sha(formula_archive) == receipt["factored_formula_gzip_sha256"]
        raw = gzip.open(formula_archive, "rb").read()
        assert hashlib.sha256(raw).hexdigest() == frozen["factored_sha256"]
        assert receipt["factored_formula_raw_sha256"] == frozen[
            "factored_sha256"]
        assert audit(source, formula_archive) == frozen["audit"]
        if frozen["witness_informed_control"]:
            n = int(cell[1:3])
            control_model = (HERE.parent / "q1439_fixed_leaf" / "runs" /
                             f"n{n}_control" / "solver.stdout.txt")
            assert audit(source, formula_archive, control_model) == frozen[
                "known_control_model_audit"]
        stdout_path = output / "solver.stdout.txt"
        stderr_path = output / "solver.stderr.txt"
        assert sha(stdout_path) == receipt["solver_stdout_sha256"]
        assert sha(stderr_path) == receipt["solver_stderr_sha256"]
        checkpoints = [int(x) for x in re.findall(
            r"q1444_branch_counter=([0-9]+)",
            stderr_path.read_text(encoding="ascii"))]
        assert all(value % 65536 == 0 for value in checkpoints)
        assert checkpoints == sorted(set(checkpoints))
        assert max(checkpoints, default=0) == receipt[
            "branch_counter_checkpoint_lower_bound"]
        assert receipt["status"] == "external_timeout"
        assert receipt["return_code"] is None
        assert receipt["verified_relations"] == 0
        assert receipt["branch_counter_final"] is None
        assert receipt["model_check"] is None
        assert receipt["group_replay"] is None
        assert not (output / "model.bits.txt").exists()
        assert not stdout_path.read_text()
        assert receipt["solver_wall_seconds"] >= protocol["wall_cap_seconds"]
        assert receipt["solver_wall_seconds"] < protocol["wall_cap_seconds"] + 2
        assert receipt["child_peak_rss_raw"] > 0
        assert receipt["unisolated_host_exploratory"] is True
        assert receipt["complete_n131_log2_work"] is None
        rows[cell] = {
            "status": receipt["status"],
            "ordinary_query": receipt["ordinary_query"],
            "verified_relations": 0,
            "solver_wall_seconds": receipt["solver_wall_seconds"],
            "branch_counter_checkpoint_lower_bound": receipt[
                "branch_counter_checkpoint_lower_bound"],
            "peak_rss_raw": receipt["child_peak_rss_raw"],
            "peak_rss_unit": receipt["child_peak_rss_unit"],
            "receipt_sha256": sha(receipt_path),
        }
    assert len(rows) == 4
    return {
        "status": "passed",
        "proposal_id": "Q1444",
        "protocol_sha256": sha(protocol_path),
        "verifier_source_sha256": sha(HERE / "verify_archive.py"),
        "rows": rows,
        "ordinary_verified_relations": 0,
        "natural_relation_yield": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "scope": "Four 60-second censored solver-stage cells; no SAT model or curve relation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify(args.scratch)
    path = HERE / "verification.json"
    if args.emit:
        assert not path.exists(), "refuse to overwrite verification"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.check:
        assert json.loads(path.read_text()) == result
    print(json.dumps(result, sort_keys=True))
