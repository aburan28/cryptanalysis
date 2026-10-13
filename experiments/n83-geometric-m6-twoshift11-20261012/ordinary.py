#!/usr/bin/env python3
"""Run valid-seed six-summand decomposition on the public N83 point."""

import hashlib
import json
import resource
import time
from itertools import product
from pathlib import Path

from m6 import DIMENSION, HERE, N, OFFSET, build, in_rotated_affine_seed, runner, selfcheck


def coordinate(bits, model):
    return sum(1 << bit for bit, literal in enumerate(bits)
               if (model.get(literal, False) if literal > 0 else
                   not model.get(-literal, False)))


def replay(onb, curve, order, public, raw_target, leaves, model, base_x_keys):
    raw_xs = [coordinate(bits, model) for bits in leaves]
    if any(not in_rotated_affine_seed(onb, x)
           for x in raw_xs):
        return {"status": "outside_rotated_affine_x_subspace",
                "raw_leaf_x": raw_xs}
    points = [curve.pointFromX(onb.fromCoords(x)) for x in raw_xs]
    if any(point is None for point in points):
        return {"status": "nonrational_leaf_x", "raw_leaf_x": raw_xs}
    for signs in product((1, -1), repeat=6):
        signed = [point if sign == 1 else curve.neg(point)
                  for point, sign in zip(points, signs)]
        total = None
        for point in signed:
            total = curve.add(total, point)
        if total != raw_target:
            continue
        projected = [curve.mul(point, 4) for point in signed]
        if any(point is None for point in projected):
            return {"status": "projected_identity", "raw_leaf_x": raw_xs}
        if any(curve.mul(point, order) is not None for point in projected):
            return {"status": "outside_subgroup", "raw_leaf_x": raw_xs}
        columns = [runner.canonical_projected_x(onb, point, N)
                   for point in projected]
        if any(key not in base_x_keys for key in columns):
            return {"status": "outside_exact_base", "raw_leaf_x": raw_xs,
                    "column_keys": columns}
        public_replay = None
        for point in projected:
            public_replay = curve.add(public_replay, point)
        assert public_replay == public
        return {
            "status": "verified_six_point_relation",
            "raw_leaf_x": raw_xs, "signs": list(signs),
            "raw_leaf_points": [[str(value) for value in point]
                                for point in points],
            "raw_target": [str(value) for value in raw_target],
            "projected_points": [[str(value) for value in point]
                                 for point in projected],
            "column_keys": columns,
            "distinct_columns": len(set(columns)),
            "public_target": [str(value) for value in public],
        }
    return {"status": "no_sign_lift", "raw_leaf_x": raw_xs}


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101268"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["point_decomposition_summands"] == 6
    assert protocol["fixed_target_choice"] == 0
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(runner.ROOT / relative) == digest, relative
    binary = Path(protocol["solver"]["path"])
    assert runner.sha(binary) == protocol["solver"]["sha256"]
    row = protocol["base_rows"][0]
    assert row["dimension"] == DIMENSION and row["offset_onb_coordinates"] == OFFSET
    base = runner.ROOT / row["base_file"]
    cache = runner.ROOT / row["canonical_x_cache_file"]
    assert runner.sha(base) == row["base_sha256"]
    assert runner.sha(cache) == row["canonical_x_cache_sha256"]
    cache_bytes = cache.read_bytes()
    assert len(cache_bytes) == 11 * row["K"]
    base_x_keys = {int.from_bytes(cache_bytes[i:i + 11], "little")
                   for i in range(0, len(cache_bytes), 11)}
    assert len(base_x_keys) == row["K"]
    onb = runner.field.Onb(N)
    arithmetic = selfcheck(onb)
    curve = runner.curves.Curve(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    setup_start = time.perf_counter_ns()
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    setup_ns = time.perf_counter_ns() - setup_start
    assert len(kernel) == 4

    online_start = time.perf_counter_ns()
    preimage_start = time.perf_counter_ns()
    raw_targets, _ = runner.raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    raw_target = raw_targets[0]
    target_x = onb.toCoords(raw_target[0])
    preimage_ns = time.perf_counter_ns() - preimage_start
    assert target_x == protocol["target_x_onb"]
    formula_start = time.perf_counter_ns()
    formula, leaves, intermediates, _ = build(onb, target_x)
    formula_ns = time.perf_counter_ns() - formula_start
    shape = runner.stats(formula)
    assert shape == protocol["formula_shape"]
    deadline = online_start + int(protocol["limits"]["wall_seconds_per_base"] * 1e9)
    attempts = []
    relation = None
    for index in range(protocol["limits"]["max_models_per_base"]):
        if time.perf_counter_ns() >= deadline:
            break
        xcnf = HERE / f"width11_m6.attempt{index}.xcnf"
        assert not xcnf.exists() and not Path(str(xcnf) + ".gz").exists()
        write_start = time.perf_counter_ns()
        formula.write(xcnf)
        write_ns = time.perf_counter_ns() - write_start
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            native = {"status": "no_solver_budget", "return_code": None,
                      "wall_seconds": 0.0, "conflicts_reported": None,
                      "observed_peak_solver_rss_bytes": None,
                      "rss_sample_interval_ms": 50, "command": None,
                      "stdout": "", "stderr": "", "model": None}
        else:
            native = runner.solve_limited(
                xcnf, binary, remaining,
                protocol["solver"]["max_conflicts"],
                protocol["limits"]["sampled_solver_rss_stop_bytes"])
        check_start = time.perf_counter_ns()
        replay_row = None
        if native["model"] is not None:
            model = dict(native["model"])
            model[1] = True
            replay_row = replay(onb, curve, order, public, raw_target,
                                leaves, model, base_x_keys)
            if replay_row["status"] == "verified_six_point_relation":
                relation = replay_row
            elif index + 1 < protocol["limits"]["max_models_per_base"]:
                block = [-bit if model.get(bit, False) else bit
                         for leaf in leaves for bit in leaf if bit > 1]
                formula.clauses.append(block)
        check_ns = time.perf_counter_ns() - check_start
        stdout = HERE / f"width11_m6.attempt{index}.stdout.txt"
        stderr = HERE / f"width11_m6.attempt{index}.stderr.txt"
        stdout.write_text(native["stdout"])
        stderr.write_text(native["stderr"])
        attempts.append({
            "index": index, "status": native["status"],
            "return_code": native["return_code"],
            "solver_command": native["command"],
            "solver_wall_seconds": native["wall_seconds"],
            "conflicts_reported": native["conflicts_reported"],
            "observed_peak_solver_rss_bytes": native["observed_peak_solver_rss_bytes"],
            "rss_sample_interval_ms": native["rss_sample_interval_ms"],
            "formula_write_ns": write_ns, "relation_check_ns": check_ns,
            "model_present": native["model"] is not None,
            "replay": replay_row,
            "stdout_file": stdout.name, "stdout_sha256": runner.sha(stdout),
            "stderr_file": stderr.name, "stderr_sha256": runner.sha(stderr),
            **runner.archive_formula(xcnf),
        })
        if relation is not None or native["model"] is None:
            break
    online_ns = time.perf_counter_ns() - online_start
    phases = {
        "target_preimages": preimage_ns, "formula_build": formula_ns,
        "formula_write": sum(a["formula_write_ns"] for a in attempts),
        "solver": sum(int(a["solver_wall_seconds"] * 1e9) for a in attempts),
        "relation_check": sum(a["relation_check_ns"] for a in attempts),
    }
    phases["target_dependent_overhead"] = max(0, online_ns - sum(phases.values()))
    if relation is not None:
        status = "verified_relation"
    elif attempts and attempts[-1]["status"] == "unsat":
        status = "restricted_slice_unsat"
    elif attempts and attempts[-1]["model_present"]:
        status = "invalid_models_cap"
    else:
        status = "bounded_unknown"
    output = HERE / "width11_m6_ordinary.json"
    assert not output.exists()
    record = {
        "kind": "n83_two_shift_width11_six_summand_valid_seed_stage",
        "status": status, "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"], "target_count": 1,
        "dimension": DIMENSION, "offset_onb_coordinates": OFFSET,
        "B": row["B"], "K": row["K"],
        "base_sha256": row["base_sha256"],
        "canonical_x_cache_sha256": row["canonical_x_cache_sha256"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "raw_target_preimage_count": len(raw_targets),
        "formula_target_choice": 0, "formula_target_x": target_x,
        "formula_shape": shape, "attempts": attempts,
        "verified_relation": relation,
        "online_pdp_wall_ns_exploratory": online_ns,
        "online_pdp_phase_ns": phases,
        "target_independent_kernel_setup_ns": setup_ns,
        "timing_tier": protocol["timing_tier"],
        "peak_runner_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": runner.sha(protocol_path),
        "runner_sha256": runner.sha(Path(__file__)),
        "m6_source_sha256": runner.sha(HERE / "m6.py"),
        "field_multiplier_selfcheck": arithmetic,
    }
    runner.save(output, record)
    print(json.dumps({"status": status,
                      "attempts": [a["status"] for a in attempts],
                      "online_pdp_seconds": online_ns / 1e9}), flush=True)


if __name__ == "__main__":
    main()
