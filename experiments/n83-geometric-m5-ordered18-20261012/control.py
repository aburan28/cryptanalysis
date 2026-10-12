#!/usr/bin/env python3
"""Check a sorted, planted five-point relation in the N83 SAT circuit."""

import json
from pathlib import Path

from ordered import HERE, N, PARENT, build, parity, runner, selfcheck


def pin(formula, bits, value):
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if value >> position & 1 else -literal])


def main():
    output = HERE / "ordered_control.json"
    assert not output.exists()
    prior = json.loads((HERE.parent /
        "n83-geometric-m5-fixedtarget16-20261012/locked_control.json").read_text())
    protocol = json.loads((PARENT / "protocol.json").read_text())
    onb = runner.field.Onb(N)
    curve = runner.curves.Curve(onb)
    selfcheck_result = selfcheck(onb)
    public = tuple(map(int, prior["public_point_onb_raw"]))
    order = protocol["workload"]["subgroup_order"]
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    raw_targets, _ = runner.raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    rotated_targets, target_xs = runner.normalized_target_coset(
        onb, curve, public, raw_targets)
    choice = prior["target_choice"]
    target_x = onb.toCoords(int(prior["replay"]["normalized_raw_target"][0]))
    assert target_x == target_xs[choice]
    formula, leaves, selector, inverse_rows = build(onb, target_x, choice)
    relative_powers = [(power + prior["normalizing_frobenius_power"]) % N
                       for power in prior["frobenius_powers"]]
    assert relative_powers[0] == 0
    point_rows = [tuple(map(int, point)) for point in
                  prior["replay"]["normalized_raw_leaf_points"]]
    raw_xs = prior["normalized_raw_leaf_x"]
    assert len(raw_xs) == len(point_rows) == 5
    permutation = [0] + sorted(range(1, 5), key=lambda i: (raw_xs[i], i))
    assert [raw_xs[i] for i in permutation[1:]] == sorted(raw_xs[1:])
    for slot, original in enumerate(permutation):
        pin(formula, formula.orbit_seed_bits[slot], prior["seed_x"][original])
        if slot:
            for power, literal in enumerate(formula.orbit_selectors[slot]):
                formula.clauses.append([literal if power ==
                                        relative_powers[original] else -literal])
        pin(formula, leaves[slot], raw_xs[original])
    points = [point_rows[index] for index in permutation]
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
    formula_path = HERE / "ordered_control.xcnf"
    assert not formula_path.exists() and not Path(str(formula_path) + ".gz").exists()
    formula.write(formula_path)
    binary = Path(protocol["solver"]["path"])
    assert runner.sha(binary) == protocol["solver"]["sha256"]
    native = runner.solve_limited(formula_path, binary, 60, 5_000_000, 4 << 30)
    stdout = HERE / "ordered_control.stdout.txt"
    stderr = HERE / "ordered_control.stderr.txt"
    stdout.write_text(native["stdout"])
    stderr.write_text(native["stderr"])
    replay = None
    if native["model"] is not None:
        model = dict(native["model"])
        model[1] = True
        replay = runner.replay_normalized(
            onb, curve, order, 18,
            runner.base_x_keys(protocol["base_rows"][0], onb,
                               runner.OrbitKey(onb)),
            public, raw_targets, rotated_targets, leaves, selector, model)
    receipt = {
        "status": "PASS" if replay and replay["status"] ==
                  "verified_five_point_relation" else "FAIL",
        "permutation": permutation,
        "sorted_raw_leaf_x": [raw_xs[i] for i in permutation],
        "selfcheck": selfcheck_result,
        "target_choice": choice,
        "formula_shape": runner.stats(formula),
        "solver_status": native["status"],
        "solver_wall_seconds": native["wall_seconds"],
        "model_present": native["model"] is not None,
        "replay": replay,
        "stdout_sha256": runner.sha(stdout),
        "stderr_sha256": runner.sha(stderr),
        "ordered_source_sha256": runner.sha(HERE / "ordered.py"),
        "control_source_sha256": runner.sha(Path(__file__)),
        **runner.archive_formula(formula_path),
    }
    runner.save(output, receipt)
    print(json.dumps({"status": receipt["status"],
                      "solver_status": native["status"],
                      "solver_wall_seconds": native["wall_seconds"]}), flush=True)
    assert receipt["status"] == "PASS"


if __name__ == "__main__":
    main()
