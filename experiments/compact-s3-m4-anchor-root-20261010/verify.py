#!/usr/bin/env python3
"""Replay Q1427's frozen anchors, exact roots, counters, and receipts."""

from __future__ import annotations

import json

import run as experiment
from hybrid import MeteredField, build_hybrid, exact_roots


def replay_relation(n, profile, reported):
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
    assert row["schema"] == "q1427-anchor-root-run-v1"
    assert row["proposal_id"] == "Q1427"
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
    assert [event["solver_call"] for event in trace] == list(range(1, len(trace) + 1))
    assert row["solver_conflicts"] == sum(
        event["solver_counters"]["conflicts"] for event in trace)
    assert row["solver_propagations"] == sum(
        event["solver_counters"]["propagations"] for event in trace)
    assert row["solver_decisions"] == sum(
        event["solver_counters"]["decisions"] for event in trace)
    assert row["status"] in ("VERIFIED_RELATION", "BOUNDED_UNKNOWN",
                             "UNSAT_TESTED_SUBSET")
    assert row["natural_relation_yield_estimate"] is None
    assert row["field_operations_complete"] is None
    assert row["n131_complete_cold_work_log2"] is None
    assert row["n131_complete_online_one_target_work_log2"] is None
    if kind == "ordinary":
        assert row["workload_id"] == case["ordinary_workload_id"]
        assert row["input_law"] == "frozen_ordinary_target_hash_anchor_subset"
        onb = experiment.prior.field.Onb(n)
        curve, keys, key = experiment.read_base(profile, onb)
        selection = experiment.choose(profile, parent, anchor_number,
                                      onb, curve, keys, key)
        assert selection == row["selected_anchor"]
        assert selection == case["ordinary_anchors"][anchor_number]
        assert row["attempted_lift_indices"] == [
            value["lift_index"] for value in row["formula_per_lift"]]
        assert set(row["attempted_lift_indices"]) <= set(case[
            "selected_lift_indices"])
    else:
        assert row["input_law"] == "known_solution_control"
        known = case["known_control"]
        assert [leaf["raw_x"] for leaf in row["selected_anchor"]["leaves"]] == (
            known["raw_leaf_x"])
        assert row["selected_anchor"]["roots"] == known["roots"]
        assert fixture is not None
    onb = experiment.prior.field.Onb(n)
    roots = exact_roots(MeteredField(onb), *(
        leaf["raw_x"] for leaf in row["selected_anchor"]["leaves"]))
    assert list(roots) == row["selected_anchor"]["roots"]
    assert roots
    raw_lifts = parent["raw_preimage_x_coordinates"]
    anchor_x = [leaf["raw_x"] for leaf in row["selected_anchor"]["leaves"]]
    for formula_row in row["formula_per_lift"]:
        target_x = raw_lifts[formula_row["lift_index"]]
        formula, leaves, _, _, _ = build_hybrid(
            n, profile["normal_basis_weight_bound"], [target_x], (0,))
        for bits, value in zip(leaves[:2], anchor_x):
            experiment.pin_bits(formula, bits, value)
        assert experiment.prior.formula_stats(formula, (0,)) == formula_row[
            "stats"]
    for event in trace:
        assert event["lift_index"] in row["attempted_lift_indices"]
        assert event["root_x"] == roots[event["root_index"]]
        assert event["state"] in ("SAT", "UNSAT", "BOUNDED_UNKNOWN")
        assert all(value >= 0 for value in event["solver_counters"].values())
        assert event["solver_counters"]["conflicts"] <= (
            frozen["limits"]["conflicts_per_call"] + 1024)
    if row["status"] == "VERIFIED_RELATION":
        assert row["verified_relation"] is not None
        assert trace[-1]["relation_status"] == "verified_four_point_relation"
        replay_relation(n, profile, row["verified_relation"])
    else:
        assert row["verified_relation"] is None
    phases = row["phase_seconds"]
    assert all(value >= 0 for value in phases.values())
    assert abs(row["anchor_selection_seconds"] + sum(phases.values()) -
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
    summary = {"schema": "q1427-anchor-root-verification-v1",
               "all_six_cases_checked": True,
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "verification.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
