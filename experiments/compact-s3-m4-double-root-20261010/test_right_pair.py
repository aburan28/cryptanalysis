#!/usr/bin/env python3
"""Q1428 fixed-output S3 and exact-root known-solution controls."""

from __future__ import annotations

import json

import run as experiment


def check_one(n, frozen):
    case = frozen["cases"][str(n)]
    profile, parent, fixture, _, fixture_path = experiment.prior.load_case(
        n, "control_both_preseed")
    assert experiment.prior.digest(fixture_path) == case[
        "control_fixture_sha256"]
    onb = experiment.prior.field.Onb(n)
    raw = fixture["fixture"]
    known_right = raw["raw_leaf_x"][2:]
    assert len(known_right) == 2
    expected_output = onb.toCoords(int(raw["raw_pair_sum_points"][1][0]))
    assert expected_output == case["control_right_mid_x"]
    assert expected_output in [branch["right_output_x"]
                                  for branch in case["control_join"]["branches"]]
    right_roots = experiment.exact_roots(
        experiment.MeteredField(onb), *known_right)
    assert expected_output in right_roots
    formula, right_leaves, output = experiment.build_right_pair(
        n, case["normal_basis_weight_bound"])
    for bits, value in zip(right_leaves, known_right):
        experiment.parent.pin_bits(formula, bits, value)
    with experiment.StatsSolver(formula.variables) as solver:
        solver.load_formula(formula)
        state, model, counters = solver.solve_assuming(
            experiment.assumptions(output, expected_output),
            seconds=15, conflicts=100000)
    assert state == "SAT", (n, state, counters)
    experiment.prior.check_formula_model(formula, [], model)
    assert experiment.bits_value(output, model) == expected_output
    assert [experiment.bits_value(bits, model) for bits in right_leaves] == (
        known_right)
    anchor_x = [leaf["raw_x"] for leaf in case["control_anchor"]["leaves"]]
    augmented, leaves = experiment.synthetic_model(
        n, formula.variables, anchor_x, model, right_leaves)
    relation = experiment.prior.verify_relation(profile, augmented, leaves)
    assert relation["status"] == "verified_four_point_relation", relation
    assert relation["raw_leaf_x"] == raw["raw_leaf_x"]
    assert parent["curve_id"] == case["curve_id"]
    return {"n": n, "state": state, "solver_counters": counters,
            "expected_right_output_x": expected_output,
            "right_root_count": len(right_roots),
            "external_join_branch_count": len(case["control_join"]["branches"]),
            "relation_status": relation["status"],
            "formula": {"variables": formula.variables,
                        "cnf_clauses": len(formula.clauses),
                        "xor_rows": len(formula.xors)}}


def main():
    frozen = experiment.check_freeze()
    rows = [check_one(n, frozen) for n in (53, 83)]
    receipt = {"schema": "q1428-right-pair-control-v1",
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "control_check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
