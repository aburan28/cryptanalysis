#!/usr/bin/env python3
"""Independent file, status and accounting audit for Q1494's frozen cells."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "archive_audit.json"
CASES = (
    ("control/r1", "n53_known_rotation_44", True),
    ("runs/n53_known_rotation_44", "n53_known_rotation_44", False),
    ("runs/n53_ordinary_rotation_0", "n53_ordinary_rotation_0", False),
    ("runs/n83_ordinary_rotation_0", "n83_ordinary_rotation_0", False),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_counter(stdout: str, name: str) -> str:
    pattern = re.compile(rf"^c {name}\s+:\s+(\S+)", re.MULTILINE)
    values = pattern.findall(stdout)
    assert values and len(set(values)) == 1, (name, values)
    return values[0]


def audit() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1494"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert sha(HERE / "design_protocol.json") == protocol["design_sha256"]
    assert sha(HERE / "run.py") == protocol["runner_source_sha256"]
    assert sha(HERE / "freeze_protocol.py") == protocol[
        "freezer_source_sha256"]
    assert protocol["degree_profiles"] == design["degree_profiles"]
    assert protocol["runs"] == design["runs"]
    profiles = {row["field_degree_n"]: row for row in design[
        "degree_profiles"]}
    summaries = []
    for folder, name, control in CASES:
        path = HERE / folder
        receipt = json.loads((path / "receipt.json").read_text())
        spec = design["runs"][name]
        profile = profiles[spec["degree_n"]]
        stdout = (path / "solver.stdout.txt").read_text()
        stderr = (path / "solver.stderr.txt").read_text()
        expected_status = "s SATISFIABLE" if control else "s INDETERMINATE"
        assert [line for line in stdout.splitlines() if line.startswith("s ")] == [
            expected_status]
        assert stderr == ""
        assert receipt["proposal_id"] == "Q1494"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["cell"] == name
        assert receipt["field_degree_n"] == spec["degree_n"]
        assert receipt["rotation"] == spec["rotation"]
        assert receipt["curve_id"] == profile["curve_id"]
        assert receipt["factor_base_actual_B"] == profile[
            "factor_base_actual_B"]
        assert receipt["factor_base_folded_columns_K"] == profile[
            "factor_base_folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == profile[
            "factor_base_enumerated_set_sha256"]
        assert receipt["parent_workload_id"] == profile[
            "parent_workload_id"]
        assert receipt["control_pins"] == (327 if control else 0)
        assert receipt["source_sha256"] == protocol[
            "runner_source_sha256"]
        assert receipt["protocol_sha256"] == sha(HERE / "protocol.json")
        assert receipt["design_sha256"] == protocol["design_sha256"]
        assert receipt["cms_binary_sha256"] == protocol[
            "input_sha256"]["cms_binary"]
        assert receipt["solver_stdout_sha256"] == sha(
            path / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(
            path / "solver.stderr.txt")
        assert receipt["charged_stage_ns"] == sum(receipt[
            "phase_ns"].values())
        assert all(value >= 0 for value in receipt["phase_ns"].values())
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        conflict = raw_counter(stdout, "conflicts")
        decisions = raw_counter(stdout, "decisions")
        propagations = raw_counter(stdout, "propagations")
        assert conflict.isdecimal() and decisions.isdecimal()
        assert receipt["solver_counters"]["conflicts"] == int(conflict)
        assert receipt["solver_counters"]["decisions"] == int(decisions)
        if propagations.isdecimal():
            assert receipt["solver_counters"]["propagations"] == int(
                propagations)
        else:
            # CMS prints a rounded K/M display. Preserve the raw token;
            # the runner's expanded integer is only an approximation.
            assert re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[KM]", propagations)
        assert receipt["full_xcnf_xor_rows"] > 0
        if control:
            assert receipt["status"] == "verified_relation"
            assert receipt["native_status"] == "sat"
            assert receipt["verified_relation"]["status"] == (
                "verified_four_point_relation")
            assert receipt["verified_relation"]["distinct_columns"] == 4
            assert receipt["verified_relation"][
                "transported_original_target"] == receipt[
                    "original_public_target"]
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
        else:
            assert receipt["status"] == receipt["native_status"] == (
                "censored")
            assert receipt["verified_relation"] is None
            assert receipt["successful_unpinned_stage_ns_exploratory"] is None
            assert receipt["natural_relation_yield_estimate"] is None
        summaries.append({
            "folder": folder,
            "cell": name,
            "control": control,
            "status": receipt["status"],
            "receipt_sha256": sha(path / "receipt.json"),
            "full_xcnf_sha256": receipt["full_xcnf_sha256"],
            "full_xcnf_variables": receipt["full_xcnf_variables"],
            "full_xcnf_clauses": receipt["full_xcnf_clauses"],
            "full_xcnf_xor_rows": receipt["full_xcnf_xor_rows"],
            "charged_stage_ns": receipt["charged_stage_ns"],
            "conflicts_exact": int(conflict),
            "decisions_exact": int(decisions),
            "propagations_display": propagations,
            "propagations_display_rounded": not propagations.isdecimal(),
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        })
    assert [row["cell"] for row in summaries[1:]] == design["run_order"]
    return {
        "kind": "q1494_independent_file_status_accounting_audit",
        "proposal_id": "Q1494",
        "status": "PASS",
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "cases": summaries,
        "ordinary_unpinned_verified_relations": 0,
        "successful_n83_pdp_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "propagation_count_note": (
            "CryptoMiniSat K/M displays are rounded; raw display tokens are "
            "preserved and must not be treated as exact operation counts."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.check:
        assert json.loads(ARCHIVE.read_text()) == result
        print("Q1494 independent accounting audit PASS (archived)")
    else:
        assert not ARCHIVE.exists(), "refusing to replace audit"
        ARCHIVE.write_text(json.dumps(result, indent=2,
                                      sort_keys=True) + "\n")
        print("Q1494 independent accounting audit written")


if __name__ == "__main__":
    main()
