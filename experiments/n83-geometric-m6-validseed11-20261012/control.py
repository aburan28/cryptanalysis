#!/usr/bin/env python3
"""Replay a planted six-point width-11 relation through the S3 tree."""

import json
from pathlib import Path

from m6 import DIMENSION, HERE, N, OFFSET, build, parity, runner, selfcheck


def pin(formula, bits, value):
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if value >> position & 1 else -literal])


def main():
    output = HERE / "six_point_control.json"
    assert not output.exists()
    parent_protocol = json.loads((HERE.parent /
        "n83-geometric-m5-karatsuba18-20261012/protocol.json").read_text())
    onb = runner.field.Onb(N)
    curve = runner.curves.Curve(onb)
    arithmetic = selfcheck(onb)
    order = parent_protocol["workload"]["subgroup_order"]
    seeds, points = [], []
    for free in range(1 << DIMENSION):
        seed = OFFSET | free
        point = curve.pointFromX(onb.fromCoords(seed))
        if point is not None:
            projected = curve.mul(point, 4)
            if projected is not None and curve.mul(projected, order) is None:
                seeds.append(free)
                points.append(point)
        if len(points) == 6:
            break
    assert len(points) == 6
    u0 = curve.add(points[0], points[1])
    u1 = curve.add(points[2], points[3])
    u2 = curve.add(points[4], points[5])
    u3 = curve.add(u0, u1)
    target = curve.add(u3, u2)
    assert all(point is not None for point in (u0, u1, u2, u3, target))
    public = curve.mul(target, 4)
    assert public is not None and curve.mul(public, order) is None
    target_x = onb.toCoords(target[0])
    formula, leaves, intermediate, inverse_rows = build(onb, target_x)
    for slot, (seed, point) in enumerate(zip(seeds, points)):
        pin(formula, formula.orbit_seed_bits[slot], seed)
        if slot:
            for power, literal in enumerate(formula.orbit_selectors[slot]):
                formula.clauses.append([literal if power == 0 else -literal])
        pin(formula, leaves[slot], onb.toCoords(point[0]))
    for bits, point in zip(intermediate, (u0, u1, u2, u3)):
        onb_x = onb.toCoords(point[0])
        pb_x = sum(parity(row & onb_x) << bit
                   for bit, row in enumerate(inverse_rows))
        pin(formula, bits, pb_x)
    pin(formula, formula.target_x_bits, target_x)
    path = HERE / "six_point_control.xcnf"
    assert not path.exists() and not Path(str(path) + ".gz").exists()
    formula.write(path)
    binary = Path(parent_protocol["solver"]["path"])
    assert runner.sha(binary) == parent_protocol["solver"]["sha256"]
    native = runner.solve_limited(path, binary, 60, 5_000_000, 4 << 30)
    stdout = HERE / "six_point_control.stdout.txt"
    stderr = HERE / "six_point_control.stderr.txt"
    stdout.write_text(native["stdout"])
    stderr.write_text(native["stderr"])
    model = native["model"]
    if model is not None:
        model = dict(model)
        model[1] = True
        def coordinate(bits):
            return sum(1 << bit for bit, literal in enumerate(bits)
                       if (model.get(literal, False) if literal > 0 else
                           not model.get(-literal, False)))
        assert all(coordinate(leaf) == OFFSET | seed
                   for leaf, seed in zip(leaves, seeds))
    receipt = {
        "status": "PASS" if model is not None and native["status"] == "sat"
                  else "FAIL",
        "curve_id": parent_protocol["curve_id"],
        "field_degree": N, "dimension": DIMENSION, "offset": OFFSET,
        "seed_free_bits": seeds,
        "leaf_x_onb": [onb.toCoords(point[0]) for point in points],
        "leaf_points_raw": [[str(value) for value in point] for point in points],
        "intermediate_points_raw": [[str(value) for value in point]
                                    for point in (u0, u1, u2, u3)],
        "raw_target": [str(value) for value in target],
        "public_target": [str(value) for value in public],
        "subgroup_order": order,
        "formula_shape": runner.stats(formula),
        "selfcheck": arithmetic,
        "solver_status": native["status"],
        "solver_wall_seconds": native["wall_seconds"],
        "model_present": model is not None,
        "stdout_sha256": runner.sha(stdout),
        "stderr_sha256": runner.sha(stderr),
        "m6_source_sha256": runner.sha(HERE / "m6.py"),
        "control_source_sha256": runner.sha(Path(__file__)),
        **runner.archive_formula(path),
    }
    runner.save(output, receipt)
    print(json.dumps({"status": receipt["status"],
                      "solver_status": native["status"],
                      "solver_wall_seconds": native["wall_seconds"]}), flush=True)
    assert receipt["status"] == "PASS"


if __name__ == "__main__":
    main()
