#!/usr/bin/env python3
"""ABBA equal-conflict pilot for one admitted CryptoMiniSat XOR matrix."""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(PARENT))
import base_run as runner  # noqa: E402
from karatsuba import build  # noqa: E402


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101262"
    assert not (HERE / "pilot_result.json").exists()
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(ROOT / relative) == digest, relative
    formula_path = HERE / "width18.xcnf"
    assert runner.sha(formula_path) == protocol["formula_raw_sha256"]
    parent = json.loads((PARENT / "width18_ordinary.json").read_text())
    assert runner.sha(PARENT / "width18_ordinary.json") == protocol[
        "parent_result_sha256"]
    assert parent["attempts"][0]["xcnf_raw_sha256"] == protocol[
        "formula_raw_sha256"]
    binaries = {name: Path(config["path"])
                for name, config in protocol["solvers"].items()}
    for name, path in binaries.items():
        assert runner.sha(path) == protocol["solvers"][name]["sha256"]
    onb = runner.field.Onb(83)
    curve = runner.curves.Curve(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    # Rebuild only to bind any returned model to its exact literals.
    formula, leaves, selector, _ = build(onb, parent["formula_target_x"])
    check_path = HERE / "rebuild_check.xcnf"
    assert not check_path.exists()
    formula.write(check_path)
    assert runner.sha(check_path) == protocol["formula_raw_sha256"]
    check_path.unlink()
    base_keys = raw_targets = rotated_targets = None
    arms = []
    relation = None
    started = time.perf_counter_ns()
    for index, variant in enumerate(protocol["run_order"]):
        native = runner.solve_limited(
            formula_path, binaries[variant],
            protocol["limits"]["wall_seconds_per_arm"],
            protocol["max_conflicts"],
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
                assert target_xs[0] == parent["formula_target_x"]
            model = dict(native["model"])
            model[1] = True
            replay = runner.replay_normalized(
                onb, curve, order, 18, base_keys, public, raw_targets,
                rotated_targets, leaves, selector, model)
            if replay["status"] == "verified_five_point_relation":
                relation = replay
        stdout = HERE / f"arm{index}_{variant}.stdout.txt"
        stderr = HERE / f"arm{index}_{variant}.stderr.txt"
        stdout.write_text(native["stdout"])
        stderr.write_text(native["stderr"])
        arms.append({"index": index, "variant": variant,
                     "status": native["status"],
                     "return_code": native["return_code"],
                     "command": native["command"],
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
    result = {
        "kind": "n83_width18_one_gauss_matrix_equal_conflict_pilot",
        "status": "verified_relation" if relation is not None else "bounded_unknown",
        "proposal_id": protocol["proposal_id"], "candidate_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "B": protocol["base_rows"][0]["B"],
        "K": protocol["base_rows"][0]["K"],
        "run_order": protocol["run_order"], "arms": arms,
        "verified_relation": relation,
        "paired_pilot_wall_ns_exploratory": time.perf_counter_ns() - started,
        "formula_raw_sha256": runner.sha(formula_path),
        "protocol_sha256": runner.sha(protocol_path),
        "runner_sha256": runner.sha(Path(__file__)),
    }
    runner.save(HERE / "pilot_result.json", result)
    print(json.dumps({"status": result["status"], "arms": len(arms)}),
          flush=True)


if __name__ == "__main__":
    main()
