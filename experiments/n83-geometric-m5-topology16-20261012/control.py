#!/usr/bin/env python3
"""Replay the frozen five-point control through the power-basis circuit."""

import json
from pathlib import Path

from karatsuba import HERE, N, build, parity, power_basis, runner, selfcheck


def pin(formula, bits, value):
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if value >> position & 1 else -literal])


def main():
    output = HERE / "karatsuba_control.json"
    assert not output.exists()
    parent = json.loads((HERE.parent /
        "n83-geometric-m5-fixedtarget16-20261012/locked_control.json").read_text())
    parent_protocol = json.loads((HERE.parent /
        "n83-geometric-m5-fixedtarget16-20261012/protocol.json").read_text())
    onb = runner.field.Onb(N)
    curve = runner.curves.Curve(onb)
    selfcheck_result = selfcheck(onb)
    public = tuple(map(int, parent["public_point_onb_raw"]))
    order = parent_protocol["workload"]["subgroup_order"]
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    raw_targets, _ = runner.raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    rotated_targets, target_xs = runner.normalized_target_coset(
        onb, curve, public, raw_targets)
    choice = parent["target_choice"]
    target_x = onb.toCoords(int(parent["replay"]["normalized_raw_target"][0]))
    assert target_x == target_xs[choice]
    formula, leaves, selector, inverse_rows = build(onb, target_x, choice)
    relative_powers = [
        (power + parent["normalizing_frobenius_power"]) % N
        for power in parent["frobenius_powers"]]
    assert relative_powers[0] == 0
    for index in range(5):
        pin(formula, formula.orbit_seed_bits[index], parent["seed_x"][index])
        if index:
            for power, literal in enumerate(formula.orbit_selectors[index]):
                formula.clauses.append([literal if power ==
                                        relative_powers[index] else -literal])
        pin(formula, leaves[index], parent["normalized_raw_leaf_x"][index])
    points = [tuple(map(int, point))
              for point in parent["replay"]["normalized_raw_leaf_points"]]
    intermediates = [curve.add(points[0], points[1]),
                     curve.add(points[2], points[3])]
    intermediates.append(curve.add(intermediates[0], intermediates[1]))
    for bits, point in zip(formula.intermediates, intermediates):
        onb_x = onb.toCoords(point[0])
        pb_x = sum(parity(row & onb_x) << bit
                   for bit, row in enumerate(inverse_rows))
        pin(formula, bits, pb_x)
    pin(formula, formula.target_x_bits, target_x)
    pin(formula, selector, choice)
    path = HERE / "karatsuba_control.xcnf"
    assert not path.exists() and not Path(str(path) + ".gz").exists()
    formula.write(path)
    binary = Path(parent_protocol["solver"]["path"])
    assert runner.sha(binary) == parent_protocol["solver"]["sha256"]
    native = runner.solve_limited(path, binary, 60, 5000000, 4294967296)
    stdout = HERE / "karatsuba_control.stdout.txt"
    stderr = HERE / "karatsuba_control.stderr.txt"
    stdout.write_text(native["stdout"])
    stderr.write_text(native["stderr"])
    replay = None
    if native["model"] is not None:
        model = dict(native["model"])
        model[1] = True
        replay = runner.replay_normalized(
            onb, curve, order, 16,
            runner.base_x_keys(parent_protocol["base_rows"][0], onb,
                               runner.OrbitKey(onb)),
            public, raw_targets, rotated_targets, leaves, selector, model)
    receipt = {
        "status": "PASS" if replay and replay["status"] ==
                  "verified_five_point_relation" else "FAIL",
        "selfcheck": selfcheck_result,
        "target_choice": choice,
        "formula_shape": runner.stats(formula),
        "solver_status": native["status"],
        "solver_wall_seconds": native["wall_seconds"],
        "model_present": native["model"] is not None,
        "replay": replay,
        "stdout_sha256": runner.sha(stdout),
        "stderr_sha256": runner.sha(stderr),
        **runner.archive_formula(path),
    }
    runner.save(output, receipt)
    print(json.dumps({"status": receipt["status"],
                      "solver_status": native["status"],
                      "solver_wall_seconds": native["wall_seconds"]}), flush=True)
    assert receipt["status"] == "PASS"


if __name__ == "__main__":
    main()
