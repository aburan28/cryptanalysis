#!/usr/bin/env python3
"""Known-solution control for the one-lift Q1426 formula construction."""

from __future__ import annotations

import json

import run as experiment


def check_one(n):
    prior = experiment.prior
    profile, parent, fixture, _, _ = prior.load_case(n, "control_both_preseed")
    raw = fixture["fixture"]
    onb = prior.field.Onb(n)
    target_x = onb.toCoords(int(raw["raw_sum"][0]))
    assert target_x in parent["raw_preimage_x_coordinates"]
    formula, leaves, mids, _, selector = experiment.build_hybrid(
        n, profile["normal_basis_weight_bound"], [target_x], (0, 1))
    for bits, value in zip(leaves, raw["raw_leaf_x"]):
        prior.pin_bits(formula, bits, value)
    added = []
    with experiment.IncrementalSolver(formula.variables) as solver:
        solver.load_formula(formula)
        for pair in (0, 1):
            a, b = raw["raw_leaf_x"][2 * pair:2 * pair + 2]
            roots = experiment.exact_roots(experiment.MeteredField(onb), a, b)
            assert roots
            branch = solver.new_var() if len(roots) == 2 else None
            rows = experiment.root_lemma(
                leaves[2 * pair], leaves[2 * pair + 1], mids[pair],
                a, b, roots, branch)
            for row in rows:
                assert solver.add_clause(row)
            added.extend(rows)
        state, model = solver.solve(seconds=25, conflicts=100000)
        assert state == "SAT", (n, state)
        prior.check_formula_model(formula, added, model)
        assert experiment.bits_value(selector, model) == 0
        checked = prior.verify_relation(profile, model, leaves)
        assert checked["status"] == "verified_four_point_relation"
        return {"n": n, "curve_id": parent["curve_id"],
                "raw_target_x": target_x,
                "factor_base_actual_B": parent["factor_base_actual_B"],
                "factor_base_folded_columns_K":
                    parent["factor_base_folded_columns"],
                "status": checked["status"]}


def main():
    frozen = experiment.check_freeze()
    rows = [check_one(n) for n in (53, 83)]
    receipt = {"schema": "q1426-lift-slice-control-v1",
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "control_check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
