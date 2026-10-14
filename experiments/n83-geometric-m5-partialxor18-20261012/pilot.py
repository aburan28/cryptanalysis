#!/usr/bin/env python3
"""Paired one-million-conflict pilot for the partial XOR circuit."""

import json
import resource
import time
from pathlib import Path

from partial import HERE, build, flat
from karatsuba import build as pairwise_build


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101259"
    assert not (HERE / "pilot_result.json").exists()
    runner = flat.runner
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(runner.ROOT / relative) == digest, relative
    solver = Path(protocol["solver"]["path"])
    assert runner.sha(solver) == protocol["solver"]["sha256"]
    parent = json.loads((flat.PARENT / "width18_ordinary.json").read_text())
    target_x = parent["formula_target_x"]
    onb = runner.field.Onb(83)
    curve = runner.curves.Curve(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    pair_formula, pair_leaves, pair_selector, _ = pairwise_build(onb, target_x)
    part_formula, part_leaves, part_selector, _ = build(onb, target_x, 21)
    assert runner.stats(pair_formula) == parent["formula_shape"]
    expected = next(row["shape"] for row in
                    json.loads((HERE / "shape_screen.json").read_text())["rows"]
                    if row["cutoff"] == 21)
    assert runner.stats(part_formula) == expected
    formulas = {"pairwise": pair_formula, "partial21": part_formula}
    leaves = {"pairwise": pair_leaves, "partial21": part_leaves}
    selectors = {"pairwise": pair_selector, "partial21": part_selector}
    paths = {variant: HERE / f"{variant}.xcnf" for variant in formulas}
    for variant, formula in formulas.items():
        path = paths[variant]
        assert not path.exists() and not Path(str(path) + ".gz").exists()
        formula.write(path)
    assert runner.sha(paths["pairwise"]) == parent["attempts"][0][
        "xcnf_raw_sha256"]
    raw = {variant: {"raw_sha256": runner.sha(path),
                     "bytes": path.stat().st_size}
           for variant, path in paths.items()}
    base_keys = kernel = raw_targets = rotated_targets = None
    arms = []
    relation = None
    started = time.perf_counter_ns()
    for index, variant in enumerate(protocol["run_order"]):
        native = runner.solve_limited(
            paths[variant], solver,
            protocol["limits"]["wall_seconds_per_arm"],
            protocol["solver"]["max_conflicts"],
            protocol["limits"]["sampled_solver_rss_stop_bytes"])
        replay = None
        if native["model"] is not None:
            if base_keys is None:
                base_keys = runner.base_x_keys(
                    protocol["base_rows"][0], onb, runner.OrbitKey(onb))
                kernel, _, _ = runner.kernel_of_cofactor(
                    curve, onb, order, 4, 141783)
                raw_targets, _ = runner.raw_preimage_coset(
                    onb, curve, order, 4, public, kernel)
                rotated_targets, target_xs = runner.normalized_target_coset(
                    onb, curve, public, raw_targets)
                assert target_xs[0] == target_x
            model = dict(native["model"])
            model[1] = True
            replay = runner.replay_normalized(
                onb, curve, order, 18, base_keys, public, raw_targets,
                rotated_targets, leaves[variant], selectors[variant], model)
            if replay["status"] == "verified_five_point_relation":
                relation = replay
        stdout = HERE / f"arm{index}_{variant}.stdout.txt"
        stderr = HERE / f"arm{index}_{variant}.stderr.txt"
        stdout.write_text(native["stdout"])
        stderr.write_text(native["stderr"])
        arms.append({"index": index, "variant": variant,
                     "status": native["status"],
                     "return_code": native["return_code"],
                     "solver_wall_seconds": native["wall_seconds"],
                     "conflicts_reported": native["conflicts_reported"],
                     "observed_peak_solver_rss_bytes": native[
                         "observed_peak_solver_rss_bytes"],
                     "model_present": native["model"] is not None,
                     "replay": replay,
                     "stdout_file": stdout.name,
                     "stdout_sha256": runner.sha(stdout),
                     "stderr_file": stderr.name,
                     "stderr_sha256": runner.sha(stderr)})
        print(json.dumps({"arm": index, "variant": variant,
                          "status": native["status"],
                          "seconds": native["wall_seconds"],
                          "conflicts": native["conflicts_reported"]}),
              flush=True)
        if relation is not None:
            break
    archived = {variant: runner.archive_formula(path)
                for variant, path in paths.items()}
    result = {
        "kind": "n83_width18_partial_xor_equal_conflict_pilot",
        "status": "verified_relation" if relation is not None else "bounded_unknown",
        "proposal_id": protocol["proposal_id"], "candidate_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "B": protocol["base_rows"][0]["B"],
        "K": protocol["base_rows"][0]["K"],
        "target_choice": 0, "target_x": target_x,
        "run_order": protocol["run_order"],
        "shapes": {v: runner.stats(f) for v, f in formulas.items()},
        "formula_inputs": {v: {**raw[v], **archived[v]} for v in paths},
        "arms": arms, "verified_relation": relation,
        "paired_pilot_wall_ns_exploratory": time.perf_counter_ns() - started,
        "peak_runner_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": runner.sha(protocol_path),
        "runner_sha256": runner.sha(Path(__file__)),
    }
    runner.save(HERE / "pilot_result.json", result)
    print(json.dumps({"status": result["status"], "arms": len(arms)}),
          flush=True)


if __name__ == "__main__":
    main()
