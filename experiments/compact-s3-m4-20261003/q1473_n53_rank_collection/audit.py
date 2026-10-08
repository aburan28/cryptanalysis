#!/usr/bin/env python3
"""Independently replay Q1473 ordinary witnesses and N53 matrix rank."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

from sage.all import GF, matrix, vector

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from orbit_key import OrbitKey  # noqa: E402
from q1469_n53_yield_panel.audit_panel import (  # noqa: E402
    load_base, rank_insert, sha, wilson,
)
from q1473_n53_rank_collection.make_panel import render  # noqa: E402
from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "audit_result.json"
RUN = HERE / "runs/primary"
Q1469 = PARENT / "q1469_n53_yield_panel"
Q1468 = PARENT / "q1468_n53_pair_oracle"
PRIMITIVES = ("mul", "sqr", "inv")


def audit() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    rendered, target_bytes = render()
    assert panel == rendered
    assert (HERE / "targets.txt").read_bytes() == target_bytes
    assert protocol["proposal_id"] == "Q1473"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert panel["panel_workload_id"] == protocol["panel_workload_id"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "batch_oracle") == protocol["binary_sha256"]
    assert sha(HERE / "compile_receipt.json") == protocol[
        "compile_receipt_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert receipt["proposal_id"] == "Q1473"
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol[
        "source_sha256"]["experiments/compact-s3-m4-20261003/"
                         "q1473_n53_rank_collection/run_batch.py"]
    assert receipt["native_stdout_sha256"] == sha(RUN / "stdout.ndjson")
    assert receipt["native_stderr_sha256"] == sha(RUN / "stderr.txt")
    assert receipt["complete"]
    assert receipt["native_exit_code"] == 0
    rows = [json.loads(line) for line in
            (RUN / "stdout.ndjson").read_text().splitlines()]
    assert len(rows) == 257
    setup, queries = rows[0], rows[1:]
    assert setup == receipt["setup_report"]
    assert setup["mode"] == "setup"
    assert setup["pair_table_entries"] == 3651700
    assert setup["duplicate_pair_sums"] == 0
    prior = json.loads((Q1469 / "panel_audit.json").read_text())
    assert sha(Q1469 / "panel_audit.json") == protocol[
        "q1469_panel_audit_sha256"]
    assert prior["status"] == "passed"
    assert prior["final_relation_matrix_rank"] == 13
    assert prior["panel_workload_id"] == panel[
        "prior_q1469_panel_workload_id"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    points, columns = load_base(onb)
    modulus = panel["subgroup_order"]
    generator = tuple(panel["generator"])
    assert curves.isPrimeBig(modulus)
    assert curve.mul(generator, modulus) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, modulus)
    inverse_eigenvalue = pow(eigenvalue, -1, modulus)
    assert pow(eigenvalue, 53, modulus) == 1
    canonical_keys = {}
    canonical_points = {}
    for point, column in zip(points, columns):
        key, _, _ = orbit.canonical(point)
        if column in canonical_keys:
            assert key == canonical_keys[column]
        else:
            canonical_keys[column] = key
            canonical_points[column] = orbit.point_from_key(key)
    assert len(canonical_keys) == 26
    basis: dict[int, list[int]] = {}
    matrix_rows = []
    rhs = []
    held_out = None
    for row in prior["rows"]:
        if row["index"] == protocol["held_out_q1469_index"]:
            assert row["status"] == "found"
            held_out = row
            continue
        if row["status"] != "found":
            continue
        coefficient = row["coefficient_row_mod_r"]
        assert rank_insert(coefficient, basis, modulus) == row[
            "novel_rank_gain"]
        matrix_rows.append(coefficient)
        rhs.append(row["known_target_generation_scalar_fixture"])
    assert held_out is not None
    prior_rank = len(basis)
    assert prior_rank == 12
    q1469_panel = json.loads((Q1469 / "panel.json").read_text())
    excluded = {tuple(row["public_target"])
                for row in q1469_panel["targets"]}
    q1468_protocol = json.loads((Q1468 / "protocol.json").read_text())
    excluded.update(tuple(row["public_target"])
                    for row in q1468_protocol["workloads"].values())
    rng = random.Random(panel["seed"])
    found = absent = censored = 0
    new_rank = 0
    totals = {name: 0 for name in PRIMITIVES}
    query_wall_ns = 0
    checked_pairs = 0
    result_rows = []
    for index, (target_row, report) in enumerate(zip(panel["targets"], queries)):
        assert report["mode"] == "query" and report["index"] == index
        assert target_row["index"] == index
        while True:
            scalar = rng.randrange(1, modulus)
            target = curve.mul(generator, scalar)
            if target not in excluded:
                break
        excluded.add(target)
        assert list(target) == target_row["public_target"]
        status = report["status"]
        assert status in ("found", "absent", "censored")
        checked_pairs += report["query_pair_sums_examined"]
        query_wall_ns += report["query_wall_ns"]
        for name in PRIMITIVES:
            totals[name] += report["query_field_calls"][name]
        coefficient = None
        gain = 0
        if status == "found":
            found += 1
            indices = report["witness_indices"]
            assert len(indices) == 4
            assert all(isinstance(i, int) and 0 <= i < 2756
                       for i in indices)
            assert len({columns[i] for i in indices}) == 4
            total = None
            coefficient = [0] * 26
            for i in indices:
                point = points[i]
                total = curve.add(total, point)
                column = columns[i]
                key, exponent, sign = orbit.canonical(point)
                assert key == canonical_keys[column]
                value = sign * pow(inverse_eigenvalue, exponent, modulus)
                assert curve.mul(canonical_points[column], value) == point
                coefficient[column] = (coefficient[column] + value) % modulus
            assert total == target
            gain = rank_insert(coefficient, basis, modulus)
            new_rank += gain
            matrix_rows.append(coefficient)
            rhs.append(scalar)
        elif status == "absent":
            absent += 1
            assert report["query_pair_sums_examined"] == 3651700
            assert report["witness_indices"] is None
            assert report["complement_hits"] == report[
                "rejected_shared_columns"]
        else:
            censored += 1
            assert report["witness_indices"] is None
        result_rows.append({
            "index": index, "workload_id": target_row["workload_id"],
            "status": status, "verified_relation": status == "found",
            "novel_rank_gain": gain, "rank_after_query": len(basis),
            "known_target_generation_scalar_fixture": scalar,
            "coefficient_row_mod_r": coefficient,
            "query_pair_sums_examined": report["query_pair_sums_examined"],
            "query_field_calls": report["query_field_calls"],
            "query_wall_ns_exploratory": report["query_wall_ns"],
        })
    assert found + absent + censored == 256
    assert receipt["status_counts"] == {
        "found": found, "absent": absent, "censored": censored}
    t_matrix = time.perf_counter_ns()
    sage_matrix = matrix(GF(modulus), matrix_rows)
    sage_rank = int(sage_matrix.rank())
    matrix_build_rank_ns = time.perf_counter_ns() - t_matrix
    assert sage_rank == len(basis) == prior_rank + new_rank
    recovered_base_logs = None
    held_out_scalar = None
    matrix_solve_ns = scalar_replay_ns = None
    if sage_rank == 26:
        t_solve = time.perf_counter_ns()
        logs = list(sage_matrix.solve_right(vector(GF(modulus), rhs)))
        matrix_solve_ns = time.perf_counter_ns() - t_solve
        recovered_base_logs = [int(value) for value in logs]
        t_replay = time.perf_counter_ns()
        for column in range(26):
            assert curve.mul(generator, recovered_base_logs[column]) == \
                   canonical_points[column]
        held_out_scalar = sum(
            c * value for c, value in zip(
                held_out["coefficient_row_mod_r"], recovered_base_logs)
        ) % modulus
        expected_scalar = held_out[
            "known_target_generation_scalar_fixture"]
        assert held_out_scalar == expected_scalar
        held_out_target = tuple(q1469_panel["targets"][held_out["index"]][
            "public_target"])
        assert curve.mul(generator, held_out_scalar) == held_out_target
        scalar_replay_ns = time.perf_counter_ns() - t_replay
    return {
        "kind": "q1473_n53_warm_table_rank_audit",
        "status": "passed", "proposal_id": "Q1473",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "panel_workload_id": panel["panel_workload_id"],
        "curve_id": panel["curve_id"],
        "factor_base_actual_B": panel["factor_base_actual_B"],
        "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": panel[
            "factor_base_enumerated_set_sha256"],
        "target_count": 256,
        "status_counts": {"found": found, "absent": absent,
                          "censored": censored},
        "natural_relation_yield": wilson(found, 256),
        "prior_q1469_rank_excluding_held_out": prior_rank,
        "new_novel_rank": new_rank,
        "combined_rank": sage_rank,
        "held_out_q1469_index": held_out["index"],
        "held_out_scalar_recovered": held_out_scalar,
        "held_out_is_preenrolled_known_representable_control": True,
        "recovered_base_logs": recovered_base_logs,
        "target_independent_table_wall_ns_exploratory": setup["table_wall_ns"],
        "target_independent_table_field_calls": setup["table_field_calls"],
        "target_query_wall_ns_total_exploratory": query_wall_ns,
        "target_query_field_calls_total": totals,
        "query_pair_sums_examined_total": checked_pairs,
        "matrix_build_rank_wall_ns_exploratory": matrix_build_rank_ns,
        "matrix_solve_wall_ns_exploratory": matrix_solve_ns,
        "scalar_replay_wall_ns_exploratory": scalar_replay_ns,
        "peak_child_rss_global_raw": receipt["peak_child_rss_global_raw"],
        "peak_child_rss_units": receipt["peak_child_rss_units"],
        "rows": result_rows,
        "receipt_sha256": sha(RUN / "receipt.json"),
        "protocol_sha256": sha(PROTOCOL),
        "auditor_source_sha256": sha(Path(__file__)),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = audit()
    if args.emit:
        assert not RESULT.exists(), "refuse overwrite"
        RESULT.write_text(json.dumps(result, sort_keys=True, indent=2) +
                          "\n")
    else:
        assert result == json.loads(RESULT.read_text())
    print(json.dumps({"status": result["status"],
                      "found": result["status_counts"]["found"],
                      "rank": result["combined_rank"],
                      "held_out_recovered": result[
                          "held_out_scalar_recovered"] is not None}),
          flush=True)


if __name__ == "__main__":
    main()
