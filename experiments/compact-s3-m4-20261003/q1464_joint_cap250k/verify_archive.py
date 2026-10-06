#!/usr/bin/env python3
"""Audit Q1464 wide-cap solver inputs, reports, models and small snapshots."""

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
Q1455 = PARENT / "q1455_joint_tail"
Q1458 = PARENT / "q1458_batch_roots"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, join  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


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
    parent_run = Q1455 / "runs" / name
    raw, varmap, targets, formula, meta, variables, clauses = make_case(name)
    assert gzip.decompress((parent_run / "system.cnf.gz").read_bytes()) == raw
    assert (parent_run / "variables.txt").read_bytes() == varmap
    assert (parent_run / "targets.txt").read_bytes() == targets
    assert sha(parent_run / "receipt.json") == cell["parent_receipt_sha256"]
    assert sha(parent_run / "system.cnf.gz") == cell["parent_cnf_archive_sha256"]
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
    assert variables == cell["cnf_variables"]
    assert clauses == cell["cnf_clauses"]
    assert sha(parent_run / "variables.txt") == cell["variable_map_sha256"]
    assert sha(parent_run / "targets.txt") == cell["targets_sha256"]
    for key in ("degree_n", "input_role", "curve_id", "factor_base_actual_B",
                "folded_columns_K", "factor_base_enumerated_set_sha256",
                "normal_basis_weight_bound", "public_target", "workload_id",
                "cnf_sha256", "cnf_variables", "cnf_clauses",
                "pair_candidate_cap", "conflict_cap", "wall_cap_seconds"):
        assert receipt[key] == cell[key], (name, key)
    assert receipt["proposal_id"] == "Q1464"
    assert receipt["candidate_id"] is None and receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["case"] == name
    assert receipt["point_decomposition_stage_code"] == "PDP4hybrid"
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == sha(HERE / "run_stage.py")
    assert receipt["runtime_info_sha256"] == sha(HERE /
                                                   "sage_runtime_info.json")
    assert receipt["binary_sha256"] == protocol["binary_sha256"] == sha(
        Q1458 / "native_batch_solver")
    assert receipt["parent_receipt_sha256"] == cell["parent_receipt_sha256"]
    assert receipt["baseline_q1458_receipt_sha256"] == cell[
        "baseline_q1458_receipt_sha256"] == sha(Q1458 / "runs" / name /
                                                "receipt.json")
    assert receipt["solver_stdout_sha256"] == sha(run / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(run / "solver.stderr.txt")
    assert receipt["solver_model_sha256"] == (
        sha(run / "solver.model.txt") if
        (run / "solver.model.txt").exists() else None)
    assert receipt["solver_process_wall_ns_exploratory"] >= 0
    assert receipt["recovery_check_wall_ns_exploratory"] >= 0
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["controlled_wall_speedup"] is None
    report = receipt["solver_report"]
    if report is not None:
        assert report == json.loads((run / "solver.stdout.txt").read_text())
        assert report["cnf_variables"] == variables
        assert report["cnf_clauses"] == clauses
        assert report["pair_cap"] == 250000
        assert report["decision_policy"] == protocol["decision_policy"]
        assert report["joint_eligible_checks"] == (
            report["joint_no_chain_rejections"] + report["joint_x_only_hits"])
        assert report["joint_pair0_root_calls"] <= (
            report["joint_eligible_checks"] * cell["pair_candidate_cap"])
        assert report["joint_pair1_root_calls"] <= (
            report["joint_eligible_checks"] * cell["pair_candidate_cap"])
        assert report["batch_root_inputs"] >= (
            report["joint_pair0_root_calls"] +
            report["joint_pair1_root_calls"])
        assert report["batch_root_inputs"] <= (
            report["joint_pair0_root_calls"] +
            report["joint_pair1_root_calls"] +
            report["joint_final_root_calls"])
        assert report["joint_field_inv_calls"] >= report[
            "batch_inverse_batches"]
        assert report["batch_inverse_batches"] <= report[
            "batch_denominators"]
        targets_x = [int(line, 16) for line in
                     targets.decode().splitlines()[1:]]
        onb = field.Onb(cell["degree_n"])
        checked_rejections = checked_hits = skipped_large_snapshots = 0
        for expected, key in (("no_chain", "joint_rejection_snapshots"),
                              ("x_only_witness", "joint_hit_snapshots")):
            snapshots = report[key]
            assert len(snapshots) <= 16
            for snapshot in snapshots:
                if max(snapshot["pair_candidate_counts"]) > 4096:
                    skipped_large_snapshots += 1
                    continue
                leaves = tuple(PartialLeaf(int(mask, 16), int(ones, 16))
                               for mask, ones in zip(
                                   snapshot["leaf_fixed_mask_onb_hex"],
                                   snapshot["leaf_ones_onb_hex"]))
                outcome = join(onb, leaves, targets_x[
                    snapshot["target_preimage_index"]],
                    cell["normal_basis_weight_bound"], 4096)
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
        checked_rejections = checked_hits = skipped_large_snapshots = 0
        assert receipt["solver_status"] in ("external_timeout", "error")
    if receipt["solver_status"] == "sat":
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses,
            run / "solver.model.txt", parent["instances"][str(
                cell["degree_n"])])
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["verified_relation_count"] == 0
        assert receipt["model_check"] is None
    assert receipt["successful_ordinary_pdp_cost_measured"] == bool(
        receipt["verified_relation_count"] and cell["input_role"] ==
        "ordinary_full_target")
    return {
        "case": name, "input_role": cell["input_role"],
        "degree_n": cell["degree_n"], "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "solver_status": receipt["solver_status"],
        "verified_relation_count": receipt["verified_relation_count"],
        "joint_partial_events": (report or {}).get("joint_partial_events"),
        "joint_cap_skips": (report or {}).get("joint_cap_skips"),
        "joint_eligible_checks": (report or {}).get("joint_eligible_checks"),
        "joint_no_chain_rejections": (report or {}).get(
            "joint_no_chain_rejections"),
        "sampled_rejections_independently_checked": checked_rejections,
        "sampled_hits_independently_checked": checked_hits,
        "large_snapshots_not_independently_replayed":
            skipped_large_snapshots,
        "field_mul_calls": (report or {}).get("field_mul_calls"),
        "field_sqr_calls": (report or {}).get("field_sqr_calls"),
        "field_inv_calls": (report or {}).get("field_inv_calls"),
        "joint_field_inv_calls": (report or {}).get("joint_field_inv_calls"),
        "batch_inverse_batches": (report or {}).get(
            "batch_inverse_batches"),
        "batch_denominators": (report or {}).get("batch_denominators"),
        "batch_root_inputs": (report or {}).get("batch_root_inputs"),
        "solver_process_wall_ns_exploratory": receipt[
            "solver_process_wall_ns_exploratory"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "receipt_sha256": sha(receipt_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1464"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["control_result_sha256"] == sha(HERE /
                                                     "control_result.json")
    assert protocol["binary_sha256"] == sha(Q1458 /
                                            "native_batch_solver")
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = [audit_row(name, protocol["cells"][name], protocol)
            for name in protocol["run_order"]]
    result = {
        "kind": "q1464_wide_batch_root_archive_audit",
        "proposal_id": "Q1464", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "rows": rows, "protocol_sha256": sha(PROTOCOL),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1464 wide batch-root archive audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1464",
                          "statuses": [row["solver_status"] for row in rows],
                          "verified_relations": sum(
                              row["verified_relation_count"] for row in rows)}))


if __name__ == "__main__":
    main()
