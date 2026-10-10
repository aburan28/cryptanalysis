#!/usr/bin/env python3
"""Replay Q1428 inputs, two exact root links, SAT counters, and relations."""

from __future__ import annotations

import json

import run as experiment


def replay_relation(profile, reported):
    n = profile["field_degree_n"]
    leaves = [list(range(1 + pair * n, 1 + (pair + 1) * n))
              for pair in range(4)]
    model = {bit: bool(value >> offset & 1)
             for bits, value in zip(leaves, reported["raw_leaf_x"])
             for offset, bit in enumerate(bits)}
    assert experiment.prior.verify_relation(profile, model, leaves) == reported


def verify_one(n, kind, anchor_number, frozen):
    stem = f"n{n}_control" if kind == "control" else (
        f"n{n}_ordinary_anchor{anchor_number}")
    path = experiment.HERE / f"{stem}.json"
    trace_path = experiment.HERE / f"{stem}.trace.jsonl"
    assert path.is_file() and trace_path.is_file(), stem
    row = json.loads(path.read_text())
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    case = frozen["cases"][str(n)]
    profile, parent, fixture, parent_path, fixture_path = (
        experiment.prior.load_case(n, "ordinary_both_lazy" if
                                   kind == "ordinary" else "control_both_preseed"))
    assert row["schema"] == "q1428-double-root-run-v1"
    assert row["proposal_id"] == "Q1428"
    assert row["candidate_id"] is None and row["run_id"] is None
    assert row["isogeny"] == "none"
    assert row["n"] == n and row["kind"] == kind
    assert row["anchor_number"] == anchor_number
    assert row["curve_id"] == case["curve_id"]
    assert row["factor_base_actual_B"] == case["B"]
    assert row["factor_base_folded_columns_K"] == case["K"]
    assert row["factor_base_enumerated_set_sha256"] == case["base_digest"]
    assert row["parent_receipt_sha256"] == experiment.prior.digest(parent_path)
    assert row["fixture_receipt_sha256"] == (
        experiment.prior.digest(fixture_path) if fixture_path else None)
    assert row["freeze_sha256"] == experiment.prior.digest(
        experiment.HERE / "freeze.json")
    assert row["trace_sha256"] == experiment.prior.digest(trace_path)
    assert row["trace_rows"] == row["solver_calls"] == len(trace)
    assert len(trace) <= frozen["limits"]["max_solver_calls"]
    assert [event["solver_call"] for event in trace] == list(
        range(1, len(trace) + 1))
    for counter in ("conflicts", "propagations", "decisions"):
        assert row["solver_" + counter] == sum(
            event["solver_counters"][counter] for event in trace)
    assert row["status"] in ("VERIFIED_RELATION", "BOUNDED_UNKNOWN",
                             "UNSAT_TESTED_SUBSET")
    assert row["natural_relation_yield_estimate"] is None
    assert row["field_operations_complete"] is None
    assert row["n131_complete_cold_work_log2"] is None
    assert row["n131_complete_online_one_target_work_log2"] is None
    onb = experiment.prior.field.Onb(n)
    if kind == "ordinary":
        assert row["workload_id"] == case["ordinary_workload_id"]
        assert row["input_law"] == "frozen_ordinary_target_hash_anchor_subset"
        curve, keys, key = experiment.parent.read_base(profile, onb)
        selected = experiment.parent.choose(
            profile, parent, anchor_number, onb, curve, keys, key)
        assert selected == case["ordinary_anchors"][anchor_number]
        assert row["selected_anchor"] == selected
        expected_join = case["ordinary_joins"][anchor_number]
        assert row["scheduled_lifts"] == case["ordinary_lifts"]
    else:
        assert row["input_law"] == "known_solution_control"
        assert fixture is not None
        selected = case["control_anchor"]
        assert [leaf["raw_x"] for leaf in row["selected_anchor"]["leaves"]] == (
            [leaf["raw_x"] for leaf in selected["leaves"]])
        assert row["selected_anchor"]["roots"] == selected["roots"]
        assert row["scheduled_lifts"] == case["control_lifts"]
        expected_join = case["control_join"]
    roots = experiment.exact_roots(experiment.MeteredField(onb), *(
        leaf["raw_x"] for leaf in row["selected_anchor"]["leaves"]))
    assert list(roots) == row["selected_anchor"]["roots"]
    assert row["outer_join"] == expected_join
    assert row["outer_join"] == experiment.joined_branches(
        onb, row["selected_anchor"], row["scheduled_lifts"])
    formula, _, _ = experiment.build_right_pair(
        n, case["normal_basis_weight_bound"])
    assert row["formula"] == {
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "right_variable_leaves": 2,
        "external_s3_links": 2,
        "inside_sat_s3_links": 1}
    branches = row["outer_join"]["branches"]
    attempted = set()
    for event in trace:
        branch = event["branch"]
        assert branch in branches
        attempted.add((branch["lift_index"], branch["left_root_index"],
                       branch["right_root_index"]))
        assert event["state"] in ("SAT", "UNSAT", "BOUNDED_UNKNOWN")
        assert all(value >= 0 for value in event["solver_counters"].values())
        assert event["solver_counters"]["conflicts"] <= (
            frozen["limits"]["conflicts_per_call"] + 1024)
        if event["state"] == "SAT":
            right = event["right_leaf_x"]
            assert len(right) == 2
            assert all(0 < value < (1 << n) and value.bit_count() <=
                       case["normal_basis_weight_bound"] for value in right)
            assert branch["right_output_x"] in experiment.exact_roots(
                experiment.MeteredField(onb), *right)
            assert event["relation_status"] in (
                "verified_four_point_relation", "nonrational_raw_x",
                "identity_projection", "outside_exact_base",
                "duplicate_columns", "no_signed_public_sum")
    assert row["attempted_branches"] == len(attempted)
    assert row["rejected_models"] == sum(
        event["state"] == "SAT" and event["relation_status"] !=
        "verified_four_point_relation" for event in trace)
    if row["status"] == "VERIFIED_RELATION":
        assert row["verified_relation"] is not None
        assert trace[-1]["relation_status"] == "verified_four_point_relation"
        replay_relation(profile, row["verified_relation"])
    else:
        assert row["verified_relation"] is None
        assert row["status"] != "UNSAT_TESTED_SUBSET" or (
            all(event["state"] == "UNSAT" for event in trace) and
            len(attempted) == len(branches))
    phases = row["phase_seconds"]
    assert all(value >= 0 for value in phases.values())
    assert abs(row["anchor_selection_seconds"] + row[
        "outer_join_seconds"] + sum(phases.values()) -
               row["target_pdp_wall_seconds"]) < 1e-4
    if row["peak_rss_units"].startswith("bytes"):
        assert row["peak_parent_rss_raw"] < frozen["limits"]["rss_mib"] * 2**20
    return {"case": stem, "status": row["status"],
            "solver_calls": len(trace),
            "solver_conflicts": row["solver_conflicts"],
            "first_sat_model": any(event["state"] == "SAT" for event in trace),
            "verified_relation": row["verified_relation"] is not None}


def main():
    frozen = experiment.check_freeze()
    rows = [verify_one(n, kind, anchor, frozen)
            for n in (53, 83)
            for kind, anchor in (("control", None), ("ordinary", 0),
                                 ("ordinary", 1))]
    assert len(rows) == 6
    summary = {"schema": "q1428-double-root-verification-v1",
               "all_six_cases_checked": True,
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "verification.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
