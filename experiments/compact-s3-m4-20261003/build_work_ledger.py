#!/usr/bin/env python3
"""Summarize frozen stage measurements without inventing a complete-solve cost."""

from __future__ import annotations

import gzip
import json
import math
import re
from decimal import Decimal, localcontext
from pathlib import Path

from run_probe import HERE, ROOT, sha


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
    q1406_bound_path, q1406_bound = read(
        "n131_q1406_uniform_query_bound.json")
    q1407_shape_path, q1407_shape = read(
        "n53_n83_n131_q1407_compact_formula_shape.json")
    q1413_prefix_path, q1413_prefix = read(
        "n131_q1413_projected_x_w5.json")
    q1413_full_path, q1413_full = read(
        "n131_q1413_projected_x_w6.json")
    q1413_replay_path, q1413_replay = read(
        "n131_q1413_sage_projection_replay.json")
    q1413_calls_path, q1413_calls = read(
        "q1413_exact_base_api_call_vectors.json")
    q1414_bound_path, q1414_bound = read(
        "n131_q1414_exact_uniform_query_bound.json")
    q1416_pair_path, q1416_pair = read(
        "n131_q1416_exact_base_pair_index_screen.json")
    q1437_dir = HERE / "q1437_weight7_frontier"
    q1437_protocol_path = q1437_dir / "protocol.json"
    q1437_sample_path = q1437_dir / "sample.json"
    q1437_verification_path = q1437_dir / "verification.json"
    q1437_protocol = json.loads(q1437_protocol_path.read_text())
    q1437_sample = json.loads(q1437_sample_path.read_text())
    q1437_verification = json.loads(q1437_verification_path.read_text())
    assert n131_sample["proposal_id"] == "Q1303"
    assert n131_sample["candidate_id"] is None
    assert n131_sample["protocol_sha256"] == sha(protocol_path)
    assert q1406_bound["proposal_id"] == "Q1406"
    assert q1406_bound["parent_base_proposal_id"] == "Q1303"
    assert q1406_bound["candidate_id"] is None
    assert q1406_bound["curve_id"] == n131_sample["curve_id"]
    assert q1406_bound["isogeny"] == "none"
    assert q1406_bound["input_sha256"][str(
        n131_sample_path.relative_to(ROOT))] == sha(n131_sample_path)
    assert q1406_bound["input_sha256"][str(
        protocol_path.relative_to(ROOT))] == sha(protocol_path)
    assert q1406_bound["source_sha256"] == sha(
        HERE / "screen_q1406_uniform_query_bound.py")
    assert q1406_bound["complete_solve_work_log2"] is None
    assert q1407_shape["proposal_id"] == "Q1407"
    assert q1407_shape["candidate_id"] is None
    assert q1407_shape["isogeny"] == "none"
    assert q1407_shape["n131_placeholder_formula_shape"]["curve_id"] == (
        n131_sample["curve_id"])
    assert q1407_shape["source_sha256"][
        "experiments/compact-s3-m4-20261003/screen_q1407_compact_formula_shape.py"
    ] == sha(HERE / "screen_q1407_compact_formula_shape.py")
    assert q1407_shape["complete_solve_work_log2"] is None
    q1413_protocol_path = HERE / "q1413_projected_x_protocol.json"
    assert q1413_prefix["proposal_id"] == q1413_full["proposal_id"] == "Q1413"
    assert q1413_full["parent_base_proposal_id"] == "Q1303"
    assert q1413_full["candidate_id"] is None
    assert q1413_full["curve_id"] == n131_sample["curve_id"]
    assert q1413_full["normal_basis_weight_bound"] == 6
    assert q1413_full["protocol_sha256"] == sha(q1413_protocol_path)
    assert q1413_full["actual_usable_points_B_before_folding"] == (
        262 * q1413_full["signed_frobenius_columns_K"])
    assert len(q1413_prefix["strata"]) == 5
    for full_row, prefix_row in zip(q1413_full["strata"][:5],
                                    q1413_prefix["strata"]):
        for field_name in ("weight", "x_orbits", "rational_x_orbits",
                           "identity_projection_orbits"):
            assert full_row[field_name] == prefix_row[field_name]
    assert q1413_replay["status"] == "PASS"
    assert q1413_replay["q1413_protocol_sha256"] == sha(q1413_protocol_path)
    assert q1413_calls["proposal_id"] == "Q1413"
    assert q1413_calls["rows"][-1]["base_receipt_sha256"] == sha(
        q1413_full_path)
    assert q1413_calls["source_sha256"] == sha(
        HERE / "derive_q1413_base_calls.py")
    assert q1414_bound["proposal_id"] == "Q1414"
    assert q1414_bound["parent_base_proposal_id"] == "Q1303"
    assert q1414_bound["base_receipt_sha256"] == sha(q1413_full_path)
    assert q1414_bound["base_set_sha256"] == q1413_full[
        "enumerated_set_sha256"]
    assert q1414_bound["actual_usable_points_B_before_folding"] == (
        q1413_full["actual_usable_points_B_before_folding"])
    assert q1414_bound["folded_columns_K"] == q1413_full[
        "signed_frobenius_columns_K"]
    assert q1414_bound["source_sha256"] == sha(
        HERE / "screen_q1414_exact_uniform_query_bound.py")
    assert q1414_bound["complete_solve_work_log2"] is None
    assert q1414_bound["challenge_dispatch_allowed"] is False
    assert q1416_pair["proposal_id"] == "Q1416"
    assert q1416_pair["parent_base_proposal_id"] == "Q1303"
    assert q1416_pair["candidate_id"] is None
    assert q1416_pair["curve_id"] == q1413_full["curve_id"]
    assert q1416_pair["base_receipt_sha256"] == sha(q1413_full_path)
    assert q1416_pair["base_set_sha256"] == q1413_full[
        "enumerated_set_sha256"]
    assert q1416_pair["actual_usable_points_B_before_folding"] == (
        q1413_full["actual_usable_points_B_before_folding"])
    assert q1416_pair["folded_columns_K"] == q1413_full[
        "signed_frobenius_columns_K"]
    assert q1416_pair["source_sha256"] == sha(
        HERE / "screen_q1416_exact_pair_index.py")
    assert q1416_pair["complete_solve_work_log2"] is None
    assert q1416_pair["challenge_dispatch_allowed"] is False
    assert q1437_protocol["proposal_id"] == q1437_sample["proposal_id"] == "Q1437"
    assert q1437_protocol["candidate_id"] is q1437_sample["candidate_id"] is None
    assert q1437_sample["curve_id"] == q1413_full["curve_id"]
    assert q1437_sample["isogeny"] == "none"
    assert q1437_protocol["exact_w6_base_receipt_sha256"] == sha(q1413_full_path)
    assert q1437_sample["protocol_sha256"] == sha(q1437_protocol_path)
    assert q1437_sample["source_sha256"] == sha(q1437_dir / "screen.py")
    assert q1437_sample["sample_size"] == q1437_protocol["sample_size"]
    assert q1437_sample["actual_usable_points_B_before_folding"] is None
    assert q1437_sample["actual_signed_frobenius_columns_K"] is None
    assert q1437_sample["complete_solve_work_log2"] is None
    assert q1437_verification["status"] == "passed"
    assert q1437_verification["sample_sha256"] == sha(q1437_sample_path)
    assert q1437_verification["controls"] == q1437_protocol[
        "independent_control_count"]
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
    q1408_protocol_path = HERE / "q1408_balanced_s3_w5_protocol.json"
    q1408_protocol = json.loads(q1408_protocol_path.read_text())
    q1408_runtime_path = HERE / "q1408_sage_runtime_info.json"
    q1408_replay_path, q1408_replay = read(
        "n83_q1408_balanced_control_replay.json")
    q1408_comparison_path, q1408_comparison = read(
        "n83_q1404_q1408_named_stage_comparison.json")
    assert q1408_protocol["proposal_id"] == q1408_replay[
        "proposal_id"] == "Q1408"
    assert q1408_protocol["curve_id"] == q1404_protocol["curve_id"]
    assert q1408_protocol["ordinary_workload_id"] == q1404_protocol[
        "ordinary_workload_id"]
    assert q1408_protocol["factor_base_enumerated_set_sha256"] == (
        q1404_protocol["factor_base_enumerated_set_sha256"])
    assert q1408_protocol["factor_base_actual_B"] == q1404_protocol[
        "factor_base_actual_B"]
    assert q1408_protocol["factor_base_folded_columns"] == q1404_protocol[
        "factor_base_folded_columns"]
    assert q1408_replay["status"] == "PASS"
    assert q1408_replay["verified_control_relation_count"] == 1
    assert q1408_replay["ordinary_relation_count"] == 0
    assert q1408_replay["four_distinct_columns"] is True
    assert q1408_replay["protocol_sha256"] == sha(q1408_protocol_path)
    assert q1408_replay["source_sha256"] == sha(
        HERE / "verify_q1408_balanced_control.py")
    assert q1408_comparison["source_sha256"] == sha(
        HERE / "build_q1408_stage_comparison.py")
    assert [profile["proposal_id"] for profile in q1408_comparison[
        "stage_profiles"]] == ["Q1404", "Q1408"]
    q1408_stages = []
    for mode, expected_status in (
        ("planted_locked", "sat"),
        ("planted_unpinned", "external_timeout"),
        ("ordinary", "censored"),
    ):
        stage_path, stage = read(f"n83_q1408_{mode}.json")
        assert stage["proposal_id"] == "Q1408"
        assert stage["status"] == expected_status
        assert stage["protocol_sha256"] == sha(q1408_protocol_path)
        assert stage["runtime_info_sha256"] == sha(q1408_runtime_path)
        assert stage["complete_solve_work_log2"] is None
        q1408_stages.append({
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
    q1409_protocol_path = HERE / "q1409_balanced_s3_n53_protocol.json"
    q1409_failure_path, q1409_failure = read(
        "n53_q1409_planted_locked_verification_failure.json")
    assert q1409_failure["status"] == "verification_failed"
    assert q1409_failure["protocol_sha256"] == sha(q1409_protocol_path)
    q1410_protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    q1410_protocol = json.loads(q1410_protocol_path.read_text())
    q1410_runtime_path = HERE / "q1410_sage_runtime_info.json"
    q1410_replay_path, q1410_replay = read(
        "n53_q1410_balanced_control_replay.json")
    q1410_comparison_path, q1410_comparison = read(
        "n53_q1410_n83_q1408_balanced_stage_comparison.json")
    assert q1410_protocol["proposal_id"] == q1410_replay[
        "proposal_id"] == "Q1410"
    assert q1410_protocol["parent_factor_base_proposal_id"] == "Q1301"
    assert q1410_protocol["curve_id"] == protocol["profiles"][0]["curve"][
        "curve_id"]
    assert q1410_protocol["factor_base_enumerated_set_sha256"] == protocol[
        "profiles"][0]["factor_base"]["enumerated_set_sha256"]
    assert q1410_replay["status"] == "PASS"
    assert q1410_replay["locked_control_distinct_columns"] == 4
    assert q1410_replay["ordinary_relation_count"] == 0
    assert q1410_replay["source_sha256"] == sha(
        HERE / "verify_q1410_n53_balanced.py")
    assert q1410_comparison["source_sha256"] == sha(
        HERE / "build_q1410_stage_comparison.py")
    assert [profile["proposal_id"] for profile in q1410_comparison[
        "stage_profiles"]] == ["Q1410", "Q1408"]
    q1410_stages = []
    for mode, expected_status in (
        ("witness_locked", "sat"),
        ("ordinary", "censored"),
    ):
        stage_path, stage = read(f"n53_q1410_{mode}.json")
        assert stage["proposal_id"] == "Q1410"
        assert stage["status"] == expected_status
        assert stage["protocol_sha256"] == sha(q1410_protocol_path)
        assert stage["runtime_info_sha256"] == sha(q1410_runtime_path)
        assert stage["complete_solve_work_log2"] is None
        q1410_stages.append({
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
    q1415_protocol_path = HERE / "q1415_gauss_n53_protocol.json"
    q1415_protocol = json.loads(q1415_protocol_path.read_text())
    q1415_runtime_path = HERE / "q1415_sage_runtime_info.json"
    q1415_path, q1415 = read("n53_q1415_gauss_ordinary.json")
    q1415_comparison_path, q1415_comparison = read(
        "n53_q1410_q1415_named_stage_comparison.json")
    assert q1415_protocol["proposal_id"] == q1415["proposal_id"] == "Q1415"
    assert q1415_protocol["parent_solver_proposal_id"] == "Q1410"
    assert q1415_protocol["candidate_id"] is q1415["candidate_id"] is None
    assert q1415_protocol["curve_id"] == q1410_protocol["curve_id"]
    assert q1415["workload_id"] == q1410_protocol["ordinary_workload_id"]
    assert q1415["formula_raw_sha256"] == q1415_protocol[
        "formula_raw_sha256"]
    assert q1415["solver_status"] == "external_timeout"
    assert q1415["gaussian_matrix_reported_active"] is True
    assert q1415["observed_verified_relation_count"] == 0
    assert q1415["complete_solve_work_log2"] is None
    assert q1415["protocol_sha256"] == sha(q1415_protocol_path)
    assert q1415["runtime_info_sha256"] == sha(q1415_runtime_path)
    assert q1415_comparison["source_sha256"] == sha(
        HERE / "build_q1415_stage_comparison.py")
    assert [profile["proposal_id"] for profile in q1415_comparison[
        "stage_profiles"]] == ["Q1410", "Q1415"]
    assert q1415_comparison["stage_profiles"][1][
        "legacy_stage_config_id"] == q1415["stage_config_id"]
    assert q1415_comparison["stage_profiles"][1][
        "legacy_stage_run_id"] == q1415["stage_run_id"]
    assert q1415_comparison["is_controlled_cpu_wall_speedup"] is False
    assert q1415_comparison["is_solve_growth_measurement"] is False
    q1412_protocol_path = HERE / "q1412_ordered_balanced_n53_protocol.json"
    q1412_protocol = json.loads(q1412_protocol_path.read_text())
    q1412_runtime_path = HERE / "q1412_sage_runtime_info.json"
    q1412_replay_path, q1412_replay = read(
        "n53_q1412_ordered_control_replay.json")
    q1412_comparison_path, q1412_comparison = read(
        "n53_q1410_q1412_named_stage_comparison.json")
    assert q1412_protocol["proposal_id"] == q1412_replay[
        "proposal_id"] == "Q1412"
    assert q1412_protocol["parent_solver_proposal_id"] == "Q1410"
    assert q1412_protocol["q1410_protocol_sha256"] == sha(q1410_protocol_path)
    assert q1412_protocol["curve_id"] == q1410_protocol["curve_id"]
    assert q1412_protocol["factor_base_enumerated_set_sha256"] == (
        q1410_protocol["factor_base_enumerated_set_sha256"])
    assert q1412_replay["status"] == "PASS"
    assert q1412_replay["locked_control_distinct_columns"] == 4
    assert q1412_replay["ordinary_relation_count"] == 0
    assert q1412_replay["source_sha256"] == sha(
        HERE / "verify_q1412_n53_ordered.py")
    assert q1412_comparison["source_sha256"] == sha(
        HERE / "build_q1412_stage_comparison.py")
    assert [profile["proposal_id"] for profile in q1412_comparison[
        "stage_profiles"]] == ["Q1410", "Q1412"]
    q1412_stages = []
    for mode, expected_status in (
        ("witness_locked", "sat"),
        ("ordinary", "censored"),
    ):
        stage_path, stage = read(f"n53_q1412_{mode}.json")
        assert stage["proposal_id"] == "Q1412"
        assert stage["status"] == expected_status
        assert stage["protocol_sha256"] == sha(q1412_protocol_path)
        assert stage["runtime_info_sha256"] == sha(q1412_runtime_path)
        assert stage["complete_solve_work_log2"] is None
        q1412_stages.append({
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
    q1419_dir = HERE / "q1419_partial_pin"
    q1419_protocol_path = q1419_dir / "protocol.json"
    q1419_verification_path = q1419_dir / "verification.json"
    q1419_protocol = json.loads(q1419_protocol_path.read_text())
    q1419_verification = json.loads(q1419_verification_path.read_text())
    assert q1419_protocol["proposal_id"] == "Q1419"
    assert q1419_protocol["candidate_id"] is None
    assert q1419_protocol["isogeny"] == "none"
    assert q1419_verification["complete"] is True
    assert q1419_verification["missing"] == []
    assert q1419_verification["protocol_sha256"] == sha(q1419_protocol_path)
    assert q1419_verification["verifier_source_sha256"] == sha(
        q1419_dir / "verify_archive.py")
    q1419_cells = []
    for n in (53, 83):
        profile = q1419_protocol["profiles"][str(n)]
        for cell in q1419_protocol["run_order"]:
            path = q1419_dir / "runs" / f"n{n}_{cell}" / "receipt.json"
            stage = json.loads(path.read_text())
            check = next(row for row in q1419_verification["checks"]
                         if row["degree"] == n and row["cell"] == cell)
            assert check["receipt_sha256"] == sha(path)
            assert stage["proposal_id"] == "Q1419"
            assert stage["candidate_id"] is None
            assert stage["curve_id"] == profile["curve_id"]
            assert stage["factor_base_actual_B"] == profile[
                "factor_base_actual_B"]
            assert stage["folded_columns_K"] == profile["folded_columns_K"]
            assert stage["workload_id"] == profile["workload_id"]
            assert stage["protocol_sha256"] == sha(q1419_protocol_path)
            assert stage["natural_relation_yield_estimate"] is None
            assert stage["complete_solve_work_log2"] is None
            q1419_cells.append({
                "proposal_id": "Q1419", "candidate_id": None,
                "stage_config_id": stage["stage_config_id"],
                "workload_id": stage["workload_id"],
                "stage_run_id": stage["stage_run_id"],
                "curve_id": stage["curve_id"], "degree_n": n,
                "cell": cell, "input_law": stage["input_law"],
                "factor_base_actual_B": stage["factor_base_actual_B"],
                "folded_columns_K": stage["folded_columns_K"],
                "solver_status": stage["solver_status"],
                "solver_conflicts_reported": stage[
                    "solver_conflicts_reported"],
                "solver_wall_seconds_exploratory": stage[
                    "solver_wall_seconds_exploratory"],
                "peak_child_rss_raw": stage["peak_child_rss_raw"],
                "peak_child_rss_units": stage["peak_child_rss_units"],
                "verified_relation_count": stage[
                    "verified_relation_count"],
                "natural_relation_yield_estimate": None,
                "complete_solve_work_log2": None,
                "receipt_sha256": sha(path),
            })
    assert len(q1419_cells) == 16
    assert sum(row["verified_relation_count"] for row in q1419_cells) == 3
    assert all(row["verified_relation_count"] == 0 for row in q1419_cells
               if row["degree_n"] == 83 and row["cell"] != "full_lock")
    q1420_dir = HERE / "q1420_root_theory"
    q1420_protocol_path = q1420_dir / "protocol.json"
    q1420_verification_path = q1420_dir / "verification.json"
    q1420_protocol = json.loads(q1420_protocol_path.read_text())
    q1420_verification = json.loads(q1420_verification_path.read_text())
    assert q1420_protocol["proposal_id"] == "Q1420"
    assert q1420_protocol["candidate_id"] is None
    assert q1420_protocol["isogeny"] == "none"
    assert q1420_verification["complete"] is True
    assert q1420_verification["missing"] == []
    assert q1420_verification["protocol_sha256"] == sha(q1420_protocol_path)
    assert q1420_verification["verifier_source_sha256"] == sha(
        q1420_dir / "verify_archive.py")
    q1420_cells = []
    q1420_control_relations = {}
    for key in q1420_protocol["run_order"]:
        path = q1420_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1420_protocol["workloads"][key]
        check = next(row for row in q1420_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1420"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        assert stage["stage_config_id"] == workload["stage_config_id"]
        assert stage["workload_id"] == workload["workload_id"]
        assert stage["stage_run_id"] == workload["stage_run_id"]
        assert stage["curve_id"] == workload["curve_id"]
        assert stage["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert stage["folded_columns_K"] == workload["folded_columns_K"]
        assert stage["protocol_sha256"] == sha(q1420_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        report = stage["solver_report"]
        if stage["solver_status"] == "external_timeout":
            assert report is None
            assert stage["verified_relation_count"] == 0
        else:
            assert report is not None
        if stage["cell"] != "ordinary":
            assert stage["solver_status"] == "sat"
            assert stage["verified_relation_count"] == 1
            relation = stage["model_check"]
            previous = q1420_control_relations.setdefault(stage["degree_n"],
                                                          relation)
            assert relation == previous
        q1420_cells.append({
            "proposal_id": "Q1420", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "cnf_variables": stage["cnf_variables"],
            "cnf_clauses": stage["cnf_clauses"],
            "solver_status": stage["solver_status"],
            "formula_build_wall_seconds_exploratory": stage[
                "formula_build_wall_seconds_exploratory"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "model_check_wall_seconds_exploratory": stage[
                "model_check_wall_seconds_exploratory"],
            "formula_build_field_mul_calls": stage[
                "formula_build_field_mul_calls"],
            "formula_build_field_sqr_calls": stage[
                "formula_build_field_sqr_calls"],
            "solver_root_calls": (report["s3_root_calls"]
                                  if report is not None else None),
            "solver_external_clauses": (report["external_clauses"]
                                        if report is not None else None),
            "solver_field_mul_calls": (report["field_mul_calls"]
                                       if report is not None else None),
            "solver_field_sqr_calls": (report["field_sqr_calls"]
                                       if report is not None else None),
            "solver_field_inv_calls": (report["field_inv_calls"]
                                       if report is not None else None),
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1420_cells) == 6
    assert len(q1420_control_relations) == 2
    assert sum(row["verified_relation_count"] for row in q1420_cells) == 4
    assert all(row["solver_status"] == "external_timeout" for row in
               q1420_cells if row["cell"] == "ordinary")
    q1421_dir = HERE / "q1421_work_counted"
    q1421_protocol_path = q1421_dir / "protocol.json"
    q1421_verification_path = q1421_dir / "verification.json"
    q1421_protocol = json.loads(q1421_protocol_path.read_text())
    q1421_verification = json.loads(q1421_verification_path.read_text())
    assert q1421_protocol["proposal_id"] == "Q1421"
    assert q1421_protocol["candidate_id"] is None
    assert q1421_protocol["isogeny"] == "none"
    assert q1421_verification["complete"] is True
    assert q1421_verification["missing"] == []
    assert q1421_verification["protocol_sha256"] == sha(q1421_protocol_path)
    assert q1421_verification["verifier_source_sha256"] == sha(
        q1421_dir / "verify_archive.py")
    q1421_cells = []
    for key in q1421_protocol["run_order"]:
        path = q1421_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1421_protocol["workloads"][key]
        check = next(row for row in q1421_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1421"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        assert stage["stage_config_id"] == workload["stage_config_id"]
        assert stage["workload_id"] == workload["workload_id"]
        assert stage["stage_run_id"] == workload["stage_run_id"]
        assert stage["curve_id"] == workload["curve_id"]
        assert stage["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert stage["folded_columns_K"] == workload["folded_columns_K"]
        assert stage["protocol_sha256"] == sha(q1421_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        report = stage["solver_report"]
        assert report is not None
        assert report["decision_policy"] == stage["decision_policy"]
        assert report["s3_root_calls"] == report[
            "cached_pair_assignments"] or stage["cell"] == "free_mids"
        q1421_cells.append({
            "proposal_id": "Q1421", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "parent_stage_run_id": stage["parent_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "decision_policy": stage["decision_policy"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "forced_leaf_decisions": report["forced_leaf_decisions"],
            "distinct_pair_assignments": report[
                "cached_pair_assignments"],
            "s3_root_calls": report["s3_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "parent_formula_build_wall_seconds_exploratory": stage[
                "parent_formula_build_wall_seconds_exploratory"],
            "parent_formula_build_field_mul_calls": stage[
                "parent_formula_build_field_mul_calls"],
            "parent_formula_build_field_sqr_calls": stage[
                "parent_formula_build_field_sqr_calls"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1421_cells) == 8
    assert sum(row["verified_relation_count"] for row in q1421_cells) == 4
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1421_cells if row["cell"] == "ordinary")
    q1422_dir = HERE / "q1422_leaf_lift_gate"
    q1422_protocol_path = q1422_dir / "protocol.json"
    q1422_verification_path = q1422_dir / "verification.json"
    q1422_protocol = json.loads(q1422_protocol_path.read_text())
    q1422_verification = json.loads(q1422_verification_path.read_text())
    assert q1422_protocol["proposal_id"] == "Q1422"
    assert q1422_protocol["candidate_id"] is None
    assert q1422_protocol["isogeny"] == "none"
    assert q1422_verification["complete"] is True
    assert q1422_verification["missing"] == []
    assert q1422_verification["protocol_sha256"] == sha(q1422_protocol_path)
    assert q1422_verification["verifier_source_sha256"] == sha(
        q1422_dir / "verify_archive.py")
    q1422_cells = []
    for key in q1422_protocol["run_order"]:
        path = q1422_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1422_protocol["workloads"][key]
        check = next(row for row in q1422_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1422"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        assert stage["stage_config_id"] == workload["stage_config_id"]
        assert stage["workload_id"] == workload["workload_id"]
        assert stage["stage_run_id"] == workload["stage_run_id"]
        assert stage["curve_id"] == workload["curve_id"]
        assert stage["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert stage["folded_columns_K"] == workload["folded_columns_K"]
        assert stage["protocol_sha256"] == sha(q1422_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1421_dir / "runs" /
                        workload["matched_q1421_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1421_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        assert matched["workload_id"] == stage["workload_id"]
        assert matched["curve_id"] == stage["curve_id"]
        assert matched["factor_base_enumerated_set_sha256"] == stage[
            "factor_base_enumerated_set_sha256"]
        report = stage["solver_report"]
        assert report is not None and report["lift_gate_active"] is True
        assert report["checked_single_leaf_values"] == (
            report["valid_single_leaf_values"] +
            report["invalid_single_leaf_values"])
        q1422_cells.append({
            "proposal_id": "Q1422", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1421_stage_run_id": stage[
                "matched_q1421_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "decision_policy": stage["decision_policy"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "checked_single_leaf_values": report[
                "checked_single_leaf_values"],
            "valid_single_leaf_values": report[
                "valid_single_leaf_values"],
            "invalid_single_leaf_values": report[
                "invalid_single_leaf_values"],
            "distinct_pair_assignments": report[
                "cached_pair_assignments"],
            "s3_root_calls": report["s3_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1421_root_calls": matched[
                "solver_report"]["s3_root_calls"],
            "matched_q1421_conflicts": matched[
                "solver_report"]["conflicts"],
            "matched_q1421_receipt_sha256": sha(matched_path),
            "parent_formula_build_wall_seconds_exploratory": stage[
                "parent_formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1422_cells) == 4
    assert sum(row["verified_relation_count"] for row in q1422_cells) == 2
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1422_cells if row["cell"] == "ordinary")
    q1423_dir = HERE / "q1423_target_coupled"
    q1423_protocol_path = q1423_dir / "protocol.json"
    q1423_verification_path = q1423_dir / "verification.json"
    q1423_protocol = json.loads(q1423_protocol_path.read_text())
    q1423_verification = json.loads(q1423_verification_path.read_text())
    assert q1423_protocol["proposal_id"] == "Q1423"
    assert q1423_protocol["candidate_id"] is None
    assert q1423_protocol["isogeny"] == "none"
    assert q1423_verification["complete"] is True
    assert q1423_verification["missing"] == []
    assert q1423_verification["protocol_sha256"] == sha(q1423_protocol_path)
    assert q1423_verification["verifier_source_sha256"] == sha(
        q1423_dir / "verify_archive.py")
    q1423_cells = []
    for key in q1423_protocol["run_order"]:
        path = q1423_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1423_protocol["workloads"][key]
        check = next(row for row in q1423_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1423"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        assert stage["stage_config_id"] == workload["stage_config_id"]
        assert stage["workload_id"] == workload["workload_id"]
        assert stage["stage_run_id"] == workload["stage_run_id"]
        assert stage["curve_id"] == workload["curve_id"]
        assert stage["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert stage["folded_columns_K"] == workload["folded_columns_K"]
        assert stage["factor_base_enumerated_set_sha256"] == workload[
            "factor_base_enumerated_set_sha256"]
        assert stage["target_input_sha256"] == workload[
            "target_input_sha256"]
        assert stage["protocol_sha256"] == sha(q1423_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1422_dir / "runs" /
                        workload["matched_q1422_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1422_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        assert matched["workload_id"] == stage["workload_id"]
        assert matched["curve_id"] == stage["curve_id"]
        assert matched["factor_base_enumerated_set_sha256"] == stage[
            "factor_base_enumerated_set_sha256"]
        report = stage["solver_report"]
        assert report is not None and report["lift_gate_active"] is True
        assert report["target_coupled_active"] is True
        assert report["target_preimage_count"] == stage[
            "target_preimage_x_count"]
        assert report["final_root_calls"] == (
            report["final_zero_roots"] + report["final_one_root"] +
            report["final_two_roots"])
        q1423_cells.append({
            "proposal_id": "Q1423", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1422_stage_run_id": stage[
                "matched_q1422_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "decision_policy": stage["decision_policy"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "target_preimage_x_count": stage["target_preimage_x_count"],
            "target_input_sha256": stage["target_input_sha256"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "checked_single_leaf_values": report[
                "checked_single_leaf_values"],
            "invalid_single_leaf_values": report[
                "invalid_single_leaf_values"],
            "distinct_pair_assignments": report[
                "cached_pair_assignments"],
            "final_root_calls": report["final_root_calls"],
            "s3_root_calls": report["s3_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1422_root_calls": matched[
                "solver_report"]["s3_root_calls"],
            "matched_q1422_receipt_sha256": sha(matched_path),
            "parent_formula_build_wall_seconds_exploratory": stage[
                "parent_formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1423_cells) == 4
    assert sum(row["verified_relation_count"] for row in q1423_cells) == 2
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1423_cells if row["cell"] == "ordinary")
    q1424_dir = HERE / "q1424_early_target"
    q1424_protocol_path = q1424_dir / "protocol.json"
    q1424_verification_path = q1424_dir / "verification.json"
    q1424_protocol = json.loads(q1424_protocol_path.read_text())
    q1424_verification = json.loads(q1424_verification_path.read_text())
    assert q1424_protocol["proposal_id"] == "Q1424"
    assert q1424_protocol["candidate_id"] is None
    assert q1424_protocol["isogeny"] == "none"
    assert q1424_verification["complete"] is True
    assert q1424_verification["missing"] == []
    assert q1424_verification["protocol_sha256"] == sha(q1424_protocol_path)
    assert q1424_verification["verifier_source_sha256"] == sha(
        q1424_dir / "verify_archive.py")
    q1424_cells = []
    for key in q1424_protocol["run_order"]:
        path = q1424_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1424_protocol["workloads"][key]
        check = next(row for row in q1424_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1424"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        assert stage["stage_config_id"] == workload["stage_config_id"]
        assert stage["workload_id"] == workload["workload_id"]
        assert stage["stage_run_id"] == workload["stage_run_id"]
        assert stage["curve_id"] == workload["curve_id"]
        assert stage["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert stage["folded_columns_K"] == workload["folded_columns_K"]
        assert stage["factor_base_enumerated_set_sha256"] == workload[
            "factor_base_enumerated_set_sha256"]
        assert stage["target_input_sha256"] == workload[
            "target_input_sha256"]
        assert stage["protocol_sha256"] == sha(q1424_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1423_dir / "runs" /
                        workload["matched_q1423_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1423_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        assert matched["workload_id"] == stage["workload_id"]
        assert matched["curve_id"] == stage["curve_id"]
        assert matched["factor_base_enumerated_set_sha256"] == stage[
            "factor_base_enumerated_set_sha256"]
        pair_comparator = None
        if stage["cell"] == "ordinary":
            if stage["degree_n"] == 53:
                assert n53["curve_id"] == stage["curve_id"]
                assert n53["factor_base_actual_B"] == stage[
                    "factor_base_actual_B"]
                assert n53["factor_base_folded_columns"] == stage[
                    "folded_columns_K"]
                assert n53["factor_base_enumerated_set_sha256"] == stage[
                    "factor_base_enumerated_set_sha256"]
                assert [int(x) for x in n53["target"]] == stage[
                    "public_target"]
                pair_comparator = {
                    "proposal_id": "Q1301",
                    "status": n53["status"],
                    "verified_relation_count": n53[
                        "verified_relation_count"],
                    "workload_id": n53["workload_id"],
                    "receipt_sha256": sha(n53_path),
                }
            else:
                assert stage["degree_n"] == 83
                assert q1400_stage["curve_id"] == stage["curve_id"]
                assert q1400_stage["factor_base_actual_B"] == stage[
                    "factor_base_actual_B"]
                assert q1400_stage[
                    "factor_base_folded_columns_K"] == stage[
                    "folded_columns_K"]
                assert q1400_stage[
                    "factor_base_enumerated_set_sha256"] == stage[
                    "factor_base_enumerated_set_sha256"]
                assert [int(x) for x in q1400_input[
                    "ordinary_public_target_onb_native_decimal"]] == stage[
                    "public_target"]
                pair_comparator = {
                    "proposal_id": "Q1400",
                    "status": q1400_stage["status"],
                    "verified_relation_count": 0,
                    "workload_id": q1400_stage["workload_id"],
                    "receipt_sha256": sha(q1400_stage_path),
                }
        report = stage["solver_report"]
        assert report is not None and report["lift_gate_active"] is True
        assert report["target_coupled_active"] is True
        assert report["target_preimage_count"] == stage[
            "target_preimage_x_count"]
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["final_root_calls"] == (
            report["final_zero_roots"] + report["final_one_root"] +
            report["final_two_roots"])
        q1424_cells.append({
            "proposal_id": "Q1424", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1423_stage_run_id": stage[
                "matched_q1423_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "decision_policy": stage["decision_policy"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "target_preimage_x_count": stage["target_preimage_x_count"],
            "target_input_sha256": stage["target_input_sha256"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "final_root_calls": report["final_root_calls"],
            "s3_root_calls": report["s3_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1423_combined_pair_root_calls": matched[
                "solver_report"]["cached_pair_assignments"],
            "matched_q1423_receipt_sha256": sha(matched_path),
            "same_curve_base_target_pair_table_stage": pair_comparator,
            "pair_table_speedup_comparison_valid": False,
            "parent_formula_build_wall_seconds_exploratory": stage[
                "parent_formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1424_cells) == 8
    assert sum(row["verified_relation_count"] for row in q1424_cells) == 4
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1424_cells if row["cell"] == "ordinary")
    q1425_dir = HERE / "q1425_reverse_pair"
    q1425_protocol_path = q1425_dir / "protocol.json"
    q1425_verification_path = q1425_dir / "verification.json"
    q1425_protocol = json.loads(q1425_protocol_path.read_text())
    q1425_verification = json.loads(q1425_verification_path.read_text())
    assert q1425_protocol["proposal_id"] == "Q1425"
    assert q1425_protocol["candidate_id"] is None
    assert q1425_protocol["isogeny"] == "none"
    assert q1425_verification["complete"] is True
    assert q1425_verification["missing"] == []
    assert q1425_verification["protocol_sha256"] == sha(q1425_protocol_path)
    assert q1425_verification["verifier_source_sha256"] == sha(
        q1425_dir / "verify_archive.py")
    q1425_cells = []
    for key in q1425_protocol["run_order"]:
        path = q1425_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1425_protocol["workloads"][key]
        check = next(row for row in q1425_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert stage["proposal_id"] == "Q1425"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        for name in ("stage_config_id", "workload_id", "stage_run_id",
                     "curve_id", "factor_base_actual_B", "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "target_input_sha256", "solver_cnf_raw_sha256",
                     "solver_cnf_variables", "solver_cnf_clauses",
                     "removed_partner_pin_units"):
            assert stage[name] == workload[name]
        assert stage["protocol_sha256"] == sha(q1425_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1424_dir / "runs" /
                        workload["matched_q1424_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1424_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        for name in ("workload_id", "curve_id", "factor_base_actual_B",
                     "folded_columns_K", "factor_base_enumerated_set_sha256",
                     "public_target", "target_input_sha256"):
            assert matched[name] == stage[name]
        if stage["cell"] == "ordinary":
            assert stage["solver_cnf_raw_sha256"] == matched[
                "parent_cnf_raw_sha256"]
            assert stage["removed_partner_pin_units"] == 0
        else:
            assert stage["cell"] == "free_partner"
            assert stage["removed_partner_pin_units"] == 2 * stage[
                "degree_n"]
        report = stage["solver_report"]
        assert report is not None and report["reverse_pair_active"] is True
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_pair0_calls"] + report["reverse_pair1_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_zero_candidates"] +
            report["reverse_one_candidate"] +
            report["reverse_two_candidates"])
        assert report["field_mul_calls"] >= 0
        assert report["field_sqr_calls"] >= 0
        assert report["field_inv_calls"] >= 0
        matched_cell = next(row for row in q1424_cells
                            if row["stage_run_id"] == matched[
                                "stage_run_id"])
        q1425_cells.append({
            "proposal_id": "Q1425", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1424_stage_run_id": stage[
                "matched_q1424_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "decision_policy": stage["decision_policy"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "target_preimage_x_count": stage["target_preimage_x_count"],
            "target_input_sha256": stage["target_input_sha256"],
            "solver_cnf_raw_sha256": stage["solver_cnf_raw_sha256"],
            "removed_partner_pin_units": stage[
                "removed_partner_pin_units"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "reverse_pair0_calls": report["reverse_pair0_calls"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "reverse_raw_roots": report["reverse_raw_roots"],
            "reverse_weight_rejects": report["reverse_weight_rejects"],
            "reverse_lift_rejects": report["reverse_lift_rejects"],
            "reverse_zero_candidates": report["reverse_zero_candidates"],
            "reverse_one_candidate": report["reverse_one_candidate"],
            "reverse_two_candidates": report["reverse_two_candidates"],
            "final_root_calls": report["final_root_calls"],
            "s3_root_calls": report["s3_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "partial_raw_field_primitive_calls": sum(
                report[f"field_{name}_calls"]
                for name in ("mul", "sqr", "inv")),
            "partial_raw_field_primitive_calls_log2": math.log2(sum(
                report[f"field_{name}_calls"]
                for name in ("mul", "sqr", "inv"))),
            "matched_q1424_pair0_root_calls": matched_cell[
                "pair0_root_calls"],
            "matched_q1424_pair1_root_calls": matched_cell[
                "pair1_root_calls"],
            "matched_q1424_receipt_sha256": sha(matched_path),
            "same_curve_base_target_pair_table_stage": matched_cell[
                "same_curve_base_target_pair_table_stage"],
            "pair_table_speedup_comparison_valid": False,
            "parent_formula_build_wall_seconds_exploratory": stage[
                "parent_formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(path),
        })
    assert len(q1425_cells) == 8
    assert sum(row["verified_relation_count"] for row in q1425_cells) == 4
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1425_cells if row["cell"] == "ordinary")
    q1425_support_path = q1425_dir / "pair_support_screen.json"
    q1425_support = json.loads(q1425_support_path.read_text())
    assert q1425_support["proposal_id"] == "Q1425"
    assert q1425_support["candidate_id"] is None
    assert q1425_support["isogeny"] == "none"
    assert q1425_support["status"] == "PASS_EXACT_CARDINALITY_SCREEN"
    assert q1425_support["protocol_sha256"] == sha(q1425_protocol_path)
    assert q1425_support["n131_exact_base_receipt_sha256"] == sha(
        q1413_full_path)
    assert q1425_support["source_sha256"] == sha(
        q1425_dir / "screen_pair_support.py")
    assert q1425_support["is_empirical_solver_measurement"] is False
    assert q1425_support["degree131_complete_solve_work_log2"] is None
    for item in q1425_support["rows"]:
        n = item["field_degree_n"]
        m = item["nominal_nonzero_sparse_x_count"]
        assert m == sum(math.comb(n, j) for j in range(
            1, item["normal_basis_weight_bound"] + 1))
        assert item["fixed_a_pair_intermediate_support_cardinality_upper"] == 2 * m
        assert item["any_sparse_a_pair_intermediate_support_cardinality_upper"] == 2 * m * m
        assert item["field_element_count"] == 1 << n
        if n == 131:
            assert item["curve_id"] == q1413_full["curve_id"]
            assert item["factor_base_enumerated_set_sha256"] == q1413_full[
                "enumerated_set_sha256"]
        else:
            matched_workload = q1425_protocol["workloads"][
                f"n{n}_ordinary_reverse_target"]
            assert item["curve_id"] == matched_workload["curve_id"]
            assert item["factor_base_enumerated_set_sha256"] == matched_workload[
                "factor_base_enumerated_set_sha256"]
    assert [item["field_degree_n"] for item in q1425_support["rows"]] == [
        53, 83, 131]
    q1426_dir = HERE / "q1426_symbolic_pair"
    q1426_protocol_path = q1426_dir / "protocol.json"
    q1426_verification_path = q1426_dir / "verification.json"
    q1426_protocol = json.loads(q1426_protocol_path.read_text())
    q1426_verification = json.loads(q1426_verification_path.read_text())
    assert q1426_protocol["proposal_id"] == "Q1426"
    assert q1426_protocol["candidate_id"] is None
    assert q1426_protocol["isogeny"] == "none"
    assert q1426_verification["complete"] is True
    assert q1426_verification["missing"] == []
    assert q1426_verification["protocol_sha256"] == sha(q1426_protocol_path)
    assert q1426_verification["verifier_source_sha256"] == sha(
        q1426_dir / "verify_archive.py")
    assert q1426_protocol["matched_q1425_protocol_sha256"] == sha(
        q1425_protocol_path)
    q1426_cells = []
    for key in q1426_protocol["run_order"]:
        path = q1426_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1426_protocol["workloads"][key]
        check = next(row for row in q1426_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert check["status"] == stage["solver_status"]
        assert stage["proposal_id"] == "Q1426"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        for name in ("stage_config_id", "workload_id", "stage_run_id",
                     "curve_id", "factor_base_actual_B", "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "target_input_sha256", "target_preimage_x_count",
                     "cnf_raw_sha256", "cnf_variables", "cnf_clauses",
                     "removed_partner_pin_units"):
            assert stage[name] == workload[name]
        assert stage["protocol_sha256"] == sha(q1426_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1425_dir / "runs" /
                        workload["matched_q1425_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1425_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        assert matched["stage_run_id"] == stage[
            "matched_q1425_stage_run_id"]
        for name in ("workload_id", "curve_id", "factor_base_actual_B",
                     "folded_columns_K", "factor_base_enumerated_set_sha256",
                     "public_target", "target_input_sha256"):
            assert matched[name] == stage[name]
        report = stage["solver_report"]
        assert report is not None and report["reverse_pair_active"] is True
        assert report["decision_policy"] == "reverse_target"
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_pair0_calls"] + report["reverse_pair1_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_zero_candidates"] +
            report["reverse_one_candidate"] +
            report["reverse_two_candidates"])
        q1426_cells.append({
            "proposal_id": "Q1426", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1425_stage_run_id": stage[
                "matched_q1425_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "target_preimage_x_count": stage["target_preimage_x_count"],
            "target_input_sha256": stage["target_input_sha256"],
            "cnf_raw_sha256": stage["cnf_raw_sha256"],
            "cnf_variables": stage["cnf_variables"],
            "cnf_clauses": stage["cnf_clauses"],
            "removed_partner_pin_units": stage[
                "removed_partner_pin_units"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "reverse_zero_candidates": report["reverse_zero_candidates"],
            "reverse_one_candidate": report["reverse_one_candidate"],
            "reverse_two_candidates": report["reverse_two_candidates"],
            "final_root_calls": report["final_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "partial_raw_field_primitive_calls": sum(
                report[f"field_{name}_calls"]
                for name in ("mul", "sqr", "inv")),
            "formula_build_wall_seconds_exploratory": stage[
                "formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "matched_q1425_receipt_sha256": sha(matched_path),
            "receipt_sha256": sha(path),
        })
    assert len(q1426_cells) == 4
    assert sum(row["verified_relation_count"] for row in q1426_cells) == 2
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1426_cells if row["cell"] == "ordinary")
    q1427_dir = HERE / "q1427_interleaved_pair"
    q1427_protocol_path = q1427_dir / "protocol.json"
    q1427_verification_path = q1427_dir / "verification.json"
    q1427_protocol = json.loads(q1427_protocol_path.read_text())
    q1427_verification = json.loads(q1427_verification_path.read_text())
    assert q1427_protocol["proposal_id"] == "Q1427"
    assert q1427_protocol["candidate_id"] is None
    assert q1427_protocol["isogeny"] == "none"
    assert q1427_verification["complete"] is True
    assert q1427_verification["missing"] == []
    assert q1427_verification["protocol_sha256"] == sha(q1427_protocol_path)
    assert q1427_verification["verifier_source_sha256"] == sha(
        q1427_dir / "verify_archive.py")
    assert q1427_protocol["matched_q1426_protocol_sha256"] == sha(
        q1426_protocol_path)
    assert q1427_protocol["compile_receipt_sha256"] == sha(
        q1427_dir / "compile_receipt.json")
    q1427_cells = []
    for key in q1427_protocol["run_order"]:
        path = q1427_dir / "runs" / key / "receipt.json"
        stage = json.loads(path.read_text())
        workload = q1427_protocol["workloads"][key]
        check = next(row for row in q1427_verification["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(path)
        assert check["verified_relation_count"] == stage[
            "verified_relation_count"]
        assert check["status"] == stage["solver_status"]
        assert stage["proposal_id"] == "Q1427"
        assert stage["candidate_id"] is None and stage["isogeny"] == "none"
        for name in ("stage_config_id", "workload_id", "stage_run_id",
                     "curve_id", "factor_base_actual_B", "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "target_input_sha256", "target_preimage_x_count",
                     "cnf_raw_sha256", "cnf_variables", "cnf_clauses",
                     "removed_partner_pin_units"):
            assert stage[name] == workload[name]
        assert stage["protocol_sha256"] == sha(q1427_protocol_path)
        assert stage["natural_relation_yield_estimate"] is None
        assert stage["complete_solve_work_log2"] is None
        matched_path = (q1426_dir / "runs" /
                        workload["matched_q1426_key"] / "receipt.json")
        assert sha(matched_path) == workload["matched_q1426_receipt_sha256"]
        matched = json.loads(matched_path.read_text())
        assert matched["stage_run_id"] == stage[
            "matched_q1426_stage_run_id"]
        for name in ("workload_id", "curve_id", "factor_base_actual_B",
                     "folded_columns_K", "factor_base_enumerated_set_sha256",
                     "public_target", "target_input_sha256", "cnf_raw_sha256",
                     "cnf_variables", "cnf_clauses", "target_preimage_x_count"):
            assert matched[name] == stage[name]
        report = stage["solver_report"]
        assert report is not None and report["reverse_pair_active"] is True
        assert report["decision_policy"] == "interleave_pair1"
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_pair0_calls"] + report["reverse_pair1_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_zero_candidates"] +
            report["reverse_one_candidate"] +
            report["reverse_two_candidates"])
        q1427_cells.append({
            "proposal_id": "Q1427", "candidate_id": None,
            "stage_config_id": stage["stage_config_id"],
            "workload_id": stage["workload_id"],
            "stage_run_id": stage["stage_run_id"],
            "matched_q1426_stage_run_id": stage[
                "matched_q1426_stage_run_id"],
            "curve_id": stage["curve_id"],
            "degree_n": stage["degree_n"],
            "cell": stage["cell"],
            "input_law": stage["input_law"],
            "factor_base_actual_B": stage["factor_base_actual_B"],
            "folded_columns_K": stage["folded_columns_K"],
            "target_preimage_x_count": stage["target_preimage_x_count"],
            "target_input_sha256": stage["target_input_sha256"],
            "cnf_raw_sha256": stage["cnf_raw_sha256"],
            "cnf_variables": stage["cnf_variables"],
            "cnf_clauses": stage["cnf_clauses"],
            "removed_partner_pin_units": stage[
                "removed_partner_pin_units"],
            "solver_status": stage["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "solver_process_wall_seconds_exploratory": stage[
                "solver_process_wall_seconds_exploratory"],
            "solver_conflicts": report["conflicts"],
            "solver_decisions": report["decisions"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "reverse_zero_candidates": report["reverse_zero_candidates"],
            "reverse_one_candidate": report["reverse_one_candidate"],
            "reverse_two_candidates": report["reverse_two_candidates"],
            "final_root_calls": report["final_root_calls"],
            "external_clauses": report["external_clauses"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "partial_raw_field_primitive_calls": sum(
                report[f"field_{name}_calls"]
                for name in ("mul", "sqr", "inv")),
            "formula_build_wall_seconds_exploratory": stage[
                "formula_build_wall_seconds_exploratory"],
            "peak_child_rss_raw": stage["peak_child_rss_raw"],
            "peak_child_rss_units": stage["peak_child_rss_units"],
            "verified_relation_count": stage["verified_relation_count"],
            "natural_relation_yield_estimate": None,
            "complete_field_operation_equivalent_count": None,
            "complete_solve_work_log2": None,
            "matched_q1426_receipt_sha256": sha(matched_path),
            "receipt_sha256": sha(path),
        })
    assert len(q1427_cells) == 4
    assert sum(row["verified_relation_count"] for row in q1427_cells) == 2
    assert all(row["solver_status"] == "censored" and
               row["solver_stop_reason"] == "wall_cap" for row in
               q1427_cells if row["cell"] == "ordinary")
    q1428_dir = HERE / "q1428_bilinear_span"
    q1428_protocol_path = q1428_dir / "protocol.json"
    q1428_result_path = q1428_dir / "result.json"
    q1428_test_path = q1428_dir / "self_test.json"
    q1428_protocol = json.loads(q1428_protocol_path.read_text())
    q1428_result = json.loads(q1428_result_path.read_text())
    q1428_test = json.loads(q1428_test_path.read_text())
    assert q1428_protocol["proposal_id"] == q1428_result[
        "proposal_id"] == "Q1428"
    assert q1428_protocol["candidate_id"] is q1428_result[
        "candidate_id"] is None
    assert q1428_protocol["isogeny"] == q1428_result["isogeny"] == "none"
    assert q1428_protocol["source_sha256"] == q1428_result[
        "source_sha256"] == sha(q1428_dir / "screen.py")
    assert q1428_protocol["q1427_protocol_sha256"] == sha(
        q1427_protocol_path)
    assert q1428_protocol["runtime_info_sha256"] == sha(
        q1428_dir / "sage_runtime_info.json")
    assert q1428_result["protocol_sha256"] == sha(q1428_protocol_path)
    assert q1428_result["complete_solve_work_log2"] is None
    assert q1428_result["is_empirical_solver_measurement"] is False
    assert len(q1428_result["rows"]) == 24
    assert sum(row["linear_relaxation_reject_count"] for row in
               q1428_result["rows"]) == 238
    assert q1428_test == {"status": "PASS", "degrees": [3, 5],
                          "rejected_partial_states": 37193}
    for item in q1428_protocol["degrees"]:
        n = item["degree_n"]
        matched = q1427_protocol["workloads"][f"n{n}_ordinary"]
        for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                     "factor_base_enumerated_set_sha256"):
            assert item[name] == matched[name]
        cell_rows = [row for row in q1428_result["rows"]
                     if row["degree_n"] == n]
        assert [row["free_suffix_size_each_leaf"] for row in cell_rows] == (
            item["free_suffix_sizes"])
        assert all(row["samples"] == q1428_protocol["samples_per_cell"]
                   for row in cell_rows)
    q1429_dir = HERE / "q1429_unsaturated_span"
    q1429_protocol_path = q1429_dir / "protocol.json"
    q1429_result_path = q1429_dir / "result.json"
    q1429_protocol = json.loads(q1429_protocol_path.read_text())
    q1429_result = json.loads(q1429_result_path.read_text())
    assert q1429_protocol["proposal_id"] == q1429_result[
        "proposal_id"] == "Q1429"
    assert q1429_protocol["candidate_id"] is q1429_result[
        "candidate_id"] is None
    assert q1429_protocol["isogeny"] == q1429_result["isogeny"] == "none"
    assert q1429_protocol["source_sha256"] == q1429_result[
        "source_sha256"] == sha(q1429_dir / "run_screen.py")
    assert q1429_protocol["q1428_protocol_sha256"] == sha(
        q1428_protocol_path)
    assert q1429_protocol["q1427_protocol_sha256"] == sha(
        q1427_protocol_path)
    assert q1429_protocol["q1425_pair_support_sha256"] == sha(
        q1425_support_path)
    assert q1429_protocol["runtime_info_sha256"] == sha(
        q1429_dir / "sage_runtime_info.json")
    assert q1429_protocol["field_source_sha256"] == sha(
        ROOT / "ecc2k130/codegen/field.py")
    for name, digest in q1429_protocol["dependency_sha256"].items():
        assert sha(HERE / name) == digest
    assert q1429_result["protocol_sha256"] == sha(q1429_protocol_path)
    assert q1429_result["complete_solve_work_log2"] is None
    assert q1429_result["is_empirical_solver_measurement"] is False
    assert len(q1429_result["samples"]) == 268
    assert len(q1429_result["cells"]) == 19
    assert sum(row["span_rejections"] for row in
               q1429_result["cells"]) == 174
    assert sum(row["exact_pairs_found"] for row in
               q1429_result["cells"]) == 0
    assert all(not row["span_rejects"] or not row["has_pair"]
               for row in q1429_result["samples"])
    for item in q1429_protocol["degrees"]:
        n = item["degree_n"]
        screen = next(row for row in q1425_support["rows"]
                      if row["field_degree_n"] == n)
        assert item["curve_id"] == screen["curve_id"]
        assert item["factor_base_actual_B"] == screen[
            "actual_usable_factor_base_points_B"]
        assert item["folded_columns_K"] == screen["folded_columns_K"]
        assert item["factor_base_enumerated_set_sha256"] == screen[
            "factor_base_enumerated_set_sha256"]
    q1430_dir = HERE / "q1430_partial_trail"
    q1430_protocol_path = q1430_dir / "protocol.json"
    q1430_audit_path = q1430_dir / "audit_verification.json"
    q1430_protocol = json.loads(q1430_protocol_path.read_text())
    q1430_audit = json.loads(q1430_audit_path.read_text())
    assert q1430_protocol["proposal_id"] == q1430_audit[
        "proposal_id"] == "Q1430"
    assert q1430_protocol["candidate_id"] is q1430_audit[
        "candidate_id"] is None
    assert q1430_protocol["isogeny"] == "none"
    assert q1430_protocol["matched_q1427_protocol_sha256"] == sha(
        q1427_protocol_path)
    assert q1430_protocol["q1429_protocol_sha256"] == sha(
        q1429_protocol_path)
    assert q1430_audit["protocol_sha256"] == sha(q1430_protocol_path)
    assert q1430_audit["verifier_source_sha256"] == sha(
        q1430_dir / "audit_archive.py")
    assert q1430_audit["frozen_verifier_source_sha256"] == (
        q1430_protocol["source_sha256"]["verify_archive.py"])
    assert q1430_audit["complete"] is True
    assert q1430_audit["missing"] == []
    q1430_cells = []
    for key in q1430_protocol["run_order"]:
        workload = q1430_protocol["workloads"][key]
        receipt_path = q1430_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1430_audit["checks"]
                     if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1430"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1430_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == workload["workload_id"]
        assert receipt["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == workload["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == workload[
            "factor_base_enumerated_set_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        q1430_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "both_partial_mid1_notification_events": report[
                "both_partial_mid1_events"],
            "weight_unsaturated_notification_events": report[
                "unsaturated_mid1_events"],
            "screen_window_notification_events": report[
                "screen_window_events"],
            "first_distinct_states_retained_capped": report[
                "screen_window_distinct_capped"],
            "first_snapshots_span_checked": check[
                "sampled_span_checks"],
            "first_snapshots_span_rejected": check[
                "sampled_span_rejections"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1430_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1430_cells] == [
        1, 0, 1, 0]
    assert [row["first_snapshots_span_rejected"] for row in q1430_cells] == [
        0, 16, 0, 16]
    q1431_dir = HERE / "q1431_guarded_span"
    q1431_protocol_path = q1431_dir / "protocol.json"
    q1431_verification_path = q1431_dir / "verification.json"
    q1431_validation_path = q1431_dir / "span_validation.json"
    q1431_protocol = json.loads(q1431_protocol_path.read_text())
    q1431_verification = json.loads(q1431_verification_path.read_text())
    q1431_validation = json.loads(q1431_validation_path.read_text())
    assert q1431_protocol["proposal_id"] == q1431_verification[
        "proposal_id"] == q1431_validation["proposal_id"] == "Q1431"
    assert q1431_protocol["candidate_id"] is q1431_verification[
        "candidate_id"] is q1431_validation["candidate_id"] is None
    assert q1431_protocol["isogeny"] == q1431_validation[
        "isogeny"] == "none"
    assert q1431_protocol["matched_q1430_protocol_sha256"] == sha(
        q1430_protocol_path)
    assert q1431_protocol["span_validation_sha256"] == sha(
        q1431_validation_path)
    assert q1431_verification["protocol_sha256"] == sha(
        q1431_protocol_path)
    assert q1431_verification["verifier_source_sha256"] == sha(
        q1431_dir / "verify_archive.py")
    assert q1431_verification["complete"] is True
    assert q1431_verification["missing"] == []
    assert q1431_validation["total_cases"] == 112
    assert q1431_validation["total_verified_witness_false_rejections"] == 0
    q1431_cells = []
    for key in q1431_protocol["run_order"]:
        workload = q1431_protocol["workloads"][key]
        receipt_path = q1431_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1431_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1430_cells if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1431"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1431_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == matched[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == matched["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
        assert receipt["matched_q1430_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        assert check["sampled_rejection_false_claims"] == 0
        q1431_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1430_stage_run_id": receipt[
                "matched_q1430_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "sampled_rejections_independently_checked": check[
                "sampled_rejection_checks"],
            "span_linear_columns": report["span_linear_columns"],
            "span_bilinear_columns": report["span_bilinear_columns"],
            "span_guard_literals": report["span_guard_literals"],
            "span_field_mul_calls": report["span_field_mul_calls"],
            "span_field_sqr_calls": report["span_field_sqr_calls"],
            "span_field_inv_calls": report["span_field_inv_calls"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1430_field_mul_calls": matched["field_mul_calls"],
            "matched_q1430_reverse_pair1_calls": matched[
                "reverse_pair1_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1431_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1431_cells] == [
        1, 0, 1, 0]
    q1432_dir = HERE / "q1432_coefficient_cache"
    q1432_protocol_path = q1432_dir / "protocol.json"
    q1432_verification_path = q1432_dir / "verification.json"
    q1432_validation_path = q1432_dir / "cache_validation.json"
    q1432_protocol = json.loads(q1432_protocol_path.read_text())
    q1432_verification = json.loads(q1432_verification_path.read_text())
    q1432_validation = json.loads(q1432_validation_path.read_text())
    assert q1432_protocol["proposal_id"] == q1432_verification[
        "proposal_id"] == q1432_validation["proposal_id"] == "Q1432"
    assert q1432_protocol["candidate_id"] is q1432_verification[
        "candidate_id"] is q1432_validation["candidate_id"] is None
    assert q1432_protocol["isogeny"] == q1432_validation[
        "isogeny"] == "none"
    assert q1432_protocol["matched_q1431_protocol_sha256"] == sha(
        q1431_protocol_path)
    assert q1432_protocol["cache_validation_sha256"] == sha(
        q1432_validation_path)
    assert q1432_verification["protocol_sha256"] == sha(
        q1432_protocol_path)
    assert q1432_verification["verifier_source_sha256"] == sha(
        q1432_dir / "verify_archive.py")
    assert q1432_verification["complete"] is True
    assert q1432_verification["missing"] == []
    assert q1432_validation["total_cases"] == 112
    assert q1432_validation["total_verified_witness_false_rejections"] == 0
    q1432_cells = []
    for key in q1432_protocol["run_order"]:
        workload = q1432_protocol["workloads"][key]
        receipt_path = q1432_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1432_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1431_cells if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1432"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1432_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == matched[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == matched["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
        assert receipt["matched_q1431_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        assert check["sampled_rejection_false_claims"] == 0
        q1432_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1431_stage_run_id": receipt[
                "matched_q1431_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "sampled_rejections_independently_checked": check[
                "sampled_rejection_checks"],
            "span_field_mul_calls_including_cache_build": report[
                "span_field_mul_calls"],
            "span_field_sqr_calls_including_cache_build": report[
                "span_field_sqr_calls"],
            "cache_pair_build_mul_calls": report[
                "cache_pair_build_mul_calls"],
            "cache_gamma_build_mul_calls": report[
                "cache_gamma_build_mul_calls"],
            "cache_gamma_table_builds": report[
                "cache_gamma_table_builds"],
            "cache_gamma_hits": report["cache_gamma_hits"],
            "cache_linear_rows_retained": report[
                "cache_linear_rows_retained"],
            "cache_linear_coefficient_hits": report[
                "cache_linear_coefficient_hits"],
            "cache_linear_coefficient_misses": report[
                "cache_linear_coefficient_misses"],
            "cache_payload_bytes_lower_bound": report[
                "cache_payload_bytes_lower_bound"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1431_field_mul_calls": matched["field_mul_calls"],
            "matched_q1431_reverse_pair1_calls": matched[
                "reverse_pair1_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1432_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1432_cells] == [
        1, 0, 1, 0]
    q1433_dir = HERE / "q1433_long_cached"
    q1433_protocol_path = q1433_dir / "protocol.json"
    q1433_verification_path = q1433_dir / "verification.json"
    q1433_protocol = json.loads(q1433_protocol_path.read_text())
    q1433_verification = json.loads(q1433_verification_path.read_text())
    assert q1433_protocol["proposal_id"] == q1433_verification[
        "proposal_id"] == "Q1433"
    assert q1433_protocol["candidate_id"] is q1433_verification[
        "candidate_id"] is None
    assert q1433_protocol["isogeny"] == "none"
    assert q1433_protocol["q1432_protocol_sha256"] == sha(
        q1432_protocol_path)
    assert q1433_protocol["q1432_verification_sha256"] == sha(
        q1432_verification_path)
    assert q1433_protocol["solver_binary_sha256"] == q1432_protocol[
        "solver_binary_sha256"]
    assert q1433_protocol["solver_wall_cap_seconds"] == 300
    assert q1433_verification["protocol_sha256"] == sha(
        q1433_protocol_path)
    assert q1433_verification["verifier_source_sha256"] == sha(
        q1433_dir / "verify_archive.py")
    assert q1433_verification["complete"] is True
    assert q1433_verification["missing"] == []
    q1433_cells = []
    for key in q1433_protocol["run_order"]:
        workload = q1433_protocol["workloads"][key]
        receipt_path = q1433_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1433_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1432_cells if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1433"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1433_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == matched[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == matched["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
        assert receipt["matched_q1432_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        assert check["sampled_rejection_false_claims"] == 0
        q1433_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1432_stage_run_id": receipt[
                "matched_q1432_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "decisions": report["decisions"],
            "conflicts": report["conflicts"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "cache_gamma_table_builds": report[
                "cache_gamma_table_builds"],
            "cache_linear_rows_retained": report[
                "cache_linear_rows_retained"],
            "cache_payload_bytes_lower_bound": report[
                "cache_payload_bytes_lower_bound"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1433_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1433_cells] == [
        1, 0, 1, 0]
    assert [row["stop_reason"] for row in q1433_cells] == [
        "sat", "wall_cap", "sat", "wall_cap"]
    q1434_dir = HERE / "q1434_exact_tail"
    q1434_protocol_path = q1434_dir / "protocol.json"
    q1434_verification_path = q1434_dir / "verification.json"
    q1434_validation_path = q1434_dir / "tail_validation.json"
    q1434_protocol = json.loads(q1434_protocol_path.read_text())
    q1434_verification = json.loads(q1434_verification_path.read_text())
    q1434_validation = json.loads(q1434_validation_path.read_text())
    assert q1434_protocol["proposal_id"] == q1434_verification[
        "proposal_id"] == q1434_validation["proposal_id"] == "Q1434"
    assert q1434_protocol["candidate_id"] is q1434_verification[
        "candidate_id"] is q1434_validation["candidate_id"] is None
    assert q1434_protocol["isogeny"] == q1434_validation[
        "isogeny"] == "none"
    assert q1434_protocol["matched_q1432_protocol_sha256"] == sha(
        q1432_protocol_path)
    assert q1434_protocol["tail_validation_sha256"] == sha(
        q1434_validation_path)
    assert q1434_verification["protocol_sha256"] == sha(
        q1434_protocol_path)
    assert q1434_verification["verifier_source_sha256"] == sha(
        q1434_dir / "verify_archive.py")
    assert q1434_verification["complete"] is True
    assert q1434_verification["missing"] == []
    assert q1434_validation["total_cases"] == 60
    assert q1434_validation["total_witness_false_rejections"] == 0
    q1434_cells = []
    for key in q1434_protocol["run_order"]:
        workload = q1434_protocol["workloads"][key]
        receipt_path = q1434_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1434_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1432_cells if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1434"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1434_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == matched[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == matched["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
        assert receipt["matched_q1432_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        assert check["sampled_rejection_false_claims"] == 0
        assert check["sampled_tail_zero_checks"] == min(
            16, report["tail_zero"])
        assert check["sampled_tail_unique_checks"] == min(
            16, report["tail_unique"])
        q1434_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1432_stage_run_id": receipt[
                "matched_q1432_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "decisions": report["decisions"],
            "conflicts": report["conflicts"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "tail_checks": report["tail_checks"],
            "tail_zero": report["tail_zero"],
            "tail_unique": report["tail_unique"],
            "tail_multiple": report["tail_multiple"],
            "tail_candidate_pairs": report["tail_candidate_pairs"],
            "tail_forced_literals": report["tail_forced_literals"],
            "tail_field_mul_calls": report["tail_field_mul_calls"],
            "tail_field_sqr_calls": report["tail_field_sqr_calls"],
            "sampled_tail_zero_independently_checked": check[
                "sampled_tail_zero_checks"],
            "sampled_tail_unique_independently_checked": check[
                "sampled_tail_unique_checks"],
            "cache_payload_bytes_lower_bound": report[
                "cache_payload_bytes_lower_bound"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1432_field_mul_calls": matched["field_mul_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1434_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1434_cells] == [
        1, 0, 1, 0]
    assert [row["stop_reason"] for row in q1434_cells] == [
        "sat", "wall_cap", "sat", "wall_cap"]
    q1435_dir = HERE / "q1435_bounded_tail"
    q1435_protocol_path = q1435_dir / "protocol.json"
    q1435_verification_path = q1435_dir / "verification.json"
    q1435_validation_path = q1435_dir / "tail_validation.json"
    q1435_protocol = json.loads(q1435_protocol_path.read_text())
    q1435_verification = json.loads(q1435_verification_path.read_text())
    q1435_validation = json.loads(q1435_validation_path.read_text())
    assert q1435_protocol["proposal_id"] == q1435_verification[
        "proposal_id"] == q1435_validation["proposal_id"] == "Q1435"
    assert q1435_protocol["candidate_id"] is q1435_verification[
        "candidate_id"] is q1435_validation["candidate_id"] is None
    assert q1435_protocol["isogeny"] == q1435_validation[
        "isogeny"] == "none"
    assert q1435_protocol["matched_q1434_protocol_sha256"] == sha(
        q1434_protocol_path)
    assert q1435_protocol["tail_validation_sha256"] == sha(
        q1435_validation_path)
    assert q1435_verification["protocol_sha256"] == sha(
        q1435_protocol_path)
    assert q1435_verification["verifier_source_sha256"] == sha(
        q1435_dir / "verify_archive.py")
    assert q1435_verification["complete"] is True
    assert q1435_verification["missing"] == []
    assert q1435_validation["total_cases"] == 103
    assert q1435_validation["total_witness_false_rejections"] == 0
    q1435_cells = []
    for key in q1435_protocol["run_order"]:
        workload = q1435_protocol["workloads"][key]
        receipt_path = q1435_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1435_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1434_cells if row["key"] == key)
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1435"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1435_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == matched[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == matched["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
        assert receipt["matched_q1434_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        report = receipt["solver_report"]
        assert report is not None
        assert check["sampled_rejection_false_claims"] == 0
        assert check["sampled_tail_zero_checks"] == min(
            16, report["tail_zero"])
        assert check["sampled_tail_unique_checks"] == min(
            16, report["tail_unique"])
        q1435_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1434_stage_run_id": receipt[
                "matched_q1434_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "decisions": report["decisions"],
            "conflicts": report["conflicts"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "tail_candidate_cap": report["tail_candidate_cap"],
            "tail_eligible": report["tail_eligible"],
            "tail_skipped_budget": report["tail_skipped_budget"],
            "tail_skipped_candidate_pairs": report[
                "tail_skipped_candidate_pairs"],
            "tail_eligible_by_slack": report["tail_eligible_by_slack"],
            "tail_checked_by_slack": report["tail_checked_by_slack"],
            "tail_zero_by_slack": report["tail_zero_by_slack"],
            "tail_checks": report["tail_checks"],
            "tail_zero": report["tail_zero"],
            "tail_unique": report["tail_unique"],
            "tail_multiple": report["tail_multiple"],
            "tail_candidate_pairs": report["tail_candidate_pairs"],
            "tail_expansion_xor_ops": report["tail_expansion_xor_ops"],
            "tail_forced_literals": report["tail_forced_literals"],
            "tail_field_mul_calls": report["tail_field_mul_calls"],
            "tail_field_sqr_calls": report["tail_field_sqr_calls"],
            "sampled_tail_zero_independently_checked": check[
                "sampled_tail_zero_checks"],
            "sampled_tail_unique_independently_checked": check[
                "sampled_tail_unique_checks"],
            "cache_payload_bytes_lower_bound": report[
                "cache_payload_bytes_lower_bound"],
            "reverse_pair1_calls": report["reverse_pair1_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "matched_q1434_field_mul_calls": matched["field_mul_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1435_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1435_cells] == [
        1, 0, 1, 0]
    assert [row["stop_reason"] for row in q1435_cells] == [
        "sat", "wall_cap", "sat", "wall_cap"]
    q1436_dir = HERE / "q1436_affine_pair"
    q1436_protocol_path = q1436_dir / "protocol.json"
    q1436_verification_path = q1436_dir / "verification.json"
    q1436_validation_path = q1436_dir / "affine_validation.json"
    q1436_protocol = json.loads(q1436_protocol_path.read_text())
    q1436_verification = json.loads(q1436_verification_path.read_text())
    q1436_validation = json.loads(q1436_validation_path.read_text())
    assert q1436_protocol["proposal_id"] == q1436_verification[
        "proposal_id"] == q1436_validation["proposal_id"] == "Q1436"
    assert q1436_protocol["candidate_id"] is q1436_verification[
        "candidate_id"] is q1436_validation["candidate_id"] is None
    assert q1436_protocol["isogeny"] == q1436_validation[
        "isogeny"] == "none"
    assert q1436_protocol["matched_q1435_protocol_sha256"] == sha(
        q1435_protocol_path)
    assert q1436_protocol["affine_validation_sha256"] == sha(
        q1436_validation_path)
    assert q1436_verification["protocol_sha256"] == sha(
        q1436_protocol_path)
    assert q1436_verification["verifier_source_sha256"] == sha(
        q1436_dir / "verify_archive.py")
    assert q1436_verification["complete"] is True
    assert q1436_verification["missing"] == []
    assert q1436_validation["total_cases"] == 49
    assert q1436_validation["total_witness_cases"] == 9
    q1436_cells = []
    for key in q1436_protocol["run_order"]:
        workload = q1436_protocol["workloads"][key]
        receipt_path = q1436_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        check = next(row for row in q1436_verification["checks"]
                     if row["key"] == key)
        matched = next(row for row in q1435_cells if row["key"] == key)
        report = receipt["solver_report"]
        assert report is not None
        assert check["receipt_sha256"] == sha(receipt_path)
        assert receipt["proposal_id"] == "Q1436"
        assert receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["protocol_sha256"] == sha(q1436_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        for name in ("workload_id", "curve_id", "factor_base_actual_B",
                     "folded_columns_K", "factor_base_enumerated_set_sha256"):
            assert receipt[name] == matched[name]
        assert receipt["matched_q1435_receipt_sha256"] == matched[
            "receipt_sha256"]
        assert receipt["complete_solve_work_log2"] is None
        assert check["sampled_affine_zero_checks"] == min(
            4, report["affine_zero"])
        assert check["sampled_affine_unique_checks"] == min(
            4, report["affine_unique"])
        q1436_cells.append({
            "key": key,
            "degree_n": receipt["degree_n"],
            "cell": receipt["cell"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1435_stage_run_id": receipt[
                "matched_q1435_stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt["verified_relation_count"],
            "span_checks": report["span_checks"],
            "span_rejections": report["span_rejections"],
            "affine_column_cap": report["affine_column_cap"],
            "affine_checks": report["affine_checks"],
            "affine_zero": report["affine_zero"],
            "affine_unique": report["affine_unique"],
            "affine_skipped_budget": report["affine_skipped_budget"],
            "affine_swapped_checks": report["affine_swapped_checks"],
            "affine_a_options": report["affine_a_options"],
            "affine_coefficient_columns": report[
                "affine_coefficient_columns"],
            "affine_inconsistent_options": report[
                "affine_inconsistent_options"],
            "affine_overweight_options": report[
                "affine_overweight_options"],
            "affine_rank_deficient_options": report[
                "affine_rank_deficient_options"],
            "affine_xor_ops": report["affine_xor_ops"],
            "affine_field_mul_calls": report["affine_field_mul_calls"],
            "affine_field_sqr_calls": report["affine_field_sqr_calls"],
            "sampled_affine_zero_independently_checked": check[
                "sampled_affine_zero_checks"],
            "sampled_affine_unique_independently_checked": check[
                "sampled_affine_unique_checks"],
            "cache_payload_bytes_lower_bound": report[
                "cache_payload_bytes_lower_bound"],
            "decisions": report["decisions"],
            "conflicts": report["conflicts"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1436_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1436_cells] == [
        1, 0, 1, 0]
    assert [row["stop_reason"] for row in q1436_cells] == [
        "sat", "wall_cap", "sat", "wall_cap"]
    q1438_dir = HERE / "q1438_dense_base"
    q1438_base_protocol_path = q1438_dir / "protocol.json"
    q1438_base_verification_path = q1438_dir / "verification.json"
    q1438_formula_validation_path = q1438_dir / "formula_validation.json"
    q1438_solver_protocol_path = q1438_dir / "solver_protocol.json"
    q1438_solver_verification_path = q1438_dir / "solver_verification.json"
    q1438_base_protocol = json.loads(q1438_base_protocol_path.read_text())
    q1438_base_verification = json.loads(
        q1438_base_verification_path.read_text())
    q1438_formula_validation = json.loads(
        q1438_formula_validation_path.read_text())
    q1438_solver_protocol = json.loads(q1438_solver_protocol_path.read_text())
    q1438_solver_verification = json.loads(
        q1438_solver_verification_path.read_text())
    assert q1438_base_protocol["proposal_id"] == q1438_solver_protocol[
        "proposal_id"] == "Q1438"
    assert q1438_base_protocol["candidate_id"] is q1438_solver_protocol[
        "candidate_id"] is None
    assert q1438_base_protocol["isogeny"] == q1438_solver_protocol[
        "isogeny"] == "none"
    assert q1438_base_verification["status"] == "passed"
    assert q1438_formula_validation["status"] == "passed"
    assert q1438_solver_verification["status"] == "passed"
    assert q1438_solver_protocol["base_protocol_sha256"] == sha(
        q1438_base_protocol_path)
    assert q1438_solver_protocol["base_verification_sha256"] == sha(
        q1438_base_verification_path)
    assert q1438_solver_protocol["formula_validation_sha256"] == sha(
        q1438_formula_validation_path)
    assert q1438_solver_protocol["matched_q1436_protocol_sha256"] == sha(
        q1436_protocol_path)
    assert q1438_solver_verification["protocol_sha256"] == sha(
        q1438_solver_protocol_path)
    assert q1438_solver_protocol["solver_binary_sha256"] == q1436_protocol[
        "solver_binary_sha256"]
    assert q1438_solver_protocol["solver_wall_cap_seconds"] == q1436_protocol[
        "solver_wall_cap_seconds"]
    assert q1438_solver_protocol["solver_conflict_cap"] == q1436_protocol[
        "solver_conflict_cap"]
    q1438_base_rows = []
    for n in (53, 83):
        instance = q1438_base_protocol["instances"][str(n)]
        base_path = q1438_dir / f"n{n}_w{instance['new_weight_bound']}_base.json"
        base = json.loads(base_path.read_text())
        checked = next(row for row in q1438_base_verification["rows"]
                       if row["degree_n"] == n)
        assert base["protocol_sha256"] == sha(q1438_base_protocol_path)
        assert base["actual_usable_points_B_before_folding"] == (
            2 * n * base["signed_frobenius_columns_K"])
        assert base["reference_exact_set_checked"] is True
        assert checked["receipt_sha256"] == sha(base_path)
        assert checked["enumerated_set_sha256"] == base[
            "enumerated_set_sha256"]
        q1438_base_rows.append({
            "degree_n": n, "curve_id": base["curve_id"],
            "cofactor": base["cofactor"],
            "normal_basis_weight_bound": base[
                "normal_basis_weight_bound"],
            "nominal_x_mask_count": base["nominal_x_mask_count"],
            "actual_usable_points_B_before_folding": base[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": base["signed_frobenius_columns_K"],
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "reference_exact_set_checked": True,
            "enumeration_wall_seconds_exploratory": base[
                "enumeration_wall_seconds"],
            "peak_rss_raw": base["peak_rss_raw"],
            "receipt_sha256": sha(base_path),
        })
    q1438_cells = []
    for key in q1438_solver_protocol["run_order"]:
        workload = q1438_solver_protocol["workloads"][key]
        receipt_path = q1438_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        checked = next(row for row in q1438_solver_verification["rows"]
                       if row["key"] == key)
        matched = next(row for row in q1436_cells if row["key"] == key)
        report = receipt["solver_report"]
        assert report is not None and receipt["solver_report_error"] is None
        assert receipt["protocol_sha256"] == sha(q1438_solver_protocol_path)
        assert receipt["stage_run_id"] == workload["stage_run_id"]
        assert receipt["workload_id"] == matched["workload_id"]
        assert receipt["curve_id"] == matched["curve_id"]
        assert receipt["factor_base_actual_B"] == workload[
            "factor_base_actual_B"]
        assert receipt["factor_base_enumerated_set_sha256"] == workload[
            "factor_base_enumerated_set_sha256"]
        assert checked["receipt_sha256"] == sha(receipt_path)
        assert receipt["complete_solve_work_log2"] is None
        q1438_cells.append({
            "key": key, "degree_n": receipt["field_degree_n"],
            "cell": receipt["cell"], "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "matched_q1436_stage_run_id": matched["stage_run_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "verified_relation_count": receipt["verified_relation_count"],
            "decisions": report["decisions"],
            "conflicts": report["conflicts"],
            "pair0_root_calls": report["pair0_root_calls"],
            "pair1_root_calls": report["pair1_root_calls"],
            "affine_checks": report["affine_checks"],
            "affine_zero": report["affine_zero"],
            "affine_xor_ops": report["affine_xor_ops"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "solver_process_wall_seconds_exploratory": receipt[
                "solver_process_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1438_cells] == [
        "sat", "censored", "sat", "censored"]
    assert [row["verified_relation_count"] for row in q1438_cells] == [
        1, 0, 1, 0]
    assert [row["stop_reason"] for row in q1438_cells] == [
        "sat", "wall_cap", "sat", "wall_cap"]
    q1439_dir = HERE / "q1439_fixed_leaf"
    q1439_protocol_path = q1439_dir / "protocol.json"
    q1439_verification_path = q1439_dir / "verification.json"
    q1439_protocol = json.loads(q1439_protocol_path.read_text())
    q1439_verification = json.loads(q1439_verification_path.read_text())
    q1439_small_path = q1439_dir / "small_field_verification.json"
    q1439_small = json.loads(q1439_small_path.read_text())
    assert q1439_small["status"] == "passed"
    assert [row["nonexceptional_checked"] for row in q1439_small["rows"]] == [
        8, 70644]
    assert q1439_protocol["proposal_id"] == "Q1439"
    assert q1439_protocol["candidate_id"] is None
    assert q1439_protocol["isogeny"] == "none"
    assert q1439_verification["status"] == "passed"
    assert q1439_verification["protocol_sha256"] == sha(q1439_protocol_path)
    q1439_cells = []
    for key in q1439_protocol["run_order"]:
        frozen = q1439_protocol["cells"][key]
        receipt_path = q1439_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        checked = next(row for row in q1439_verification["rows"]
                       if row["key"] == key)
        assert checked["receipt_sha256"] == sha(receipt_path)
        assert receipt["protocol_sha256"] == sha(q1439_protocol_path)
        assert receipt["stage_run_id"] == frozen["stage_run_id"]
        assert receipt["curve_id"] == frozen["curve_id"]
        assert receipt["factor_base_actual_B"] == frozen[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == frozen["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == frozen[
            "factor_base_enumerated_set_sha256"]
        assert receipt["verified_relation_count"] == checked[
            "verified_relation_count"]
        assert receipt["complete_solve_work_log2"] is None
        q1439_cells.append({
            "key": key, "degree_n": receipt["degree_n"],
            "cell": receipt["cell"], "curve_id": receipt["curve_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "anchor_raw_x": receipt["anchor_raw_x"],
            "adjustment_case_count": receipt["adjustment_case_count"],
            "adjusted_target_x_count": receipt["adjusted_target_x_count"],
            "solver_status": receipt["solver_status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "solver_conflicts_reported": receipt[
                "solver_conflicts_reported"],
            "formula_and_gates": receipt["formula"]["and_gates"],
            "formula_xor_rows": receipt["formula"]["xor_rows"],
            "target_preparation_and_formula_wall_seconds_exploratory": receipt[
                "target_preparation_and_formula_wall_seconds_exploratory"],
            "solver_wall_seconds_exploratory": receipt[
                "solver_wall_seconds_exploratory"],
            "charged_stage_wall_seconds_exploratory": receipt[
                "charged_stage_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1439_cells] == [
        "sat", "external_timeout", "sat", "external_timeout"]
    assert [row["verified_relation_count"] for row in q1439_cells] == [
        1, 0, 1, 0]
    fixed_anchor_model = []
    for n in (53, 83):
        b = q1438_solver_protocol["workloads"][f"n{n}_ordinary"][
            "factor_base_actual_B"]
        r = q1438_solver_protocol["instances"][str(n)]["subgroup_order"]
        mean = math.comb(b, 3) / r
        fixed_anchor_model.append({
            "degree_n": n, "base_source": "Q1438 exact",
            "factor_base_actual_B": b,
            "mean_unordered_three_subsets_per_uniform_target_and_fixed_anchor": mean,
            "log2_mean": math.log2(mean),
            "anchors_per_expected_hit": 1 / mean,
            "log2_anchors_per_expected_hit": -math.log2(mean),
        })
    for label, b in (("Q1413 exact W<=6", q1413_full[
            "actual_usable_points_B_before_folding"]),
            ("Q1437 conditional W<=7", q1437_sample[
                "conditional_estimate"]["conditional_B"])):
        mean = (b * (b - 1) * (b - 2) / 6) / order131
        fixed_anchor_model.append({
            "degree_n": 131, "base_source": label,
            "factor_base_actual_B": (b if "exact" in label else None),
            "conditional_factor_base_B": (b if "conditional" in label else None),
            "mean_unordered_three_subsets_per_uniform_target_and_fixed_anchor": mean,
            "log2_mean": math.log2(mean),
            "anchors_per_expected_hit": 1 / mean,
            "log2_anchors_per_expected_hit": -math.log2(mean),
        })
    q1440_dir = HERE / "q1440_witness_anchor"
    q1440_protocol_path = q1440_dir / "protocol.json"
    q1440_verification_path = q1440_dir / "verification.json"
    q1440_witness_path = q1440_dir / "known_witness_verification.json"
    q1440_protocol = json.loads(q1440_protocol_path.read_text())
    q1440_verification = json.loads(q1440_verification_path.read_text())
    q1440_witness = json.loads(q1440_witness_path.read_text())
    assert q1440_protocol["proposal_id"] == "Q1440"
    assert q1440_protocol["candidate_id"] is None
    assert q1440_protocol["isogeny"] == "none"
    assert q1440_verification["status"] == q1440_witness["status"] == "passed"
    assert q1440_verification["protocol_sha256"] == sha(q1440_protocol_path)
    assert q1440_witness["protocol_sha256"] == sha(q1440_protocol_path)
    q1440_cells = []
    for key in q1440_protocol["run_order"]:
        frozen = q1440_protocol["cells"][key]
        receipt_path = q1440_dir / "runs" / key / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        checked = next(row for row in q1440_verification["rows"]
                       if row["key"] == key)
        witness = next(row for row in q1440_witness["rows"]
                       if row["key"] == key)
        assert checked["receipt_sha256"] == sha(receipt_path)
        assert witness["verified_relation_status"] == (
            "verified_four_point_relation")
        assert receipt["protocol_sha256"] == sha(q1440_protocol_path)
        assert receipt["stage_run_id"] == frozen["stage_run_id"]
        assert receipt["curve_id"] == frozen["curve_id"]
        assert receipt["factor_base_actual_B"] == frozen[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == frozen["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == frozen[
            "factor_base_enumerated_set_sha256"]
        assert receipt["formula_raw_sha256"] == frozen[
            "formula_raw_sha256"]
        assert receipt["verified_relation_count"] == 0
        assert receipt["complete_solve_work_log2"] is None
        q1440_cells.append({
            "key": key, "degree_n": receipt["degree_n"],
            "cell": receipt["cell"], "curve_id": receipt["curve_id"],
            "target_origin": receipt["target_origin"],
            "input_law": receipt["input_law"],
            "public_target": receipt["public_target"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "workload_id": receipt["workload_id"],
            "stage_run_id": receipt["stage_run_id"],
            "anchor_raw_x": receipt["anchor_raw_x"],
            "adjusted_target_x_count": receipt[
                "adjusted_target_x_count"],
            "known_witness_model_satisfies_formula": True,
            "solver_status": receipt["solver_status"],
            "solver_conflicts_reported": receipt[
                "solver_conflicts_reported"],
            "verified_relation_count": receipt[
                "verified_relation_count"],
            "formula_and_gates": receipt["formula"]["and_gates"],
            "formula_xor_rows": receipt["formula"]["xor_rows"],
            "target_preparation_and_formula_wall_seconds_exploratory": receipt[
                "target_preparation_and_formula_wall_seconds_exploratory"],
            "solver_wall_seconds_exploratory": receipt[
                "solver_wall_seconds_exploratory"],
            "charged_stage_wall_seconds_exploratory": receipt[
                "charged_stage_wall_seconds_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["solver_status"] for row in q1440_cells] == [
        "censored", "censored", "external_timeout", "external_timeout"]
    assert [row["solver_conflicts_reported"] for row in q1440_cells] == [
        1000001, 1000002, None, None]
    q1441_dir = HERE / "q1441_full_scan_budget"
    q1441_protocol_path = q1441_dir / "protocol.json"
    q1441_result_path = q1441_dir / "result.json"
    q1441_verification_path = q1441_dir / "verification.json"
    q1441_protocol = json.loads(q1441_protocol_path.read_text())
    q1441_result = json.loads(q1441_result_path.read_text())
    q1441_verification = json.loads(q1441_verification_path.read_text())
    assert q1441_protocol["proposal_id"] == q1441_result[
        "proposal_id"] == "Q1441"
    assert q1441_protocol["candidate_id"] is q1441_result[
        "candidate_id"] is None
    assert q1441_protocol["isogeny"] == q1441_result[
        "isogeny"] == "none"
    assert q1441_result["protocol_sha256"] == sha(q1441_protocol_path)
    assert q1441_result["source_sha256"] == sha(q1441_dir / "screen.py")
    assert q1441_verification["status"] == "passed"
    assert q1441_verification["result_sha256"] == sha(q1441_result_path)
    assert q1441_verification["protocol_sha256"] == sha(
        q1441_protocol_path)
    assert q1441_result["complete_solve_work_log2"] is None
    assert q1441_result["challenge_dispatch_allowed"] is False
    assert len(q1441_result["rows"]) == 4
    assert q1441_result["rows"][0][
        "actual_usable_points_B_before_folding"] == q1413_full[
            "actual_usable_points_B_before_folding"]
    assert q1441_result["rows"][0][
        "minimum_queries_for_declared_policy"] == q1414_bound[
            "query_bounds"]["rank_success_95_percent"][
                "minimum_uniform_nonidentity_queries"]
    assert all(row["actual_usable_points_B_before_folding"] is None
               for row in q1441_result["rows"][1:])
    assert all(row["one_action_scan_below_budget"] is False
               for row in q1441_result["rows"][1:])
    q1442_dir = HERE / "q1442_selected_base_screen"
    q1442_protocol_path = q1442_dir / "protocol.json"
    q1442_result_path = q1442_dir / "result.json"
    q1442_verification_path = q1442_dir / "verification.json"
    q1442_protocol = json.loads(q1442_protocol_path.read_text())
    q1442_result = json.loads(q1442_result_path.read_text())
    q1442_verification = json.loads(q1442_verification_path.read_text())
    assert q1442_protocol["proposal_id"] == q1442_result[
        "proposal_id"] == "Q1442"
    assert q1442_protocol["candidate_id"] is q1442_result[
        "candidate_id"] is None
    assert q1442_protocol["isogeny"] == q1442_result[
        "isogeny"] == "none"
    assert q1442_result["protocol_sha256"] == sha(q1442_protocol_path)
    assert q1442_result["source_sha256"] == sha(q1442_dir / "screen.py")
    assert q1442_verification["status"] == "passed"
    assert q1442_verification["result_sha256"] == sha(q1442_result_path)
    assert q1442_verification["protocol_sha256"] == sha(
        q1442_protocol_path)
    assert q1442_result["actual_selected_B"] is None
    assert q1442_result["actual_selected_K"] is None
    assert q1442_result["selected_base_set_sha256"] is None
    assert q1442_result["complete_solve_work_log2"] is None
    assert q1442_result["challenge_dispatch_allowed"] is False
    assert len(q1442_result["rows"]) == 3
    q1443_dir = HERE / "q1443_residual_pair_bound"
    q1443_protocol_path = q1443_dir / "protocol.json"
    q1443_result_path = q1443_dir / "result.json"
    q1443_verification_path = q1443_dir / "verification.json"
    q1443_protocol = json.loads(q1443_protocol_path.read_text())
    q1443_result = json.loads(q1443_result_path.read_text())
    q1443_verification = json.loads(q1443_verification_path.read_text())
    assert q1443_protocol["proposal_id"] == q1443_result[
        "proposal_id"] == "Q1443"
    assert q1443_protocol["candidate_id"] is q1443_result[
        "candidate_id"] is None
    assert q1443_protocol["isogeny"] == q1443_result[
        "isogeny"] == "none"
    assert q1443_result["protocol_sha256"] == sha(q1443_protocol_path)
    assert q1443_result["source_sha256"] == sha(q1443_dir / "screen.py")
    assert q1443_verification["status"] == "passed"
    assert q1443_verification["protocol_sha256"] == sha(
        q1443_protocol_path)
    assert q1443_verification["result_sha256"] == sha(
        q1443_result_path)
    assert len(q1443_result["rows"]) == 4
    assert q1443_result["rows"][-1]["conditional_base_model"] is True
    assert q1443_result["rows"][-1]["actual_B"] is None
    assert q1443_result["complete_solve_work_log2"] is None
    assert q1443_result["challenge_dispatch_allowed"] is False
    q1444_dir = HERE / "q1444_wdsat_adapter"
    q1444_protocol_path = q1444_dir / "protocol.json"
    q1444_verification_path = q1444_dir / "verification.json"
    q1444_protocol = json.loads(q1444_protocol_path.read_text())
    q1444_verification = json.loads(q1444_verification_path.read_text())
    assert q1444_protocol["proposal_id"] == q1444_verification[
        "proposal_id"] == "Q1444"
    assert q1444_protocol["candidate_id"] is None
    assert q1444_protocol["isogeny"] == "none"
    assert q1444_verification["status"] == "passed"
    assert q1444_verification["protocol_sha256"] == sha(
        q1444_protocol_path)
    assert set(q1444_verification["rows"]) == set(q1444_protocol[
        "run_order"])
    assert q1444_verification["ordinary_verified_relations"] == 0
    assert q1444_verification["natural_relation_yield"] is None
    assert q1444_verification["cost_per_useful_row"] is None
    assert q1444_verification["complete_n131_log2_work"] is None
    assert q1444_verification["challenge_run_admitted"] is False
    q1445_dir = HERE / "q1445_matched_pair_table"
    q1445_protocol_path = q1445_dir / "protocol.json"
    q1445_verification_path = q1445_dir / "verification.json"
    q1445_protocol = json.loads(q1445_protocol_path.read_text())
    q1445_verification = json.loads(q1445_verification_path.read_text())
    assert q1445_protocol["proposal_id"] == q1445_verification[
        "proposal_id"] == "Q1445"
    assert q1445_protocol["candidate_id"] is None
    assert q1445_protocol["isogeny"] == "none"
    assert q1445_verification["status"] == "pass"
    assert q1445_verification["protocol_sha256"] == sha(q1445_protocol_path)
    assert q1445_verification["complete_n131_log2_work"] is None
    assert q1445_verification["challenge_run_admitted"] is False
    q1445_rows = []
    for n in (53, 83):
        cell = q1445_protocol["cells"][str(n)]
        receipt_path = q1445_dir / f"runs/n{n}_ordinary.json"
        receipt = json.loads(receipt_path.read_text())
        verified = next(row for row in q1445_verification["cells"]
                        if row["degree"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert receipt["protocol_sha256"] == sha(q1445_protocol_path)
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["workload_id"] == cell["workload_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["verified_relation_count"] == verified[
            "verified_relation_count"]
        table = receipt["target_independent_table"]
        query = receipt["ordinary_query"]
        assert query["identity_or_zero_residual_pairs"] == 0
        q1445_rows.append({
            "proposal_id": "Q1445", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "matched_public_target": cell["public_target"],
            "target_independent_base_load_ns_exploratory": receipt[
                "target_independent_base_load_ns"],
            "table_pair_samples": table["samples"],
            "table_distinct_keys": table["distinct_keys"],
            "table_wall_ns_exploratory": table["wall_ns"],
            "table_sampler_counters": table["sampler"],
            "ordinary_query_status": query["status"],
            "ordinary_query_pair_samples": query["samples"],
            "ordinary_query_key_hits": query["key_hits"],
            "ordinary_query_wall_ns_exploratory": query["wall_ns"],
            "ordinary_query_sampler_counters": query["sampler"],
            "main_loop_point_add_calls": (
                table["samples"] + 2 * query["samples"]),
            "main_loop_point_add_scope": (
                "table pair sums, query pair sums, and target residuals; "
                "excludes base generation, subgroup checks, and replay"),
            "peak_rss_raw": receipt["peak_rss_raw"],
            "peak_rss_units": receipt["peak_rss_units"],
            "verified_relation_count": receipt["verified_relation_count"],
            "independent_relation_replay": verified["relation_check"],
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "natural_relation_yield_estimate": None,
            "calibrated_field_operation_cost": None,
            "verified_single_target_dlp": False,
            "replicates": 1,
            "cpu_isolation_receipt": None,
            "complete_n131_log2_work": None,
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["verified_relation_count"] for row in q1445_rows] == [1, 0]
    q1446_dir = HERE / "q1446_joint_pair_span"
    q1446_protocol_path = q1446_dir / "protocol.json"
    q1446_verification_path = q1446_dir / "verification.json"
    q1446_protocol = json.loads(q1446_protocol_path.read_text())
    q1446_verification = json.loads(q1446_verification_path.read_text())
    assert q1446_protocol["proposal_id"] == q1446_verification[
        "proposal_id"] == "Q1446"
    assert q1446_protocol["candidate_id"] is None
    assert q1446_protocol["isogeny"] == "none"
    assert q1446_verification["status"] == "pass"
    assert q1446_verification["protocol_sha256"] == sha(q1446_protocol_path)
    assert q1446_verification["complete_n131_log2_work"] is None
    assert q1446_verification["challenge_run_admitted"] is False
    q1446_rows = []
    for n in (53, 83):
        cell = q1446_protocol["cells"][str(n)]
        matched = q1445_protocol["cells"][str(n)]
        for name, q1445_name in (
            ("curve_id", "curve_id"),
            ("factor_base_actual_B", "factor_base_actual_B"),
            ("folded_columns_K", "folded_columns_K"),
            ("factor_base_enumerated_set_sha256",
             "factor_base_enumerated_set_sha256"),
            ("public_target", "public_target"),
        ):
            assert cell[name] == matched[q1445_name], name
        receipt_path = q1446_dir / f"runs/n{n}_ordinary/receipt.json"
        receipt = json.loads(receipt_path.read_text())
        verified = next(row for row in q1446_verification["rows"]
                        if row["degree"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert receipt["protocol_sha256"] == sha(q1446_protocol_path)
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["public_target"] == cell["public_target"]
        assert receipt["verified_relation_count"] == verified[
            "verified_relation_count"] == 0
        report = receipt["solver_report"]
        assert report is not None
        assert report["stop_reason"] == "wall_cap"
        assert report["final_root_calls"] == 1
        assert report["complete_pair_visits"] == 0
        sampled_rejections_by_pair = [sum(
            row["pair"] == pair
            for row in report["span_rejection_snapshots"])
            for pair in (0, 1)]
        assert all(sampled_rejections_by_pair)
        assert sum(sampled_rejections_by_pair) == verified[
            "sampled_span_replay"]["sampled_rejections_replayed"]
        q1446_rows.append({
            "proposal_id": "Q1446", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "matched_q1445_public_target": matched["public_target"],
            "status": receipt["solver_status"],
            "native_stop_reason": report["stop_reason"],
            "native_decisions": report["decisions"],
            "native_conflicts": report["conflicts"],
            "final_root_calls": report["final_root_calls"],
            "complete_pair_visits": report["complete_pair_visits"],
            "span_checks_pair0": report["span_checks_pair0"],
            "span_checks_pair1": report["span_checks_pair1"],
            "span_rejections_pair0": report["span_rejections_pair0"],
            "span_rejections_pair1": report["span_rejections_pair1"],
            "span_field_mul_calls": report["span_field_mul_calls"],
            "field_mul_calls": report["field_mul_calls"],
            "field_sqr_calls": report["field_sqr_calls"],
            "field_inv_calls": report["field_inv_calls"],
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "online_stage_wall_ns_exploratory": receipt[
                "online_stage_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "sampled_span_replay": verified["sampled_span_replay"],
            "sampled_rejection_replay_counts_by_pair":
                sampled_rejections_by_pair,
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1447_dir = HERE / "q1447_midpoint_support"
    q1447_protocol_path = q1447_dir / "protocol.json"
    q1447_result_path = q1447_dir / "result.json"
    q1447_verification_path = q1447_dir / "verification.json"
    q1447_protocol = json.loads(q1447_protocol_path.read_text())
    q1447_result = json.loads(q1447_result_path.read_text())
    q1447_verification = json.loads(q1447_verification_path.read_text())
    assert q1447_protocol["proposal_id"] == q1447_result[
        "proposal_id"] == q1447_verification["proposal_id"] == "Q1447"
    assert q1447_protocol["candidate_id"] is q1447_result[
        "candidate_id"] is None
    assert q1447_result["isogeny"] == "none"
    assert q1447_verification["status"] == "pass"
    assert q1447_result["protocol_sha256"] == sha(q1447_protocol_path)
    assert q1447_verification["result_sha256"] == sha(q1447_result_path)
    assert q1447_result["complete_n131_log2_work"] is None
    assert q1447_result["challenge_run_admitted"] is False
    assert len(q1447_result["rows"]) == 4
    for i, n in enumerate((53, 83)):
        screen = q1447_result["rows"][i]
        matched = q1445_protocol["cells"][str(n)]
        assert screen["curve_id"] == matched["curve_id"]
        assert screen["actual_B"] == matched["factor_base_actual_B"]
        assert screen["actual_K"] == matched["folded_columns_K"]
        assert screen["base_set_sha256"] == matched[
            "factor_base_enumerated_set_sha256"]
    assert q1447_result["rows"][2]["curve_id"] == q1443_result[
        "rows"][2]["curve_id"]
    assert q1447_result["rows"][2]["actual_B"] == q1443_result[
        "rows"][2]["actual_B"]
    assert q1447_result["rows"][2]["base_set_sha256"] == q1443_result[
        "rows"][2]["base_set_sha256"]
    assert q1447_result["rows"][3]["conditional_base_model"] is True
    assert q1447_result["rows"][3]["actual_B"] is None
    q1448_dir = HERE / "q1448_torsion_phi5"
    q1448_protocol_path = q1448_dir / "protocol.json"
    q1448_verification_path = q1448_dir / "verification.json"
    q1448_protocol = json.loads(q1448_protocol_path.read_text())
    q1448_verification = json.loads(q1448_verification_path.read_text())
    assert q1448_protocol["proposal_id"] == q1448_verification[
        "proposal_id"] == "Q1448"
    assert q1448_protocol["candidate_id"] is q1448_verification[
        "candidate_id"] is None
    assert q1448_protocol["isogeny"] == q1448_verification[
        "isogeny"] == "none"
    assert q1448_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1448_verification["status"] == "pass"
    assert q1448_verification["protocol_sha256"] == sha(q1448_protocol_path)
    assert q1448_verification["complete_n131_log2_work"] is None
    assert q1448_verification["challenge_run_admitted"] is False
    q1448_rows = []
    for n in (53, 83):
        cell = q1448_protocol["cells"][str(n)]
        matched = q1445_protocol["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target"):
            assert cell[name] == matched[name], name
        assert cell["workload_id"] == q1438_solver_protocol[
            "workloads"][f"n{n}_ordinary"]["workload_id"]
        receipt_path = q1448_dir / f"runs/n{n}_ordinary/receipt.json"
        stdout_path = q1448_dir / f"runs/n{n}_ordinary/solver.stdout.txt"
        receipt = json.loads(receipt_path.read_text())
        stdout = stdout_path.read_text()
        verified = next(row for row in q1448_verification["rows"]
                        if row["degree_n"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert verified["solver_status"] == receipt["solver_status"] == "censored"
        assert receipt["protocol_sha256"] == sha(q1448_protocol_path)
        assert receipt["solver_stdout_sha256"] == sha(stdout_path)
        assert receipt["cadical_binary_sha256"] == q1448_protocol[
            "cadical_binary_sha256"]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "workload_id", "cnf_variables", "cnf_clauses",
                     "cnf_raw_bytes"):
            assert receipt[name] == cell[name], name
        assert receipt["verified_relation_count"] == verified[
            "verified_relation_count"] == 0
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["cost_per_useful_row"] is None
        stats = {}
        for name in ("conflicts", "decisions", "propagations"):
            match = re.search(rf"^c {name}:\s+(\d+)\s", stdout, re.M)
            assert match is not None, name
            stats[name] = int(match.group(1))
        q1448_rows.append({
            "proposal_id": "Q1448", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "target_preimage_x_count": receipt["target_preimage_x_count"],
            "status": "censored_at_60_second_solver_wall_cap",
            "cnf_variables": receipt["cnf_variables"],
            "cnf_clauses": receipt["cnf_clauses"],
            "cnf_raw_bytes": receipt["cnf_raw_bytes"],
            "solver_conflicts": stats["conflicts"],
            "solver_decisions": stats["decisions"],
            "solver_propagations": stats["propagations"],
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "instrumentation_inclusive_stage_wall_ns_exploratory": receipt[
                "charged_target_dependent_stage_wall_ns_exploratory"],
            "stage_interval_includes_cnf_archive_compression": True,
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1449_dir = HERE / "q1449_phi5_native_xor"
    q1449_protocol_path = q1449_dir / "protocol.json"
    q1449_controls_path = q1449_dir / "controls.json"
    q1449_verification_path = q1449_dir / "verification.json"
    q1449_protocol = json.loads(q1449_protocol_path.read_text())
    q1449_controls = json.loads(q1449_controls_path.read_text())
    q1449_verification = json.loads(q1449_verification_path.read_text())
    assert q1449_protocol["proposal_id"] == q1449_controls[
        "proposal_id"] == q1449_verification["proposal_id"] == "Q1449"
    assert q1449_protocol["candidate_id"] is q1449_verification[
        "candidate_id"] is None
    assert q1449_protocol["isogeny"] == q1449_verification[
        "isogeny"] == "none"
    assert q1449_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1449_controls["status"] == q1449_verification[
        "status"] == "pass"
    assert q1449_protocol["parent_q1448_protocol_sha256"] == sha(
        q1448_protocol_path)
    assert q1449_protocol["controls_sha256"] == sha(q1449_controls_path)
    assert q1449_verification["protocol_sha256"] == sha(q1449_protocol_path)
    assert q1449_verification["ordinary_n83_relation_measured"] is False
    assert q1449_verification["complete_n131_log2_work"] is None
    assert q1449_verification["challenge_run_admitted"] is False
    q1449_rows = []
    for n in (53, 83):
        cell = q1449_protocol["cells"][str(n)]
        matched = q1448_protocol["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "workload_id", "target_preimage_x_count"):
            assert cell[name] == matched[name], name
        receipt_path = q1449_dir / f"runs/n{n}_ordinary/receipt.json"
        stdout_path = q1449_dir / f"runs/n{n}_ordinary/attempt_000.stdout.txt"
        receipt = json.loads(receipt_path.read_text())
        stdout = stdout_path.read_text()
        verified = next(row for row in q1449_verification["rows"]
                        if row["degree_n"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert verified["status"] == receipt["status"] == "solver_censored"
        assert receipt["protocol_sha256"] == sha(q1449_protocol_path)
        assert receipt["cms_binary_sha256"] == q1449_protocol[
            "cms_binary_sha256"]
        assert receipt["verified_relation_count"] == 0
        assert receipt["complete_n131_log2_work"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["solver_status"] == "external_timeout"
        assert attempt["stdout_sha256"] == sha(stdout_path)
        assert re.search(r"^c \[matrix\] Using 0 matrices recovered from ",
                         stdout, re.M)
        progress = re.findall(r"^c rst\s+.*$", stdout, re.M)
        assert progress
        last_conflicts_rounded = progress[-1].split()[6]
        assert last_conflicts_rounded.endswith("K")
        q1449_rows.append({
            "proposal_id": "Q1449", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "status": receipt["status"],
            "attempt_count": len(receipt["attempts"]),
            "invalid_models_blocked": len(receipt["blocked_assignments"]),
            "xcnf_variables": cell["xcnf_variables"],
            "cnf_clauses": cell["cnf_clauses"],
            "native_xor_rows": cell["native_xor_rows"],
            "native_gaussian_matrices_used": 0,
            "last_progress_conflicts_rounded": last_conflicts_rounded,
            "exact_final_solver_operation_counts": None,
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "target_dependent_stage_wall_ns_exploratory": receipt[
                "target_dependent_stage_wall_ns_exploratory"],
            "archive_wall_ns_outside_stage": receipt[
                "archive_wall_ns_outside_stage"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1450_dir = HERE / "q1450_phi5_gauss"
    q1450_protocol_path = q1450_dir / "protocol.json"
    q1450_controls_path = q1450_dir / "controls.json"
    q1450_verification_path = q1450_dir / "verification.json"
    q1450_protocol = json.loads(q1450_protocol_path.read_text())
    q1450_controls = json.loads(q1450_controls_path.read_text())
    q1450_verification = json.loads(q1450_verification_path.read_text())
    assert q1450_protocol["proposal_id"] == q1450_controls[
        "proposal_id"] == q1450_verification["proposal_id"] == "Q1450"
    assert q1450_protocol["candidate_id"] is q1450_verification[
        "candidate_id"] is None
    assert q1450_protocol["isogeny"] == q1450_verification[
        "isogeny"] == "none"
    assert q1450_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1450_controls["status"] == q1450_verification[
        "status"] == "pass"
    assert q1450_protocol["parent_q1449_protocol_sha256"] == sha(
        q1449_protocol_path)
    assert q1450_protocol["controls_sha256"] == sha(q1450_controls_path)
    assert q1450_verification["protocol_sha256"] == sha(q1450_protocol_path)
    assert q1450_verification["ordinary_n83_relation_measured"] is False
    assert q1450_verification["complete_n131_log2_work"] is None
    assert q1450_verification["challenge_run_admitted"] is False
    assert [row["gaussian_matrices_used"] for row in q1450_controls[
        "rows"]] == [8, 6]
    q1450_rows = []
    for n in (53, 83):
        cell = q1450_protocol["cells"][str(n)]
        matched = q1449_protocol["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "workload_id", "target_preimage_x_count",
                     "initial_xcnf_sha256", "xcnf_variables",
                     "cnf_clauses", "native_xor_rows"):
            assert cell[name] == matched[name], name
        receipt_path = q1450_dir / f"runs/n{n}_ordinary/receipt.json"
        stdout_path = q1450_dir / f"runs/n{n}_ordinary/attempt_000.stdout.txt"
        receipt = json.loads(receipt_path.read_text())
        stdout = stdout_path.read_text()
        verified = next(row for row in q1450_verification["rows"]
                        if row["degree_n"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert verified["status"] == receipt["status"] == "solver_censored"
        assert receipt["protocol_sha256"] == sha(q1450_protocol_path)
        assert receipt["cms_binary_sha256"] == q1450_protocol[
            "cms_binary_sha256"]
        assert receipt["verified_relation_count"] == 0
        assert receipt["complete_n131_log2_work"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["solver_status"] == "external_timeout"
        assert attempt["stdout_sha256"] == sha(stdout_path)
        assert attempt["initial_gaussian_matrices_used"] > 0
        progress = re.findall(r"^c rst\s+.*$", stdout, re.M)
        assert progress
        last_conflicts_rounded = progress[-1].split()[6]
        assert last_conflicts_rounded.endswith("K")
    q1450_rows.append({
            "proposal_id": "Q1450", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "status": receipt["status"],
            "attempt_count": len(receipt["attempts"]),
            "gaussian_matrices_used": attempt[
                "initial_gaussian_matrices_used"],
            "last_progress_conflicts_rounded": last_conflicts_rounded,
            "exact_final_solver_operation_counts": None,
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "target_dependent_stage_wall_ns_exploratory": receipt[
                "target_dependent_stage_wall_ns_exploratory"],
            "archive_wall_ns_outside_stage": receipt[
                "archive_wall_ns_outside_stage"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1451_dir = HERE / "q1451_phi5_fixed_target"
    q1451_protocol_path = q1451_dir / "protocol.json"
    q1451_controls_path = q1451_dir / "controls.json"
    q1451_verification_path = q1451_dir / "verification.json"
    q1451_protocol = json.loads(q1451_protocol_path.read_text())
    q1451_controls = json.loads(q1451_controls_path.read_text())
    q1451_verification = json.loads(q1451_verification_path.read_text())
    assert q1451_protocol["proposal_id"] == q1451_controls[
        "proposal_id"] == q1451_verification["proposal_id"] == "Q1451"
    assert q1451_protocol["candidate_id"] is q1451_verification[
        "candidate_id"] is None
    assert q1451_protocol["isogeny"] == q1451_verification[
        "isogeny"] == "none"
    assert q1451_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1451_controls["status"] == q1451_verification[
        "status"] == "pass"
    assert q1451_protocol["parent_q1450_protocol_sha256"] == sha(
        q1450_protocol_path)
    assert q1451_protocol["controls_sha256"] == sha(q1451_controls_path)
    assert q1451_verification["protocol_sha256"] == sha(
        q1451_protocol_path)
    assert q1451_verification["ordinary_n83_relation_measured"] is False
    assert q1451_verification["complete_n131_log2_work"] is None
    assert q1451_verification["challenge_run_admitted"] is False
    assert all(row["verified_relation"]["status"] ==
               "verified_four_point_relation" for row in q1451_controls[
                   "rows"])
    q1451_rows = []
    for n in (53, 83):
        cell = q1451_protocol["cells"][str(n)]
        matched = q1450_protocol["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "workload_id"):
            assert cell[name] == matched[name], name
        assert cell["target_preimage_index"] == 0
        assert cell["target_preimage_x_count"] == 1
        assert cell["full_target_preimage_x_count"] == matched[
            "target_preimage_x_count"]
        assert cell["and_gates"] > 0
        assert cell["cnf_clauses"] < matched["cnf_clauses"]
        receipt_path = q1451_dir / f"runs/n{n}_ordinary/receipt.json"
        stdout_path = q1451_dir / f"runs/n{n}_ordinary/attempt_000.stdout.txt"
        receipt = json.loads(receipt_path.read_text())
        stdout = stdout_path.read_text()
        verified = next(row for row in q1451_verification["rows"]
                        if row["degree_n"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert verified["status"] == receipt["status"] == "solver_censored"
        assert receipt["protocol_sha256"] == sha(q1451_protocol_path)
        assert receipt["cms_binary_sha256"] == q1451_protocol[
            "cms_binary_sha256"]
        assert receipt["verified_relation_count"] == 0
        assert receipt["complete_n131_log2_work"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["solver_status"] == "external_timeout"
        assert attempt["stdout_sha256"] == sha(stdout_path)
        assert attempt["initial_gaussian_matrices_used"] == 5
        progress = re.findall(r"^c rst\s+.*$", stdout, re.M)
        assert progress
        last_conflicts_rounded = progress[-1].split()[6]
        assert last_conflicts_rounded.endswith("K")
        q1451_rows.append({
            "proposal_id": "Q1451", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "target_preimage_index": cell["target_preimage_index"],
            "selected_raw_target_x": cell["selected_raw_target_x"],
            "target_preimage_x_count": cell["target_preimage_x_count"],
            "full_target_preimage_x_count": cell[
                "full_target_preimage_x_count"],
            "and_gates": cell["and_gates"],
            "xcnf_variables": cell["xcnf_variables"],
            "cnf_clauses": cell["cnf_clauses"],
            "native_xor_rows": cell["native_xor_rows"],
            "status": receipt["status"],
            "attempt_count": len(receipt["attempts"]),
            "gaussian_matrices_used": attempt[
                "initial_gaussian_matrices_used"],
            "last_progress_conflicts_rounded": last_conflicts_rounded,
            "exact_final_solver_operation_counts": None,
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "target_dependent_stage_wall_ns_exploratory": receipt[
                "target_dependent_stage_wall_ns_exploratory"],
            "archive_wall_ns_outside_stage": receipt[
                "archive_wall_ns_outside_stage"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1452_dir = HERE / "q1452_known_satisfiable_phi5"
    q1452_protocol_path = q1452_dir / "protocol.json"
    q1452_controls_path = q1452_dir / "controls.json"
    q1452_verification_path = q1452_dir / "verification.json"
    q1452_protocol = json.loads(q1452_protocol_path.read_text())
    q1452_controls = json.loads(q1452_controls_path.read_text())
    q1452_verification = json.loads(q1452_verification_path.read_text())
    assert q1452_protocol["proposal_id"] == q1452_controls[
        "proposal_id"] == q1452_verification["proposal_id"] == "Q1452"
    assert q1452_protocol["candidate_id"] is q1452_verification[
        "candidate_id"] is None
    assert q1452_protocol["isogeny"] == q1452_verification[
        "isogeny"] == "none"
    assert q1452_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1452_controls["status"] == q1452_verification[
        "status"] == "pass"
    assert q1452_protocol["parent_q1451_protocol_sha256"] == sha(
        q1451_protocol_path)
    assert q1452_protocol["controls_sha256"] == sha(q1452_controls_path)
    assert q1452_verification["protocol_sha256"] == sha(
        q1452_protocol_path)
    assert q1452_verification["ordinary_n53_relation_measured"] is False
    assert q1452_verification["complete_n131_log2_work"] is None
    assert q1452_verification["challenge_run_admitted"] is False
    assert q1452_controls["target_preimage_index"] == 201
    assert q1452_controls["witness_not_supplied_to_ordinary_solver"] is True
    assert q1452_controls["archived_pinned_verified_relation"]["status"] == (
        "verified_four_point_relation")
    q1452_cell = q1452_protocol["cells"]["53"]
    q1451_cell = q1451_protocol["cells"]["53"]
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "workload_id", "and_gates", "xcnf_variables",
                 "cnf_clauses", "native_xor_rows"):
        assert q1452_cell[name] == q1451_cell[name], name
    assert q1452_cell["target_preimage_index"] == 201
    assert q1452_cell["selected_raw_target_x"] == q1452_controls[
        "selected_raw_target_x"]
    assert q1452_cell["full_target_preimage_x_count"] == 428
    q1452_receipt_path = (q1452_dir /
                          "runs/n53_known_satisfiable_ordinary/receipt.json")
    q1452_stdout_path = (q1452_dir /
                         "runs/n53_known_satisfiable_ordinary/attempt_000.stdout.txt")
    q1452_receipt = json.loads(q1452_receipt_path.read_text())
    q1452_verified = q1452_verification["rows"][0]
    assert q1452_verified["receipt_sha256"] == sha(q1452_receipt_path)
    assert q1452_verified["status"] == q1452_receipt[
        "status"] == "solver_censored"
    assert q1452_receipt["protocol_sha256"] == sha(q1452_protocol_path)
    assert q1452_receipt["cms_binary_sha256"] == q1452_protocol[
        "cms_binary_sha256"]
    assert q1452_receipt["selected_slice_known_satisfiable_by_archived_witness"] is True
    assert q1452_receipt["witness_leaf_values_supplied_to_solver"] is False
    assert q1452_receipt["verified_relation_count"] == 0
    assert q1452_receipt["complete_n131_log2_work"] is None
    assert len(q1452_receipt["attempts"]) == 1
    q1452_attempt = q1452_receipt["attempts"][0]
    assert q1452_attempt["solver_status"] == "external_timeout"
    assert q1452_attempt["stdout_sha256"] == sha(q1452_stdout_path)
    assert q1452_attempt["initial_gaussian_matrices_used"] == 5
    assert q1452_attempt["last_progress_conflicts_rounded"] == "369K"
    q1452_rows = [{
        "proposal_id": "Q1452", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "degree": 53, "curve_id": q1452_cell["curve_id"],
        "workload_id": q1452_cell["workload_id"],
        "factor_base_actual_B": q1452_cell["factor_base_actual_B"],
        "folded_columns_K": q1452_cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": q1452_cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": q1452_cell["public_target"],
        "target_preimage_index": 201,
        "selected_raw_target_x": q1452_cell["selected_raw_target_x"],
        "selected_slice_known_satisfiable_by_archived_witness": True,
        "witness_leaf_values_supplied_to_solver": False,
        "and_gates": q1452_cell["and_gates"],
        "xcnf_variables": q1452_cell["xcnf_variables"],
        "cnf_clauses": q1452_cell["cnf_clauses"],
        "native_xor_rows": q1452_cell["native_xor_rows"],
        "status": q1452_receipt["status"],
        "attempt_count": 1,
        "gaussian_matrices_used": 5,
        "last_progress_conflicts_rounded": "369K",
        "exact_final_solver_operation_counts": None,
        "solver_child_user_cpu_ns": q1452_attempt[
            "solver_child_user_cpu_ns"],
        "solver_child_system_cpu_ns": q1452_attempt[
            "solver_child_system_cpu_ns"],
        "formula_build_wall_ns_exploratory": q1452_receipt[
            "formula_build_wall_ns_exploratory"],
        "solver_process_wall_ns_exploratory": q1452_receipt[
            "solver_process_wall_ns_exploratory"],
        "target_dependent_stage_wall_ns_exploratory": q1452_receipt[
            "target_dependent_stage_wall_ns_exploratory"],
        "archive_wall_ns_outside_stage": q1452_receipt[
            "archive_wall_ns_outside_stage"],
        "peak_child_rss_raw": q1452_receipt["peak_child_rss_raw"],
        "peak_child_rss_units": q1452_receipt["peak_child_rss_units"],
        "verified_relation_count": 0,
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "cpu_isolation_receipt": None,
        "receipt_sha256": sha(q1452_receipt_path),
    }]
    q1453_dir = HERE / "q1453_projective_phi5"
    q1453_protocol_path = q1453_dir / "protocol.json"
    q1453_controls_path = q1453_dir / "controls.json"
    q1453_algebra_path = q1453_dir / "algebra_validation.json"
    q1453_verification_path = q1453_dir / "verification.json"
    q1453_protocol = json.loads(q1453_protocol_path.read_text())
    q1453_controls = json.loads(q1453_controls_path.read_text())
    q1453_algebra = json.loads(q1453_algebra_path.read_text())
    q1453_verification = json.loads(q1453_verification_path.read_text())
    assert q1453_protocol["proposal_id"] == q1453_controls[
        "proposal_id"] == q1453_algebra["proposal_id"] == (
            q1453_verification["proposal_id"]) == "Q1453"
    assert q1453_protocol["candidate_id"] is q1453_verification[
        "candidate_id"] is None
    assert q1453_protocol["isogeny"] == q1453_verification[
        "isogeny"] == "none"
    assert q1453_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1453_controls["status"] == q1453_algebra[
        "status"] == q1453_verification["status"] == "pass"
    assert q1453_protocol["parent_q1452_protocol_sha256"] == sha(
        q1452_protocol_path)
    assert q1453_protocol["n83_parent_q1451_protocol_sha256"] == sha(
        q1451_protocol_path)
    assert q1453_protocol["controls_sha256"] == sha(q1453_controls_path)
    assert q1453_protocol["algebra_validation_sha256"] == sha(
        q1453_algebra_path)
    assert q1453_verification["protocol_sha256"] == sha(
        q1453_protocol_path)
    assert q1453_verification["ordinary_n53_relation_measured"] is False
    assert q1453_verification["ordinary_n83_relation_measured"] is False
    assert q1453_verification["complete_n131_log2_work"] is None
    assert q1453_verification["challenge_run_admitted"] is False
    assert all(row["all_projective_equal_D8_times_original"] and
               row["archived_witness_zero_in_both_forms"]
               for row in q1453_algebra["rows"])
    assert all(row["verified_relation"]["status"] ==
               "verified_four_point_relation" for row in q1453_controls[
                   "rows"])
    q1453_rows = []
    for n in (53, 83):
        cell = q1453_protocol["cells"][str(n)]
        matched = (q1452_protocol if n == 53 else
                   q1451_protocol)["cells"][str(n)]
        for name in ("curve_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "workload_id", "target_preimage_index",
                     "selected_raw_target_x",
                     "full_target_preimage_x_count"):
            assert cell[name] == matched[name], name
        assert cell["and_gates"] > matched["and_gates"]
        assert cell["cnf_clauses"] > matched["cnf_clauses"]
        receipt_path = q1453_dir / "runs" / cell["run_label"] / "receipt.json"
        stdout_path = (q1453_dir / "runs" / cell["run_label"] /
                       "attempt_000.stdout.txt")
        receipt = json.loads(receipt_path.read_text())
        verified = next(row for row in q1453_verification["rows"]
                        if row["degree_n"] == n)
        assert verified["receipt_sha256"] == sha(receipt_path)
        assert verified["status"] == receipt["status"] == "solver_censored"
        assert receipt["protocol_sha256"] == sha(q1453_protocol_path)
        assert receipt["cms_binary_sha256"] == q1453_protocol[
            "cms_binary_sha256"]
        assert receipt["verified_relation_count"] == 0
        assert receipt["complete_n131_log2_work"] is None
        assert len(receipt["attempts"]) == 1
        attempt = receipt["attempts"][0]
        assert attempt["solver_status"] == "external_timeout"
        assert attempt["stdout_sha256"] == sha(stdout_path)
        assert attempt["initial_gaussian_matrices_used"] > 0
        q1453_rows.append({
            "proposal_id": "Q1453", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "degree": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "target_preimage_index": cell["target_preimage_index"],
            "selected_raw_target_x": cell["selected_raw_target_x"],
            "selected_slice_known_satisfiable_by_archived_witness": cell[
                "selected_slice_known_satisfiable_by_archived_witness"],
            "witness_leaf_values_supplied_to_solver": False,
            "and_gates": cell["and_gates"],
            "xcnf_variables": cell["xcnf_variables"],
            "cnf_clauses": cell["cnf_clauses"],
            "native_xor_rows": cell["native_xor_rows"],
            "status": receipt["status"],
            "attempt_count": 1,
            "gaussian_matrices_used": attempt[
                "initial_gaussian_matrices_used"],
            "last_progress_conflicts_rounded": attempt[
                "last_progress_conflicts_rounded"],
            "exact_final_solver_operation_counts": None,
            "solver_child_user_cpu_ns": attempt[
                "solver_child_user_cpu_ns"],
            "solver_child_system_cpu_ns": attempt[
                "solver_child_system_cpu_ns"],
            "formula_build_wall_ns_exploratory": receipt[
                "formula_build_wall_ns_exploratory"],
            "solver_process_wall_ns_exploratory": receipt[
                "solver_process_wall_ns_exploratory"],
            "target_dependent_stage_wall_ns_exploratory": receipt[
                "target_dependent_stage_wall_ns_exploratory"],
            "archive_wall_ns_outside_stage": receipt[
                "archive_wall_ns_outside_stage"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    q1454_dir = HERE / "q1454_phi5_conflict_cap"
    q1454_protocol_path = q1454_dir / "protocol.json"
    q1454_verification_path = q1454_dir / "verification.json"
    q1454_cap_path = q1454_dir / "cap_interpretation.json"
    q1454_protocol = json.loads(q1454_protocol_path.read_text())
    q1454_verification = json.loads(q1454_verification_path.read_text())
    q1454_cap = json.loads(q1454_cap_path.read_text())
    assert q1454_protocol["proposal_id"] == q1454_verification[
        "proposal_id"] == q1454_cap["proposal_id"] == "Q1454"
    assert q1454_protocol["candidate_id"] is q1454_verification[
        "candidate_id"] is q1454_cap["candidate_id"] is None
    assert q1454_protocol["isogeny"] == q1454_verification[
        "isogeny"] == q1454_cap["isogeny"] == "none"
    assert q1454_protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert q1454_verification["status"] == q1454_cap["status"] == "pass"
    assert q1454_protocol["parent_q1452_protocol_sha256"] == sha(
        q1452_protocol_path)
    assert q1454_protocol["cells"]["53"] == q1452_protocol["cells"]["53"]
    assert q1454_protocol["controls_sha256"] == sha(q1452_controls_path)
    assert q1454_verification["protocol_sha256"] == sha(
        q1454_protocol_path)
    assert q1454_cap["verification_sha256"] == sha(
        q1454_verification_path)
    assert q1454_verification["ordinary_n53_relation_measured"] is False
    assert q1454_cap["interpreted_outcome"] == (
        "conflict_cap_indeterminate_no_model")
    assert q1454_cap["native_exit_code"] == 15
    assert q1454_cap["exact_final_conflicts"] >= 1000000
    assert q1454_cap["exact_final_decisions"] > 0
    assert q1454_cap["successful_decomposition_cost_measured"] is False
    assert q1454_cap["complete_n131_log2_work"] is None
    assert q1454_cap["challenge_run_admitted"] is False
    q1454_cell = q1454_protocol["cells"]["53"]
    q1454_receipt_path = (q1454_dir /
                          "runs/n53_known_satisfiable_ordinary/receipt.json")
    q1454_receipt = json.loads(q1454_receipt_path.read_text())
    assert q1454_verification["rows"][0]["receipt_sha256"] == sha(
        q1454_receipt_path)
    assert q1454_cap["receipt_sha256"] == sha(q1454_receipt_path)
    assert q1454_receipt["status"] == q1454_cap[
        "raw_runner_status"] == "solver_error"
    assert q1454_receipt["verified_relation_count"] == 0
    assert len(q1454_receipt["attempts"]) == 1
    q1454_attempt = q1454_receipt["attempts"][0]
    assert q1454_attempt["exit_code"] == 15
    assert q1454_attempt["exact_final_conflicts"] == q1454_cap[
        "exact_final_conflicts"]
    assert q1454_attempt["exact_final_decisions"] == q1454_cap[
        "exact_final_decisions"]
    q1454_matched_pair = q1445_protocol["cells"]["53"]
    for key in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256", "public_target"):
        assert q1454_cell[key] == q1454_matched_pair[key], key
    assert q1445_rows[0]["verified_relation_count"] == 1
    q1454_rows = [{
        "proposal_id": "Q1454", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "degree": 53, "curve_id": q1454_cell["curve_id"],
        "workload_id": q1454_cell["workload_id"],
        "factor_base_actual_B": q1454_cell["factor_base_actual_B"],
        "folded_columns_K": q1454_cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": q1454_cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": q1454_cell["public_target"],
        "matched_pair_table_proposal_id": "Q1445",
        "matched_pair_table_workload_id": q1454_matched_pair["workload_id"],
        "matched_pair_table_receipt_sha256": q1445_rows[0][
            "receipt_sha256"],
        "matched_pair_table_verified_relations": 1,
        "matched_pair_table_speed_ratio": None,
        "target_preimage_index": q1454_cell["target_preimage_index"],
        "selected_raw_target_x": q1454_cell["selected_raw_target_x"],
        "selected_slice_known_satisfiable_by_archived_witness": True,
        "witness_leaf_values_supplied_to_solver": False,
        "status": q1454_cap["interpreted_outcome"],
        "raw_runner_status": q1454_receipt["status"],
        "native_exit_code": 15,
        "attempt_count": 1,
        "gaussian_matrices_used": q1454_attempt[
            "initial_gaussian_matrices_used"],
        "exact_final_conflicts": q1454_cap["exact_final_conflicts"],
        "exact_final_conflicts_log2": math.log2(q1454_cap[
            "exact_final_conflicts"]),
        "exact_final_decisions": q1454_cap["exact_final_decisions"],
        "final_propagations_rounded_display": q1454_cap[
            "final_propagations_rounded_display"],
        "exact_final_field_operations": None,
        "solver_child_user_cpu_ns": q1454_attempt[
            "solver_child_user_cpu_ns"],
        "solver_child_system_cpu_ns": q1454_attempt[
            "solver_child_system_cpu_ns"],
        "formula_build_wall_ns_exploratory": q1454_receipt[
            "formula_build_wall_ns_exploratory"],
        "solver_process_wall_ns_exploratory": q1454_receipt[
            "solver_process_wall_ns_exploratory"],
        "target_dependent_stage_wall_ns_exploratory": q1454_receipt[
            "target_dependent_stage_wall_ns_exploratory"],
        "archive_wall_ns_outside_stage": q1454_receipt[
            "archive_wall_ns_outside_stage"],
        "peak_child_rss_raw": q1454_receipt["peak_child_rss_raw"],
        "peak_child_rss_units": q1454_receipt["peak_child_rss_units"],
        "verified_relation_count": 0,
        "successful_decomposition_cost_measured": False,
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "cpu_isolation_receipt": None,
        "receipt_sha256": sha(q1454_receipt_path),
        "cap_interpretation_sha256": sha(q1454_cap_path),
    }]
    q1455_dir = HERE / "q1455_joint_tail"
    q1455_protocol_path = q1455_dir / "native_protocol.json"
    q1455_controls_path = q1455_dir / "controls.json"
    q1455_verification_path = q1455_dir / "native_verification.json"
    q1455_protocol = json.loads(q1455_protocol_path.read_text())
    q1455_controls = json.loads(q1455_controls_path.read_text())
    q1455_verification = json.loads(q1455_verification_path.read_text())
    assert q1455_protocol["proposal_id"] == q1455_controls[
        "proposal_id"] == q1455_verification["proposal_id"] == "Q1455"
    assert q1455_protocol["candidate_id"] is q1455_verification[
        "candidate_id"] is None
    assert q1455_protocol["isogeny"] == q1455_verification[
        "isogeny"] == "none"
    assert q1455_protocol["point_decomposition_stage_code"] == "PDP4hybrid"
    assert q1455_controls["status"] == q1455_verification[
        "status"] == "pass"
    assert q1455_verification["protocol_sha256"] == sha(
        q1455_protocol_path)
    assert q1455_protocol["parent_control_result_sha256"] == sha(
        q1455_controls_path)
    assert q1455_controls["small_field"]["complete_leaf_target_cases"] == 9072
    assert q1455_controls["small_field"]["partial_four_leaf_cases"] == 128
    assert [row["degree_n"] for row in q1455_controls[
        "archived_witnesses"]] == [53, 83]
    assert len(q1455_verification["rows"]) == len(q1455_protocol[
        "run_order"]) == 5
    q1455_rows = []
    for name, audit in zip(q1455_protocol["run_order"],
                           q1455_verification["rows"]):
        cell = q1455_protocol["cells"][name]
        receipt_path = q1455_dir / f"runs/{name}/receipt.json"
        receipt = json.loads(receipt_path.read_text())
        report = receipt["solver_report"]
        assert audit["case"] == receipt["case"] == name
        assert audit["receipt_sha256"] == sha(receipt_path)
        assert receipt["protocol_sha256"] == sha(q1455_protocol_path)
        assert receipt["workload_id"] == cell["workload_id"]
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert receipt["folded_columns_K"] == cell["folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        assert receipt["public_target"] == cell["public_target"]
        assert report is not None
        assert report["joint_eligible_checks"] == (
            report["joint_no_chain_rejections"] +
            report["joint_x_only_hits"])
        matched_pair = None
        if cell["input_role"] == "ordinary_full_target":
            matched = q1445_protocol["cells"][str(cell["degree_n"])]
            for key in ("curve_id", "factor_base_actual_B",
                        "folded_columns_K",
                        "factor_base_enumerated_set_sha256",
                        "public_target"):
                assert cell[key] == matched[key], key
            matched_pair = q1445_rows[0 if cell["degree_n"] == 53 else 1]
        q1455_rows.append({
            "proposal_id": "Q1455", "candidate_id": None,
            "run_id": None, "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid",
            "case": name, "input_role": cell["input_role"],
            "degree": cell["degree_n"], "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "factor_base_actual_B": cell["factor_base_actual_B"],
            "folded_columns_K": cell["folded_columns_K"],
            "factor_base_enumerated_set_sha256": cell[
                "factor_base_enumerated_set_sha256"],
            "public_target": cell["public_target"],
            "selected_target_preimage_index": cell[
                "selected_target_preimage_index"],
            "matched_pair_table_receipt_sha256": (
                matched_pair["receipt_sha256"] if matched_pair else None),
            "matched_pair_table_speed_ratio": None,
            "solver_status": receipt["solver_status"],
            "solver_stop_reason": report["stop_reason"],
            "sat_conflicts": report["conflicts"],
            "sat_decisions": report["decisions"],
            "partial_four_leaf_events": report["joint_partial_events"],
            "joint_cap_skips": report["joint_cap_skips"],
            "joint_eligible_checks": report["joint_eligible_checks"],
            "joint_no_chain_rejections": report[
                "joint_no_chain_rejections"],
            "independently_checked_rejection_snapshots": audit[
                "sampled_rejections_independently_checked"],
            "joint_pair0_root_calls": report["joint_pair0_root_calls"],
            "joint_pair1_root_calls": report["joint_pair1_root_calls"],
            "joint_final_root_calls": report["joint_final_root_calls"],
            "native_field_mul_calls": report["field_mul_calls"],
            "native_field_sqr_calls": report["field_sqr_calls"],
            "native_field_inv_calls": report["field_inv_calls"],
            "native_field_call_scope": (
                "native solver and joint propagator, excludes Sage "
                "formula construction, relation replay, and setup"),
            "online_stage_wall_ns_exploratory": receipt[
                "online_stage_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "peak_child_rss_units": receipt["peak_child_rss_units"],
            "verified_relation_count": receipt["verified_relation_count"],
            "successful_ordinary_pdp_cost_measured": receipt[
                "successful_ordinary_pdp_cost_measured"],
            "natural_relation_yield_estimate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
            "complete_n131_log2_work": None,
            "cpu_isolation_receipt": None,
            "receipt_sha256": sha(receipt_path),
        })
    assert [row["verified_relation_count"] for row in q1455_rows] == [
        1, 1, 0, 0, 0]
    assert [row["joint_eligible_checks"] for row in q1455_rows] == [
        13, 25, 0, 0, 0]
    assert all(row["joint_cap_skips"] == row["partial_four_leaf_events"]
               for row in q1455_rows[2:])
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
        "q1408_balanced_s3_w5_stage": {
            "proposal_id": "Q1408",
            "candidate_id": None,
            "stage_config_id": q1408_comparison["stage_profiles"][1][
                "stage_config_id"],
            "run_id": q1408_comparison["stage_profiles"][1]["run_id"],
            "curve_id": q1408_protocol["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1408_protocol[
                "factor_base_actual_B"],
            "factor_base_folded_columns_K": q1408_protocol[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1408_protocol[
                "factor_base_enumerated_set_sha256"],
            "matched_ordinary_workload_id": q1408_protocol[
                "ordinary_workload_id"],
            "stages": q1408_stages,
            "independently_verified_planted_control_relation_count": (
                q1408_replay["verified_control_relation_count"]),
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1408_protocol_path),
            "runtime_info_sha256": sha(q1408_runtime_path),
            "independent_replay_receipt_sha256": sha(q1408_replay_path),
        },
        "q1404_q1408_named_stage_comparison": {
            "candidate_id": None,
            "curve_id": q1408_comparison["curve_id"],
            "workload_id": q1408_comparison["workload_id"],
            "factor_base_enumerated_set_sha256": q1408_comparison[
                "factor_base_enumerated_set_sha256"],
            "controlled_variable": q1408_comparison[
                "controlled_variable"],
            "profiles": [{
                "proposal_id": profile["proposal_id"],
                "stage_config_id": profile["stage_config_id"],
                "run_id": profile["run_id"],
                "ordinary_stage_status": profile[
                    "ordinary_stage_status"],
                "observed_verified_relation_count": profile[
                    "observed_verified_relation_count"],
            } for profile in q1408_comparison["stage_profiles"]],
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1408_comparison_path),
        },
        "q1409_n53_verifier_preflight_failure": {
            "proposal_id": "Q1409",
            "candidate_id": None,
            "status": "verification_failed",
            "reason": q1409_failure["failure"],
            "ordinary_relation_count": None,
            "complete_solve_work_log2": None,
            "protocol_sha256": sha(q1409_protocol_path),
            "failure_receipt_sha256": sha(q1409_failure_path),
        },
        "q1410_balanced_s3_n53_stage": {
            "proposal_id": "Q1410",
            "candidate_id": None,
            "stage_config_id": q1410_comparison["stage_profiles"][0][
                "stage_config_id"],
            "run_id": q1410_comparison["stage_profiles"][0]["run_id"],
            "curve_id": q1410_protocol["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1410_protocol["factor_base_actual_B"],
            "factor_base_folded_columns_K": q1410_protocol[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1410_protocol[
                "factor_base_enumerated_set_sha256"],
            "matched_ordinary_workload_id": q1410_protocol[
                "ordinary_workload_id"],
            "stages": q1410_stages,
            "independently_verified_locked_control_relation_count": (
                q1410_replay["verified_locked_control_relation_count"]),
            "locked_control_distinct_columns": q1410_replay[
                "locked_control_distinct_columns"],
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1410_protocol_path),
            "runtime_info_sha256": sha(q1410_runtime_path),
            "independent_replay_receipt_sha256": sha(q1410_replay_path),
        },
        "q1410_q1408_named_cross_degree_stage_comparison": {
            "candidate_id": None,
            "different_curves_and_factor_bases": True,
            "profiles": [{
                "proposal_id": profile["proposal_id"],
                "stage_config_id": profile["stage_config_id"],
                "run_id": profile["run_id"],
                "ordinary_stage_status": profile[
                    "ordinary_stage_status"],
                "observed_verified_relation_count": profile[
                    "observed_verified_relation_count"],
            } for profile in q1410_comparison["stage_profiles"]],
            "is_solve_growth_measurement": False,
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1410_comparison_path),
        },
        "q1412_ordered_balanced_s3_n53_stage": {
            "proposal_id": "Q1412",
            "candidate_id": None,
            "stage_config_id": q1412_comparison["stage_profiles"][1][
                "stage_config_id"],
            "run_id": q1412_comparison["stage_profiles"][1]["run_id"],
            "curve_id": q1412_protocol["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1412_protocol["factor_base_actual_B"],
            "factor_base_folded_columns_K": q1412_protocol[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1412_protocol[
                "factor_base_enumerated_set_sha256"],
            "matched_ordinary_workload_id": q1412_protocol[
                "ordinary_workload_id"],
            "stages": q1412_stages,
            "independently_verified_locked_control_relation_count": (
                q1412_replay["verified_locked_control_relation_count"]),
            "locked_control_distinct_columns": q1412_replay[
                "locked_control_distinct_columns"],
            "verified_ordinary_relation_count": 0,
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1412_protocol_path),
            "runtime_info_sha256": sha(q1412_runtime_path),
            "independent_replay_receipt_sha256": sha(q1412_replay_path),
        },
        "q1410_q1412_named_stage_comparison": {
            "candidate_id": None,
            "curve_id": q1412_comparison["curve_id"],
            "workload_id": q1412_comparison["workload_id"],
            "factor_base_enumerated_set_sha256": q1412_comparison[
                "factor_base_enumerated_set_sha256"],
            "controlled_variable": q1412_comparison[
                "controlled_variable"],
            "profiles": [{
                "proposal_id": profile["proposal_id"],
                "stage_config_id": profile["stage_config_id"],
                "run_id": profile["run_id"],
                "ordinary_stage_status": profile[
                    "ordinary_stage_status"],
                "observed_verified_relation_count": profile[
                    "observed_verified_relation_count"],
            } for profile in q1412_comparison["stage_profiles"]],
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "is_solve_growth_measurement": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1412_comparison_path),
        },
        "q1415_xor_gaussian_n53_ordinary_solver_stage": {
            "proposal_id": "Q1415",
            "candidate_id": None,
            "stage_config_id": q1415_comparison["stage_profiles"][1][
                "stage_config_id"],
            "stage_run_id": q1415_comparison["stage_profiles"][1][
                "stage_run_id"],
            "legacy_stage_config_id": q1415["stage_config_id"],
            "legacy_stage_run_id": q1415["stage_run_id"],
            "curve_id": q1415["curve_id"],
            "isogeny": "none",
            "factor_base_actual_B": q1415["factor_base_actual_B"],
            "factor_base_folded_columns_K": q1415[
                "factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": q1415[
                "factor_base_enumerated_set_sha256"],
            "ordinary_workload_id": q1415["workload_id"],
            "same_ordinary_target_and_formula_as_q1410": True,
            "solver_status": q1415["solver_status"],
            "solver_only_wall_seconds_exploratory": q1415[
                "solver_wall_seconds_exploratory"],
            "gaussian_matrix_reported_active": True,
            "verified_ordinary_relation_count": 0,
            "solver_conflicts_reported": q1415[
                "solver_conflicts_reported"],
            "natural_relation_yield_rate_estimate": None,
            "cost_per_useful_relation": None,
            "field_operations": None,
            "verified_single_target_dlp": False,
            "complete_solve_work_log2": None,
            "controlled_wall_speedup_claim_allowed": False,
            "protocol_sha256": sha(q1415_protocol_path),
            "runtime_info_sha256": sha(q1415_runtime_path),
            "receipt_sha256": sha(q1415_path),
        },
        "q1419_known_satisfiable_partial_pinning_controls": {
            "proposal_id": "Q1419",
            "candidate_id": None,
            "isogeny": "none",
            "cells": q1419_cells,
            "n53_ordinary_target_is_known_satisfiable": True,
            "n83_target_is_planted_known_satisfiable": True,
            "n53_free_target_reuses_known_witness_leaves": True,
            "verified_n83_ordinary_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "The balanced-S3 CryptoMiniSat encoding fails the N53 and "
                "N83 free-pair-intermediate controls at the frozen cap. "
                "It does not establish ordinary N83 yield or solver growth; "
                "replace the search mechanism before a degree-131 fit."),
            "protocol_sha256": sha(q1419_protocol_path),
            "verification_sha256": sha(q1419_verification_path),
        },
        "q1420_external_s3_root_theory_stage": {
            "proposal_id": "Q1420",
            "candidate_id": None,
            "isogeny": "none",
            "cells": q1420_cells,
            "verified_known_satisfiable_control_cells": 4,
            "distinct_archived_relations_reused": 2,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Exact external roots recover both N53/N83 free-mid "
                "known-witness controls, but both unpinned ordinary targets "
                "hit the 60-second external timeout without a relation. "
                "The timeout kills the solver before its operation counters "
                "are printed; ordinary-query solver work and growth remain "
                "unknown. Instrument graceful stop and improve free-leaf "
                "search before fitting degree-131 work."),
            "protocol_sha256": sha(q1420_protocol_path),
            "verification_sha256": sha(q1420_verification_path),
        },
        "q1421_counted_root_theory_decision_policy_stage": {
            "proposal_id": "Q1421",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "CaDiCaL default versus first-unassigned-leaf positive "
                "decision policy on the same archived Q1420 CNF and target"),
            "cells": q1421_cells,
            "verified_known_satisfiable_control_cells": 4,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both policies verify the fixed-leaf controls. All four "
                "ordinary runs hit the synchronous 60-second wall cap with "
                "complete operation counters and no model. At N83 default "
                "only two distinct leaf-pair assignments reach the root "
                "oracle; leaf-first reaches 5,167 but still no relation. "
                "A sound earlier partial-leaf gate or different target-"
                "coupled search is needed before a solve-growth fit."),
            "protocol_sha256": sha(q1421_protocol_path),
            "verification_sha256": sha(q1421_verification_path),
        },
        "q1422_exact_rational_leaf_gate_stage": {
            "proposal_id": "Q1422",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact Tr(x+x^-1)=0 raw-curve-lift clause versus matched "
                "Q1421 leaf-first search on identical CNF/target/cap"),
            "cells": q1422_cells,
            "verified_known_satisfiable_control_cells": 2,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "The sound leaf-lift gate preserves both fixed-leaf "
                "controls and rejects about half the completed ordinary "
                "leaf values. It reduces N83 pair-root calls from 5,167 "
                "to 2,645 at the wall cap, but both N53 and N83 ordinary "
                "queries remain censored with no relation. This single-"
                "leaf rationality filter is insufficient; target-coupled "
                "pruning or another search mechanism is still required."),
            "protocol_sha256": sha(q1422_protocol_path),
            "verification_sha256": sha(q1422_verification_path),
            "n53_lift_validation_sha256": sha(
                q1422_dir / "n53_lift_validation.json"),
            "n83_lift_validation_sha256": sha(
                q1422_dir / "n83_lift_validation.json"),
        },
        "q1423_target_coupled_exact_root_stage": {
            "proposal_id": "Q1423",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "pair-first target-coupled final S3 root propagation "
                "versus matched Q1422 leaf-first lift-gated search on "
                "identical CNF/target/cap"),
            "cells": q1423_cells,
            "verified_known_satisfiable_control_cells": 2,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify, and the exact "
                "target-coupled final root rule activates. The two "
                "ordinary queries still hit the 60-second cap without "
                "a relation. Pair-first search computes 62,269 and "
                "66,824 distinct pair assignments at N53/N83, yet "
                "the target-coupled final-root rule activates only once "
                "per ordinary query. These counts combine both leaf-pair "
                "links and do not identify which pair dominates; a "
                "sound earlier target condition or a different search "
                "mechanism is the next gate."),
            "protocol_sha256": sha(q1423_protocol_path),
            "verification_sha256": sha(q1423_verification_path),
        },
        "q1424_early_target_decision_stage": {
            "proposal_id": "Q1424",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "target selector first or target selector plus first "
                "intermediate first, against matched Q1423 on identical "
                "CNF/target/cap"),
            "cells": q1424_cells,
            "verified_known_satisfiable_control_cells": 4,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "All four known-witness controls verify, but all four "
                "ordinary N53/N83 queries hit the 60-second cap with no "
                "relation. Target-first spends the cap on pair 1 "
                "(58,514/65,289 roots), while target-mid-first spends "
                "it on pair 0 (225,790/135,141 roots). The exact "
                "target-coupled final root rule activates once per "
                "ordinary cell. Decision order shifts pair enumeration "
                "but does not make it feasible; an early partner-feasibility "
                "condition or indexed two-sided search is the next gate."),
            "protocol_sha256": sha(q1424_protocol_path),
            "verification_sha256": sha(q1424_verification_path),
        },
        "q1425_reverse_pair_root_stage": {
            "proposal_id": "Q1425",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact reverse S3 partner-root propagation versus matched "
                "Q1424 decision orders on identical ordinary CNF, target, "
                "factor base and caps; controls free two archived partner "
                "leaf pin sets and are correctness checks only"),
            "cells": q1425_cells,
            "verified_known_satisfiable_control_cells": 4,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "All four freed-partner known-witness controls verify. "
                "All four ordinary N53/N83 queries hit the 60-second cap "
                "without a relation. Reverse propagation nearly removes "
                "complete pair-root enumeration in these caps, but "
                "generates hundreds of thousands to over one million "
                "reverse-root checks and more field operations than "
                "the matched Q1424 cells. No natural relation yield, "
                "solver scaling exponent or degree-131 complete-work "
                "projection follows from censored runs. A compact "
                "target-guided pair-sum membership and witness method "
                "is the next gate; independent uniform intermediate "
                "sampling is outside the 2^61 logical-trial target "
                "under the exact pair-support screen."),
            "protocol_sha256": sha(q1425_protocol_path),
            "verification_sha256": sha(q1425_verification_path),
            "exact_uniform_mid_pair_support_screen": {
                "status": q1425_support["status"],
                "rows": q1425_support["rows"],
                "sampling_law": q1425_support[
                    "sampling_law_for_probability_and_trials"],
                "scope_limit": q1425_support["scope_limit"],
                "is_empirical_solver_measurement": False,
                "degree131_complete_solve_work_log2": None,
                "receipt_sha256": sha(q1425_support_path),
            },
        },
        "q1426_symbolic_second_pair_stage": {
            "proposal_id": "Q1426",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "all factored symbolic S3 equations for second pair added "
                "before search versus matched Q1425 reverse_target on the "
                "same curve, exact base, public target and limits"),
            "cells": q1426_cells,
            "verified_known_satisfiable_control_cells": 2,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both freed-partner known-witness controls verify. The "
                "ordinary N53 and N83 cells each hit the 60-second cap "
                "without a relation. Symbolic pair equations did not "
                "produce an accepted sparse reverse-root partner in either "
                "cell. Censored runs do not establish natural yield, a "
                "solver scaling exponent, or complete degree-131 work. "
                "A new target-conditioned algebraic feasibility method "
                "must replace the reverse-root rejection loop."),
            "protocol_sha256": sha(q1426_protocol_path),
            "verification_sha256": sha(q1426_verification_path),
        },
        "q1427_interleaved_second_pair_stage": {
            "proposal_id": "Q1427",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "bitwise interleaving of second-pair leaves versus matched "
                "Q1426 reverse_target on identical CNF, curve, exact base, "
                "public target, target-preimage list, and limits"),
            "cells": q1427_cells,
            "verified_known_satisfiable_control_cells": 2,
            "verified_ordinary_n53_relation_count": 0,
            "verified_ordinary_n83_relation_count": 0,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both freed-partner controls verify. Both ordinary "
                "N53/N83 cells hit the 60-second cap without a relation. "
                "Interleaving reduces reverse pair-1 calls from "
                "1,080,547 to 135,226 at N53 and 485,107 to 71,988 at "
                "N83, but every returned reverse root still fails the "
                "sparse weight rule. No natural yield, cost per useful "
                "row, scaling exponent, or complete degree-131 work "
                "follows from censored runs. The next method needs "
                "algebraic pair-sum feasibility before a leaf is fixed."),
            "protocol_sha256": sha(q1427_protocol_path),
            "verification_sha256": sha(q1427_verification_path),
        },
        "q1428_bilinear_partial_pair_span_screen": {
            "proposal_id": "Q1428",
            "candidate_id": None,
            "isogeny": "none",
            "rows": q1428_result["rows"],
            "small_field_self_test": q1428_test,
            "is_empirical_solver_measurement": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "The linearized S3 span condition is sound and can reject "
                "synthetic partial states. In this frozen law, each leaf "
                "has already exhausted its weight allowance at the first "
                "rank-deficient cells, so it demonstrates no early solver "
                "pruning. A weight-unsaturated comparison with exact "
                "completion enumeration is required before integration."),
            "protocol_sha256": sha(q1428_protocol_path),
            "result_sha256": sha(q1428_result_path),
            "self_test_sha256": sha(q1428_test_path),
        },
        "q1429_unsaturated_span_vs_exact_completion_screen": {
            "proposal_id": "Q1429",
            "candidate_id": None,
            "isogeny": "none",
            "cells": q1429_result["cells"],
            "is_empirical_solver_measurement": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "The sound partial-pair span filter rejects synthetic "
                "weight-unsaturated states, including all four N131 "
                "samples with 32 free bits and two one bits remaining. "
                "Each such rejection saves at most 529 exact root calls "
                "after testing 1,024 bilinear columns, which are not "
                "equivalent work units. No exact pair occurred under "
                "the uniform-intermediate law. The next gate must check "
                "whether target-conditioned Q1427 trails reach these "
                "partial states and measure a sound filter on ordinary "
                "queries; no complete-work projection follows."),
            "protocol_sha256": sha(q1429_protocol_path),
            "result_sha256": sha(q1429_result_path),
        },
        "q1430_actual_partial_trail_observation": {
            "proposal_id": "Q1430",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "observation-only counters and first 16 partial-state "
                "snapshots on the exact Q1427 CNF, ordinary targets, "
                "factor bases, decision order, and 60-second limits"),
            "cells": q1430_cells,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both archived known-witness controls verify; both "
                "ordinary searches remain censored with no relation. "
                "Within their respective 60-second caps, N53 and N83 "
                "record 207,522 and 81,765 notification events in which "
                "both second-pair leaves are partial with 1-2 weight "
                "units left and at most 14/20 free bits each. These are "
                "events, not distinct states or independent samples. "
                "An independent post-run audit applies the sound Q1428 "
                "span check to the first 16 saved distinct states per "
                "ordinary cell and rejects all 16 in each. The frozen "
                "verifier had a Boolean-parentheses typo, preserved in "
                "the preregistered source; the separate audit fixes only "
                "verification. This establishes filter reachability, "
                "not net savings, natural yield, a solve-growth exponent, "
                "or complete N131 work. The next gate is a guarded "
                "span propagator with charged field work on matched "
                "ordinary N53/N83 queries."),
            "protocol_sha256": sha(q1430_protocol_path),
            "audit_verification_sha256": sha(q1430_audit_path),
        },
        "q1431_guarded_partial_span_stage": {
            "proposal_id": "Q1431",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "a sound guarded partial-pair span propagator versus "
                "Q1430 observation only on identical Q1426 CNF, exact "
                "curve and base, public target, decision order, and "
                "60-second/one-million-conflict caps"),
            "cells": q1431_cells,
            "native_vs_sage_validation_cases": 112,
            "verified_witness_false_rejections": 0,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify and both ordinary "
                "N53/N83 cells hit the 60-second cap without a relation. "
                "The filter reduces reverse pair-1 calls within those "
                "caps but performs 67,632,400/53,520,040 field "
                "multiplications itself at N53/N83. Total multiplication "
                "calls rise from matched Q1430 4,764,022/3,676,888 to "
                "68,182,727/54,467,127; the branches also explore "
                "different search prefixes. This naive span integration "
                "does not establish a faster solver. The next gate should "
                "reuse bilinear columns for each fixed intermediate and "
                "charge that cache's construction and memory. No useful "
                "row rate, solve-growth fit, or complete N131 exponent "
                "follows from the censored cells."),
            "protocol_sha256": sha(q1431_protocol_path),
            "verification_sha256": sha(q1431_verification_path),
            "span_validation_sha256": sha(q1431_validation_path),
        },
        "q1432_cached_span_coefficient_stage": {
            "proposal_id": "Q1432",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact reuse of pair-basis products, intermediate-keyed "
                "bilinear columns, and fixed-value-keyed linear "
                "coefficients versus Q1431 on identical CNF, curve, "
                "base, target, decision policy, and caps"),
            "cells": q1432_cells,
            "cached_native_vs_sage_validation_cases": 112,
            "verified_witness_false_rejections": 0,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify and both ordinary "
                "N53/N83 cells again hit the 60-second cap without a "
                "relation. Exact coefficient reuse lowers total field "
                "multiplications from Q1431's 68,182,727/54,467,127 to "
                "1,457,636/1,296,699 while the filter checks "
                "219,179/67,183 partial states. Cache construction is "
                "included in those calls, and retained payload lower "
                "bounds are 2,205,936/4,563,408 bytes. Q1432's "
                "operation counts are also below Q1430's matched "
                "censored prefixes, but search paths differ and CPU "
                "wall times lack isolation. There is no verified "
                "ordinary relation, natural yield, useful-row rate, "
                "solve-growth fit, or complete N131 exponent. The next "
                "gate is a longer frozen ordinary N53 solve attempt "
                "or a stronger target-conditioned witness method."),
            "protocol_sha256": sha(q1432_protocol_path),
            "verification_sha256": sha(q1432_verification_path),
            "cache_validation_sha256": sha(q1432_validation_path),
        },
        "q1433_long_cached_solver_stage": {
            "proposal_id": "Q1433",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "300-second/five-million-conflict resource cap versus "
                "Q1432's 60-second/one-million-conflict cap, with the "
                "same exact binary, curve, base, public target, CNF, "
                "and decision policy"),
            "cells": q1433_cells,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify; both ordinary "
                "N53/N83 cells remain censored at the 300-second wall "
                "cap with zero verified relations. N53 made 903,175 "
                "decisions and 4,753,049 field multiplications; N83 "
                "made 677,658 decisions and 4,490,849 multiplications. "
                "Peak child RSS reached 1,557,807,104/2,222,800,896 "
                "bytes. These are observed lower bounds for the "
                "specific ordinary solver attempts, not solved-query "
                "costs, natural yield, or a degree-131 scaling fit. "
                "Further cap increases without a stronger witness "
                "method risk growing clauses and memory while leaving "
                "the complete N131 exponent unknown."),
            "protocol_sha256": sha(q1433_protocol_path),
            "verification_sha256": sha(q1433_verification_path),
        },
        "q1434_exact_sparse_tail_stage": {
            "proposal_id": "Q1434",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact weight-one tail membership and unique-witness "
                "clauses after the Q1432 cached span screen, on identical "
                "CNF, curve, base, public target, decision policy and "
                "60-second cap"),
            "cells": q1434_cells,
            "native_vs_direct_sage_validation_cases": 60,
            "verified_witness_false_rejections": 0,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify and both ordinary "
                "N53/N83 queries remain censored at 60 seconds. Exact "
                "tail checks reject 42,903/3,180 span-accepted states "
                "with zero S3 completions; no ordinary unique completion "
                "or verified relation occurs. Charged total field "
                "multiplications are 2,036,720/1,372,405 on different "
                "censored prefixes. This proves useful local pruning, "
                "not a solved-query cost, natural yield, CPU wall "
                "speedup, or complete N131 exponent. The next gate is "
                "earlier target-conditioned sparse-pair membership with "
                "witness recovery."),
            "protocol_sha256": sha(q1434_protocol_path),
            "verification_sha256": sha(q1434_verification_path),
            "tail_validation_sha256": sha(q1434_validation_path),
        },
        "q1435_bounded_sparse_tail_stage": {
            "proposal_id": "Q1435",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact completion for one or two remaining weight units "
                "per leaf under a 4096-candidate cap versus Q1434's "
                "one/one-only completion, on identical CNF, curve, base, "
                "public target, decision policy and 60-second cap"),
            "cells": q1435_cells,
            "native_vs_direct_sage_validation_cases": 103,
            "verified_witness_false_rejections": 0,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify; both ordinary "
                "N53/N83 queries remain censored at 60 seconds. Fully "
                "checked completion domains reject 328,408/3,067 "
                "span-accepted states, but the search still finds no "
                "ordinary relation. N53 spends 110,100,907 candidate "
                "pairs and 354,587,110 expansion XORs; all observed "
                "N53 two/two-slack states exceed the cap. This is "
                "bounded late pruning, not a solved-query cost, natural "
                "yield, controlled CPU speedup, or complete N131 work "
                "exponent. The next method needs target-conditioned "
                "sparse-pair membership before near-complete leaves."),
            "protocol_sha256": sha(q1435_protocol_path),
            "verification_sha256": sha(q1435_verification_path),
            "tail_validation_sha256": sha(q1435_validation_path),
        },
        "q1436_affine_pair_stage": {
            "proposal_id": "Q1436",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "exact one-sided affine S3 feasibility at 18/24 free "
                "bits per second-pair leaf versus Q1435 bounded pair "
                "enumeration at 14/20, on identical CNF, curve, base, "
                "public target, decision policy, and 60-second cap"),
            "cells": q1436_cells,
            "native_vs_direct_sage_validation_cases": 49,
            "verified_witness_validation_cases": 9,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both known-witness controls verify. Ordinary N53/N83 "
                "queries cap at 60 seconds with zero relations. The "
                "affine filter soundly rejects 395906/75525 checked "
                "partial domains at an earlier 18/24-free-bit window, "
                "charging 1335395670/571525667 XORs. Each ordinary run "
                "still finishes only one first-pair root call. These are "
                "censored stage diagnostics, not successful query cost, "
                "natural relation yield, controlled CPU wall speedup, or "
                "complete N131 work. A target-conditioned global pair "
                "support oracle remains necessary for this search order."),
            "protocol_sha256": sha(q1436_protocol_path),
            "verification_sha256": sha(q1436_verification_path),
            "affine_validation_sha256": sha(q1436_validation_path),
            "archived_v1_control_report_failure_sha256": sha(
                q1436_dir / "failed_v1/n53_free_partner/receipt.json"),
        },
        "q1438_exact_dense_base_solver_stage": {
            "proposal_id": "Q1438",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_variable": (
                "N53 W<=3 to W<=4 and N83 W<=5 to W<=6 exact "
                "factor-base construction, size, and digest; Q1436's "
                "native compact-S3 binary, public target, decision "
                "policy, and resource caps are unchanged"),
            "exact_base_rows": q1438_base_rows,
            "formula_byte_equivalence_cells": len(
                q1438_formula_validation["rows"]),
            "cells": q1438_cells,
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both denser-base known-witness controls verify, but "
                "both unpinned ordinary N53/N83 cells hit the 60-second "
                "cap with zero relations. Each completed only one "
                "first-pair root call. The exact B and K increase "
                "about thirteenfold at each degree; this base change "
                "does not make Q1436's search leave its first pair "
                "within the cap. These are censored stage costs, not "
                "successful PDP costs, relation yield, novel rank, "
                "or a complete N131 exponent. Prioritize a target-"
                "conditioned pair witness method."),
            "base_protocol_sha256": sha(q1438_base_protocol_path),
            "base_verification_sha256": sha(
                q1438_base_verification_path),
            "formula_validation_sha256": sha(
                q1438_formula_validation_path),
            "solver_protocol_sha256": sha(q1438_solver_protocol_path),
            "solver_verification_sha256": sha(
                q1438_solver_verification_path),
        },
        "q1439_fixed_leaf_three_sum_stage": {
            "proposal_id": "Q1439",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_question": (
                "One target-independent usable anchor reduces a four-point "
                "query to a three-leaf two-S3 chain. The exact Q1438 "
                "bases and public targets are retained; anchor-restricted "
                "coverage differs from the complete Q1438 search."),
            "cells": q1439_cells,
            "uniform_fixed_anchor_representation_model": fixed_anchor_model,
            "uniform_model_assumptions": (
                "Distinct unordered triples from the B subgroup-usable "
                "points have independently uniform sums in the r-order "
                "subgroup. This is a counting mean, not a measured hit "
                "probability, solver cost, or complete work bound. The "
                "Q1437 W<=7 B is conditional on no unsampled collisions."),
            "is_empirical_solver_stage_measurement": True,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "Both planted controls verify, but independent ordinary "
                "anchors at N53/N83 reach 60-second external timeouts with "
                "zero relations. A fixed anchor can miss a representation "
                "even when the target has a four-point relation, so these "
                "censored cells cannot distinguish anchor coverage from "
                "three-leaf search cost. They do not establish ordinary "
                "yield, useful-row cost, N53-to-N83 successful-solve growth, "
                "or a complete N131 work exponent."),
            "protocol_sha256": sha(q1439_protocol_path),
            "verification_sha256": sha(q1439_verification_path),
            "small_field_verification_sha256": sha(q1439_small_path),
            "small_field_nonexceptional_cases": 70652,
        },
        "q1440_known_witness_anchor_search_gate": {
            "proposal_id": "Q1440",
            "candidate_id": None,
            "isogeny": "none",
            "controlled_question": (
                "With one anchor and an adjusted-target choice known to "
                "belong to a valid relation, can the two-S3 SAT solver "
                "recover the other three leaves within fixed caps? Both "
                "selector-pinned and selector-free variants are tested."),
            "cells": q1440_cells,
            "known_witness_satisfiability_proved_for_all_cells": True,
            "is_empirical_solver_stage_measurement": True,
            "is_ordinary_yield_measurement": False,
            "is_controlled_cpu_wall_speedup": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "degree131_complete_solve_work_log2": None,
            "decision": (
                "All four formulas contain an independently replayed "
                "four-point witness. Both N53 cells consume more than "
                "one million SAT conflicts without finding a model; both "
                "N83 cells reach 60-second external timeouts without a "
                "model. This removes anchor absence as the sole explanation "
                "for Q1439's ordinary failures, but supplies no successful "
                "three-leaf cost, natural yield, rank gain, or complete "
                "N131 exponent. Prioritize an exact target-conditioned "
                "sparse-pair witness method over selector-only SAT variants."),
            "protocol_sha256": sha(q1440_protocol_path),
            "verification_sha256": sha(q1440_verification_path),
            "known_witness_verification_sha256": sha(q1440_witness_path),
        },
        "q1441_n131_full_base_scan_budget_screen": {
            "proposal_id": "Q1441",
            "candidate_id": None,
            "curve_id": q1441_result["curve_id"],
            "isogeny": "none",
            "budget_abstract_work_units": q1441_result[
                "budget_abstract_work_units"],
            "work_unit": q1441_result["work_unit"],
            "w6_query_policy": q1441_result["w6_query_policy"],
            "w7_query_policy": q1441_result["w7_query_policy"],
            "scan_policy": q1441_result["scan_policy"],
            "matrix_scenario": q1441_result["matrix_scenario"],
            "scope": q1441_result["scope"],
            "rows": q1441_result["rows"],
            "is_empirical_solver_stage_measurement": False,
            "natural_relation_yield_estimate": None,
            "calibrated_field_operation_cost": None,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": q1441_result["decision"],
            "protocol_sha256": sha(q1441_protocol_path),
            "result_sha256": sha(q1441_result_path),
            "verification_sha256": sha(q1441_verification_path),
        },
        "q1442_n131_conditional_selected_base_screen": {
            "proposal_id": "Q1442",
            "candidate_id": None,
            "curve_id": q1442_result["curve_id"],
            "isogeny": "none",
            "actual_selected_B": None,
            "actual_selected_K": None,
            "selected_base_set_sha256": None,
            "lambda_continuous_optimum_model": q1442_result[
                "lambda_continuous_optimum_model"],
            "continuous_optimum_B_model": q1442_result[
                "continuous_optimum_B_model"],
            "selected_orbit_count_model": q1442_result[
                "selected_orbit_count_model"],
            "rows": q1442_result["rows"],
            "work_unit": q1442_result["work_unit"],
            "assumptions": q1442_result["assumptions"],
            "is_empirical_solver_stage_measurement": False,
            "natural_relation_yield_estimate": None,
            "calibrated_field_operation_cost": None,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": q1442_result["decision"],
            "protocol_sha256": sha(q1442_protocol_path),
            "result_sha256": sha(q1442_result_path),
            "verification_sha256": sha(q1442_verification_path),
        },
        "q1443_residual_pair_support_bound": {
            "proposal_id": "Q1443",
            "candidate_id": None,
            "isogeny": "none",
            "budget_abstract_first_pair_trials": q1443_result[
                "budget_abstract_first_pair_trials"],
            "work_unit": q1443_result["work_unit"],
            "law": q1443_result["law"],
            "scope": q1443_result["scope"],
            "proof": q1443_result["proof"],
            "rows": q1443_result["rows"],
            "ordinary_N83_relation_measured": False,
            "is_empirical_solver_stage_measurement": False,
            "natural_relation_yield_estimate": None,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": q1443_result["decision"],
            "protocol_sha256": sha(q1443_protocol_path),
            "result_sha256": sha(q1443_result_path),
            "verification_sha256": sha(q1443_verification_path),
        },
        "q1444_wdsat_sound_adapter_stage": {
            "proposal_id": "Q1444",
            "candidate_id": None,
            "isogeny": "none",
            "solver_family": "wdsat_sat_xor",
            "solver_xor_gaussian_elimination": False,
            "input_curve_ids": {
                cell: q1444_protocol["cells"][cell]["curve_id"]
                for cell in q1444_protocol["run_order"]},
            "input_base_actual_B": {
                cell: q1444_protocol["cells"][cell][
                    "factor_base_actual_B"]
                for cell in q1444_protocol["run_order"]},
            "input_folded_columns_K": {
                cell: q1444_protocol["cells"][cell]["folded_columns_K"]
                for cell in q1444_protocol["run_order"]},
            "rows": q1444_verification["rows"],
            "ordinary_N83_relation_measured": False,
            "is_empirical_solver_stage_measurement": True,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "Four soundly adapted 60-second N53/N83 controls and "
                "ordinary cells all censor without a model; the dedicated "
                "SAT solver remains a diagnostic, not a measured useful-row "
                "or complete-work path."),
            "protocol_sha256": sha(q1444_protocol_path),
            "verification_sha256": sha(q1444_verification_path),
        },
        "q1445_exact_base_pair_table_control": {
            "proposal_id": "Q1445", "candidate_id": None,
            "isogeny": "none",
            "method": "target-independent signed-Frobenius pair table",
            "operation_unit": (
                "logical pair samples and raw sparse-x draws; not calibrated "
                "field operations or complete-solve work"),
            "rows": q1445_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "protocol_sha256": sha(q1445_protocol_path),
            "verification_sha256": sha(q1445_verification_path),
        },
        "q1446_joint_target_linked_pair_span_stage": {
            "proposal_id": "Q1446", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid",
            "method": q1446_protocol["method"],
            "rows": q1446_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "Both sound partial-pair filters fire and reject many states, "
                "but each 60-second ordinary cell explores just one "
                "target-linked intermediate choice, completes no pair, "
                "and yields no relation. The next method must process "
                "intermediate choices in shared target-conditioned work."),
            "protocol_sha256": sha(q1446_protocol_path),
            "verification_sha256": sha(q1446_verification_path),
        },
        "q1447_uniform_midpoint_support_bound": {
            "proposal_id": "Q1447", "candidate_id": None,
            "isogeny": "none",
            "kind": "analytic_support_bound_not_solver_measurement",
            "work_unit": q1447_result["work_unit"],
            "input_law": q1447_result["input_law"],
            "scope": q1447_result["scope"],
            "proof": q1447_result["proof"],
            "rows": q1447_result["rows"],
            "ordinary_N83_relation_measured_here": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": q1447_result["decision"],
            "protocol_sha256": sha(q1447_protocol_path),
            "result_sha256": sha(q1447_result_path),
            "verification_sha256": sha(q1447_verification_path),
        },
        "q1448_torsion_symmetrized_phi5_sat_stage": {
            "proposal_id": "Q1448", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1448_protocol["method"],
            "rows": q1448_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "The compact invariant directly couples four sparse leaves "
                "and the target without enumerating pair midpoints or "
                "expanding ordinary S5. Fully pinned N53/N83 controls pass, "
                "but both ordinary SAT cells reach the 60-second solver "
                "cap without a model or verified relation. The archived "
                "N53 ordinary target has a known witness. Censored stage "
                "runs cannot establish natural yield or a complete work "
                "exponent."),
            "protocol_sha256": sha(q1448_protocol_path),
            "verification_sha256": sha(q1448_verification_path),
        },
        "q1449_phi5_native_xor_solver_stage": {
            "proposal_id": "Q1449", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1449_protocol["method"],
            "controlled_variable": q1449_protocol["controlled_variable"],
            "rows": q1449_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "Native XOR input reduces the Boolean representation, "
                "but CryptoMiniSat uses zero Gaussian matrices under its "
                "default 1000-column limit. Both ordinary cells hit the "
                "external wall safeguard without a model. The next "
                "configuration should admit bounded multiplication "
                "matrices and prove activation before measuring ordinary "
                "queries."),
            "protocol_sha256": sha(q1449_protocol_path),
            "controls_sha256": sha(q1449_controls_path),
            "verification_sha256": sha(q1449_verification_path),
        },
        "q1450_phi5_bounded_gaussian_stage": {
            "proposal_id": "Q1450", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1450_protocol["method"],
            "controlled_variable": q1450_protocol["controlled_variable"],
            "rows": q1450_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "Bounded Gaussian matrices activate on both partial "
                "controls and on both unpinned ordinary queries. The "
                "ordinary cells nevertheless hit the external wall "
                "safeguard without a model or verified relation, so no "
                "natural rate or complete-work exponent follows."),
            "protocol_sha256": sha(q1450_protocol_path),
            "controls_sha256": sha(q1450_controls_path),
            "verification_sha256": sha(q1450_verification_path),
        },
        "q1451_phi5_fixed_target_stage": {
            "proposal_id": "Q1451", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1451_protocol["method"],
            "controlled_variable": q1451_protocol["controlled_variable"],
            "rows": q1451_rows,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "Specializing one public-target raw preimage reduces "
                "the phi5 Boolean circuit and passes pinned relation "
                "controls. Both unpinned ordinary index-0 slices "
                "nevertheless reach the external safeguard without "
                "a model. One slice per target cannot estimate "
                "whole-target relation yield; neither slice is known "
                "to contain a relation. The next controlled screen "
                "should use the known-satisfiable N53 preimage 201 "
                "with all leaves unpinned."),
            "protocol_sha256": sha(q1451_protocol_path),
            "controls_sha256": sha(q1451_controls_path),
            "verification_sha256": sha(q1451_verification_path),
        },
        "q1452_known_satisfiable_phi5_stage": {
            "proposal_id": "Q1452", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1452_protocol["method"],
            "controlled_variable": q1452_protocol["controlled_variable"],
            "rows": q1452_rows,
            "ordinary_N53_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "A fully pinned, exact group-verified witness proves "
                "that the archived N53 ordinary target has a four-point "
                "relation at raw preimage 201. Q1452 leaves all four "
                "leaves unpinned and reaches the external safeguard "
                "without a model, despite five active Gaussian "
                "matrices and about 369K rounded partial conflicts. "
                "The successful-solve cost remains unmeasured; "
                "field-level target-coupled pruning is required "
                "before a credible growth projection."),
            "protocol_sha256": sha(q1452_protocol_path),
            "controls_sha256": sha(q1452_controls_path),
            "verification_sha256": sha(q1452_verification_path),
        },
        "q1453_projective_phi5_stage": {
            "proposal_id": "Q1453", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1453_protocol["method"],
            "controlled_variable": q1453_protocol["controlled_variable"],
            "rows": q1453_rows,
            "ordinary_N53_relation_measured": False,
            "ordinary_N83_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "The denominator-cleared phi5 identity is exact and "
                "both pinned controls replay verified relations. "
                "Removing four inverse constraints grows the Boolean "
                "circuits by about 70 percent in AND gates, and both "
                "ordinary cells reach the external safeguard without "
                "a model. The N53 slice is known satisfiable. This "
                "representation does not measure a successful "
                "decomposition or a complete-work exponent."),
            "protocol_sha256": sha(q1453_protocol_path),
            "algebra_validation_sha256": sha(q1453_algebra_path),
            "controls_sha256": sha(q1453_controls_path),
            "verification_sha256": sha(q1453_verification_path),
        },
        "q1454_phi5_conflict_cap_stage": {
            "proposal_id": "Q1454", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4phi5",
            "method": q1454_protocol["method"],
            "controlled_variable": q1454_protocol["controlled_variable"],
            "rows": q1454_rows,
            "matched_pair_table_protocol_sha256": sha(q1445_protocol_path),
            "matched_pair_table_curve_base_target_equal": True,
            "matched_pair_table_speed_ratio": None,
            "ordinary_N53_relation_measured": False,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "The exact Q1452 N53 known-satisfiable XCNF reaches "
                "the one-million-conflict cap and CryptoMiniSat prints "
                "exact final conflict and decision counts but no model. "
                "Native exit 15 is INDETERMINATE; a supplementary audit "
                "preserves the frozen runner's raw error label and "
                "classifies the capped outcome. This is a censored "
                "search prefix in SAT-event units, not a measured "
                "successful decomposition or N131 field-operation "
                "projection."),
            "protocol_sha256": sha(q1454_protocol_path),
            "verification_sha256": sha(q1454_verification_path),
            "cap_interpretation_sha256": sha(q1454_cap_path),
        },
        "q1455_joint_tail_stage": {
            "proposal_id": "Q1455", "candidate_id": None,
            "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid",
            "method": q1455_protocol["method"],
            "controlled_variable": q1455_protocol["controlled_variable"],
            "rows": q1455_rows,
            "small_field_complete_cases": q1455_controls[
                "small_field"]["complete_leaf_target_cases"],
            "small_field_partial_cases": q1455_controls[
                "small_field"]["partial_four_leaf_cases"],
            "ordinary_verified_relations": 0,
            "ordinary_eligible_joint_checks": 0,
            "natural_relation_yield_estimate": None,
            "cost_per_useful_row": None,
            "successful_N53_N83_solve_growth_measurement": False,
            "degree131_complete_solve_work_log2": None,
            "challenge_dispatch_allowed": False,
            "decision": (
                "The unfixed-midpoint joint-tail rule passes exhaustive "
                "small-field and N53/N83 witness controls, with sampled "
                "native rejections independently replayed. The N53 "
                "known-satisfiable and full ordinary N53/N83 cells all "
                "reach the 60-second wall cap; every observed partial "
                "state exceeds the frozen pair-domain cap, so no ordinary "
                "joint check or verified relation is measured. Determine "
                "actual domain sizes before raising the cap or claiming "
                "a successful decomposition cost."),
            "protocol_sha256": sha(q1455_protocol_path),
            "controls_sha256": sha(q1455_controls_path),
            "verification_sha256": sha(q1455_verification_path),
        },
        "q1410_q1415_named_solver_only_method_gate": {
            "candidate_id": None,
            "curve_id": q1415_comparison["curve_id"],
            "workload_id": q1415_comparison["workload_id"],
            "factor_base_enumerated_set_sha256": q1415_comparison[
                "factor_base_enumerated_set_sha256"],
            "controlled_variable": q1415_comparison[
                "controlled_variable"],
            "profiles": q1415_comparison["stage_profiles"],
            "timing_boundaries_differ": True,
            "is_complete_ic_comparison": False,
            "is_controlled_cpu_wall_speedup": False,
            "is_solve_growth_measurement": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1415_comparison_path),
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
            "status": "historical_sample_superseded_by_q1413_exact_enumeration",
            "exact_enumerated_base_B": q1413_full[
                "actual_usable_points_B_before_folding"],
            "exact_enumerated_base_digest": q1413_full[
                "enumerated_set_sha256"],
            "exact_enumeration_receipt_sha256": sha(q1413_full_path),
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
        "q1406_n131_uniform_query_rank_supply_bound": {
            "proposal_id": "Q1406",
            "parent_base_proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": q1406_bound["curve_id"],
            "base_status": q1406_bound["base_status"],
            "scope": q1406_bound["scope"],
            "proof": q1406_bound["proof"],
            "conditional_scenarios": q1406_bound["conditional_scenarios"],
            "budget_interpretation": q1406_bound["budget_interpretation"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1406_bound_path),
        },
        "q1413_exact_n131_weight6_factor_base": {
            "proposal_id": "Q1413",
            "parent_base_proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": q1413_full["curve_id"],
            "isogeny": "none",
            "normal_basis_weight_bound": 6,
            "actual_usable_points_B_before_folding": q1413_full[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": q1413_full[
                "signed_frobenius_columns_K"],
            "enumerated_set_encoding": q1413_full[
                "enumerated_set_encoding"],
            "enumerated_set_sha256": q1413_full[
                "enumerated_set_sha256"],
            "weight_strata": q1413_full["strata"],
            "exact_weight5_prefix_B": q1413_prefix[
                "actual_usable_points_B_before_folding"],
            "n83_reference_orbit_sets_verified": True,
            "independent_sage_projection_replay_status": q1413_replay[
                "status"],
            "independent_sage_projection_replay_sha256": sha(
                q1413_replay_path),
            "base_core_api_call_vector": q1413_calls["rows"][-1][
                "base_core_api_calls"],
            "base_core_api_call_boundary": q1413_calls[
                "accounting_boundary"],
            "base_core_api_call_receipt_sha256": sha(q1413_calls_path),
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "receipt_sha256": sha(q1413_full_path),
        },
        "q1414_n131_exact_base_uniform_query_rank_supply_bound": {
            "proposal_id": "Q1414",
            "parent_base_proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": q1414_bound["curve_id"],
            "isogeny": "none",
            "actual_usable_points_B_before_folding": q1414_bound[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": q1414_bound["folded_columns_K"],
            "base_set_sha256": q1414_bound["base_set_sha256"],
            "scope": q1414_bound["scope"],
            "proof": q1414_bound["proof"],
            "uniform_nonidentity_target_mean_relations_upper_decimal":
                q1414_bound[
                    "uniform_nonidentity_target_mean_relations_upper_decimal"],
            "query_bounds": q1414_bound["query_bounds"],
            "budget_interpretation": q1414_bound["budget_interpretation"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1414_bound_path),
        },
        "q1416_n131_exact_base_pure_pair_index_model": {
            "proposal_id": "Q1416",
            "parent_base_proposal_id": "Q1303",
            "candidate_id": None,
            "curve_id": q1416_pair["curve_id"],
            "isogeny": "none",
            "actual_usable_points_B_before_folding": q1416_pair[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": q1416_pair["folded_columns_K"],
            "base_set_sha256": q1416_pair["base_set_sha256"],
            "index_states_exact": q1416_pair["index_states_exact"],
            "index_states_log2": q1416_pair["index_states_log2"],
            "minimum_17_byte_key_storage_log2_bytes": q1416_pair[
                "minimum_17_byte_key_storage_log2_bytes"],
            "K_rows_pair_probes_model_log2": q1416_pair[
                "K_rows_pair_probes_model_log2"],
            "index_plus_K_rows_pair_actions_model_log2": q1416_pair[
                "index_plus_K_rows_pair_actions_model_log2"],
            "scope": q1416_pair["scope"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1416_pair_path),
        },
        "q1437_n131_conditional_weight7_frontier": {
            "proposal_id": "Q1437",
            "candidate_id": None,
            "curve_id": q1437_sample["curve_id"],
            "isogeny": "none",
            "normal_basis_weight_bound": 7,
            "actual_usable_points_B_before_folding": None,
            "folded_columns_K": None,
            "enumerated_set_sha256": None,
            "sample_size": q1437_sample["sample_size"],
            "rational_x_orbits_in_sample": q1437_sample[
                "rational_x_orbits_in_sample"],
            "duplicate_projected_x_orbits_in_sample": q1437_sample[
                "duplicate_projected_x_orbits_in_sample"],
            "sample_wilson_95_interval": q1437_sample[
                "sample_wilson_95_interval"],
            "conditional_estimate": q1437_sample["conditional_estimate"],
            "conditional_wilson_interval_endpoints": q1437_sample[
                "conditional_wilson_interval_endpoints"],
            "conditional_assumptions": q1437_sample[
                "conditional_assumptions"],
            "independent_group_control_count": q1437_verification[
                "controls"],
            "is_empirical_relation_yield": False,
            "is_complete_solve_projection": False,
            "complete_solve_work_log2": None,
            "protocol_sha256": sha(q1437_protocol_path),
            "sample_sha256": sha(q1437_sample_path),
            "verification_sha256": sha(q1437_verification_path),
        },
        "q1407_compact_s3_formula_shape": {
            "proposal_id": "Q1407",
            "candidate_id": None,
            "isogeny": "none",
            "n53": q1407_shape["n53_matched_measured_formula_shape"],
            "n83": q1407_shape["n83_matched_measured_formula_shape"],
            "n131": q1407_shape["n131_placeholder_formula_shape"],
            "interpretation": q1407_shape["interpretation"],
            "is_decomposition_cost_measurement": False,
            "is_complete_solve_projection": False,
            "complete_solve_work_log2": None,
            "receipt_sha256": sha(q1407_shape_path),
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
            "factor_base_actual_B": q1413_full[
                "actual_usable_points_B_before_folding"],
            "factor_base_folded_columns_K": q1413_full[
                "signed_frobenius_columns_K"],
            "factor_base_enumerated_set_sha256": q1413_full[
                "enumerated_set_sha256"],
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
                "uniform targets; Q1329, Q1332, Q1335, Q1338, Q1401, "
                "Q1403, Q1404, and Q1408 "
                "independently verified planted n83 four-leaf controls, but "
                "none estimates ordinary-query yield; Q1403's ordered "
                "implicit Q1325 SAT formula timed out on both its ordinary "
                "target and an unpinned satisfiable planted target; Q1404's "
                "smaller raw-preimage W<=5 SAT formula stopped at one million "
                "conflicts on the ordinary target and timed out on an unpinned "
                "satisfiable planted target, with no model in either run; "
                "Q1408's balanced raw-preimage S3 tree also timed out on "
                "the unpinned planted target and exhausted one million "
                "ordinary-target conflicts without a model; "
                "Q1410's same balanced solver independently verifies a "
                "locked four-distinct-column N53 ordinary witness but also "
                "exhausts one million conflicts unpinned on that ordinary "
                "target without a model, so the two censored rows cannot "
                "fit a solve-growth exponent; "
                "Q1412's unsigned leaf ordering preserves the locked N53 "
                "witness but also exhausts one million ordinary-target "
                "conflicts without a model; "
                "Q1415 activates XOR Gaussian matrices on Q1410's exact "
                "ordinary N53 formula but reaches the external 120-second "
                "cap without a model, so it provides no N83 solve-growth "
                "estimate; Q1419's 16 pinned controls show that freeing pair "
                "intermediates already hits the SAT cap at both N53 and N83, "
                "while all N83 cells beyond full lock remain censored; these "
                "known-satisfiable controls do not measure natural yield or "
                "growth; Q1420's exact external S3 root clauses recover "
                "both N53/N83 free-mid known-witness controls, but its two "
                "ordinary targets time out before solver operation counts "
                "are reported, with no verified relation; Q1421 counts "
                "those missing operations under matched default and "
                "leaf-first policies, but all ordinary N53/N83 cells hit "
                "the wall cap with no model, so no solve-growth fit or "
                "natural useful-row rate follows; Q1422 proves and tests "
                "an exact single-leaf curve-lift gate, rejecting many "
                "nonrational raw x candidates at both degrees, but its "
                "ordinary N53/N83 cells also hit the wall cap without a "
                "model; Q1423 adds exact target-coupled final S3 roots "
                "and verifies both controls, but its ordinary cells "
                "enumerate over 62,000 leaf-pair assignments each "
                "while final-root propagation activates just once per "
                "query, with no relation at either wall cap; Q1424's "
                "two target-first orders verify all controls and show "
                "which pair link consumes the search, yet all ordinary "
                "cells again cap with one final-root activation and no "
                "relation; Q1425's exact reverse-S3 partner roots verify "
                "four freed-partner controls and reject nearly all "
                "complete pair attempts early, yet four ordinary cells "
                "still cap without a relation and consume many reverse "
                "root calls; Q1333/Q1334 use "
                "an adaptive target-local inversion "
                "window and reproduce the fixed-window ordinary outcomes; "
                "Q1336/Q1337 fuse one field multiplication per S3 root but "
                "show no repeatable wall-time gain in one unisolated "
                "observation per field; older n53/n83 SAT variants remain "
                "censored; Q1413 now "
                "enumerates the exact n131 W<=6 base B/K/digest and Q1414 "
                "recomputes the uniform-query rank-supply bound from it; "
                "Q1416 recomputes the pure pair-index model on the exact "
                "base, but none supplies a decomposition-cost measurement; "
                "Q1442's selected W7 optimum is a conditional Poisson and "
                "novel-row model with actual B/K/digest unknown, not a "
                "measured relation yield or complete work charge; "
                "Q1443 bounds target-oblivious first-pair trials but does "
                "not measure a joint target-guided solver; "
                "Q1444's sound WDSat adapter reaches all four N53/N83 "
                "control and ordinary caps with no model or relation; "
                "Q1445 independently verifies one exact-base N53 pair-table "
                "relation, but its N83 10000-query control has zero hits "
                "and the target-independent first-pair method remains outside "
                "the N131 affordability path; "
                "Q1446 fires sound cached span filters on both partial "
                "pairs but each 60-second ordinary cell still reaches only "
                "one target-linked intermediate choice and no relation; "
                "Q1447 excludes uniform midpoint restarts on the exact "
                "N131 W<=6 base in an abstract trial unit but does not "
                "bound target-guided joint search or measure its cost; "
                "Q1448's compact torsion-symmetrized five-input SAT "
                "circuit passes pinned N53/N83 controls but both ordinary "
                "cells hit the 60-second solver cap without a model, so "
                "it yields no natural rate or successful-solve trend; "
                "Q1449 preserves its native XOR rows and passes pinned "
                "controls, but CryptoMiniSat uses zero Gaussian matrices "
                "at its default column limit and both ordinary cells "
                "reach the external timeout without a model; "
                "Q1450 activates bounded Gaussian matrices at both "
                "degrees, yet both ordinary cells still reach the "
                "external timeout without a model; "
                "Q1451 reduces both circuits by specializing one "
                "public-target preimage, but both ordinary index-0 "
                "slices still time out without a model and do not "
                "measure whole-target relation yield; "
                "Q1452 selects the archived known-satisfiable N53 "
                "preimage 201 with four unpinned leaves, yet also "
                "times out without a model after about 369K rounded "
                "partial conflicts; "
                "Q1453 clears phi5 denominators exactly and passes "
                "N53/N83 pinned controls, but its larger projective "
                "circuits also time out on both ordinary cells; "
                "Q1454 extends Q1452's exact N53 known-satisfiable "
                "XCNF to 1,000,002 exact SAT conflicts, exits "
                "INDETERMINATE without a model, and still supplies "
                "no successful-solve cost; "
                "Q1455's exact joint-pair join passes both witness "
                "controls but sees only over-cap partial domains on "
                "all three unpinned N53/N83 cells; "
                "one n53 success and censored n83 ordinary "
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
