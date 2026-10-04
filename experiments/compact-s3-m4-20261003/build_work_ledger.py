#!/usr/bin/env python3
"""Summarize frozen stage measurements without inventing a complete-solve cost."""

from __future__ import annotations

import gzip
import json
import math
import re
from decimal import Decimal, localcontext
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
    support_path, support = read("n83_four_point_support_screen.json")
    assert support["status"] == (
        "exact_count_bound_plus_separately_labeled_heuristic")
    assert support["profiles"][1]["actual_usable_points_B_before_folding"] == (
        profile_for(protocol, 83)["factor_base"][
            "actual_usable_points_B_before_folding"])
    assert support["profiles"][1][
        "uniform_nonidentity_target_coverage_upper_bound"] < 0.242
    q1324_protocol_path = HERE / "q1324_protocol.json"
    q1324_protocol = json.loads(q1324_protocol_path.read_text())
    assert q1324_protocol["proposal_id"] == "Q1324"
    assert q1324_protocol["candidate_id"] is None
    assert q1324_protocol["factor_base"][
        "actual_usable_points_B_before_folding"] == 4000102
    q1324_replay_path, q1324_replay = read(
        "n83_q1324_q1041_full_base_verification.json")
    assert q1324_replay["status"] == "PASS"
    assert q1324_replay["actual_usable_points_B_before_folding"] == 4000102
    assert q1324_replay["signed_frobenius_columns"] == 24097
    assert q1324_replay["verified_projected_representatives"] == 24097
    q1324_stage = []
    for mode in ("planted_locked", "ordinary"):
        path, stage = read(f"n83_q1324_{mode}.json")
        assert stage["proposal_id"] == "Q1324"
        assert stage["candidate_id"] is None
        assert stage["protocol_sha256"] == sha(q1324_protocol_path)
        assert stage["factor_base_actual_B"] == 4000102
        assert stage["factor_base_folded_columns"] == 24097
        assert stage["factor_base_enumerated_set_sha256"] == q1324_protocol[
            "factor_base"]["enumerated_set_sha256"]
        assert stage["complete_solve_work_log2"] is None
        assert stage["field_operations"] is None
        q1324_stage.append({
            "proposal_id": "Q1324", "candidate_id": None,
            "workload_id": stage["workload_id"], "run_id": None,
            "curve_id": stage["curve_id"], "mode": mode,
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "factor_base_digest": stage[
                "factor_base_enumerated_set_sha256"],
            "oracle_assisted": stage["oracle_assisted"],
            "status": stage["status"],
            "formula": stage["formula"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "oracle_control_wall_seconds": stage[
                "oracle_control_wall_seconds"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    q1325_base_path = HERE / "bases/n83_weight5_full_orbits.json"
    q1325_base = json.loads(q1325_base_path.read_text())
    q1325_key_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    q1325_fb = q1325_base["factor_base"]
    assert q1325_base["proposal_id"] == "Q1325"
    assert q1325_base["candidate_id"] is None
    assert q1325_fb["actual_usable_points_B_before_folding"] == 30977592
    assert q1325_fb["signed_frobenius_columns"] == 186612
    assert q1325_fb["enumerated_set_sha256"] == sha(q1325_key_path)
    assert q1325_base["q1041_subset"]["subset_columns_verified"] == 24097
    q1325_replay_path, q1325_replay = read("n83_q1325_full_base_replay.json")
    assert q1325_replay["status"] == "PASS"
    assert q1325_replay["q1302_weight4_subset_columns_verified"] == 11651
    assert q1325_replay["q1041_subset_columns_verified"] == 24097
    q1325_protocol_path = HERE / "q1325_protocol.json"
    q1325_protocol = json.loads(q1325_protocol_path.read_text())
    assert q1325_protocol["proposal_id"] == "Q1325"
    assert q1325_protocol["candidate_id"] is None
    assert q1325_protocol["factor_base"][
        "actual_usable_points_B_before_folding"] == 30977592
    q1325_stage = []
    for mode in ("planted_locked", "ordinary"):
        path, stage = read(f"n83_q1325_{mode}.json")
        assert stage["proposal_id"] == "Q1325"
        assert stage["candidate_id"] is None
        assert stage["protocol_sha256"] == sha(q1325_protocol_path)
        assert stage["factor_base_actual_B"] == 30977592
        assert stage["factor_base_folded_columns"] == 186612
        assert stage["factor_base_enumerated_set_sha256"] == q1325_fb[
            "enumerated_set_sha256"]
        assert stage["complete_solve_work_log2"] is None
        assert stage["field_operations"] is None
        q1325_stage.append({
            "proposal_id": "Q1325", "candidate_id": None,
            "workload_id": stage["workload_id"], "run_id": None,
            "curve_id": stage["curve_id"], "mode": mode,
            "factor_base_B": stage["factor_base_actual_B"],
            "folded_columns": stage["factor_base_folded_columns"],
            "factor_base_digest": stage[
                "factor_base_enumerated_set_sha256"],
            "oracle_assisted": stage["oracle_assisted"],
            "status": stage["status"],
            "formula": stage["formula"],
            "target_pdp_wall_seconds": stage["target_pdp_wall_seconds"],
            "oracle_control_wall_seconds": stage[
                "oracle_control_wall_seconds"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "peak_parent_rss_raw": stage["peak_parent_rss_raw"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_rss_units": stage["peak_rss_units"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    q1325_b = q1325_fb["actual_usable_points_B_before_folding"]
    q1325_r = q1325_base["curve"]["subgroup_order"]
    q1325_mean = math.comb(q1325_b, 4) / q1325_r
    q1326_protocol_path = HERE / "q1326_protocol.json"
    q1326_protocol = json.loads(q1326_protocol_path.read_text())
    assert q1326_protocol["proposal_id"] == "Q1326"
    assert q1326_protocol["candidate_id"] is None
    assert q1326_protocol["ordinary_workload_id"] == "74f2979b3e68"
    q1326_summary_path, q1326_summary = read(
        "n53_q1326_ordinary_summary.json")
    assert q1326_summary["status"] == "censored"
    assert q1326_summary["observed_verified_relation_count"] == 0
    assert len(q1326_summary["stage_attempts"]) == 3
    q1326_stages = []
    for stage in q1326_protocol["search_restrictions"]:
        path, attempt = read(f"n53_q1326_ordinary_{stage['stage']}.json")
        assert attempt["proposal_id"] == "Q1326"
        assert attempt["candidate_id"] is None
        assert attempt["workload_id"] == q1326_protocol[
            "ordinary_workload_id"]
        assert attempt["eligible_actual_B_before_folding"] == stage[
            "eligible_actual_B_before_folding"]
        assert attempt["eligible_folded_columns"] == stage[
            "eligible_folded_columns"]
        assert attempt["eligible_set_sha256"] == stage[
            "eligible_set_sha256"]
        assert attempt["observed_verified_relation_count"] == 0
        assert attempt["field_operations"] is None
        assert attempt["complete_solve_work_log2"] is None
        q1326_stages.append({
            "proposal_id": "Q1326", "candidate_id": None,
            "workload_id": attempt["workload_id"], "run_id": None,
            "curve_id": attempt["curve_id"], "isogeny": "none",
            "stage": stage["stage"],
            "eligible_actual_B_before_folding": stage[
                "eligible_actual_B_before_folding"],
            "eligible_folded_columns": stage[
                "eligible_folded_columns"],
            "eligible_set_sha256": stage["eligible_set_sha256"],
            "uniform_target_mean_distinct_four_subsets_exact": stage[
                "uniform_target_mean_distinct_four_subsets_exact"],
            "status": attempt["status"],
            "solver_conflicts_reported": attempt[
                "solver_conflicts_reported"],
            "formula": attempt["formula"],
            "target_pdp_wall_seconds": attempt[
                "target_pdp_wall_seconds"],
            "target_relation_check_wall_seconds": attempt[
                "target_relation_check_wall_seconds"],
            "peak_parent_rss_raw": attempt["peak_parent_rss_raw"],
            "peak_child_rss_raw_cumulative": attempt[
                "peak_child_rss_raw_cumulative"],
            "peak_rss_units": attempt["peak_rss_units"],
            "observed_verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert math.isclose(q1326_summary[
        "total_target_pdp_wall_seconds"], sum(row[
            "target_pdp_wall_seconds"] for row in q1326_stages),
        rel_tol=1e-12)
    q1326_planted_path, q1326_planted = read(
        "n53_q1326_planted_locked.json")
    q1326_unpinned_path, q1326_unpinned = read(
        "n53_q1326_planted_unpinned.json")
    assert q1326_planted["status"] == (
        "locked_sat_verified_public_relation")
    assert q1326_unpinned["status"] == "censored"
    assert q1326_unpinned["public_target"] == q1326_planted[
        "public_target"]
    assert q1326_unpinned["observed_verified_relation_count"] == 0
    q1326_support_path, q1326_support = read(
        "n53_q1326_k128_support_diagnostic.json")
    assert q1326_support["status"] == "budget"
    assert q1326_support["observed_verified_relation_count"] == 0
    assert q1326_support["total_logical_pair_samples"] == 2000000
    native_bridge_profiles = []
    for n in (53, 83):
        bridge_path = HERE / "field_bridges" / f"n{n}_onb_poly.json"
        bridge = json.loads(bridge_path.read_text())
        replay_path, replay = read(f"n{n}_onb_poly_bridge_replay.json")
        assert bridge["status"] == replay["status"] == "PASS"
        assert bridge["field_degree"] == replay["field_degree"] == n
        assert bridge["curve_id"] == replay["curve_id"]
        assert bridge["changes_curve_identity"] is False
        assert replay["all_basis_products_checked"] == n * n
        assert replay["bridge_sha256"] == sha(bridge_path)
        native_bridge_profiles.append({
            "field_degree": n,
            "curve_id": bridge["curve_id"],
            "isogeny": "none",
            "polynomial_modulus": bridge[
                "target_implementation_basis"]["defining_modulus"],
            "field_isomorphism_exact": True,
            "changes_curve_or_base_identity": False,
            "all_basis_products_checked": n * n,
            "factor_base_representatives_checked": replay[
                "factor_base_representatives_checked_on_polynomial_curve"],
            "native_root_solver_invoked": True,
            "native_root_stage_proposal_id": (
                "Q1327" if n == 53 else "Q1328"),
            "native_root_solver_field_operation_equivalent_cost": None,
            "native_root_top_level_operation_counts_recorded_below": True,
            "bridge_receipt_sha256": sha(bridge_path),
            "independent_replay_receipt_sha256": sha(replay_path),
        })
    native_protocol_path = HERE / "q1327_q1328_native_root_protocol.json"
    native_protocol = json.loads(native_protocol_path.read_text())
    assert native_protocol["candidate_id"] is None
    assert native_protocol["point_decomposition"]["stage_code"] == (
        "PDP4root")
    native_build_path = HERE / "native_build_receipt.json"
    native_build = json.loads(native_build_path.read_text())
    assert native_build["status"] == "PASS"
    assert native_build["source_sha256"] == sha(
        HERE / "native_s3_root.rs")
    native_root_stages = []
    for n, expected_status in ((53, "native_relation_found"),
                               (83, "state_cap_no_relation")):
        profile = next(row for row in native_protocol["profiles"]
                       if row["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        reps_path = HERE / "native_inputs" / f"n{n}_x_representatives.bin"
        stage_path, stage = read(
            "n53_native_root_full.json" if n == 53
            else "n83_native_root_capped_2m.json")
        replay_path, replay = read(
            f"n{n}_native_root_independent_replay.json")
        assert manifest["stage_protocol_sha256"] == sha(
            native_protocol_path)
        assert manifest["representatives_file_sha256"] == sha(reps_path)
        assert manifest["proposal_id"] == stage["proposal_id"]
        assert stage["proposal_id"] == replay["proposal_id"]
        assert replay["proposal_id"] == profile["proposal_id"]
        assert stage["status"] == replay[
            "native_stage_status"] == expected_status
        assert stage["native_source_sha256"] == native_build[
            "source_sha256"]
        assert stage["cargo_manifest_sha256"] == native_build[
            "cargo_manifest_sha256"]
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["native_build_receipt_sha256"] == sha(
            native_build_path)
        assert replay["ordinary_relation_independently_verified"] is (
            n == 53)
        assert stage["complete_work_log2"] is None
        assert stage["verified_single_target_dlp"] is False
        native_root_stages.append({
            "proposal_id": profile["proposal_id"],
            "parent_factor_base_proposal_id": profile[
                "parent_factor_base_proposal_id"],
            "candidate_id": None,
            "run_id": None,
            "curve_id": stage["curve_id"],
            "workload_id": stage["workload_id"],
            "target_count": 1,
            "target_policy": "one frozen ordinary public target; no target batching",
            "measurement_scope": "target-dependent PDP and native relation-check stage only",
            "field_degree": n,
            "actual_usable_points_B": stage["actual_usable_points_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "status": expected_status,
            "index_pair_states_examined": stage[
                "index_pair_states_examined"],
            "target_states_scanned": stage["target_states_scanned"],
            "target_state_orientations_tested": stage[
                "target_state_orientations_tested"],
            "index_distinct_root_keys": stage[
                "index_distinct_root_keys"],
            "target_table_hits": stage["target_table_hits"],
            "target_pdp_and_native_check_wall_seconds_exploratory": (
                int(stage["timing_ns"]["target_pdp_and_native_check"]) / 1e9),
            "target_independent_setup_and_index_wall_seconds_exploratory": (
                (int(stage["timing_ns"]["setup"]) +
                 int(stage["timing_ns"]["index_build"])) / 1e9),
            "peak_rss_bytes": stage["peak_rss_bytes"],
            "memory_cap_bytes": stage["limits"]["peak_rss_cap_bytes"],
            "operation_counts_by_phase": stage["operation_counts"],
            "index_hash_probes": stage["root_table_hash_probes"][
                "index_insert_and_rehash"],
            "target_hash_probes": stage["root_table_hash_probes"][
                "target_lookup"],
            "verified_ordinary_relation_count": int(n == 53),
            "observed_rank_of_native_and_matched_pair_rows": (
                replay["rank_of_native_and_matched_pair_rows"]
                if n == 53 else None),
            "natural_relation_yield_rate_estimate": None,
            "common_field_operation_equivalent_calibration": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "source_bound_native_receipt_sha256": sha(stage_path),
            "independent_replay_receipt_sha256": sha(replay_path),
            "native_input_manifest_sha256": sha(manifest_path),
        })
    control_fixture_path, control_fixture = read(
        "n83_q1329_planted_fixture.json")
    control_manifest_path = HERE / "native_inputs/n83_planted_control_manifest.json"
    control_manifest = json.loads(control_manifest_path.read_text())
    control_stage_path, control_stage = read(
        "n83_q1329_planted_unpinned.json")
    control_replay_path, control_replay = read(
        "n83_q1329_planted_independent_replay.json")
    assert control_fixture["proposal_id"] == control_manifest[
        "proposal_id"] == control_stage["proposal_id"] == control_replay[
            "proposal_id"] == "Q1329"
    assert control_fixture["parent_solver_proposal_id"] == control_manifest[
        "parent_solver_proposal_id"] == "Q1328"
    assert control_fixture["parent_factor_base_proposal_id"] == (
        control_manifest["parent_factor_base_proposal_id"])
    assert control_fixture["parent_factor_base_proposal_id"] == (
        control_stage["parent_factor_base_proposal_id"])
    assert control_fixture["parent_factor_base_proposal_id"] == "Q1325"
    assert control_fixture["candidate_id"] is control_manifest[
        "candidate_id"] is control_stage["candidate_id"] is control_replay[
            "candidate_id"] is None
    assert control_fixture["is_natural_yield_measurement"] is False
    assert control_replay["is_natural_yield_measurement"] is False
    assert control_stage["status"] == "native_relation_found"
    assert control_replay["status"] == "PASS"
    assert control_replay["native_relation_independently_verified"] is True
    assert control_replay["four_recovered_points_in_exact_q1325_factor_base"] is True
    assert control_replay["native_receipt_sha256"] == sha(control_stage_path)
    assert control_replay["native_build_receipt_sha256"] == sha(native_build_path)
    assert control_stage["native_source_sha256"] == native_build[
        "source_sha256"]
    assert control_stage["sampling"]["orientations_per_state"] == 83
    assert control_stage["index_pair_states_examined"] == 2_000_000
    assert control_stage["verified_single_target_dlp"] is False
    assert control_stage["complete_work_log2"] is None
    q1329_control = {
        "proposal_id": "Q1329",
        "parent_solver_proposal_id": "Q1328",
        "parent_factor_base_proposal_id": "Q1325",
        "candidate_id": None,
        "run_id": None,
        "curve_id": control_stage["curve_id"],
        "workload_id": control_stage["workload_id"],
        "target_count": 1,
        "target_policy": "one planted target used only as a correctness control",
        "isogeny": "none",
        "actual_usable_points_B": control_stage["actual_usable_points_B"],
        "folded_columns_K": control_stage["folded_columns_K"],
        "status": control_stage["status"],
        "is_known_satisfiable_planted_control": True,
        "solver_received_no_witness_or_index_positions": True,
        "is_natural_relation_yield_measurement": False,
        "index_pair_states_examined": control_stage[
            "index_pair_states_examined"],
        "target_states_scanned": control_stage["target_states_scanned"],
        "target_state_orientations_tested": control_stage[
            "target_state_orientations_tested"],
        "target_pdp_and_native_check_wall_seconds_exploratory": (
            int(control_stage["timing_ns"]["target_pdp_and_native_check"]) / 1e9),
        "peak_rss_bytes": control_stage["peak_rss_bytes"],
        "operation_counts_by_phase": control_stage["operation_counts"],
        "native_relation_independently_verified": True,
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "fixture_sha256": sha(control_fixture_path),
        "manifest_sha256": sha(control_manifest_path),
        "native_receipt_sha256": sha(control_stage_path),
        "independent_replay_receipt_sha256": sha(control_replay_path),
    }
    batch_protocol_path = HERE / "q1330_q1331_batch_root_protocol.json"
    batch_protocol = json.loads(batch_protocol_path.read_text())
    assert batch_protocol["candidate_id"] is None
    assert batch_protocol["parent_stage_protocol_sha256"] == sha(
        native_protocol_path)
    assert batch_protocol["native_source_sha256"] == native_build[
        "source_sha256"]
    assert batch_protocol["point_decomposition"]["stage_code"] == "PDP4root"
    batch_stages = []
    for n, proposal, parent, stage_name in (
        (53, "Q1330", "Q1327", "n53_batch_root_full.json"),
        (83, "Q1331", "Q1328", "n83_batch_root_capped_2m.json"),
    ):
        profile = next(row for row in batch_protocol["profiles"]
                       if row["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_batch_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        stage_path, stage = read(stage_name)
        replay_path, replay = read(
            f"n{n}_batch_root_independent_replay.json")
        scalar = next(row for row in native_root_stages
                      if row["field_degree"] == n)
        assert profile["proposal_id"] == manifest["proposal_id"] == (
            stage["proposal_id"])
        assert profile["proposal_id"] == replay["proposal_id"] == proposal
        assert profile["parent_solver_proposal_id"] == manifest[
            "parent_solver_proposal_id"] == parent
        assert manifest["stage_protocol_sha256"] == stage[
            "stage_protocol_sha256"] == sha(batch_protocol_path)
        assert manifest["s3_batch_size"] == stage["s3_batch_size"] == 4096
        assert stage["native_source_sha256"] == native_build[
            "source_sha256"]
        assert stage["candidate_id"] is None
        assert stage["verified_single_target_dlp"] is False
        assert stage["complete_work_log2"] is None
        assert replay["ordinary_relation_independently_verified"] is (
            n == 53)
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["native_build_receipt_sha256"] == sha(native_build_path)
        assert replay["matched_scalar_stage_sha256"] == scalar[
            "source_bound_native_receipt_sha256"]
        assert stage["curve_id"] == scalar["curve_id"]
        assert stage["workload_id"] == scalar["workload_id"]
        assert stage["index_pair_states_examined"] == scalar[
            "index_pair_states_examined"]
        assert stage["target_states_scanned"] == scalar[
            "target_states_scanned"]
        batch_stages.append({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent,
            "parent_factor_base_proposal_id": profile[
                "parent_factor_base_proposal_id"],
            "candidate_id": None,
            "run_id": None,
            "curve_id": stage["curve_id"],
            "workload_id": stage["workload_id"],
            "target_count": 1,
            "target_policy": "one frozen ordinary public target; no target batching",
            "measurement_scope": "target-dependent PDP and native relation-check stage only",
            "isogeny": "none",
            "field_degree": n,
            "actual_usable_points_B": stage["actual_usable_points_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "status": stage["status"],
            "s3_batch_size": 4096,
            "target_local_inversion_window_states": 4096,
            "window_scope": "groups S3 root-equation field arithmetic for this one target; it is not a target batch",
            "index_pair_states_examined": stage[
                "index_pair_states_examined"],
            "target_states_scanned": stage["target_states_scanned"],
            "target_states_prepared": stage["target_states_prepared"],
            "target_state_orientations_tested": stage[
                "target_state_orientations_tested"],
            "target_state_orientations_prepared": stage[
                "target_state_orientations_prepared"],
            "target_pdp_and_native_check_wall_seconds_exploratory": (
                int(stage["timing_ns"]["target_pdp_and_native_check"]) / 1e9),
            "window_1_target_stage_wall_seconds_exploratory": scalar[
                "target_pdp_and_native_check_wall_seconds_exploratory"],
            "target_stage_ratio_vs_window_1_exploratory": (
                scalar["target_pdp_and_native_check_wall_seconds_exploratory"] /
                (int(stage["timing_ns"]["target_pdp_and_native_check"]) /
                 1e9)),
            "index_build_wall_seconds_exploratory": (
                int(stage["timing_ns"]["index_build"]) / 1e9),
            "peak_rss_bytes": stage["peak_rss_bytes"],
            "operation_counts_by_phase": stage["operation_counts"],
            "matched_scalar_operation_counts_by_phase": scalar[
                "operation_counts_by_phase"],
            "verified_ordinary_relation_count": int(n == 53),
            "observed_rank_of_native_and_matched_pair_rows": (
                replay["rank_of_native_and_matched_pair_rows"]
                if n == 53 else None),
            "natural_relation_yield_rate_estimate": None,
            "common_field_operation_equivalent_calibration": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "stage_receipt_sha256": sha(stage_path),
            "replay_receipt_sha256": sha(replay_path),
            "manifest_sha256": sha(manifest_path),
        })
    q1332_protocol_path = HERE / "q1332_batch_planted_control_protocol.json"
    q1332_protocol = json.loads(q1332_protocol_path.read_text())
    q1332_manifest_path = HERE / "native_inputs/n83_batch_planted_manifest.json"
    q1332_manifest = json.loads(q1332_manifest_path.read_text())
    q1332_stage_path, q1332_stage = read(
        "n83_q1332_batch_planted_unpinned.json")
    q1332_replay_path, q1332_replay = read(
        "n83_q1332_batch_planted_independent_replay.json")
    assert q1332_protocol["proposal_id"] == q1332_manifest[
        "proposal_id"] == q1332_stage["proposal_id"] == q1332_replay[
            "proposal_id"] == "Q1332"
    assert q1332_protocol["parent_solver_proposal_id"] == "Q1331"
    assert q1332_protocol["planted_fixture_sha256"] == sha(
        control_fixture_path)
    assert q1332_protocol["native_source_sha256"] == native_build[
        "source_sha256"]
    assert q1332_stage["relation"] == control_stage["relation"]
    assert q1332_replay["native_relation_independently_verified"] is True
    assert q1332_replay["is_natural_yield_measurement"] is False
    assert q1332_replay["native_receipt_sha256"] == sha(q1332_stage_path)
    assert q1332_stage["verified_single_target_dlp"] is False
    assert q1332_stage["complete_work_log2"] is None
    q1332_control = {
        "proposal_id": "Q1332",
        "parent_solver_proposal_id": "Q1331",
        "parent_planted_control_proposal_id": "Q1329",
        "candidate_id": None,
        "run_id": None,
        "curve_id": q1332_stage["curve_id"],
        "workload_id": q1332_stage["workload_id"],
        "target_count": 1,
        "target_policy": "one planted target used only as a correctness control",
        "isogeny": "none",
        "s3_batch_size": 4096,
        "target_local_inversion_window_states": 4096,
        "window_scope": "groups S3 root-equation field arithmetic for this one target; it is not a target batch",
        "status": q1332_stage["status"],
        "index_pair_states_examined": q1332_stage[
            "index_pair_states_examined"],
        "target_states_scanned": q1332_stage["target_states_scanned"],
        "target_states_prepared": q1332_stage["target_states_prepared"],
        "target_state_orientations_tested": q1332_stage[
            "target_state_orientations_tested"],
        "target_state_orientations_prepared": q1332_stage[
            "target_state_orientations_prepared"],
        "target_pdp_and_native_check_wall_seconds_exploratory": (
            int(q1332_stage["timing_ns"]["target_pdp_and_native_check"]) / 1e9),
        "peak_rss_bytes": q1332_stage["peak_rss_bytes"],
        "is_natural_relation_yield_measurement": False,
        "native_relation_independently_verified": True,
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(q1332_protocol_path),
        "manifest_sha256": sha(q1332_manifest_path),
        "stage_receipt_sha256": sha(q1332_stage_path),
        "replay_receipt_sha256": sha(q1332_replay_path),
    }
    coverage_path, coverage = read(
        "n83_q1331_uniform_target_coverage_bound.json")
    q1331_stage = next(row for row in batch_stages
                       if row["proposal_id"] == "Q1331")
    assert coverage["proposal_id"] == q1331_stage["proposal_id"]
    assert coverage["candidate_id"] is None and coverage["run_id"] is None
    assert coverage["isogeny"] == q1331_stage["isogeny"] == "none"
    assert coverage["curve_id"] == q1331_stage["curve_id"]
    assert coverage["workload_id"] == q1331_stage["workload_id"]
    assert coverage["factor_base_actual_B"] == q1331_stage[
        "actual_usable_points_B"]
    assert coverage["factor_base_folded_columns_K"] == q1331_stage[
        "folded_columns_K"]
    assert coverage["fixed_index_pair_states_M"] == q1331_stage[
        "index_pair_states_examined"]
    assert coverage["q1331_stage_receipt_sha256"] == q1331_stage[
        "stage_receipt_sha256"]
    assert coverage["source_sha256"] == sha(
        HERE / "screen_q1331_target_coverage.py")
    assert coverage["q1330_q1331_protocol_sha256"] == sha(
        batch_protocol_path)
    assert coverage["is_empirical_relation_yield"] is False
    assert coverage["is_complete_solve_projection"] is False
    primitives_path, primitives = read(
        "n53_n83_s3_primitive_field_calls.json")
    assert primitives["kind"] == (
        "source_level_primitive_field_call_expansion_for_s3_stages")
    assert primitives["source_sha256"] == sha(
        HERE / "derive_s3_primitive_calls.py")
    assert primitives["native_build_receipt_sha256"] == sha(
        native_build_path)
    assert primitives["field_implementation_source_sha256"] == (
        native_build["crypto_arithmetic_sources_sha256"][
            "src/cryptanalysis/semaev_decomp.rs"])
    assert [row["proposal_id"] for row in primitives["rows"]] == [
        "Q1327", "Q1330", "Q1328", "Q1331"]
    assert primitives["is_common_weighted_field_operation_unit"] is False
    assert primitives["is_complete_solve_projection"] is False
    q1400_protocol_path = HERE / "q1400_pair_protocol.json"
    q1400_protocol = json.loads(q1400_protocol_path.read_text())
    q1400_input_path = HERE / "native_inputs/n83_q1400_pair_manifest.json"
    q1400_input = json.loads(q1400_input_path.read_text())
    q1400_build_path = HERE / "native_q1400_pair_build_receipt.json"
    q1400_build = json.loads(q1400_build_path.read_text())
    q1400_stage_path, q1400_stage = read("n83_q1400_pair_comparator.json")
    q1331_run_path, q1331_run = read("n83_batch_root_capped_2m.json")
    q1401_protocol_path = HERE / "q1401_pair_control_protocol.json"
    q1401_protocol = json.loads(q1401_protocol_path.read_text())
    q1401_fixture_path, q1401_fixture = read(
        "n83_q1401_pair_planted_fixture.json")
    q1401_stage_path, q1401_stage = read(
        "n83_q1401_pair_planted_native.json")
    q1401_replay_path, q1401_replay = read(
        "n83_q1401_pair_planted_independent_replay.json")
    assert q1400_protocol["proposal_id"] == q1400_input[
        "proposal_id"] == q1400_build["proposal_id"] == q1400_stage[
            "proposal_id"] == "Q1400"
    assert q1400_protocol["curve_id"] == q1400_input[
        "curve_id"] == q1400_stage["curve_id"] == q1331_stage["curve_id"]
    assert q1400_protocol["workload_id"] == q1400_stage[
        "workload_id"] == q1331_stage["workload_id"]
    assert q1400_protocol["factor_base_enumerated_set_sha256"] == q1400_stage[
        "factor_base_enumerated_set_sha256"] == q1331_run[
            "factor_base_enumerated_set_sha256"]
    assert q1400_stage["status"] == "no_exact_hit_at_cap"
    assert q1400_stage["native_output"]["exact_hit_keys"] == 0
    assert q1400_stage["matched_s3_stage_receipt_sha256"] == q1331_stage[
        "stage_receipt_sha256"]
    assert q1331_stage["stage_receipt_sha256"] == sha(q1331_run_path)
    assert q1400_stage["stage_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1400_stage["input_manifest_sha256"] == sha(q1400_input_path)
    assert q1400_stage["native_build_receipt_sha256"] == sha(q1400_build_path)
    assert q1400_stage["source_sha256"] == sha(
        HERE / "run_q1400_pair_comparator.py")
    assert q1401_protocol["proposal_id"] == q1401_fixture[
        "proposal_id"] == q1401_stage["proposal_id"] == q1401_replay[
            "proposal_id"] == "Q1401"
    assert q1401_protocol["parent_solver_proposal_id"] == "Q1400"
    assert q1401_protocol["workload_id"] == q1401_fixture[
        "workload_id"] == q1401_replay["workload_id"]
    assert q1401_stage["status"] == "native_hit_pending_independent_replay"
    assert q1401_replay["status"] == "PASS"
    assert q1401_replay["verified_relation_count"] >= 1
    assert all(hit["target_sum_verified"] and hit[
        "four_distinct_signed_frobenius_columns"]
               for hit in q1401_replay["verified_hits"])
    assert q1401_replay["native_receipt_sha256"] == sha(q1401_stage_path)
    assert q1401_replay["fixture_sha256"] == sha(q1401_fixture_path)
    assert q1401_replay["source_sha256"] == sha(
        HERE / "verify_q1401_pair_control.py")
    q1400_pdp = q1400_protocol["point_decomposition"]
    q1400_order = int(q1400_input["subgroup_order_r"])
    q1400_support_cap = ((2 * 83 * q1400_pdp["table_descriptors"])
                         * (2 * 83 * q1400_pdp["query_representatives"]))
    with localcontext() as decimal_context:
        decimal_context.prec = 35
        q1400_coverage_text = f"{Decimal(q1400_support_cap) / Decimal(q1400_order - 1):.14E}"
    q1402_path, q1402 = read("n83_n131_q1402_fixed_pair_family_screen.json")
    assert q1402["proposal_id"] == "Q1402"
    assert q1402["parent_stage_proposal_id"] == "Q1400"
    assert q1402["n131_factor_base_proposal_id"] == "Q1303"
    assert q1402["candidate_id"] is None and q1402["run_id"] is None
    assert q1402["isogeny"] == "none"
    assert q1402["source_sha256"] == sha(
        HERE / "screen_q1402_fixed_pair_family.py")
    assert q1402["q1400_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1402["q1400_ordinary_stage_sha256"] == sha(q1400_stage_path)
    assert q1402["n131_protocol_sha256"] == sha(protocol_path)
    assert q1402["n131_sample_sha256"] == sha(n131_sample_path)
    assert q1402["n131_independent_sample_replay_sha256"] == sha(
        n131_replay_path)
    assert q1402["n83_exact_q1325_measured_rectangle"][
        "support_ceiling"][
            "uniform_nonidentity_target_support_numerator_cap"] == (
                q1400_support_cap)
    assert q1402["n131_conditional_q1303_full_table"]["subgroup_order_r"] == (
        protocol["degree_131_design"]["curve"]["subgroup_order"])
    assert q1402["is_empirical_relation_yield"] is False
    assert q1402["is_complete_solve_projection"] is False
    assert q1402["challenge_dispatch_allowed"] is False
    q1400_calls_path, q1400_calls = read(
        "n83_q1400_primitive_field_calls.json")
    assert q1400_calls["proposal_id"] == "Q1400"
    assert q1400_calls["candidate_id"] is None
    assert q1400_calls["run_id"] is None
    assert q1400_calls["isogeny"] == "none"
    assert q1400_calls["curve_id"] == q1400_stage["curve_id"]
    assert q1400_calls["workload_id"] == q1400_stage["workload_id"]
    assert q1400_calls["factor_base_enumerated_set_sha256"] == q1400_stage[
        "factor_base_enumerated_set_sha256"]
    assert q1400_calls["source_sha256"] == sha(
        HERE / "derive_q1400_primitive_calls.py")
    assert q1400_calls["q1400_protocol_sha256"] == sha(q1400_protocol_path)
    assert q1400_calls["q1400_stage_receipt_sha256"] == sha(q1400_stage_path)
    assert q1400_calls["q1400_native_build_receipt_sha256"] == sha(
        q1400_build_path)
    assert q1400_calls["target_dependent_phase_sum_including_untimed_frobenius"][
        "expanded_primitive_field_mul_calls"] == 16_901_576
    assert q1400_calls["target_dependent_phase_sum_including_untimed_frobenius"][
        "expanded_primitive_field_sqr_calls"] == 4_944_328
    assert q1400_calls["wall_timing_boundary"][
        "all_target_dependent_wall_seconds"] is None
    assert q1400_calls["is_common_weighted_field_operation_unit"] is False
    assert q1400_calls["is_complete_solve_projection"] is False
    q1403_protocol_path = HERE / "q1403_ordered_q1325_protocol.json"
    q1403_protocol = json.loads(q1403_protocol_path.read_text())
    q1403_runtime_path = HERE / "q1403_sage_runtime_info.json"
    q1403_replay_path, q1403_replay = read(
        "n83_q1403_ordered_control_replay.json")
    assert q1403_protocol["proposal_id"] == q1403_replay[
        "proposal_id"] == "Q1403"
    assert q1403_protocol["parent_factor_base_proposal_id"] == "Q1325"
    assert q1403_protocol["curve_id"] == q1325_protocol["curve"]["curve_id"]
    assert q1403_protocol["ordinary_workload_id"] == q1325_protocol[
        "ordinary_workload_id"]
    assert q1403_protocol["factor_base_enumerated_set_sha256"] == q1325_fb[
        "enumerated_set_sha256"]
    assert q1403_protocol["factor_base_actual_B"] == q1325_b
    assert q1403_protocol["factor_base_folded_columns"] == q1325_fb[
        "signed_frobenius_columns"]
    assert q1403_replay["status"] == "PASS"
    assert q1403_replay["verified_control_relation_count"] == 1
    assert q1403_replay["ordinary_relation_count"] == 0
    assert q1403_replay["protocol_sha256"] == sha(q1403_protocol_path)
    assert q1403_replay["source_sha256"] == sha(
        HERE / "verify_q1403_ordered_control.py")
    q1403_comparison_path, q1403_comparison = read(
        "n83_q1325_q1403_named_stage_comparison.json")
    assert q1403_comparison["source_sha256"] == sha(
        HERE / "build_q1403_stage_comparison.py")
    assert q1403_comparison["curve_id"] == q1403_protocol["curve_id"]
    assert q1403_comparison["workload_id"] == q1403_protocol[
        "ordinary_workload_id"]
    assert [profile["proposal_id"] for profile in q1403_comparison[
        "stage_profiles"]] == ["Q1325", "Q1403"]
    q1403_stages = []
    for mode, expected_status in (
        ("planted_locked", "sat"),
        ("planted_unpinned", "external_timeout"),
        ("ordinary", "external_timeout"),
    ):
        stage_path, stage = read(f"n83_q1403_{mode}.json")
        assert stage["proposal_id"] == "Q1403"
        assert stage["status"] == expected_status
        assert stage["protocol_sha256"] == sha(q1403_protocol_path)
        assert stage["runtime_info_sha256"] == sha(q1403_runtime_path)
        assert stage["complete_solve_work_log2"] is None
        q1403_stages.append({
            "mode": mode,
            "workload_id": stage["workload_id"],
            "status": stage["status"],
            "solver_conflicts_reported": stage[
                "solver_conflicts_reported"],
            "target_pdp_wall_seconds_exploratory": stage[
                "target_pdp_wall_seconds"],
            "target_relation_check_wall_seconds_exploratory": stage[
                "target_relation_check_wall_seconds"],
            "control_pdp_wall_seconds_exploratory": stage[
                "control_pdp_wall_seconds"],
            "formula": stage["formula"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "receipt_sha256": sha(stage_path),
        })
    q1404_protocol_path = HERE / "q1404_raw_preimage_w5_protocol.json"
    q1404_protocol = json.loads(q1404_protocol_path.read_text())
    q1404_runtime_path = HERE / "q1404_sage_runtime_info.json"
    q1404_replay_path, q1404_replay = read(
        "n83_q1404_raw_control_replay.json")
    q1404_comparison_path, q1404_comparison = read(
        "n83_q1325_q1404_named_stage_comparison.json")
    assert q1404_protocol["proposal_id"] == q1404_replay[
        "proposal_id"] == "Q1404"
    assert q1404_protocol["parent_factor_base_proposal_id"] == "Q1325"
    assert q1404_protocol["curve_id"] == q1325_protocol["curve"]["curve_id"]
    assert q1404_protocol["ordinary_workload_id"] == q1325_protocol[
        "ordinary_workload_id"]
    assert q1404_protocol["factor_base_enumerated_set_sha256"] == q1325_fb[
        "enumerated_set_sha256"]
    assert q1404_protocol["factor_base_actual_B"] == q1325_b
    assert q1404_protocol["factor_base_folded_columns"] == q1325_fb[
        "signed_frobenius_columns"]
    assert q1404_replay["status"] == "PASS"
    assert q1404_replay["verified_control_relation_count"] == 1
    assert q1404_replay["ordinary_relation_count"] == 0
    assert q1404_replay["four_distinct_columns"] is True
    assert q1404_replay["protocol_sha256"] == sha(q1404_protocol_path)
    assert q1404_replay["source_sha256"] == sha(
        HERE / "verify_q1404_raw_control.py")
    assert q1404_comparison["source_sha256"] == sha(
        HERE / "build_q1404_stage_comparison.py")
    assert q1404_comparison["curve_id"] == q1404_protocol["curve_id"]
    assert q1404_comparison["workload_id"] == q1404_protocol[
        "ordinary_workload_id"]
    assert [profile["proposal_id"] for profile in q1404_comparison[
        "stage_profiles"]] == ["Q1325", "Q1404"]
    q1404_stages = []
    for mode, expected_status in (
        ("planted_locked", "sat"),
        ("planted_unpinned", "external_timeout"),
        ("ordinary", "censored"),
    ):
        stage_path, stage = read(f"n83_q1404_{mode}.json")
        assert stage["proposal_id"] == "Q1404"
        assert stage["status"] == expected_status
        assert stage["protocol_sha256"] == sha(q1404_protocol_path)
        assert stage["runtime_info_sha256"] == sha(q1404_runtime_path)
        assert stage["complete_solve_work_log2"] is None
        q1404_stages.append({
            "mode": mode,
            "workload_id": stage["workload_id"],
            "status": stage["status"],
            "solver_conflicts_reported": stage["attempts"][0][
                "solver_conflicts_reported"],
            "target_preimage_wall_seconds_exploratory": stage[
                "target_preimage_wall_seconds"],
            "target_pdp_wall_seconds_exploratory": stage[
                "target_pdp_wall_seconds"],
            "target_relation_check_wall_seconds_exploratory": stage[
                "target_relation_check_wall_seconds"],
            "target_dependent_stage_wall_seconds_exploratory": stage[
                "target_dependent_stage_wall_seconds"],
            "control_stage_wall_seconds_exploratory": stage[
                "control_stage_wall_seconds"],
            "formula": stage["formula"],
            "peak_parent_rss_raw": stage["peak_parent_rss_raw"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "observed_verified_relation_count": stage[
                "observed_verified_relation_count"],
            "receipt_sha256": sha(stage_path),
        })
    adaptive_protocol_path = HERE / "q1333_q1334_adaptive_window_protocol.json"
    adaptive_protocol = json.loads(adaptive_protocol_path.read_text())
    adaptive_build_path = HERE / "native_adaptive_build_receipt.json"
    adaptive_build = json.loads(adaptive_build_path.read_text())
    assert adaptive_protocol["native_source_sha256"] == adaptive_build[
        "source_sha256"] == sha(HERE / "native_s3_root_adaptive.rs")
    assert adaptive_build["build_script_sha256"] == sha(
        HERE / "build_native_s3_root_adaptive.py")
    adaptive_schedule = [1, 16, 64, 256, 1024, 4096]
    assert adaptive_protocol["target_count"] == 1
    assert adaptive_protocol["target_s3_window_schedule"] == adaptive_schedule
    adaptive_stages = []
    for n, proposal, parent, status, stage_name in (
        (53, "Q1333", "Q1330", "native_relation_found",
         "n53_adaptive_root_full.json"),
        (83, "Q1334", "Q1331", "state_cap_no_relation",
         "n83_adaptive_root_capped_2m.json"),
    ):
        profile = next(row for row in adaptive_protocol["profiles"]
                       if row["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_adaptive_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        stage_path, stage = read(stage_name)
        replay_path, replay = read(
            f"n{n}_adaptive_root_independent_replay.json")
        fixed = next(row for row in batch_stages
                     if row["field_degree"] == n)
        fixed_run_path = HERE / "runs" / (
            "n53_batch_root_full.json" if n == 53 else
            "n83_batch_root_capped_2m.json")
        fixed_run = json.loads(fixed_run_path.read_text())
        window_one = next(row for row in native_root_stages
                          if row["field_degree"] == n)
        assert profile["proposal_id"] == manifest["proposal_id"] == (
            stage["proposal_id"]) == replay["proposal_id"] == proposal
        assert profile["parent_solver_proposal_id"] == manifest[
            "parent_solver_proposal_id"] == replay[
                "parent_solver_proposal_id"] == parent
        assert profile["target_count"] == manifest["target_count"] == (
            stage["target_count"]) == replay["target_count"] == 1
        assert profile["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"] == stage[
                "target_s3_window_schedule"] == adaptive_schedule
        assert manifest["stage_protocol_sha256"] == stage[
            "stage_protocol_sha256"] == sha(adaptive_protocol_path)
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_adaptive_window_protocol.py")
        assert stage["native_source_sha256"] == adaptive_build[
            "source_sha256"]
        assert stage["cargo_manifest_sha256"] == adaptive_build[
            "cargo_manifest_sha256"]
        assert stage["status"] == replay["native_stage_status"] == status
        for key in ("curve_id", "workload_id", "actual_usable_points_B",
                    "folded_columns_K", "index_pair_states_examined",
                    "index_distinct_root_keys", "target_states_scanned",
                    "target_table_hits", "relation", "status"):
            assert stage[key] == fixed_run[key]
        assert replay["status"] == "PASS"
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["native_build_receipt_sha256"] == sha(
            adaptive_build_path)
        assert replay["matched_fixed_window_stage_sha256"] == fixed[
            "stage_receipt_sha256"]
        assert replay["ordinary_relation_independently_verified"] is (n == 53)
        assert stage["verified_single_target_dlp"] is False
        assert stage["complete_work_log2"] is None
        window = int(stage["timing_ns"]["target_pdp_and_native_check"])
        adaptive_stages.append({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent,
            "candidate_id": None,
            "run_id": None,
            "curve_id": stage["curve_id"],
            "workload_id": stage["workload_id"],
            "target_count": 1,
            "target_policy": "one frozen ordinary public target; no target batching",
            "target_local_inversion_window_schedule": adaptive_schedule,
            "measurement_scope": "target-dependent PDP and native relation-check stage only",
            "field_degree": n,
            "actual_usable_points_B": stage["actual_usable_points_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "status": status,
            "target_states_scanned": stage["target_states_scanned"],
            "target_states_prepared": stage["target_states_prepared"],
            "target_state_orientations_tested": stage[
                "target_state_orientations_tested"],
            "target_state_orientations_prepared": stage[
                "target_state_orientations_prepared"],
            "target_stage_wall_seconds_exploratory": window / 1e9,
            "ratio_vs_window_1_exploratory": (
                window_one["target_pdp_and_native_check_wall_seconds_exploratory"] /
                (window / 1e9)),
            "ratio_vs_fixed_window_4096_exploratory": (
                fixed["target_pdp_and_native_check_wall_seconds_exploratory"] /
                (window / 1e9)),
            "fixed_window_4096_stage_wall_seconds_exploratory": fixed[
                "target_pdp_and_native_check_wall_seconds_exploratory"],
            "window_1_stage_wall_seconds_exploratory": window_one[
                "target_pdp_and_native_check_wall_seconds_exploratory"],
            "operation_counts_by_phase": stage["operation_counts"],
            "verified_ordinary_relation_count": int(n == 53),
            "natural_relation_yield_rate_estimate": None,
            "common_field_operation_equivalent_calibration": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "stage_receipt_sha256": sha(stage_path),
            "replay_receipt_sha256": sha(replay_path),
            "manifest_sha256": sha(manifest_path),
        })
    adaptive_planted_path = HERE / "native_inputs/n83_adaptive_planted_manifest.json"
    adaptive_planted = json.loads(adaptive_planted_path.read_text())
    adaptive_planted_stage_path, adaptive_planted_stage = read(
        "n83_q1335_adaptive_planted_unpinned.json")
    adaptive_planted_replay_path, adaptive_planted_replay = read(
        "n83_q1335_adaptive_planted_independent_replay.json")
    adaptive_control_profile = adaptive_protocol["planted_control"]
    assert adaptive_control_profile["proposal_id"] == adaptive_planted[
        "proposal_id"] == adaptive_planted_stage["proposal_id"] == (
            adaptive_planted_replay["proposal_id"]) == "Q1335"
    assert adaptive_control_profile["target_count"] == adaptive_planted[
        "target_count"] == adaptive_planted_stage["target_count"] == (
            adaptive_planted_replay["target_count"]) == 1
    assert adaptive_planted["target_s3_window_schedule"] == (
        adaptive_planted_stage["target_s3_window_schedule"]) == (
            adaptive_schedule)
    assert adaptive_planted_stage["relation"] == q1332_stage["relation"]
    assert adaptive_planted_stage["target_states_scanned"] == 1
    assert adaptive_planted_stage["target_states_prepared"] == 1
    assert adaptive_planted_stage["target_state_orientations_tested"] == 34
    assert adaptive_planted_stage["target_state_orientations_prepared"] == 83
    assert adaptive_planted_stage["verified_single_target_dlp"] is False
    assert adaptive_planted_replay["status"] == "PASS"
    assert adaptive_planted_replay[
        "native_relation_independently_verified"] is True
    q1335_control = {
        "proposal_id": "Q1335",
        "parent_solver_proposal_id": "Q1334",
        "parent_planted_control_proposal_id": "Q1329",
        "candidate_id": None,
        "run_id": None,
        "curve_id": adaptive_planted_stage["curve_id"],
        "workload_id": adaptive_planted_stage["workload_id"],
        "target_count": 1,
        "target_policy": "one planted target used only as an early-hit and correctness control",
        "target_local_inversion_window_schedule": adaptive_schedule,
        "target_states_scanned": adaptive_planted_stage[
            "target_states_scanned"],
        "target_states_prepared": adaptive_planted_stage[
            "target_states_prepared"],
        "target_state_orientations_tested": adaptive_planted_stage[
            "target_state_orientations_tested"],
        "target_state_orientations_prepared": adaptive_planted_stage[
            "target_state_orientations_prepared"],
        "target_pdp_and_native_check_wall_seconds_exploratory": (
            int(adaptive_planted_stage["timing_ns"][
                "target_pdp_and_native_check"]) / 1e9),
        "fixed_window_4096_target_stage_seconds_exploratory": (
            int(q1332_stage["timing_ns"][
                "target_pdp_and_native_check"]) / 1e9),
        "window_1_target_stage_seconds_exploratory": (
            int(control_stage["timing_ns"][
                "target_pdp_and_native_check"]) / 1e9),
        "is_natural_relation_yield_measurement": False,
        "native_relation_independently_verified": True,
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(adaptive_protocol_path),
        "manifest_sha256": sha(adaptive_planted_path),
        "stage_receipt_sha256": sha(adaptive_planted_stage_path),
        "replay_receipt_sha256": sha(adaptive_planted_replay_path),
    }
    fast_protocol_path = HERE / "q1336_q1337_fast_root_protocol.json"
    fast_protocol = json.loads(fast_protocol_path.read_text())
    fast_build_path = HERE / "native_fast_build_receipt.json"
    fast_build = json.loads(fast_build_path.read_text())
    assert fast_protocol["native_source_sha256"] == fast_build[
        "source_sha256"] == sha(HERE / "native_s3_root_fast.rs")
    assert fast_build["build_script_sha256"] == sha(
        HERE / "build_native_s3_root_fast.py")
    assert fast_protocol["target_count"] == 1
    assert fast_protocol["target_s3_window_schedule"] == adaptive_schedule
    fused_stages = []
    for n, proposal, parent, expected_status, stage_name in (
        (53, "Q1336", "Q1333", "native_relation_found",
         "n53_fast_root_full.json"),
        (83, "Q1337", "Q1334", "state_cap_no_relation",
         "n83_fast_root_capped_2m.json"),
    ):
        profile = next(row for row in fast_protocol["profiles"]
                       if row["field_degree"] == n)
        manifest_path = HERE / "native_inputs" / f"n{n}_fast_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        stage_path, stage = read(stage_name)
        replay_path, replay = read(f"n{n}_fast_root_independent_replay.json")
        adaptive_row = next(row for row in adaptive_stages
                            if row["field_degree"] == n)
        adaptive_path = HERE / "runs" / (
            "n53_adaptive_root_full.json" if n == 53 else
            "n83_adaptive_root_capped_2m.json")
        adaptive_run = json.loads(adaptive_path.read_text())
        assert profile["proposal_id"] == manifest["proposal_id"] == (
            stage["proposal_id"]) == replay["proposal_id"] == proposal
        assert profile["parent_solver_proposal_id"] == manifest[
            "parent_solver_proposal_id"] == replay[
                "parent_solver_proposal_id"] == parent
        assert profile["target_count"] == manifest["target_count"] == (
            stage["target_count"]) == replay["target_count"] == 1
        assert manifest["stage_protocol_sha256"] == stage[
            "stage_protocol_sha256"] == sha(fast_protocol_path)
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_fast_root_protocol.py")
        assert manifest["parent_adaptive_input_manifest_sha256"] == sha(
            HERE / "native_inputs" / f"n{n}_adaptive_manifest.json")
        assert stage["native_source_sha256"] == fast_build[
            "source_sha256"]
        assert stage["cargo_manifest_sha256"] == fast_build[
            "cargo_manifest_sha256"]
        assert stage["status"] == replay["native_stage_status"] == (
            expected_status)
        assert stage["verified_single_target_dlp"] is False
        assert stage["complete_work_log2"] is None
        for key in ("curve_id", "workload_id", "actual_usable_points_B",
                    "folded_columns_K", "index_pair_states_examined",
                    "index_distinct_root_keys", "target_states_scanned",
                    "target_states_prepared", "target_root_windows",
                    "target_table_hits", "relation", "status"):
            assert stage[key] == adaptive_run[key]
        ops = stage["operation_counts"]["target_pdp_and_native_check"]
        adaptive_ops = adaptive_run["operation_counts"][
            "target_pdp_and_native_check"]
        assert adaptive_ops["field_mul_calls"] - ops["field_mul_calls"] == (
            ops["s3_root_calls"])
        assert replay["status"] == "PASS"
        assert replay["native_receipt_sha256"] == sha(stage_path)
        assert replay["matched_adaptive_stage_sha256"] == sha(adaptive_path)
        assert replay["native_build_receipt_sha256"] == sha(fast_build_path)
        assert replay["target_field_multiplications"] == ops[
            "field_mul_calls"]
        window = int(stage["timing_ns"]["target_pdp_and_native_check"])
        fused_stages.append({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent,
            "candidate_id": None,
            "run_id": None,
            "curve_id": stage["curve_id"],
            "workload_id": stage["workload_id"],
            "target_count": 1,
            "target_policy": "one frozen ordinary public target; no target batching",
            "measurement_scope": "target-dependent PDP and native relation-check stage only",
            "field_degree": n,
            "status": expected_status,
            "adaptive_target_stage_wall_seconds_exploratory": (
                adaptive_row["target_stage_wall_seconds_exploratory"]),
            "fused_target_stage_wall_seconds_exploratory": window / 1e9,
            "adaptive_over_fused_stage_ratio_exploratory": (
                adaptive_row["target_stage_wall_seconds_exploratory"] /
                (window / 1e9)),
            "paired_single_observation_is_repeatable": False,
            "s3_root_calls": ops["s3_root_calls"],
            "field_mul_calls_adaptive": adaptive_ops["field_mul_calls"],
            "field_mul_calls_fused": ops["field_mul_calls"],
            "field_mul_calls_saved": (adaptive_ops["field_mul_calls"] -
                                      ops["field_mul_calls"]),
            "field_mul_savings_are_exactly_one_per_s3_root": True,
            "operation_counts_by_phase": stage["operation_counts"],
            "ordinary_relation_independently_verified": bool(n == 53),
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "stage_receipt_sha256": sha(stage_path),
            "replay_receipt_sha256": sha(replay_path),
            "manifest_sha256": sha(manifest_path),
        })
    fast_planted_path = HERE / "native_inputs/n83_fast_planted_manifest.json"
    fast_planted = json.loads(fast_planted_path.read_text())
    fast_planted_stage_path, fast_planted_stage = read(
        "n83_q1338_fast_planted_unpinned.json")
    fast_planted_replay_path, fast_planted_replay = read(
        "n83_q1338_fast_planted_independent_replay.json")
    fast_planted_profile = fast_protocol["planted_control"]
    assert fast_planted_profile["proposal_id"] == fast_planted[
        "proposal_id"] == fast_planted_stage["proposal_id"] == (
            fast_planted_replay["proposal_id"]) == "Q1338"
    assert fast_planted_profile["parent_solver_proposal_id"] == (
        fast_planted["parent_solver_proposal_id"]) == "Q1337"
    assert fast_planted["target_count"] == fast_planted_stage[
        "target_count"] == fast_planted_replay["target_count"] == 1
    assert fast_planted["stage_protocol_sha256"] == (
        fast_planted_stage["stage_protocol_sha256"]) == sha(
            fast_protocol_path)
    assert fast_planted_stage["native_source_sha256"] == fast_build[
        "source_sha256"]
    assert fast_planted_stage["relation"] == adaptive_planted_stage[
        "relation"]
    assert fast_planted_stage["status"] == "native_relation_found"
    assert fast_planted_stage["target_states_scanned"] == 1
    assert fast_planted_stage["target_states_prepared"] == 1
    assert fast_planted_stage["target_state_orientations_tested"] == 34
    assert fast_planted_stage["target_state_orientations_prepared"] == 83
    assert fast_planted_replay["status"] == "PASS"
    assert fast_planted_replay[
        "native_relation_independently_verified"] is True
    assert fast_planted_replay["native_receipt_sha256"] == sha(
        fast_planted_stage_path)
    assert fast_planted_replay["native_build_receipt_sha256"] == sha(
        fast_build_path)
    adaptive_planted_ops = adaptive_planted_stage["operation_counts"][
        "target_pdp_and_native_check"]
    fast_planted_ops = fast_planted_stage["operation_counts"][
        "target_pdp_and_native_check"]
    assert adaptive_planted_ops["field_mul_calls"] - fast_planted_ops[
        "field_mul_calls"] == fast_planted_ops["s3_root_calls"]
    fast_planted_control = {
        "proposal_id": "Q1338",
        "parent_solver_proposal_id": "Q1337",
        "parent_planted_control_proposal_id": "Q1329",
        "candidate_id": None,
        "run_id": None,
        "curve_id": fast_planted_stage["curve_id"],
        "workload_id": fast_planted_stage["workload_id"],
        "target_count": 1,
        "target_policy": "one planted target used only as an early-hit and correctness control",
        "target_local_inversion_window_schedule": adaptive_schedule,
        "target_pdp_and_native_check_wall_seconds_exploratory": (
            int(fast_planted_stage["timing_ns"][
                "target_pdp_and_native_check"]) / 1e9),
        "target_field_multiplications_adaptive": adaptive_planted_ops[
            "field_mul_calls"],
        "target_field_multiplications_fused": fast_planted_ops[
            "field_mul_calls"],
        "target_s3_root_calls": fast_planted_ops["s3_root_calls"],
        "is_natural_relation_yield_measurement": False,
        "native_relation_independently_verified": True,
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(fast_protocol_path),
        "manifest_sha256": sha(fast_planted_path),
        "stage_receipt_sha256": sha(fast_planted_stage_path),
        "replay_receipt_sha256": sha(fast_planted_replay_path),
    }
    conditional_root_states131 = n131_sample[
        "conditional_folded_columns_estimate"] ** 2 * 131
    conditional_batch_count131 = (conditional_root_states131 + 4095) // 4096
    conditional_batch_mul131 = 8 * conditional_root_states131 + 3 * (
        conditional_root_states131 - conditional_batch_count131)
    conditional_batch_full_target_mul131 = 16 * conditional_root_states131 + 3 * (
        2 * conditional_root_states131 - conditional_batch_count131)
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
        "four_summand_target_support_screen": {
            "rigorous_bound": support["bound_scope"],
            "poisson_model_scope": support["poisson_scope"],
            "profiles": support["profiles"],
            "receipt_sha256": sha(support_path),
        },
        "q1324_exact_n83_weight5_stage_measurements": q1324_stage,
        "q1324_protocol_sha256": sha(q1324_protocol_path),
        "q1324_independent_full_base_replay": {
            "status": q1324_replay["status"],
            "actual_usable_points_B_before_folding": q1324_replay[
                "actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": q1324_replay[
                "signed_frobenius_columns"],
            "verified_projected_representatives": q1324_replay[
                "verified_projected_representatives"],
            "receipt_sha256": sha(q1324_replay_path),
        },
        "q1325_exact_n83_weight5_base": {
            "proposal_id": "Q1325", "candidate_id": None,
            "curve_id": q1325_base["curve"]["curve_id"],
            "isogeny": "none",
            "normal_basis_weight_bound": 5,
            "nominal_x_mask_count": q1325_fb["nominal_x_mask_count"],
            "geometric_point_count_before_projection": q1325_fb[
                "geometric_point_count_before_projection"],
            "actual_usable_points_B_before_folding": q1325_b,
            "signed_frobenius_columns": q1325_fb[
                "signed_frobenius_columns"],
            "enumerated_set_sha256": q1325_fb["enumerated_set_sha256"],
            "uniform_target_mean_distinct_four_subsets": q1325_mean,
            "is_empirical_relation_yield": False,
            "base_enumeration_wall_seconds": q1325_base[
                "enumeration_wall_seconds"],
            "base_peak_rss_raw": q1325_base["peak_rss_raw"],
            "base_peak_rss_units": q1325_base["peak_rss_units"],
            "point_keys_independently_replayed": q1325_replay[
                "point_keys_replayed_on_curve_and_canonical"],
            "q1041_subset_columns_verified": q1325_replay[
                "q1041_subset_columns_verified"],
            "q1302_weight4_subset_columns_verified": q1325_replay[
                "q1302_weight4_subset_columns_verified"],
            "base_receipt_sha256": sha(q1325_base_path),
            "point_key_file_sha256": sha(q1325_key_path),
            "independent_replay_receipt_sha256": sha(q1325_replay_path),
        },
        "q1325_full_weight5_stage_measurements": q1325_stage,
        "q1325_protocol_sha256": sha(q1325_protocol_path),
        "q1326_nested_n53_stage_measurements": q1326_stages,
        "q1326_ordinary_search_summary": {
            "status": q1326_summary["status"],
            "attempt_count": len(q1326_stages),
            "total_target_pdp_wall_seconds": q1326_summary[
                "total_target_pdp_wall_seconds"],
            "total_target_relation_check_wall_seconds": q1326_summary[
                "total_target_relation_check_wall_seconds"],
            "observed_verified_relation_count": 0,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1326_summary_path),
        },
        "q1326_known_satisfiable_planted_diagnostics": {
            "eligible_actual_B_before_folding": q1326_planted[
                "eligible_actual_B_before_folding"],
            "eligible_folded_columns": q1326_planted[
                "eligible_folded_columns"],
            "same_planted_public_target": q1326_planted["public_target"],
            "locked_status": q1326_planted["status"],
            "locked_verified_relation_count": 1,
            "locked_oracle_control_wall_seconds": q1326_planted[
                "oracle_control_wall_seconds"],
            "unpinned_status": q1326_unpinned["status"],
            "unpinned_solver_conflicts_reported": q1326_unpinned[
                "solver_conflicts_reported"],
            "unpinned_target_pdp_wall_seconds": q1326_unpinned[
                "target_pdp_wall_seconds"],
            "unpinned_peak_child_rss_raw_cumulative": q1326_unpinned[
                "peak_child_rss_raw_cumulative"],
            "unpinned_verified_relation_count": 0,
            "is_natural_relation_yield_estimate": False,
            "locked_receipt_sha256": sha(q1326_planted_path),
            "unpinned_receipt_sha256": sha(q1326_unpinned_path),
        },
        "q1326_post_run_k128_support_diagnostic": {
            "method": q1326_support["method"],
            "status": q1326_support["status"],
            "total_logical_pair_samples": q1326_support[
                "total_logical_pair_samples"],
            "peak_parent_rss_raw": q1326_support["peak_parent_rss_raw"],
            "peak_rss_units": q1326_support["peak_rss_units"],
            "observed_verified_relation_count": 0,
            "proves_target_has_no_representation": False,
            "receipt_sha256": sha(q1326_support_path),
        },
        "q1326_protocol_sha256": sha(q1326_protocol_path),
        "native_onb_polynomial_field_bridges": native_bridge_profiles,
        "q1327_q1328_bounded_native_s3_root_stages": native_root_stages,
        "q1329_n83_unpinned_planted_control": q1329_control,
        "q1330_q1331_single_target_inversion_window_stages": batch_stages,
        "q1332_n83_single_target_inversion_window_planted_control": q1332_control,
        "q1331_fixed_state_uniform_target_coverage_bound": {
            "proposal_id": "Q1331",
            "curve_id": coverage["curve_id"],
            "workload_id": coverage["workload_id"],
            "factor_base_actual_B": coverage["factor_base_actual_B"],
            "factor_base_folded_columns_K": coverage[
                "factor_base_folded_columns_K"],
            "fixed_index_pair_states_M": coverage["fixed_index_pair_states_M"],
            "uniform_target_hit_probability_upper_bound": coverage[
                "uniform_target_hit_probability_upper_bound"],
            "necessary_state_count_thresholds": coverage[
                "necessary_state_count_thresholds"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "receipt_sha256": sha(coverage_path),
        },
        "n53_n83_native_s3_primitive_field_call_vectors": {
            "unit_boundary": primitives["unit_boundary"],
            "is_common_weighted_field_operation_unit": False,
            "is_complete_solve_projection": False,
            "rows": primitives["rows"],
            "receipt_sha256": sha(primitives_path),
        },
        "q1400_matched_n83_q1325_native_pair_table_stage": {
            "proposal_id": "Q1400",
            "candidate_id": None,
            "run_id": None,
            "isogeny": "none",
            "curve_id": q1400_stage["curve_id"],
            "workload_id": q1400_stage["workload_id"],
            "factor_base_actual_B": q1400_stage["factor_base_actual_B"],
            "factor_base_folded_columns_K": q1400_stage[
                "factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": q1400_stage[
                "factor_base_enumerated_set_sha256"],
            "status": q1400_stage["status"],
            "table_descriptors": q1400_stage["table_descriptors_charged"],
            "target_lifted_pair_queries": q1400_stage[
                "target_lifted_pair_queries_charged"],
            "base_export_wall_ns_including_checked_launcher": q1400_stage[
                "base_export_wall_ns_including_checked_launcher"],
            "native_base_load_seconds_exploratory": q1400_stage[
                "native_output"]["base_load_seconds"],
            "table_build_seconds_exploratory": q1400_stage[
                "native_output"]["build_seconds"],
            "target_online_seconds_exploratory": q1400_stage[
                "target_online_seconds_exploratory"],
            "peak_rss_bytes": q1400_stage["peak_rss_bytes"],
            "bloom_positives": q1400_stage["native_output"][
                "bloom_positive_queries"],
            "exact_hit_keys": q1400_stage["native_output"][
                "exact_hit_keys"],
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "uniform_target_support_upper_bound_fixed_rectangle": {
                "numerator_cap": q1400_support_cap,
                "denominator": q1400_order - 1,
                "probability_upper_bound": q1400_coverage_text,
                "is_empirical_relation_yield": False,
            },
            "matched_s3_proposal_id": "Q1331",
            "controlled_wall_speedup_claim_allowed": False,
            "complete_solve_work_log2": None,
            "protocol_sha256": sha(q1400_protocol_path),
            "input_manifest_sha256": sha(q1400_input_path),
            "build_receipt_sha256": sha(q1400_build_path),
            "stage_receipt_sha256": sha(q1400_stage_path),
        },
        "q1401_n83_q1325_native_pair_planted_control": {
            "proposal_id": "Q1401",
            "parent_solver_proposal_id": "Q1400",
            "candidate_id": None,
            "run_id": None,
            "isogeny": "none",
            "curve_id": q1401_replay["curve_id"],
            "workload_id": q1401_replay["workload_id"],
            "status": q1401_replay["status"],
            "native_exact_hit_keys": q1401_stage["native_output"][
                "exact_hit_keys"],
            "independently_verified_four_point_relation_count": q1401_replay[
                "verified_relation_count"],
            "is_natural_relation_yield_measurement": False,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "protocol_sha256": sha(q1401_protocol_path),
            "fixture_sha256": sha(q1401_fixture_path),
            "native_stage_receipt_sha256": sha(q1401_stage_path),
            "independent_replay_receipt_sha256": sha(q1401_replay_path),
        },
        "q1402_fixed_pair_family_counting_screen": {
            "proposal_id": "Q1402",
            "candidate_id": None,
            "run_id": None,
            "isogeny": "none",
            "n83_exact_q1325_measured_rectangle": q1402[
                "n83_exact_q1325_measured_rectangle"],
            "n131_conditional_q1303_full_table": q1402[
                "n131_conditional_q1303_full_table"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "challenge_dispatch_allowed": False,
            "receipt_sha256": sha(q1402_path),
        },
        "q1400_native_pair_primitive_field_call_vectors": {
            "proposal_id": "Q1400",
            "candidate_id": None,
            "run_id": None,
            "curve_id": q1400_calls["curve_id"],
            "workload_id": q1400_calls["workload_id"],
            "phase_call_vectors": q1400_calls["phase_call_vectors"],
            "target_dependent_phase_sum_including_untimed_frobenius": (
                q1400_calls[
                    "target_dependent_phase_sum_including_untimed_frobenius"]),
            "wall_timing_boundary": q1400_calls["wall_timing_boundary"],
            "unit_boundary": q1400_calls["unit_boundary"],
            "is_common_weighted_field_operation_unit": False,
            "is_complete_solve_projection": False,
            "receipt_sha256": sha(q1400_calls_path),
        },
        "q1403_ordered_implicit_q1325_s3_stage": {
            "proposal_id": "Q1403",
            "candidate_id": None,
            "stage_config_id": q1403_comparison["stage_profiles"][1][
                "stage_config_id"],
            "run_id": q1403_comparison["stage_profiles"][1]["run_id"],
            "curve_id": q1403_protocol["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1403_protocol[
                "factor_base_actual_B"],
            "factor_base_folded_columns_K": q1403_protocol[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1403_protocol[
                "factor_base_enumerated_set_sha256"],
            "matched_ordinary_workload_id": q1403_protocol[
                "ordinary_workload_id"],
            "ordered_raw_leaf_rule": q1403_protocol[
                "point_decomposition"]["leaf_rule"],
            "stages": q1403_stages,
            "independently_verified_planted_control_relation_count": (
                q1403_replay["verified_control_relation_count"]),
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1403_protocol_path),
            "runtime_info_sha256": sha(q1403_runtime_path),
            "independent_replay_receipt_sha256": sha(q1403_replay_path),
        },
        "q1325_q1403_named_stage_comparison": {
            "candidate_id": None,
            "curve_id": q1403_comparison["curve_id"],
            "workload_id": q1403_comparison["workload_id"],
            "factor_base_enumerated_set_sha256": q1403_comparison[
                "factor_base_enumerated_set_sha256"],
            "controlled_variable": q1403_comparison[
                "controlled_variable"],
            "profiles": [{
                "proposal_id": profile["proposal_id"],
                "stage_config_id": profile["stage_config_id"],
                "run_id": profile["run_id"],
                "ordinary_stage_status": profile[
                    "ordinary_stage_status"],
                "observed_verified_relation_count": profile[
                    "observed_verified_relation_count"],
            } for profile in q1403_comparison["stage_profiles"]],
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1403_comparison_path),
        },
        "q1404_raw_preimage_w5_s3_stage": {
            "proposal_id": "Q1404",
            "candidate_id": None,
            "stage_config_id": q1404_comparison["stage_profiles"][1][
                "stage_config_id"],
            "run_id": q1404_comparison["stage_profiles"][1]["run_id"],
            "curve_id": q1404_protocol["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1404_protocol[
                "factor_base_actual_B"],
            "factor_base_folded_columns_K": q1404_protocol[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1404_protocol[
                "factor_base_enumerated_set_sha256"],
            "matched_ordinary_workload_id": q1404_protocol[
                "ordinary_workload_id"],
            "target_preimage_rule": q1404_protocol[
                "point_decomposition"]["target_rule"],
            "stages": q1404_stages,
            "independently_verified_planted_control_relation_count": (
                q1404_replay["verified_control_relation_count"]),
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1404_protocol_path),
            "runtime_info_sha256": sha(q1404_runtime_path),
            "independent_replay_receipt_sha256": sha(q1404_replay_path),
        },
        "q1325_q1404_named_stage_comparison": {
            "candidate_id": None,
            "curve_id": q1404_comparison["curve_id"],
            "workload_id": q1404_comparison["workload_id"],
            "factor_base_enumerated_set_sha256": q1404_comparison[
                "factor_base_enumerated_set_sha256"],
            "controlled_variable": q1404_comparison[
                "controlled_variable"],
            "profiles": [{
                "proposal_id": profile["proposal_id"],
                "stage_config_id": profile["stage_config_id"],
                "run_id": profile["run_id"],
                "ordinary_stage_status": profile[
                    "ordinary_stage_status"],
                "observed_verified_relation_count": profile[
                    "observed_verified_relation_count"],
            } for profile in q1404_comparison["stage_profiles"]],
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1404_comparison_path),
        },
        "q1333_q1334_adaptive_single_target_window_stages": adaptive_stages,
        "q1335_n83_adaptive_single_target_planted_control": q1335_control,
        "q1336_q1337_fused_root_single_target_stages": fused_stages,
        "q1338_n83_fused_root_planted_control": fast_planted_control,
        "q1327_q1328_native_root_protocol_sha256": sha(
            native_protocol_path),
        "q1330_q1331_batch_root_protocol_sha256": sha(batch_protocol_path),
        "q1333_q1334_adaptive_window_protocol_sha256": sha(
            adaptive_protocol_path),
        "q1336_q1337_fused_root_protocol_sha256": sha(fast_protocol_path),
        "native_s3_root_build_receipt_sha256": sha(native_build_path),
        "native_s3_adaptive_build_receipt_sha256": sha(adaptive_build_path),
        "native_s3_fused_root_build_receipt_sha256": sha(fast_build_path),
        "degree131_conditional_full_s3_root_index_screen": {
            "proposal_id": "Q1303",
            "candidate_id": None,
            "condition": "Q1303 W<=6 folded-column estimate and a complete K^2*n pair-root index like Q1327, without base or key collisions credited",
            "folded_columns_estimate_not_exact": n131_sample[
                "conditional_folded_columns_estimate"],
            "pair_state_count_estimate": conditional_root_states131,
            "pair_state_count_log2": math.log2(
                conditional_root_states131),
            "same_non_degenerate_root_kernel_assumption": (
                "one S3 root call per pair state, with eight top-level field multiplications and one top-level inversion as observed on the N83 capped stage; excludes batch inversion and alternative root kernels"),
            "conditional_index_field_mul_calls": (
                8 * conditional_root_states131),
            "conditional_index_field_mul_calls_log2": math.log2(
                8 * conditional_root_states131),
            "conditional_index_field_inv_calls": (
                conditional_root_states131),
            "conditional_index_field_inv_calls_log2": math.log2(
                conditional_root_states131),
            "conditional_target_local_inversion_window_4096_screen": {
                "proposal_ids_measured_at_n53_n83": ["Q1330", "Q1331"],
                "target_count": 1,
                "assumption": "same nondegenerate two-root S3 path as the measured N83 run, exact Q1303 K estimate, one complete K^2*n index and a 4096-state field-arithmetic inversion window for the single target; no target batching, claim about earlier hits, collisions, base construction, or alternative solvers",
                "index_root_batches_estimate": conditional_batch_count131,
                "index_field_mul_calls_estimate": conditional_batch_mul131,
                "index_field_mul_calls_log2": math.log2(
                    conditional_batch_mul131),
                "index_field_inv_calls_estimate": conditional_batch_count131,
                "index_field_inv_calls_log2": math.log2(
                    conditional_batch_count131),
                "one_full_target_scan_field_mul_calls_estimate": (
                    conditional_batch_full_target_mul131),
                "one_full_target_scan_field_mul_calls_log2": math.log2(
                    conditional_batch_full_target_mul131),
                "index_plus_one_full_target_scan_field_mul_calls_estimate": (
                    conditional_batch_mul131 +
                    conditional_batch_full_target_mul131),
                "index_plus_one_full_target_scan_field_mul_calls_log2": math.log2(
                    conditional_batch_mul131 +
                    conditional_batch_full_target_mul131),
                "is_complete_solve_projection": False,
                "is_lower_bound_on_other_solver_families": False,
            },
            "full_index_memory_estimate_bytes": None,
            "field_operation_equivalent_calibration": None,
            "is_lower_bound_on_other_solver_families": False,
            "is_complete_solve_projection": False,
        },
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
            "reason_unestimated": (
                "Q1327, Q1330, and Q1333 independently verified the same unassisted "
                "ordinary n53 four-point relation and a nonzero row "
                "independent of the matched pair-table row; Q1328, Q1331, Q1334, and Q1337 "
                "both exhausted the same 2,000,000-pair-state n83 ordinary "
                "cap without a relation, covering only about 6.9e-7 of the "
                "full quotient pair-state space; the exact fixed-state "
                "counting screen bounds uniform-target support of that cap "
                "by 9.12e-8 even with every Frobenius orientation, so this "
                "no-hit cannot estimate typical natural yield; Q1400 found "
                "no exact hit on the matched Q1325 ordinary target and its "
                "fixed quotient-pair rectangle covers at most 3.735e-10 of "
                "uniform targets; Q1329, Q1332, Q1335, Q1338, Q1401, Q1403, and Q1404 "
                "independently verified planted n83 four-leaf controls, but "
                "none estimates ordinary-query yield; Q1403's ordered "
                "implicit Q1325 SAT formula timed out on both its ordinary "
                "target and an unpinned satisfiable planted target; Q1404's "
                "smaller raw-preimage W<=5 SAT formula stopped at one million "
                "conflicts on the ordinary target and timed out on an unpinned "
                "satisfiable planted target, with no model in either run; "
                "Q1333/Q1334 use an adaptive target-local inversion window "
                "and reproduce the fixed-window ordinary outcomes; Q1336/Q1337 "
                "fuse one field multiplication per S3 root but show no repeatable "
                "wall-time gain in one unisolated observation per field; "
                "older n53/n83 SAT variants remain censored; the n131 W<=6 "
                "base B/K remain conditional estimates rather than an exact "
                "enumerated base; one n53 success and censored n83 ordinary "
                "runs do not measure natural useful-row or novel-rank rates; "
                "exact primitive mul/sqr call vectors now include inversions "
                "but conversions, hashing, memory and arithmetic types still "
                "lack a common calibrated unit; complete relation collection, "
                "final matrix solve, target descent, and scalar replay are absent"
            ),
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
