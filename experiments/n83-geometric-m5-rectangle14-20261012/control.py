#!/usr/bin/env python3
"""Locked five-point control for normalized rectangle width-14 S3 encoding."""

import json
from pathlib import Path

from run import (HERE, OrbitKey, archive_formula, base_x_keys,
                 build_affine_formula, curves, field, kernel_of_cofactor,
                 normalized_target_coset, raw_preimage_coset,
                 replay_normalized, save, sha, solve_limited, stats)


def pin(formula, bits, value):
    for position, literal in enumerate(bits):
        formula.clauses.append([literal if (value >> position) & 1
                                else -literal])


def main():
    output = HERE / "locked_control.json"
    assert not output.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    row = protocol["base_rows"][0]
    assert row["dimension"] == 14
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = protocol["workload"]["subgroup_order"]
    base_keys = base_x_keys(row, onb, OrbitKey(onb))
    offset = row["offset_onb_coordinates"]
    basis = row["basis_onb_coordinates"]
    seeds, coefficients, points, columns = [], [], [], set()
    for coset in (0, 1, 2, 3, 0):
        found = False
        for low in range(1 << 12):
            coefficient = low | (coset << 12)
            seed = offset ^ low
            if coset & 1:
                seed ^= basis[12]
            if coset & 2:
                seed ^= basis[13]
            point = curve.pointFromX(onb.fromCoords(seed))
            if point is None:
                continue
            projected = curve.mul(point, 4)
            if projected is None:
                continue
            key = min(onb.toCoords(onb.frob(projected[0], power))
                      for power in range(83))
            if key not in base_keys or key in columns:
                continue
            seeds.append(seed)
            coefficients.append(coefficient)
            points.append(point)
            columns.add(key)
            found = True
            break
        assert found
    assert len(seeds) == len(columns) == 5
    powers = [17, 1, 7, 23, 41]
    points = [curve.frob(point, power)
              for point, power in zip(points, powers)]
    leaf_xs = [onb.toCoords(point[0]) for point in points]
    for seed, power, leaf in zip(seeds, powers, leaf_xs):
        assert onb.toCoords(onb.frob(onb.fromCoords(seed), power)) == leaf
    normalizing_power = (83 - powers[0]) % 83
    normalized_points = [curve.frob(point, normalizing_power)
                         for point in points]
    normalized_leaf_xs = [onb.toCoords(point[0])
                           for point in normalized_points]
    relative_powers = [(power + normalizing_power) % 83
                       for power in powers]
    assert relative_powers[0] == 0
    intermediate = [curve.add(normalized_points[0], normalized_points[1]),
                    curve.add(normalized_points[2], normalized_points[3])]
    intermediate.append(curve.add(intermediate[0], intermediate[1]))
    assert all(point is not None for point in intermediate)
    normalized_raw_sum = curve.add(intermediate[2], normalized_points[4])
    assert normalized_raw_sum is not None
    original_raw_sum = curve.frob(normalized_raw_sum, powers[0])
    public = curve.mul(original_raw_sum, 4)
    assert public is not None and curve.mul(public, order) is None
    kernel, _, _ = kernel_of_cofactor(curve, onb, order, 4, 141783)
    raw_targets, _ = raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    rotated_targets, target_xs = normalized_target_coset(
        onb, curve, public, raw_targets)
    choice = target_xs.index(onb.toCoords(normalized_raw_sum[0]))
    assert choice // 4 == normalizing_power
    formula, leaves, target_selector = build_affine_formula(
        14, offset, basis, target_xs, onb)
    for index in range(5):
        pin(formula, formula.orbit_seed_bits[index], coefficients[index])
        if index:
            for power, literal in enumerate(formula.orbit_selectors[index]):
                formula.clauses.append([literal if power ==
                                        relative_powers[index] else -literal])
        pin(formula, leaves[index], normalized_leaf_xs[index])
    for bits, point in zip(formula.intermediates, intermediate):
        pin(formula, bits, onb.toCoords(point[0]))
    pin(formula, formula.target_x_bits, onb.toCoords(normalized_raw_sum[0]))
    pin(formula, target_selector, choice)
    xcnf = HERE / "locked_control.xcnf"
    assert not xcnf.exists() and not Path(str(xcnf) + ".gz").exists()
    formula.write(xcnf)
    binary = Path(protocol["solver"]["path"])
    assert sha(binary) == protocol["solver"]["sha256"]
    native = solve_limited(xcnf, binary, 60,
                           protocol["solver"]["max_conflicts"],
                           protocol["limits"]["sampled_solver_rss_stop_bytes"])
    stdout = HERE / "locked_control.stdout.txt"
    stderr = HERE / "locked_control.stderr.txt"
    stdout.write_text(native["stdout"])
    stderr.write_text(native["stderr"])
    replay = None
    if native["model"] is not None:
        model = dict(native["model"])
        model[1] = True
        replay = replay_normalized(
            onb, curve, order, base_keys, public, offset, basis, raw_targets,
            rotated_targets, leaves, target_selector, model)
    receipt = {
        "kind": "n83_rectangle14_normalized_locked_five_point_control",
        "status": "PASS" if replay is not None and replay["status"] ==
                  "verified_five_point_relation" else "FAIL",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "dimension": 14,
        "seed_x": seeds,
        "seed_coefficients": coefficients,
        "frobenius_powers": powers,
        "raw_leaf_x": leaf_xs,
        "normalized_raw_leaf_x": normalized_leaf_xs,
        "normalizing_frobenius_power": normalizing_power,
        "target_choice": choice,
        "public_point_onb_raw": [str(value) for value in public],
        "formula_shape": stats(formula),
        "solver_status": native["status"],
        "solver_wall_seconds": native["wall_seconds"],
        "observed_peak_solver_rss_bytes": native[
            "observed_peak_solver_rss_bytes"],
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "replay": replay,
        **archive_formula(xcnf),
    }
    save(output, receipt)
    print(json.dumps({"status": receipt["status"],
                      "solver_status": native["status"],
                      "replay_status": None if replay is None else replay["status"]}),
          flush=True)
    assert receipt["status"] == "PASS"


if __name__ == "__main__":
    main()
