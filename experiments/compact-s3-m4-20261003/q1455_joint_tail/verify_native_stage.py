#!/usr/bin/env python3
"""Independent archive, clause-soundness, and relation audit for Q1455."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, join  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

PROTOCOL = HERE / "native_protocol.json"
OUTPUT = HERE / "native_verification.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_row(name: str, cell: dict, protocol: dict) -> dict:
    run = HERE / "runs" / name
    receipt_path = run / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    raw, varmap, targets, formula, meta, variables, clauses = make_case(name)
    assert receipt["proposal_id"] == "Q1455"
    assert receipt["candidate_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["case"] == name
    assert receipt["workload_id"] == cell["workload_id"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == sha(
        HERE / "run_native_stage.py")
    assert receipt["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert receipt["solver_binary_sha256"] == sha(
        HERE / "native_joint_solver") == protocol["native_binary_sha256"]
    assert receipt["cnf_raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["cnf_raw_sha256"] == cell["cnf_sha256"]
    assert receipt["cnf_raw_bytes"] == len(raw) == cell["cnf_bytes"]
    assert receipt["cnf_archive_sha256"] == sha(run / "system.cnf.gz")
    assert gzip.decompress((run / "system.cnf.gz").read_bytes()) == raw
    assert receipt["variable_map_sha256"] == sha(run / "variables.txt")
    assert (run / "variables.txt").read_bytes() == varmap
    assert receipt["target_input_sha256"] == sha(run / "targets.txt")
    assert (run / "targets.txt").read_bytes() == targets
    assert receipt["cnf_variables"] == variables
    assert receipt["cnf_clauses"] == clauses
    assert receipt["solver_stdout_sha256"] == sha(run / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(run / "solver.stderr.txt")
    assert receipt["solver_model_sha256"] == (
        sha(run / "solver.model.txt") if
        (run / "solver.model.txt").exists() else None)
    phases = ("formula_build_wall_ns_exploratory",
              "input_materialize_wall_ns_exploratory",
              "solver_process_wall_ns_exploratory",
              "recovery_check_wall_ns_exploratory",
              "other_online_wall_ns_exploratory")
    assert sum(receipt[key] for key in phases) == receipt[
        "online_stage_wall_ns_exploratory"]
    report = receipt["solver_report"]
    if report is not None:
        assert report == json.loads((run / "solver.stdout.txt").read_text())
        assert report["cnf_variables"] == variables
        assert report["cnf_clauses"] == clauses
        assert report["pair_cap"] == cell["pair_candidate_cap"]
        assert report["joint_eligible_checks"] == (
            report["joint_no_chain_rejections"] +
            report["joint_x_only_hits"])
        assert report["joint_pair0_root_calls"] <= (
            report["joint_eligible_checks"] * cell["pair_candidate_cap"])
        assert report["joint_pair1_root_calls"] <= (
            report["joint_eligible_checks"] * cell["pair_candidate_cap"])
        target_values = [int(line, 16) for line in
                         targets.decode().splitlines()[1:]]
        onb = field.Onb(cell["degree_n"])
        checked_rejections = checked_hits = 0
        for expected, key in (("no_chain", "joint_rejection_snapshots"),
                              ("x_only_witness", "joint_hit_snapshots")):
            snapshots = report[key]
            assert len(snapshots) <= 16
            for snapshot in snapshots:
                leaves = tuple(PartialLeaf(int(mask, 16), int(ones, 16))
                               for mask, ones in zip(
                                   snapshot["leaf_fixed_mask_onb_hex"],
                                   snapshot["leaf_ones_onb_hex"]))
                outcome = join(onb, leaves, target_values[
                    snapshot["target_preimage_index"]],
                    cell["normal_basis_weight_bound"],
                    cell["pair_candidate_cap"])
                assert outcome["status"] == expected, (name, outcome)
                assert outcome["pair_candidate_counts"] == snapshot[
                    "pair_candidate_counts"]
                if expected == "no_chain":
                    checked_rejections += 1
                else:
                    checked_hits += 1
        assert checked_rejections <= report["joint_no_chain_rejections"]
        assert checked_hits <= report["joint_x_only_hits"]
    else:
        checked_rejections = checked_hits = 0
        assert receipt["solver_status"] in ("external_timeout", "error")
    if receipt["solver_status"] == "sat":
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses,
            run / "solver.model.txt", parent["instances"][
                str(cell["degree_n"])])
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["verified_relation_count"] == 0
    return {"case": name, "input_role": cell["input_role"],
            "degree_n": cell["degree_n"],
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "solver_status": receipt["solver_status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "joint_eligible_checks": (report or {}).get(
                "joint_eligible_checks"),
            "joint_no_chain_rejections": (report or {}).get(
                "joint_no_chain_rejections"),
            "sampled_rejections_independently_checked": checked_rejections,
            "sampled_hits_independently_checked": checked_hits,
            "online_stage_wall_ns_exploratory": receipt[
                "online_stage_wall_ns_exploratory"],
            "field_mul_calls": (report or {}).get("field_mul_calls"),
            "field_sqr_calls": (report or {}).get("field_sqr_calls"),
            "field_inv_calls": (report or {}).get("field_inv_calls"),
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1455"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["parent_control_protocol_sha256"] == sha(
        HERE / "protocol.json")
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = [audit_row(name, protocol["cells"][name], protocol)
            for name in protocol["run_order"]]
    result = {"kind": "q1455_native_joint_tail_archive_audit",
              "proposal_id": "Q1455", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "rows": rows, "protocol_sha256": sha(PROTOCOL),
              "natural_relation_yield_estimate": None,
              "cost_per_useful_row": None,
              "complete_n131_log2_work": None,
              "challenge_run_admitted": False}
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1455 native joint-tail archive audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1455",
                          "statuses": [row["solver_status"] for row in rows],
                          "verified_relations": sum(
                              row["verified_relation_count"] for row in rows)}))


if __name__ == "__main__":
    main()
