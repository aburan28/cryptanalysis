#!/usr/bin/env python3
"""Replay Q1429's paired output-encoding grid and accepted relations."""

from __future__ import annotations

import json

import run as experiment


def replay_relation(profile, relation):
    n = profile["field_degree_n"]
    leaves = [list(range(1 + pair * n, 1 + (pair + 1) * n))
              for pair in range(4)]
    model = {bit: bool(value >> index & 1)
             for bits, value in zip(leaves, relation["raw_leaf_x"])
             for index, bit in enumerate(bits)}
    assert experiment.prior.verify_relation(profile, model, leaves) == relation


def verify_one(n, kind, variant, frozen, old):
    stem = f"n{n}_{kind}_{variant}"
    path, trace_path = experiment.HERE / f"{stem}.json", (
        experiment.HERE / f"{stem}.trace.jsonl")
    assert path.is_file() and trace_path.is_file(), stem
    row = json.loads(path.read_text())
    trace_lines = trace_path.read_text().splitlines()
    assert len(trace_lines) == 1
    trace = json.loads(trace_lines[0])
    case, previous = frozen["cases"][str(n)], old["cases"][str(n)]
    profile, parent_receipt, fixture, parent_path, fixture_path = (
        experiment.prior.load_case(
            n, "control_both_preseed" if kind == "control" else
            "ordinary_both_lazy"))
    assert row["schema"] == "q1429-fixed-output-run-v1"
    assert row["proposal_id"] == "Q1429"
    assert row["candidate_id"] is None and row["run_id"] is None
    assert row["isogeny"] == "none"
    assert (row["n"], row["kind"], row["variant"]) == (n, kind, variant)
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
    assert row["workload_id"] == parent_receipt["workload_id"]
    assert row["solver_calls"] == 1
    assert row["status"] in ("VERIFIED_RELATION", "SAT_NONRELATION",
                             "UNSAT_FOR_FIXED_OUTPUT", "BOUNDED_UNKNOWN")
    assert row["natural_relation_yield_estimate"] is None
    assert row["field_operations_complete"] is None
    assert row["n131_complete_cold_work_log2"] is None
    assert row["n131_complete_online_one_target_work_log2"] is None
    if kind == "ordinary":
        assert row["workload_id"] == case["ordinary_workload_id"]
        onb = experiment.prior.field.Onb(n)
        curve, keys, key = experiment.parent.parent.read_base(profile, onb)
        anchor = experiment.parent.parent.choose(
            profile, parent_receipt, 0, onb, curve, keys, key)
        assert anchor == previous["ordinary_anchors"][0]
        lifts = previous["ordinary_lifts"]
    else:
        assert fixture is not None
        anchor = previous["control_anchor"]
        lifts = previous["control_lifts"]
    assert row["selected_anchor"] == anchor
    joined = experiment.parent.joined_branches(
        experiment.prior.field.Onb(n), anchor, lifts)
    assert row["outer_join"] == joined
    branch = case["selected"][kind]["branch"]
    assert branch == row["branch"] and branch in joined["branches"]
    value = branch["right_output_x"]
    assert row["right_output_x"] == value
    formula, _, _, _ = experiment.build(
        n, case["normal_basis_weight_bound"], value, variant)
    assert row["formula"] == experiment.shape(formula)
    assert row["formula"] == case["selected"][kind]["formula"][variant]
    assert trace["state"] in ("SAT", "UNSAT", "BOUNDED_UNKNOWN")
    for key in ("conflicts", "propagations", "decisions"):
        assert row["solver_" + key] == trace["solver_counters"][key]
    assert trace["solver_counters"]["conflicts"] <= (
        frozen["limits"]["conflicts_per_call"] + 1024)
    if trace["state"] == "SAT":
        right = row["right_leaf_x"]
        assert right == trace["right_leaf_x"] and len(right) == 2
        assert value in experiment.exact_roots(
            experiment.MeteredField(experiment.prior.field.Onb(n)), *right)
        assert row["relation_check"]["status"] == trace["relation_status"]
        if row["status"] == "VERIFIED_RELATION":
            replay_relation(profile, row["relation_check"])
        else:
            assert row["status"] == "SAT_NONRELATION"
    else:
        assert row["right_leaf_x"] is None
        assert row["relation_check"] is None
        assert row["status"] == ("UNSAT_FOR_FIXED_OUTPUT" if
                                 trace["state"] == "UNSAT" else
                                 "BOUNDED_UNKNOWN")
    phases = row["phase_seconds"]
    assert all(amount >= 0 for amount in phases.values())
    assert abs(sum(phases.values()) - row["target_pdp_wall_seconds"]) < 1e-4
    if row["peak_rss_units"].startswith("bytes"):
        assert row["peak_parent_rss_raw"] < frozen["limits"]["rss_mib"] * 2**20
    return {"case": stem, "status": row["status"],
            "conflicts": row["solver_conflicts"],
            "wall_seconds": row["target_pdp_wall_seconds"]}


def main():
    frozen = experiment.check_freeze()
    old = experiment.parent.check_freeze()
    rows = [verify_one(n, kind, variant, frozen, old)
            for n in (53, 83)
            for kind in ("control", "ordinary")
            for variant in experiment.VARIANTS]
    assert len(rows) == 12
    summary = {"schema": "q1429-fixed-output-verification-v1",
               "all_twelve_cases_checked": True,
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "verification.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
