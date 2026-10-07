#!/usr/bin/env python3
"""Independent Q1498 exact-formula, Gaussian activity and accounting audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q1497_karatsuba_poly_xcnf"
ARCHIVE = HERE / "archive_audit.json"
CASES = (
    ("control/n53_r1", "n53_known_rotation_44", True),
    ("control/n83_r1", "n83_planted_rotation_0", True),
    ("runs/n53_known_rotation_44", "n53_known_rotation_44", False),
    ("runs/n53_ordinary_rotation_0", "n53_ordinary_rotation_0", False),
    ("runs/n83_planted_rotation_0", "n83_planted_rotation_0", False),
    ("runs/n83_ordinary_rotation_0", "n83_ordinary_rotation_0", False),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_counter(stdout: str, name: str) -> str:
    found = re.findall(rf"^c {name}\s*:\s*(\S+)", stdout, re.MULTILINE)
    assert found and len(set(found)) == 1, (name, found)
    return found[-1]


def gauss_footer(stdout: str) -> list[dict]:
    checks = {int(index): token for index, token in re.findall(
        r"^c \[g (\d+)\] truth-find prop checks\s*:\s*(\S+)",
        stdout, re.MULTILINE)}
    sizes = [(int(index), int(rows), int(columns))
             for index, rows, columns in re.findall(
                 r"^c \[g (\d+)\] size:\s*(\d+)\s*x\s*(\d+)",
                 stdout, re.MULTILINE)]
    assert set(checks) == {index for index, _, _ in sizes}
    return [{"matrix_index": index, "rows": rows, "columns": columns,
             "truth_find_checks_display": checks[index]}
            for index, rows, columns in sizes]


def audit() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1498"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert sha(HERE / "design_protocol.json") == protocol["design_sha256"]
    assert sha(HERE / "run.py") == protocol["runner_source_sha256"]
    assert sha(HERE / "freeze_protocol.py") == protocol[
        "freezer_source_sha256"]
    assert design["degree_profiles"] == protocol["degree_profiles"]
    assert design["runs"] == protocol["runs"]
    profiles = {row["field_degree_n"]: row for row in design[
        "degree_profiles"]}
    summaries = []
    for folder, cell, control in CASES:
        path = HERE / folder
        parent_path = PARENT / folder / "receipt.json"
        receipt = json.loads((path / "receipt.json").read_text())
        parent = json.loads(parent_path.read_text())
        spec = design["runs"][cell]
        profile = profiles[spec["degree_n"]]
        stdout = (path / "solver.stdout.txt").read_text()
        assert (path / "solver.stderr.txt").read_text() == ""
        assert receipt["proposal_id"] == "Q1498"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["cell"] == cell
        assert receipt["target_role"] == spec["target_role"]
        assert receipt["curve_id"] == profile["curve_id"]
        assert receipt["factor_base_actual_B"] == profile[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns_K"] == profile[
            "factor_base_folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == profile[
            "factor_base_enumerated_set_sha256"]
        assert receipt["parent_workload_id"] == parent[
            "parent_workload_id"]
        assert receipt["rotation"] == parent["rotation"]
        assert receipt["control_pins"] == parent["control_pins"]
        assert receipt["original_public_target"] == parent[
            "original_public_target"]
        assert receipt["rotated_public_target"] == parent[
            "rotated_public_target"]
        assert receipt["full_xcnf_sha256"] == parent[
            "full_xcnf_sha256"]
        for name in ("full_xcnf_bytes", "full_xcnf_variables",
                     "full_xcnf_clauses", "full_xcnf_xor_rows", "and_gates"):
            assert receipt[name] == parent[name]
        assert receipt["source_sha256"] == protocol["runner_source_sha256"]
        assert receipt["design_sha256"] == protocol["design_sha256"]
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["cms_binary_sha256"] == protocol[
            "input_sha256"]["cms_binary"]
        assert receipt["solver_stdout_sha256"] == sha(
            path / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            path / "solver.stderr.txt")
        assert receipt["charged_stage_ns"] == sum(receipt[
            "phase_ns"].values())
        assert all(value >= 0 for value in receipt["phase_ns"].values())
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        assert receipt["solver_command_options"] == protocol[
            "cms_command_options_control" if control else
            "cms_command_options_ordinary"]
        old = parent["solver_command_options"]
        new = receipt["solver_command_options"]
        assert len(old) == len(new)
        assert [(a, b) for a, b in zip(old, new) if a != b] == [(
            "512", "16384")]
        displays = {name: raw_counter(stdout, name) for name in
                    ("conflicts", "decisions", "propagations", "restarts")}
        assert displays == receipt["solver_counter_display"]
        for name in ("conflicts", "decisions", "restarts"):
            assert displays[name].isdecimal()
            assert receipt["solver_counters"][name] == int(displays[name])
        statuses = [line for line in stdout.splitlines() if line.startswith(
            "s ")]
        footer = gauss_footer(stdout)
        if control:
            assert statuses == ["s SATISFIABLE"]
            assert receipt["status"] == "verified_relation"
            assert receipt["verified_relation"]["distinct_columns"] == 4
            assert receipt["verified_relation"][
                "transported_original_target"] == receipt[
                    "original_public_target"]
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
        else:
            assert statuses == ["s INDETERMINATE"]
            assert receipt["status"] == receipt["native_status"] == (
                "censored")
            assert receipt["verified_relation"] is None
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
            assert receipt["matrix_log"]["initial_matrix_count"] >= 6
            assert receipt["matrix_log"]["too_many_rows_messages"] == 0
            assert receipt["matrix_log"]["too_many_columns_messages"] == 0
            threshold = 3900 if spec["degree_n"] == 53 else 12000
            assert any(row["rows"] >= threshold and row[
                "truth_find_checks_display"] != "0" for row in footer)
        summaries.append({
            "folder": folder, "cell": cell, "control": control,
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
            "initial_gaussian_matrices": receipt["matrix_log"][
                "initial_matrix_count"],
            "largest_accepted_matrix_columns": receipt["matrix_log"][
                "maximum_good_matrix_columns"],
            "gaussian_footer": footer,
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        })
    assert [row["cell"] for row in summaries[2:]] == design["run_order"]
    return {
        "kind": "q1498_independent_matched_gauss_activity_audit",
        "proposal_id": "Q1498", "status": "PASS",
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "cases": summaries,
        "ordinary_unpinned_verified_relations": 0,
        "successful_n83_pdp_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "note": "K/M solver displays are rounded, not exact operation counts.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.check:
        assert json.loads(ARCHIVE.read_text()) == result
        print("Q1498 independent matched-Gauss audit PASS (archived)")
    else:
        assert not ARCHIVE.exists(), "refusing to replace audit"
        ARCHIVE.write_text(json.dumps(result, indent=2,
                                      sort_keys=True) + "\n")
        print("Q1498 independent matched-Gauss audit written")


if __name__ == "__main__":
    main()
