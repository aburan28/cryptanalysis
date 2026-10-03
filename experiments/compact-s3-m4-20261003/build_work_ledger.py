#!/usr/bin/env python3
"""Summarize frozen stage measurements without inventing a complete-solve cost."""

from __future__ import annotations

import json
import math
from pathlib import Path

from run_probe import HERE, sha


def read(name):
    path = HERE / "runs" / name
    return path, json.loads(path.read_text())


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert sha(protocol_path) == "a011020e25a0c7d8366eb76d26f2d0c345a2ddf1beed6d7be2c8ab22ff8350ba"
    rows = []
    for n in (53, 83):
        profile = next(row for row in protocol["profiles"]
                       if row["field"]["n"] == n)
        for kind in ("planted", "ordinary"):
            path, stage = read(f"n{n}_{kind}_frozen.json")
            assert stage["proposal_id"] == profile["proposal_id"]
            assert stage["curve_id"] == profile["curve"]["curve_id"]
            assert stage["factor_base_enumerated_set_sha256"] == profile[
                "factor_base"]["enumerated_set_sha256"]
            assert stage["protocol_sha256"] == sha(protocol_path)
            assert stage["attempts"] and all(
                attempt["status"] == "external_timeout"
                for attempt in stage["attempts"])
            assert stage["verified_relation"] is None
            rows.append({
                "proposal_id": stage["proposal_id"],
                "candidate_id": None,
                "workload_id": stage["workload_id"],
                "run_id": None,
                "curve_id": stage["curve_id"],
                "n": n,
                "kind": kind,
                "status": "censored_at_external_20_second_cap",
                "factor_base_B": stage["factor_base_actual_B"],
                "folded_columns": stage["factor_base_folded_columns"],
                "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
                "verified_relation_count": 0,
                "natural_relation_yield_estimate": None,
                "field_operations": None,
                "complete_solve_work_log2": None,
                "receipt_sha256": sha(path),
            })
    n53_path, n53 = read("n53_ordinary_matched_pair_table.json")
    n83_path, n83 = read("n83_ordinary_matched_pair_sample.json")
    for n, path, comparison in ((53, n53_path, n53), (83, n83_path, n83)):
        ordinary = next(row for row in rows if row["n"] == n
                        and row["kind"] == "ordinary")
        assert comparison["matched_s3_stage_receipt_sha256"] == ordinary[
            "receipt_sha256"]
        assert comparison["workload_id"] == ordinary["workload_id"]
        assert comparison["factor_base_actual_B"] == ordinary["factor_base_B"]
        assert comparison["factor_base_folded_columns"] == ordinary[
            "folded_columns"]
    samples53 = n53["ordinary_query"]["table_samples"] + n53[
        "ordinary_query"]["query_samples"]
    samples83 = n83["table_samples"] + n83["query_samples"]
    order131 = protocol["degree_131_design"]["curve"]["subgroup_order"]
    heuristic_samples131 = 2 * math.sqrt(order131 / (2 * 131))
    ledger = {
        "kind": "compact_s3_m4_go_no_go_work_ledger",
        "schema_version": 1,
        "protocol_sha256": sha(protocol_path),
        "stage_measurements": rows,
        "matched_pair_table": {
            "n53": {
                "status": n53["status"],
                "verified_relation_count": n53["verified_relation_count"],
                "table_pair_samples": n53["ordinary_query"]["table_samples"],
                "query_pair_samples": n53["ordinary_query"]["query_samples"],
                "total_logical_pair_samples": samples53,
                "total_logical_pair_samples_log2": math.log2(samples53),
                "base_setup_seconds": n53["base_setup_wall_ns"] / 1e9,
                "table_seconds": n53["ordinary_query"]["table_wall_ns"] / 1e9,
                "query_seconds": n53["ordinary_query"]["query_wall_ns"] / 1e9,
                "receipt_sha256": sha(n53_path),
            },
            "n83": {
                "status": n83["status"],
                "verified_relation_count": len(n83["verified_relations"]),
                "table_pair_samples": n83["table_samples"],
                "query_pair_samples": n83["query_samples"],
                "total_logical_pair_samples": samples83,
                "total_logical_pair_samples_log2": math.log2(samples83),
                "table_seconds": n83["table_wall_ns"] / 1e9,
                "query_seconds": n83["query_wall_ns"] / 1e9,
                "receipt_sha256": sha(n83_path),
            },
        },
        "degree_131": {
            "proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": protocol["degree_131_design"]["curve"]["curve_id"],
            "four_summand_s3_complete_solve_work_log2": None,
            "four_summand_s3_per_decomposition_field_ops_log2": None,
            "reason_unestimated": "n53 and n83 ordinary S3 runs were censored; no field-operation calibration, natural yield, rank contribution, matrix cost, or target descent is measured on this pipeline",
            "balanced_random_quotient_pair_table_heuristic": {
                "assumption": "independent uniform pair-sum orbit keys of size approximately r/(2n); one expected match when table_samples*query_samples approximately r/(2n)",
                "total_logical_pair_samples": heuristic_samples131,
                "total_logical_pair_samples_log2": math.log2(heuristic_samples131),
                "is_complete_solve_estimate": False,
                "is_empirical_measurement": False,
            },
            "challenge_dispatch_allowed": False,
        },
    }
    output = HERE / "work_ledger.json"
    output.write_text(json.dumps(ledger, indent=2) + "\n")
    print(json.dumps({"n53_pair_samples_log2": math.log2(samples53),
                      "n83_pair_samples_log2": math.log2(samples83),
                      "degree131_pair_heuristic_log2":
                      math.log2(heuristic_samples131),
                      "s3_complete_solve_log2": None}))


if __name__ == "__main__":
    main()
