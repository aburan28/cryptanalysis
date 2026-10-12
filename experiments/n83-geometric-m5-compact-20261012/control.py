#!/usr/bin/env python3
"""Locked five-point correctness control for the balanced affine encoding."""

import json
from pathlib import Path

from run import (HERE, archive_formula, base_x_keys, build_affine_formula,
                 curves, field, kernel_of_cofactor, raw_preimage_coset,
                 replay_model, save, sha, solve_limited, stats, OrbitKey)


def main():
    output = HERE / "locked_control.json"
    assert not output.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    row = next(row for row in protocol["base_rows"] if row["dimension"] == 12)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    order = protocol["workload"]["subgroup_order"]
    base_keys = base_x_keys(row, onb, orbit)
    raw_xs, raw_points, columns = [], [], set()
    for low in range(1 << 12):
        x = (1 << 81) | low
        point = curve.pointFromX(onb.fromCoords(x))
        if point is None:
            continue
        projected = curve.mul(point, 4)
        if projected is None:
            continue
        key = min(onb.toCoords(onb.frob(projected[0], i)) for i in range(83))
        if key not in base_keys or key in columns:
            continue
        raw_xs.append(x)
        raw_points.append(point)
        columns.add(key)
        if len(raw_xs) == 5:
            break
    assert len(raw_xs) == len(columns) == 5
    raw_sum = None
    for point in raw_points:
        raw_sum = curve.add(raw_sum, point)
        assert raw_sum is not None
    public = curve.mul(raw_sum, 4)
    assert public is not None and curve.mul(public, order) is None
    kernel, _, _ = kernel_of_cofactor(curve, onb, order, 4, 141783)
    raw_targets, target_xs = raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    choice = target_xs.index(onb.toCoords(raw_sum[0]))
    formula, leaves, selector = build_affine_formula(
        12, row["offset_onb_coordinates"], target_xs, onb)
    for bits, value in zip(leaves, raw_xs):
        for position, literal in enumerate(bits):
            expected = bool((value >> position) & 1)
            if abs(literal) == 1:
                assert (literal == 1) == expected
            else:
                formula.clauses.append([literal if expected else -literal])
    for position, literal in enumerate(selector):
        formula.clauses.append([literal if (choice >> position) & 1 else -literal])
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
        replay = replay_model(onb, curve, order, 4, 83, base_keys, public,
                              raw_targets, leaves, selector, model)
    receipt = {
        "kind": "n83_balanced_folded_locked_five_point_control",
        "status": "PASS" if replay is not None and replay["status"] ==
                  "verified_five_point_relation" else "FAIL",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "dimension": 12,
        "raw_leaf_x": raw_xs,
        "target_choice": choice,
        "public_point_onb_raw": [str(v) for v in public],
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
