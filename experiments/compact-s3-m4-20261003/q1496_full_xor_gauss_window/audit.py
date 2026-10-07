#!/usr/bin/env python3
"""Independent Q1496 receipt, matched-formula and Gauss-activation audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1494_full_xor_window_s3"
ARCHIVE = HERE / "archive_audit.json"
CASES = (
    ("control/r1", "n53_known_rotation_44", True),
    ("runs/n53_known_rotation_44", "n53_known_rotation_44", False),
    ("runs/n53_ordinary_rotation_0", "n53_ordinary_rotation_0", False),
    ("runs/n83_ordinary_rotation_0", "n83_ordinary_rotation_0", False),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counter(stdout: str, name: str) -> str:
    found = re.findall(rf"^c {name}\s*:\s*(\S+)", stdout, re.MULTILINE)
    assert found and len(set(found)) == 1, (name, found)
    return found[-1]


def audit() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1496"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert sha(HERE / "design_protocol.json") == protocol["design_sha256"]
    assert sha(HERE / "run.py") == protocol["runner_source_sha256"]
    assert sha(HERE / "freeze_protocol.py") == protocol[
        "freezer_source_sha256"]
    assert design["runs"] == protocol["runs"]
    profiles = {item["field_degree_n"]: item for item in design[
        "degree_profiles"]}
    summaries = []
    for folder, cell, control in CASES:
        path = HERE / folder
        receipt = json.loads((path / "receipt.json").read_text())
        parent_path = PARENT / folder / "receipt.json"
        parent = json.loads(parent_path.read_text())
        stdout = (path / "solver.stdout.txt").read_text()
        stderr = (path / "solver.stderr.txt").read_text()
        spec = design["runs"][cell]
        profile = profiles[spec["degree_n"]]
        assert receipt["proposal_id"] == "Q1496"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["cell"] == cell
        assert receipt["curve_id"] == profile["curve_id"]
        assert receipt["factor_base_actual_B"] == profile[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns_K"] == profile[
            "factor_base_folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == profile[
            "factor_base_enumerated_set_sha256"]
        assert receipt["parent_workload_id"] == profile["parent_workload_id"]
        assert receipt["rotation"] == spec["rotation"]
        assert receipt["original_public_target"] == parent[
            "original_public_target"]
        assert receipt["rotated_public_target"] == parent[
            "rotated_public_target"]
        assert receipt["full_xcnf_sha256"] == parent[
            "full_xcnf_sha256"]
        assert receipt["full_xcnf_bytes"] == parent["full_xcnf_bytes"]
        assert receipt["full_xcnf_variables"] == parent[
            "full_xcnf_variables"]
        assert receipt["full_xcnf_clauses"] == parent[
            "full_xcnf_clauses"]
        assert receipt["full_xcnf_xor_rows"] == parent[
            "full_xcnf_xor_rows"]
        assert receipt["control_pins"] == (327 if control else 0)
        assert receipt["source_sha256"] == protocol["runner_source_sha256"]
        assert receipt["design_sha256"] == protocol["design_sha256"]
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["cms_binary_sha256"] == protocol[
            "input_sha256"]["cms_binary"]
        assert receipt["solver_stdout_sha256"] == sha(
            path / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            path / "solver.stderr.txt")
        assert stderr == ""
        assert receipt["charged_stage_ns"] == sum(receipt[
            "phase_ns"].values())
        assert all(value >= 0 for value in receipt["phase_ns"].values())
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        assert receipt["solver_command_options"] == protocol[
            "cms_command_options_control" if control else
            "cms_command_options_ordinary"]
        displays = {name: counter(stdout, name) for name in
                    ("conflicts", "decisions", "propagations", "restarts")}
        assert displays == receipt["solver_counter_display"]
        for name in ("conflicts", "decisions", "restarts"):
            assert displays[name].isdecimal()
            assert receipt["solver_counters"][name] == int(displays[name])
        matrix_counts = [int(item) for item in re.findall(
            r"\[matrix\] Using (\d+) matrices recovered from", stdout)]
        assert receipt["matrix_log"]["matrix_initializations"] == len(
            matrix_counts)
        if control:
            assert [line for line in stdout.splitlines() if line.startswith(
                "s ")] == ["s SATISFIABLE"]
            assert receipt["status"] == "verified_relation"
            assert receipt["verified_relation"]["distinct_columns"] == 4
            assert receipt["verified_relation"][
                "transported_original_target"] == receipt[
                    "original_public_target"]
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
        else:
            assert [line for line in stdout.splitlines() if line.startswith(
                "s ")] == ["s INDETERMINATE"]
            assert receipt["status"] == receipt["native_status"] == (
                "censored")
            assert receipt["verified_relation"] is None
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
            assert matrix_counts and matrix_counts[0] >= 3
            assert receipt["matrix_log"]["too_many_columns_messages"] == 0
            assert "Too many columns in matrix" not in stdout
            expected_large = 8586 if spec["degree_n"] == 53 else 20916
            assert receipt["matrix_log"][
                "maximum_good_matrix_columns"] >= expected_large
        gaussian_sizes = [[int(i), int(rows), int(columns)] for i, rows,
                          columns in re.findall(
                              r"^c \[g (\d+)\] size:\s*(\d+)\s*x\s*(\d+)",
                              stdout, re.MULTILINE)]
        if not control:
            assert any(columns >= expected_large for _, _, columns in
                       gaussian_sizes)
        summaries.append({
            "folder": folder,
            "cell": cell,
            "control": control,
            "status": receipt["status"],
            "receipt_sha256": sha(path / "receipt.json"),
            "parent_receipt_sha256": sha(parent_path),
            "matched_full_xcnf_sha256": receipt["full_xcnf_sha256"],
            "charged_stage_ns": receipt["charged_stage_ns"],
            "parent_charged_stage_ns": parent["charged_stage_ns"],
            "exact_conflicts": int(displays["conflicts"]),
            "parent_exact_conflicts": parent["solver_counters"]["conflicts"],
            "exact_decisions": int(displays["decisions"]),
            "propagations_display": displays["propagations"],
            "propagations_display_rounded": not displays[
                "propagations"].isdecimal(),
            "initial_gaussian_matrices": matrix_counts[0] if matrix_counts
                else None,
            "maximum_accepted_matrix_columns": receipt["matrix_log"][
                "maximum_good_matrix_columns"],
            "final_gaussian_matrix_sizes": gaussian_sizes,
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        })
    assert [row["cell"] for row in summaries[1:]] == design["run_order"]
    return {
        "kind": "q1496_independent_matched_gauss_accounting_audit",
        "proposal_id": "Q1496", "status": "PASS",
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "cases": summaries,
        "ordinary_unpinned_verified_relations": 0,
        "successful_n83_pdp_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "note": "K/M propagation displays are rounded and are not exact operation counts.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.check:
        assert json.loads(ARCHIVE.read_text()) == result
        print("Q1496 independent matched-Gauss audit PASS (archived)")
    else:
        assert not ARCHIVE.exists(), "refusing to replace audit"
        ARCHIVE.write_text(json.dumps(result, indent=2,
                                      sort_keys=True) + "\n")
        print("Q1496 independent matched-Gauss audit written")


if __name__ == "__main__":
    main()
