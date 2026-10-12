#!/usr/bin/env python3
"""Independently replay Q1446 inputs, relations, and sampled span claims."""

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
Q1438 = PARENT / "q1438_dense_base"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1428_bilinear_span.screen import relaxed_feasible  # noqa: E402
from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_snapshots(n, weight, report):
    sampled = rejected = 0
    onb = field.Onb(n)
    basis = [onb.fromCoords(1 << j) for j in range(n)]
    mask = (1 << n) - 1
    for kind, rows in (("screen", report["screen_snapshots"]),
                       ("rejection", report["span_rejection_snapshots"])):
        assert len(rows) <= 16
        for row in rows:
            assert row["pair"] in (0, 1)
            mid = int(row["mid_onb_hex"], 16)
            a_fixed = int(row["a_fixed_mask_onb_hex"], 16)
            a_ones = int(row["a_ones_onb_hex"], 16)
            b_fixed = int(row["b_fixed_mask_onb_hex"], 16)
            b_ones = int(row["b_ones_onb_hex"], 16)
            assert not (mid | a_fixed | a_ones | b_fixed | b_ones) & ~mask
            for side, fixed, ones in (("a", a_fixed, a_ones),
                                      ("b", b_fixed, b_ones)):
                assert ones & ~fixed == 0
                assert row[f"free_{side}"] == n - fixed.bit_count()
                assert 1 <= row[f"free_{side}"] <= (14 if n == 53 else 20)
                assert row[f"slack_{side}"] == weight - ones.bit_count()
                assert 1 <= row[f"slack_{side}"] <= 2
            free_a = [j for j in range(n) if not (a_fixed >> j & 1)]
            free_b = [j for j in range(n) if not (b_fixed >> j & 1)]
            oracle = relaxed_feasible(
                onb, basis, onb.fromCoords(a_ones),
                onb.fromCoords(b_ones), onb.fromCoords(mid),
                free_a, free_b)
            if kind == "rejection":
                assert not oracle["constant_in_span"]
                rejected += 1
            else:
                sampled += 1
    return {"sampled_window_states_replayed": sampled,
            "sampled_rejections_replayed": rejected,
            "sampled_false_rejections": 0}


def verify_cell(n, protocol):
    cell = protocol["cells"][str(n)]
    output = HERE / f"runs/n{n}_ordinary"
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1446"
    assert receipt["candidate_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "experiments/compact-s3-m4-20261003/q1446_joint_pair_span/"
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "workload_id", "matched_q1438_workload_id",
                 "cnf_raw_sha256", "variable_map_sha256",
                 "target_input_sha256"):
        assert receipt[name] == cell[name], name
    raw, varmap, formula, meta, variables, clauses = build_cnf(n, "ordinary")
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == cell["variable_map_sha256"]
    assert gzip.decompress((output / "system.cnf.gz").read_bytes()) == raw
    assert sha(output / "system.cnf.gz") == receipt["cnf_archive_sha256"]
    assert sha(output / "variables.txt") == receipt["variable_map_sha256"]
    assert sha(output / "targets.txt") == receipt["target_input_sha256"]
    assert sha(output / "solver.stdout.txt") == receipt[
        "solver_stdout_sha256"]
    assert sha(output / "solver.stderr.txt") == receipt[
        "solver_stderr_sha256"]
    assert variables == receipt["cnf_variables"] == cell["cnf_variables"]
    assert clauses == receipt["cnf_clauses"] == cell["cnf_clauses"]
    assert receipt["formula_build_wall_ns_exploratory"] >= 0
    assert receipt["solver_process_wall_ns_exploratory"] >= 0
    assert receipt["recovery_check_wall_ns_exploratory"] >= 0
    assert receipt["other_online_wall_ns_exploratory"] >= 0
    assert receipt["online_stage_wall_ns_exploratory"] == sum(
        receipt[k] for k in (
            "formula_build_wall_ns_exploratory",
            "solver_process_wall_ns_exploratory",
            "recovery_check_wall_ns_exploratory",
            "other_online_wall_ns_exploratory"))
    report = receipt["solver_report"]
    replay = {"sampled_window_states_replayed": 0,
              "sampled_rejections_replayed": 0,
              "sampled_false_rejections": 0}
    if report is not None:
        assert report["decision_policy"] == protocol["policy"]
        assert report["target_coupled_active"] is True
        assert report["span_checks"] == (report["span_checks_pair0"] +
                                          report["span_checks_pair1"])
        assert report["span_rejections"] == (
            report["span_rejections_pair0"] +
            report["span_rejections_pair1"])
        assert report["span_checks"] == report["span_checked_state_count"]
        assert report["span_rejections"] <= report["span_checks"]
        for pair in (0, 1):
            assert report[f"span_checks_pair{pair}"] <= report[
                f"screen_window_pair{pair}_events"]
            assert report[f"screen_window_pair{pair}_events"] <= report[
                f"unsaturated_pair{pair}_events"]
            assert report[f"unsaturated_pair{pair}_events"] <= report[
                f"both_partial_pair{pair}_events"]
        assert report["screen_window_distinct_capped"] <= 512
        assert report["span_field_inv_calls"] == 0
        replay = check_snapshots(n, cell["weight_bound"], report)
    relation = None
    if receipt["solver_status"] == "sat":
        model_path = output / "solver.model.txt"
        assert sha(model_path) == receipt["solver_model_sha256"]
        parent = json.loads((Q1438 / "solver_protocol.json").read_text())
        relation = model_relation(raw, formula, meta, variables, clauses,
                                  model_path, parent["instances"][str(n)])
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["solver_status"] in (
            "censored", "external_timeout", "unsat", "error")
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["solver_model_sha256"] is None
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["novel_rank_per_query"] is None
    assert receipt["cost_per_useful_row"] is None
    assert receipt["complete_n131_log2_work"] is None
    assert receipt["challenge_run_admitted"] is False
    return {"degree": n, "status": receipt["solver_status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "span_checks_pair0": ((report or {}).get("span_checks_pair0")),
            "span_checks_pair1": ((report or {}).get("span_checks_pair1")),
            "span_rejections_pair0": ((report or {}).get(
                "span_rejections_pair0")),
            "span_rejections_pair1": ((report or {}).get(
                "span_rejections_pair1")),
            "field_mul_calls": ((report or {}).get("field_mul_calls")),
            "field_sqr_calls": ((report or {}).get("field_sqr_calls")),
            "field_inv_calls": ((report or {}).get("field_inv_calls")),
            "relation_replayed": relation is not None,
            "sampled_span_replay": replay,
            "receipt_sha256": sha(receipt_path)}


def verify():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1446"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest, name
    assert sha(HERE / "theory_solver") == protocol["solver_binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "validation.json") == protocol["validation_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    return {"proposal_id": "Q1446", "status": "pass",
            "protocol_sha256": sha(PROTOCOL),
            "rows": [verify_cell(n, protocol) for n in (53, 83)],
            "complete_n131_log2_work": None,
            "challenge_run_admitted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1446 archive: PASS")
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"],
                          "rows": result["rows"]}, sort_keys=True))
