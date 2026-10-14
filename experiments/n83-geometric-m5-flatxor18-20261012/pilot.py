#!/usr/bin/env python3
"""Paired equal-conflict pilot for materialized and flattened XOR circuits."""

import json
import resource
import time
from pathlib import Path

from flat_karatsuba import HERE, PARENT, build, runner, selfcheck
from karatsuba import build as pairwise_build


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101257"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert not (HERE / "pilot_result.json").exists()
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(runner.ROOT / relative) == digest, relative
    solver = Path(protocol["solver"]["path"])
    assert runner.sha(solver) == protocol["solver"]["sha256"]
    parent_result = json.loads((PARENT / "width18_ordinary.json").read_text())
    target_x = parent_result["formula_target_x"]
    onb = runner.field.Onb(83)
    curve = runner.curves.Curve(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    field_selfcheck = selfcheck(onb)
    pair_formula, pair_leaves, pair_selector, _ = pairwise_build(onb, target_x)
    flat_formula, flat_leaves, flat_selector, _ = build(onb, target_x)
    assert runner.stats(pair_formula) == parent_result["formula_shape"]
    assert runner.stats(flat_formula)["and_gates"] == 12174
    paths = {"pairwise": HERE / "pairwise.xcnf",
             "flattened": HERE / "flattened.xcnf"}
    for variant, formula in (("pairwise", pair_formula),
                             ("flattened", flat_formula)):
        path = paths[variant]
        assert not path.exists() and not Path(str(path) + ".gz").exists()
        formula.write(path)
    parent_attempt = parent_result["attempts"][0]
    assert runner.sha(paths["pairwise"]) == parent_attempt["xcnf_raw_sha256"]
    assert parent_attempt["xcnf_gzip_sha256"] == runner.sha(
        PARENT / parent_attempt["xcnf_gzip"])
    binary_inputs = {variant: {"raw_sha256": runner.sha(path),
                               "bytes": path.stat().st_size}
                     for variant, path in paths.items()}
    base_keys = None
    kernel = raw_targets = rotated_targets = None
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
                row = protocol["base_rows"][0]
                base_keys = runner.base_x_keys(row, onb, runner.OrbitKey(onb))
                kernel, _, _ = runner.kernel_of_cofactor(
                    curve, onb, order, 4, 141783)
                raw_targets, _ = runner.raw_preimage_coset(
                    onb, curve, order, 4, public, kernel)
                rotated_targets, target_xs = runner.normalized_target_coset(
                    onb, curve, public, raw_targets)
                assert target_xs[0] == target_x
            model = dict(native["model"])
            model[1] = True
            leaves = pair_leaves if variant == "pairwise" else flat_leaves
            selector = pair_selector if variant == "pairwise" else flat_selector
            replay = runner.replay_normalized(
                onb, curve, order, 18, base_keys, public, raw_targets,
                rotated_targets, leaves, selector, model)
            if replay["status"] == "verified_five_point_relation":
                relation = replay
        stdout = HERE / f"arm{index}_{variant}.stdout.txt"
        stderr = HERE / f"arm{index}_{variant}.stderr.txt"
        stdout.write_text(native["stdout"])
        stderr.write_text(native["stderr"])
        arms.append({
            "index": index, "variant": variant,
            "status": native["status"],
            "return_code": native["return_code"],
            "solver_command": native["command"],
            "solver_wall_seconds": native["wall_seconds"],
            "conflicts_reported": native["conflicts_reported"],
            "observed_peak_solver_rss_bytes": native[
                "observed_peak_solver_rss_bytes"],
            "rss_sample_interval_ms": native["rss_sample_interval_ms"],
            "model_present": native["model"] is not None,
            "replay": replay,
            "stdout_file": stdout.name,
            "stdout_sha256": runner.sha(stdout),
            "stderr_file": stderr.name,
            "stderr_sha256": runner.sha(stderr),
        })
        print(json.dumps({"arm": index, "variant": variant,
                          "status": native["status"],
                          "seconds": native["wall_seconds"],
                          "conflicts": native["conflicts_reported"]}),
              flush=True)
        if relation is not None:
            break
    wall_ns = time.perf_counter_ns() - started
    archived = {variant: runner.archive_formula(path)
                for variant, path in paths.items()}
    result = {
        "kind": "n83_width18_flattened_xor_equal_conflict_pilot",
        "status": "verified_relation" if relation is not None else "bounded_unknown",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "B": protocol["base_rows"][0]["B"],
        "K": protocol["base_rows"][0]["K"],
        "target_choice": 0,
        "target_x": target_x,
        "run_order": protocol["run_order"],
        "shapes": {"pairwise": runner.stats(pair_formula),
                   "flattened": runner.stats(flat_formula)},
        "formula_inputs": {variant: {**binary_inputs[variant],
                                     **archived[variant]}
                           for variant in paths},
        "arms": arms,
        "verified_relation": relation,
        "paired_pilot_wall_ns_exploratory": wall_ns,
        "field_selfcheck": field_selfcheck,
        "peak_runner_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": runner.sha(protocol_path),
        "runner_sha256": runner.sha(Path(__file__)),
    }
    runner.save(HERE / "pilot_result.json", result)
    print(json.dumps({"status": result["status"],
                      "arms": len(arms), "wall_seconds": wall_ns / 1e9}),
          flush=True)


if __name__ == "__main__":
    main()
