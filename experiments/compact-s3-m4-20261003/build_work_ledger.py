#!/usr/bin/env python3
"""Summarize frozen stage measurements without inventing a complete-solve cost."""

from __future__ import annotations

import gzip
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
    rational_support_path = HERE / "bases/n53_weight3_nonrational_supports.json.gz"
    with gzip.open(rational_support_path, "rt") as stream:
        rational_support = json.load(stream)
    assert rational_support["rational_x_masks"] == 12031
    assert rational_support["nonrational_x_masks"] == 12826
    rational_results = []
    for kind in ("planted", "ordinary"):
        rational_path, rational = read(f"n53_{kind}_rational.json")
        assert rational["proposal_id"] == "Q1308"
        assert rational["rational_support_archive_sha256"] == sha(
            rational_support_path)
        assert rational["raw_preimage_receipt_sha256"] == next(
            row["coset_receipt_sha256"] for row in corrected
            if row["n"] == 53 and row["kind"] == kind)
        assert rational["verified_relation"] is None
        rational_results.append({
            "kind": kind,
            "status": rational["attempts"][0]["status"],
            "solver_conflicts_reported": rational["attempts"][0][
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": rational["target_pdp_wall_seconds"],
            "formula_cnf_clauses": rational["formula_cnf_clauses"],
            "verified_relation_count": 0,
            "receipt_sha256": sha(rational_path),
        })
    rational_control_path, rational_control = read(
        "n53_ordinary_rational_locked_verify.json")
    assert rational_control["status"] == "verified_locked_sat_relation"
    assert rational_control["choice_index"] == 201
    assert rational_control["stage_receipt_sha256"] == next(
        row["receipt_sha256"] for row in rational_results
        if row["kind"] == "ordinary")
    orbit_variants = []
    for n in (53, 83):
        for kind in ("planted", "ordinary"):
            baseline_path, baseline = read(f"n{n}_{kind}_frozen.json")
            coset_path, coset = read(f"n{n}_{kind}_raw_preimages.json")
            for variant in ("orbit", "ordered"):
                path, stage = read(f"n{n}_{kind}_{variant}.json")
                assert stage["protocol_sha256"] == sha(protocol_path)
                assert stage["matched_baseline_receipt_sha256"] == sha(
                    baseline_path)
                assert stage["raw_preimage_receipt_sha256"] == sha(coset_path)
                assert stage["curve_id"] == baseline["curve_id"]
                assert stage["public_target"] == baseline[
                    "public_subgroup_target"]
                assert stage["factor_base_enumerated_set_sha256"] == baseline[
                    "factor_base_enumerated_set_sha256"]
                assert stage["target_orbit_x_count"] == n * coset[
                    "raw_target_preimage_count"]
                assert stage["verified_relation"] is None
                assert len(stage["attempts"]) == 1
                orbit_variants.append({
                    "proposal_id": stage["proposal_id"],
                    "candidate_id": None,
                    "workload_id": stage["workload_id"],
                    "run_id": None,
                    "curve_id": stage["curve_id"],
                    "n": n,
                    "kind": kind,
                    "variant": variant,
                    "raw_target_policy": "all exact cofactor preimages and their Frobenius conjugates for one public target",
                    "cofactor_preimage_count": stage["raw_preimage_count"],
                    "target_orbit_x_count": stage["target_orbit_x_count"],
                    "factor_base_B": stage["factor_base_actual_B"],
                    "folded_columns": stage["factor_base_folded_columns"],
                    "formula_and_gates": stage["formula_and_gates"],
                    "formula_cnf_clauses": stage["formula_cnf_clauses"],
                    "status": stage["attempts"][0]["status"],
                    "solver_conflicts_reported": stage["attempts"][0][
                        "solver_conflicts_reported"],
                    "target_orbit_generation_seconds": stage[
                        "target_orbit_generation_seconds"],
                    "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
                    "verified_relation_count": 0,
                    "natural_relation_yield_estimate": None,
                    "field_operations": None,
                    "complete_solve_work_log2": None,
                    "receipt_sha256": sha(path),
                })
    orbit_controls = []
    for variant in ("orbit", "ordered"):
        for n, kind in ((53, "ordinary"), (53, "planted"), (83, "planted")):
            path, control = read(f"n{n}_{kind}_{variant}_locked_verify.json")
            stage = next(row for row in orbit_variants
                         if row["variant"] == variant and row["n"] == n
                         and row["kind"] == kind)
            assert control["status"] == (
                "verified_locked_sat_relation_mapped_back")
            assert control["matched_" + variant + "_receipt_sha256"] == (
                stage["receipt_sha256"])
            assert control["frobenius_shift"] == 1
            orbit_controls.append({
                "n": n, "kind": kind, "variant": variant,
                "preimage_index": control["preimage_index"],
                "frobenius_shift": control["frobenius_shift"],
                "verified_relation_count": 1,
                "is_natural_solver_measurement": False,
                "receipt_sha256": sha(path),
            })
    orbit_extended_path, orbit_extended = read(
        "n53_ordinary_orbit_extended.json")
    assert orbit_extended["matched_stage_receipt_sha256"] == next(
        row["receipt_sha256"] for row in orbit_variants
        if row["n"] == 53 and row["kind"] == "ordinary"
        and row["variant"] == "orbit")
    assert orbit_extended["solver_conflicts_reported"] >= 1_000_000
    assert orbit_extended["verified_relation"] is None
    fixed_witness_targets = []
    for n, stem, kind in (
            (53, "n53_ordinary_known_preimage_fixed", "ordinary"),
            (83, "n83_planted_raw_target_fixed", "planted")):
        path, diagnostic = read(f"{stem}.json")
        baseline_path, baseline = read(f"n{n}_{kind}_frozen.json")
        assert diagnostic["baseline_receipt_sha256"] == sha(baseline_path)
        assert diagnostic["curve_id"] == baseline["curve_id"]
        assert diagnostic["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert diagnostic["candidate_id"] is None
        assert diagnostic["workload_id"] is None
        assert diagnostic["is_natural_relation_yield_measurement"] is False
        assert diagnostic["status"] == "censored"
        assert diagnostic["verified_relation"] is None
        assert diagnostic["locked_control"]["status"] == (
            "locked_sat_verified_relation")
        fixed_witness_targets.append({
            "proposal_id": diagnostic["proposal_id"],
            "candidate_id": None, "workload_id": None, "run_id": None,
            "curve_id": diagnostic["curve_id"], "n": n,
            "kind": kind,
            "oracle_assisted_raw_target_selection": diagnostic[
                "oracle_assisted_raw_target_selection"],
            "raw_preimage_index": diagnostic["raw_preimage_index"],
            "factor_base_B": diagnostic["factor_base_actual_B"],
            "folded_columns": diagnostic["factor_base_folded_columns"],
            "formula_and_gates": diagnostic["formula_and_gates"],
            "status": diagnostic["status"],
            "solver_conflicts_reported": diagnostic[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": diagnostic["target_pdp_wall_seconds"],
            "locked_control_status": diagnostic["locked_control"]["status"],
            "verified_unassisted_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    exact_base_orbit = []
    for n, kind in ((53, "ordinary"), (83, "planted"),
                    (83, "ordinary")):
        path, stage = read(f"n{n}_{kind}_exact_base_orbit.json")
        baseline_path, baseline = read(f"n{n}_{kind}_frozen.json")
        assert stage["proposal_id"] == ("Q1315" if n == 53 else "Q1316")
        assert stage["baseline_receipt_sha256"] == sha(baseline_path)
        assert stage["protocol_sha256"] == sha(protocol_path)
        assert stage["curve_id"] == baseline["curve_id"]
        assert stage["workload_id"] == baseline["workload_id"]
        assert stage["public_target"] == baseline["public_subgroup_target"]
        assert stage["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert stage["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert stage["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert stage["observed_verified_relation_count"] == int(
            stage["verified_relation"] is not None)
        control = stage["locked_control"]
        if n == 53 or kind == "planted":
            assert control["status"] == "locked_sat_verified_public_relation"
        else:
            assert control is None
        exact_base_orbit.append({
            "proposal_id": stage["proposal_id"],
            "candidate_id": None,
            "workload_id": stage["workload_id"],
            "run_id": None,
            "curve_id": stage["curve_id"],
            "n": n, "kind": kind,
            "target_policy": stage["target_policy"],
            "leaf_policy": stage["leaf_policy"],
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "status": stage["status"],
            "formula": stage["formula"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "peak_child_rss_raw_before_control": stage[
                "peak_child_rss_raw_before_control"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "locked_control_status": control["status"] if control else None,
            "natural_relation_yield_estimate": stage[
                "natural_relation_yield_estimate"],
            "field_operations": stage["field_operations"],
            "complete_solve_work_log2": stage["complete_solve_work_log2"],
            "receipt_sha256": sha(path),
        })
    projected_sparse = []
    for kind in ("planted", "ordinary"):
        path, stage = read(f"n83_{kind}_projected_sparse.json")
        baseline_path, baseline = read(f"n83_{kind}_frozen.json")
        assert stage["proposal_id"] == "Q1317"
        assert stage["baseline_receipt_sha256"] == sha(baseline_path)
        assert stage["protocol_sha256"] == sha(protocol_path)
        assert stage["curve_id"] == baseline["curve_id"]
        assert stage["workload_id"] == baseline["workload_id"]
        assert stage["public_target"] == baseline["public_subgroup_target"]
        assert stage["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert stage["factor_base_actual_B"] == baseline[
            "factor_base_actual_B"]
        assert stage["factor_base_folded_columns"] == baseline[
            "factor_base_folded_columns"]
        assert stage["observed_verified_relation_count"] == int(
            stage["verified_relation"] is not None)
        control = stage["locked_control"]
        if kind == "planted":
            assert control["status"] == "locked_sat_verified_public_relation"
        else:
            assert control is None
        projected_sparse.append({
            "proposal_id": stage["proposal_id"],
            "candidate_id": None,
            "workload_id": stage["workload_id"],
            "run_id": None,
            "curve_id": stage["curve_id"],
            "n": 83, "kind": kind,
            "target_policy": stage["target_policy"],
            "leaf_policy": stage["leaf_policy"],
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "status": stage["status"],
            "formula": stage["formula"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "peak_child_rss_raw_before_control": stage[
                "peak_child_rss_raw_before_control"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "locked_control_status": control["status"] if control else None,
            "natural_relation_yield_estimate": stage[
                "natural_relation_yield_estimate"],
            "field_operations": stage["field_operations"],
            "complete_solve_work_log2": stage["complete_solve_work_log2"],
            "receipt_sha256": sha(path),
        })
    projected_sparse_pin_diagnostics = []
    for stem, expected_status in (
            ("n83_planted_projected_sparse_rawpin4", "censored"),
            ("n83_planted_projected_sparse_leaf_x_pin", "censored"),
            ("n83_planted_projected_sparse_leaf_x_mid1_pin", "sat"),
            ("n83_planted_projected_sparse_full_pin", "sat")):
        path, diagnostic = read(f"{stem}.json")
        assert diagnostic["proposal_id"] == "Q1317"
        assert diagnostic["candidate_id"] is None
        assert diagnostic["workload_id"] is None
        assert diagnostic["is_natural_relation_yield_measurement"] is False
        assert diagnostic["matched_unassisted_receipt_sha256"] == (
            next(row["receipt_sha256"] for row in projected_sparse
                 if row["kind"] == "planted"))
        assert diagnostic["status"] == expected_status
        projected_sparse_pin_diagnostics.append({
            "variant": stem,
            "proposal_id": "Q1317",
            "candidate_id": None,
            "workload_id": None,
            "run_id": None,
            "oracle_assisted": True,
            "raw_leaf_count_pinned": diagnostic.get(
                "raw_leaf_count_pinned", diagnostic.get("pin_count")),
            "projected_leaf_count_pinned": diagnostic.get(
                "projected_leaf_count_pinned", 0),
            "intermediate_x_count_pinned": diagnostic.get(
                "intermediate_x_count_pinned", 0),
            "status": diagnostic["status"],
            "solver_conflicts_reported": diagnostic[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": diagnostic["target_pdp_wall_seconds"],
            "verified_relation_count": int(
                diagnostic["verified_relation"] is not None),
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    rooted_stage = []
    for stem, kind, links, pinned in (
            ("n83_planted_rooted1_rawpin4", "planted", 1, True),
            ("n83_planted_rooted2_rawpin4", "planted", 2, True),
            ("n83_ordinary_rooted2", "ordinary", 2, False)):
        path, stage = read(f"{stem}.json")
        baseline_path, baseline = read(f"n83_{kind}_frozen.json")
        assert stage["proposal_id"] == "Q1319"
        assert stage["baseline_receipt_sha256"] == sha(baseline_path)
        assert stage["curve_id"] == baseline["curve_id"]
        assert stage["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert stage["rooted_links"] == links
        assert stage["oracle_assisted_raw_leaf_choices"] == pinned
        assert stage["observed_verified_relation_count"] == int(
            stage["verified_relation"] is not None)
        rooted_stage.append({
            "variant": stem,
            "proposal_id": "Q1319", "candidate_id": None,
            "workload_id": stage["workload_id"], "run_id": None,
            "curve_id": stage["curve_id"],
            "n": 83, "kind": kind,
            "rooted_links": links,
            "oracle_assisted": pinned,
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "status": stage["status"],
            "formula": stage["formula"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "locked_control_status": (stage["locked_control"]["status"]
                                      if stage["locked_control"] else None),
            "natural_relation_yield_estimate": stage[
                "natural_relation_yield_estimate"],
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    group_add_stage = []
    for n, kind in ((53, "ordinary"), (83, "planted"),
                    (83, "ordinary")):
        path, stage = read(f"n{n}_{kind}_group_add.json")
        baseline_path, baseline = read(f"n{n}_{kind}_frozen.json")
        assert stage["proposal_id"] == ("Q1320" if n == 53 else "Q1321")
        assert stage["baseline_receipt_sha256"] == sha(baseline_path)
        assert stage["curve_id"] == baseline["curve_id"]
        assert stage["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert stage["status"] == "external_timeout"
        assert stage["verified_relation"] is None
        group_add_stage.append({
            "proposal_id": stage["proposal_id"],
            "candidate_id": None,
            "workload_id": stage["workload_id"], "run_id": None,
            "curve_id": stage["curve_id"],
            "n": n, "kind": kind,
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "formula": stage["formula"],
            "status": stage["status"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "observed_verified_relation_count": 0,
            "locked_control_status": (stage["control"]["status"]
                                      if stage["control"] else None),
            "locked_control_solver_wall_seconds": (
                stage["control"]["solver_wall_seconds"]
                if stage["control"] else None),
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    incomplete_path, incomplete = read(
        "n83_planted_group_add_incomplete.json")
    assert incomplete["status"] == "artifact_write_failure"
    group_add_stage.append({
        "proposal_id": "Q1321", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "n": 83, "kind": "planted",
        "status": incomplete["status"],
        "target_pdp_wall_seconds": None,
        "observed_verified_relation_count": 0,
        "complete_solve_work_log2": None,
        "receipt_sha256": sha(incomplete_path),
    })
    forward_pin_path, forward_pin = read(
        "n53_ordinary_group_add_forward_pin3.json")
    assert forward_pin["proposal_id"] == "Q1320"
    assert forward_pin["status"] == "external_timeout"
    assert forward_pin["pin_leaves"] == 3
    assert forward_pin["target_pdp_wall_seconds"] is None
    reverse_stage = []
    for n, kind, pinned, expected_status in (
            (53, "ordinary", 3, "sat"),
            (53, "ordinary", 2, "external_timeout"),
            (53, "ordinary", 0, "external_timeout"),
            (83, "planted", 3, "external_timeout"),
            (83, "ordinary", 0, "external_timeout")):
        path, stage = read(
            f"n{n}_{kind}_group_add_reverse_pin{pinned}.json")
        baseline_path, baseline = read(f"n{n}_{kind}_frozen.json")
        assert stage["proposal_id"] == ("Q1322" if n == 53 else "Q1323")
        assert stage["baseline_receipt_sha256"] == sha(baseline_path)
        assert stage["curve_id"] == baseline["curve_id"]
        assert stage["factor_base_enumerated_set_sha256"] == baseline[
            "factor_base_enumerated_set_sha256"]
        assert stage["pin_leaves"] == pinned
        assert stage["status"] == expected_status
        reverse_stage.append({
            "proposal_id": stage["proposal_id"],
            "candidate_id": None,
            "workload_id": stage["workload_id"], "run_id": None,
            "curve_id": stage["curve_id"],
            "n": n, "kind": kind,
            "pin_leaves": pinned,
            "oracle_assisted": stage["oracle_assisted"],
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "formula": stage["formula"],
            "status": stage["status"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "oracle_diagnostic_wall_seconds": stage[
                "oracle_diagnostic_wall_seconds"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    order131 = protocol["degree_131_design"]["curve"]["subgroup_order"]
    heuristic_samples131 = 2 * math.sqrt(order131 / (2 * 131))
    relation_density_heuristic = []
    for n in (53, 83):
        profile = profile_for(protocol, n)
        base_size = profile["factor_base"][
            "actual_usable_points_B_before_folding"]
        subgroup_order = profile["curve"]["subgroup_order"]
        expected = math.comb(base_size, 4) / subgroup_order
        relation_density_heuristic.append({
            "n": n,
            "curve_id": profile["curve"]["curve_id"],
            "factor_base_B": base_size,
            "subgroup_order": subgroup_order,
            "expected_distinct_unordered_four_point_subsets_per_uniform_target": expected,
            "poisson_approximate_probability_at_least_one": -math.expm1(-expected),
            "assumption": "each distinct four-point subset sum is independently uniform in the subgroup; sign/Frobenius and base structure can violate this model",
            "is_empirical_yield_estimate": False,
        })
    n131_sample_path, n131_sample = read(
        "n131_weight6_stratified_sample.json")
    n131_replay_path, n131_replay = read(
        "n131_weight6_sage_independent_replay.json")
    n131_projected_path, n131_projected = read(
        "n131_projected_sparse_geometry.json")
    n131_projected_replay_path, n131_projected_replay = read(
        "n131_projected_sparse_sage_replay.json")
    n131_pair_screen_path, n131_pair_screen = read(
        "n131_weight6_pure_pair_index_screen.json")
    assert n131_sample["proposal_id"] == "Q1303"
    assert n131_sample["candidate_id"] is None
    assert n131_sample["protocol_sha256"] == sha(protocol_path)
    assert n131_replay["status"] == "PASS"
    assert n131_replay["sample_receipt_sha256"] == sha(n131_sample_path)
    assert n131_replay["exact_rational_x_counts_weights_one_two"] == {
        "1": n131_sample["strata"][0]["rational_x_count_in_sample"],
        "2": n131_sample["strata"][1]["rational_x_count_in_sample"],
    }
    assert n131_replay["distinct_weight_two_control_projected_points"] == 16
    assert n131_projected["proposal_id"] == "Q1318"
    assert n131_projected["candidate_id"] is None
    assert n131_projected["solver_invoked"] is False
    assert n131_projected["n131_base_sample_receipt_sha256"] == sha(
        n131_sample_path)
    assert n131_projected_replay["status"] == "PASS"
    assert n131_projected_replay["screen_receipt_sha256"] == sha(
        n131_projected_path)
    assert n131_pair_screen["proposal_id"] == "Q1303"
    assert n131_pair_screen["base_sample_receipt_sha256"] == sha(
        n131_sample_path)
    assert n131_pair_screen["independent_replay_receipt_sha256"] == sha(
        n131_replay_path)
    assert n131_pair_screen["is_complete_solve_projection"] is False
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
        "n53_exact_sparse_x_rational_filter": {
            "proposal_id": "Q1308",
            "rational_x_masks": rational_support["rational_x_masks"],
            "nonrational_x_masks": rational_support["nonrational_x_masks"],
            "support_archive_sha256": sha(rational_support_path),
            "bounded_stage_results": rational_results,
            "known_ordinary_witness_locked_control_receipt_sha256": sha(
                rational_control_path),
            "conclusion": "exact rationality clauses preserve the known ordinary relation but did not produce a natural solve within the paired 100000-conflict and 20-second caps; one timing per variant is not a stable speed ratio",
        },
        "frobenius_orbit_stage_measurements": orbit_variants,
        "frobenius_orbit_locked_witness_controls": orbit_controls,
        "n53_ordinary_orbit_extended": {
            "status": orbit_extended["status"],
            "solver_conflicts_reported": orbit_extended[
                "solver_conflicts_reported"],
            "solver_conflicts_log2": math.log2(orbit_extended[
                "solver_conflicts_reported"]),
            "solver_wall_seconds_with_formula_precomputed": orbit_extended[
                "solver_wall_seconds"],
            "verified_relation_count": 0,
            "receipt_sha256": sha(orbit_extended_path),
        },
        "fixed_witness_target_search_diagnostics": fixed_witness_targets,
        "exact_base_orbit_stage_measurements": exact_base_orbit,
        "projected_sparse_stage_measurements": projected_sparse,
        "projected_sparse_planted_pin_diagnostics": (
            projected_sparse_pin_diagnostics),
        "half_trace_rooted_stage_measurements": rooted_stage,
        "full_group_addition_stage_measurements": group_add_stage,
        "n53_forward_group_addition_three_pin_diagnostic": {
            "proposal_id": "Q1320", "candidate_id": None,
            "workload_id": None, "run_id": None,
            "curve_id": forward_pin["curve_id"],
            "oracle_assisted": True,
            "pin_leaves": 3,
            "status": forward_pin["status"],
            "oracle_diagnostic_wall_seconds": forward_pin[
                "oracle_diagnostic_wall_seconds"],
            "verified_relation_count": 0,
            "receipt_sha256": sha(forward_pin_path),
        },
        "reverse_group_addition_stage_measurements": reverse_stage,
        "relation_density_planning_heuristic": relation_density_heuristic,
        "n131_weight6_geometry_estimate": {
            "proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": n131_sample["curve_id"],
            "exact_enumerated_base_B": None,
            "exact_enumerated_base_digest": None,
            "rational_x_count_estimate": n131_sample[
                "rational_x_count_estimate"],
            "conditional_B_estimate": n131_sample[
                "conditional_B_estimate"],
            "conditional_B_normal_95_percent_interval": n131_sample[
                "conditional_B_normal_95_percent_interval"],
            "conditional_folded_columns_estimate": n131_sample[
                "conditional_folded_columns_estimate"],
            "conditional_assumptions": n131_sample[
                "conditional_B_assumptions"],
            "independent_sage_replay_status": n131_replay["status"],
            "sample_receipt_sha256": sha(n131_sample_path),
            "replay_receipt_sha256": sha(n131_replay_path),
            "optimistic_uniform_subset_screen": n131_sample[
                "uniform_subset_sum_planning_heuristic"],
            "is_complete_solve_projection": False,
        },
        "n131_projected_sparse_formula_geometry": {
            "proposal_id": "Q1318",
            "candidate_id": None,
            "curve_id": n131_projected["curve_id"],
            "factor_base_exact_B": None,
            "factor_base_exact_digest": None,
            "formula": n131_projected["formula"],
            "one_hot_exact_base_selector_screen": n131_projected[
                "one_hot_exact_base_selector_screen"],
            "group_control_count": n131_projected[
                "group_control_count"],
            "independent_sage_replay_status": n131_projected_replay[
                "status"],
            "independent_sage_replay_receipt_sha256": sha(
                n131_projected_replay_path),
            "solver_invoked": False,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(n131_projected_path),
        },
        "n131_weight6_pure_pair_index_screen": {
            "proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": n131_pair_screen["curve_id"],
            "factor_base_exact_B": None,
            "factor_base_exact_digest": None,
            "method_family": n131_pair_screen["method_family"],
            "estimate": n131_pair_screen["estimate"],
            "sampling_95_percent_B_interval_cases": n131_pair_screen[
                "sampling_95_percent_B_interval_cases"],
            "optimistic_total_pair_actions_log2": n131_pair_screen[
                "optimistic_total_pair_actions_log2"],
            "gap_above_2pow61_pair_actions_log2": n131_pair_screen[
                "gap_above_2pow61_pair_actions_log2"],
            "model_assumptions": n131_pair_screen["model_assumptions"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "receipt_sha256": sha(n131_pair_screen_path),
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
            "reason_unestimated": "n53 and n83 ordinary four-point runs remain censored across raw cofactor-preimage, Frobenius-orbit, ordered-leaf, exact subgroup-base-orbit, implicit cofactor-four projected-base, half-trace-rooted, full group-addition, and reverse-link encodings; reverse-link arithmetic recovers the last n53 leaf with three oracle-pinned leaves but no unassisted four-point relation; the n131 implicit formula was only assembled, not solved; no field-operation calibration, natural yield, novel-rank contribution, matrix cost, or target descent is measured on this pipeline",
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
