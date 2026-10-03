#!/usr/bin/env python3
"""Summarize frozen stage measurements without inventing a complete-solve cost."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from run_probe import HERE, sha


def read(name):
    path = HERE / "runs" / name
    return path, json.loads(path.read_text())


def profile_for(protocol, n):
    return next(row for row in protocol["profiles"]
                if row["field"]["n"] == n)


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
                "raw_target_policy": "one subgroup preimage only; diagnostic is not equivalent to decomposing the public target over the full cofactor-projected base",
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
    corrected = []
    factored = []
    for n in (53, 83):
        for kind in ("planted", "ordinary"):
            coset_path, coset = read(f"n{n}_{kind}_raw_preimages.json")
            multi_path, multi = read(f"n{n}_{kind}_multitarget.json")
            factored_path, fact = read(f"n{n}_{kind}_factored.json")
            baseline = next(row for row in rows if row["n"] == n
                            and row["kind"] == kind)
            assert coset["stage_receipt_sha256"] == baseline[
                "receipt_sha256"]
            assert coset["raw_target_preimage_count"] == coset["cofactor"]
            assert multi["raw_preimage_receipt_sha256"] == sha(coset_path)
            assert multi["matched_baseline_receipt_sha256"] == baseline[
                "receipt_sha256"]
            assert multi["factor_base_enumerated_set_sha256"] == profile_for(
                protocol, n)["factor_base"]["enumerated_set_sha256"]
            assert multi["verified_relation"] is None
            assert fact["matched_baseline_receipt_sha256"] == baseline[
                "receipt_sha256"]
            assert fact["verified_relation"] is None
            factored.append({
                "proposal_id": fact["proposal_id"],
                "n": n, "kind": kind,
                "target_policy": "one subgroup preimage",
                "formula_and_gates": fact["formula_and_gates"],
                "status": fact["attempts"][0]["status"],
                "conflicts_reported": fact["attempts"][0][
                    "solver_conflicts_reported"],
                "target_pdp_wall_seconds": fact["target_pdp_wall_seconds"],
                "verified_relation_count": 0,
                "receipt_sha256": sha(factored_path),
            })
            corrected.append({
                "proposal_id": multi["proposal_id"],
                "candidate_id": None,
                "workload_id": multi["workload_id"],
                "run_id": None,
                "curve_id": multi["curve_id"],
                "n": n, "kind": kind,
                "raw_target_policy": "all exact cofactor preimages of the one public target",
                "cofactor_preimage_count": coset["raw_target_preimage_count"],
                "factor_base_B": multi["factor_base_actual_B"],
                "folded_columns": multi["factor_base_folded_columns"],
                "formula_and_gates": multi["formula_and_gates"],
                "status": multi["attempts"][0]["status"],
                "solver_conflicts_reported": multi["attempts"][0][
                    "solver_conflicts_reported"],
                "preimage_coset_generation_seconds_with_kernel_construction":
                    coset["elapsed_seconds"],
                "target_pdp_wall_seconds": multi["target_pdp_wall_seconds"],
                "peak_child_rss_raw": multi["peak_child_rss_raw"],
                "peak_child_rss_units": multi["peak_child_rss_units"],
                "verified_relation_count": 0,
                "natural_relation_yield_estimate": None,
                "field_operations": None,
                "complete_solve_work_log2": None,
                "coset_receipt_sha256": sha(coset_path),
                "receipt_sha256": sha(multi_path),
            })
    witness_path, witness = read("n53_ordinary_raw_pair_witness.json")
    assert witness["preimage_coset_sha256"] == next(
        row["coset_receipt_sha256"] for row in corrected
        if row["n"] == 53 and row["kind"] == "ordinary")
    assert witness["raw_leaf_x_weights"] == [3] * 4
    locked = []
    for n, kind in ((53, "planted"), (53, "ordinary"), (83, "planted")):
        path, control = read(f"n{n}_{kind}_multitarget_locked_verify.json")
        assert control["status"] == "verified_locked_sat_relation"
        assert control["matched_multitarget_receipt_sha256"] == next(
            row["receipt_sha256"] for row in corrected
            if row["n"] == n and row["kind"] == kind)
        locked.append({"n": n, "kind": kind,
                       "choice_index": control["choice_index"],
                       "verified_relation_count": 1,
                       "is_natural_solver_measurement": False,
                       "receipt_sha256": sha(path)})
    extended_path, extended = read("n53_ordinary_multitarget_extended.json")
    assert extended["matched_stage_receipt_sha256"] == next(
        row["receipt_sha256"] for row in corrected
        if row["n"] == 53 and row["kind"] == "ordinary")
    assert extended["solver_conflicts_reported"] >= 1_000_000
    assert extended["verified_relation"] is None
    extended_stdout = HERE / "runs/n53_ordinary_multitarget_extended.stdout.txt"
    assert sha(extended_stdout) == extended["stdout_sha256"]
    extended_propagations = re.findall(r"^c propagations\s*:\s*(\S+)",
                                        extended_stdout.read_text(),
                                        flags=re.MULTILINE)
    assert extended_propagations
    meter_path, meter = read("n83_ordinary_multitarget_conflict_meter.json")
    assert meter["matched_stage_receipt_sha256"] == next(
        row["receipt_sha256"] for row in corrected
        if row["n"] == 83 and row["kind"] == "ordinary")
    assert meter["solver_conflicts_reported"] >= 100_000
    assert meter["verified_relation"] is None
    order131 = protocol["degree_131_design"]["curve"]["subgroup_order"]
    heuristic_samples131 = 2 * math.sqrt(order131 / (2 * 131))
    ledger = {
        "kind": "compact_s3_m4_go_no_go_work_ledger",
        "schema_version": 1,
        "protocol_sha256": sha(protocol_path),
        "stage_measurements": rows,
        "factored_single_preimage_diagnostics": factored,
        "corrected_full_preimage_stage_measurements": corrected,
        "locked_witness_controls": locked,
        "n53_ordinary_known_raw_relation": {
            "raw_preimage_index": 201,
            "all_four_leaf_x_weights": [3, 3, 3, 3],
            "receipt_sha256": sha(witness_path),
            "is_natural_solver_measurement": False,
        },
        "extended_corrected_stage_diagnostics": {
            "n53_ordinary_known_satisfiable": {
                "status": extended["status"],
                "solver_conflicts_reported": extended[
                    "solver_conflicts_reported"],
                "solver_conflicts_log2": math.log2(extended[
                    "solver_conflicts_reported"]),
                "solver_propagations_rounded_display": extended_propagations[-1],
                "solver_wall_seconds_with_formula_precomputed": extended[
                    "solver_wall_seconds"],
                "peak_child_rss_raw": extended["peak_child_rss_raw"],
                "peak_child_rss_units": extended["peak_child_rss_units"],
                "verified_relation_count": 0,
                "receipt_sha256": sha(extended_path),
            },
            "n83_ordinary": {
                "status": meter["status"],
                "solver_conflicts_reported": meter[
                    "solver_conflicts_reported"],
                "solver_conflicts_log2": math.log2(meter[
                    "solver_conflicts_reported"]),
                "solver_propagations_rounded_display": meter[
                    "solver_propagations_rounded_display"],
                "solver_wall_seconds_with_formula_precomputed": meter[
                    "solver_wall_seconds"],
                "peak_child_rss_raw": meter["peak_child_rss_raw"],
                "peak_child_rss_units": meter["peak_child_rss_units"],
                "verified_relation_count": 0,
                "receipt_sha256": sha(meter_path),
            },
            "operation_unit_boundary": "CryptoMiniSat conflicts are exact solver events; propagation display is rounded; neither is a calibrated field-operation count or complete-solve work",
        },
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
            "reason_unestimated": "even after all cofactor preimages are included, n53 and n83 ordinary S3 runs remain censored; no field-operation calibration, natural yield, novel-rank contribution, matrix cost, or target descent is measured on this pipeline",
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
