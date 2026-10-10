#!/usr/bin/env python3
"""Q1429 pinned true and false fixed-output S3 controls."""

from __future__ import annotations

import json

import run as experiment


def check(n, variant, frozen):
    case = frozen["cases"][str(n)]
    old = experiment.parent.check_freeze()["cases"][str(n)]
    profile, _, fixture, _, _ = experiment.prior.load_case(
        n, "control_both_preseed")
    onb = experiment.prior.field.Onb(n)
    known_right = fixture["fixture"]["raw_leaf_x"][2:]
    output_x = old["control_right_mid_x"]
    roots = experiment.exact_roots(experiment.MeteredField(onb),
                                   *known_right)
    assert output_x in roots
    wrong_x = next(output_x ^ (1 << bit) for bit in range(n)
                   if output_x ^ (1 << bit) not in roots)
    observations = []
    for value, expected in ((output_x, "SAT"), (wrong_x, "UNSAT")):
        formula, leaves, output, assumptions = experiment.build(
            n, case["normal_basis_weight_bound"], value, variant)
        for bits, coordinate in zip(leaves, known_right):
            experiment.parent.parent.pin_bits(formula, bits, coordinate)
        with experiment.StatsSolver(formula.variables) as solver:
            if expected == "SAT":
                solver.load_formula(formula)
                consistent_at_root = True
            else:
                consistent_at_root = all(solver.add_clause(row)
                                         for row in formula.clauses)
                if consistent_at_root:
                    consistent_at_root = all(solver.add_xor(row, rhs)
                                             for row, rhs in formula.xors)
            if consistent_at_root:
                state, model, counters = solver.solve_assuming(
                    assumptions, seconds=10, conflicts=100000)
            else:
                state, model = "UNSAT_ROOT", None
                counters = {"conflicts": 0, "propagations": 0,
                            "decisions": 0}
        assert state == expected or (expected == "UNSAT" and
                                     state == "UNSAT_ROOT"), (
            n, variant, value, state, counters)
        if state == "SAT":
            experiment.prior.check_formula_model(formula, [], model)
            assert output is None or experiment.bits_value(output, model) == value
            assert [experiment.bits_value(bits, model) for bits in leaves] == (
                known_right)
            augmented, four = experiment.parent.synthetic_model(
                n, formula.variables,
                [leaf["raw_x"] for leaf in old["control_anchor"]["leaves"]],
                model, leaves)
            relation = experiment.prior.verify_relation(profile,
                                                        augmented, four)
            assert relation["status"] == "verified_four_point_relation"
        observations.append({"output_x": value, "state": state,
                             "solver_counters": counters})
    assert experiment.shape(experiment.build(
        n, case["normal_basis_weight_bound"], output_x, variant)[0]) == (
            case["selected"]["control"]["formula"][variant])
    return {"n": n, "variant": variant,
            "known_right_leaf_x": known_right,
            "observations": observations}


def main():
    frozen = experiment.check_freeze()
    rows = [check(n, variant, frozen)
            for n in (53, 83) for variant in experiment.VARIANTS]
    receipt = {"schema": "q1429-fixed-output-control-v1",
               "freeze_sha256": experiment.prior.digest(
                   experiment.HERE / "freeze.json"),
               "rows": rows}
    (experiment.HERE / "control_check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(rows), "controls": "PASS"}))


if __name__ == "__main__":
    main()
