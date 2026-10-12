#!/usr/bin/env python3
"""Try frozen raw-target slices of one public N83 point on the width-18 base."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(SOURCE))
from karatsuba import build, runner, selfcheck  # noqa: E402


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101255"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert not (HERE / "portfolio_ordinary.json").exists()
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(ROOT / relative) == digest, relative
    solver = Path(protocol["solver"]["path"])
    assert runner.sha(solver) == protocol["solver"]["sha256"]
    onb = runner.field.Onb(83)
    curve = runner.curves.Curve(onb)
    orbit = runner.OrbitKey(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    row = protocol["base_rows"][0]
    assert row["dimension"] == 18
    base_keys = runner.base_x_keys(row, onb, orbit)
    selfcheck_result = selfcheck(onb)
    setup_started = time.perf_counter_ns()
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(kernel) == 4
    started = time.perf_counter_ns()
    deadline = started + int(protocol["limits"]["total_wall_seconds"] * 1e9)
    preimage_started = time.perf_counter_ns()
    raw_targets, _ = runner.raw_preimage_coset(
        onb, curve, order, 4, public, kernel)
    rotated_targets, target_xs = runner.normalized_target_coset(
        onb, curve, public, raw_targets)
    preimage_ns = time.perf_counter_ns() - preimage_started
    attempts = []
    relation = None
    for choice in protocol["target_choices"]:
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        if remaining <= 0:
            break
        formula_started = time.perf_counter_ns()
        formula, leaves, selector, _ = build(onb, target_xs[choice], choice)
        formula_ns = time.perf_counter_ns() - formula_started
        shape = runner.stats(formula)
        path = HERE / f"choice{choice}.xcnf"
        assert not path.exists() and not Path(str(path) + ".gz").exists()
        write_started = time.perf_counter_ns()
        formula.write(path)
        write_ns = time.perf_counter_ns() - write_started
        remaining = (deadline - time.perf_counter_ns()) / 1e9
        limit = min(protocol["limits"]["per_choice_wall_seconds"], remaining)
        if limit <= 0:
            native = {"status": "no_solver_budget", "return_code": None,
                      "wall_seconds": 0.0, "conflicts_reported": None,
                      "observed_peak_solver_rss_bytes": None,
                      "rss_sample_interval_ms": 50, "command": None,
                      "stdout": "", "stderr": "", "model": None}
        else:
            native = runner.solve_limited(
                path, solver, limit, protocol["solver"]["max_conflicts"],
                protocol["limits"]["sampled_solver_rss_stop_bytes"])
        check_started = time.perf_counter_ns()
        replay = None
        if native["model"] is not None:
            model = dict(native["model"])
            model[1] = True
            replay = runner.replay_normalized(
                onb, curve, order, 18, base_keys, public, raw_targets,
                rotated_targets, leaves, selector, model)
            if "raw_leaf_x" in replay and any(
                not runner.in_rotated_affine_seed(onb, x, 18)
                for x in replay["raw_leaf_x"]
            ):
                replay = {"status": "outside_rotated_affine_x_subspace",
                          "raw_leaf_x": replay["raw_leaf_x"]}
            if replay["status"] == "verified_five_point_relation":
                relation = replay
        check_ns = time.perf_counter_ns() - check_started
        stdout = HERE / f"choice{choice}.stdout.txt"
        stderr = HERE / f"choice{choice}.stderr.txt"
        stdout.write_text(native["stdout"])
        stderr.write_text(native["stderr"])
        archived = runner.archive_formula(path)
        attempt = {
            "choice": choice,
            "target_x": target_xs[choice],
            "status": native["status"],
            "return_code": native["return_code"],
            "solver_command": native["command"],
            "solver_wall_seconds": native["wall_seconds"],
            "conflicts_reported": native["conflicts_reported"],
            "observed_peak_solver_rss_bytes": native[
                "observed_peak_solver_rss_bytes"],
            "rss_sample_interval_ms": native["rss_sample_interval_ms"],
            "formula_shape": shape,
            "formula_build_ns": formula_ns,
            "formula_write_ns": write_ns,
            "relation_check_ns": check_ns,
            "model_present": native["model"] is not None,
            "replay": replay,
            "stdout_file": stdout.name,
            "stdout_sha256": runner.sha(stdout),
            "stderr_file": stderr.name,
            "stderr_sha256": runner.sha(stderr),
            **archived,
        }
        attempts.append(attempt)
        print(json.dumps({"choice": choice, "status": native["status"],
                          "solver_seconds": native["wall_seconds"],
                          "relation": relation is not None}), flush=True)
        if relation is not None:
            break
    online_ns = time.perf_counter_ns() - started
    phases = {
        "target_preimages": preimage_ns,
        "formula_build": sum(a["formula_build_ns"] for a in attempts),
        "formula_write": sum(a["formula_write_ns"] for a in attempts),
        "solver": sum(int(a["solver_wall_seconds"] * 1e9) for a in attempts),
        "relation_check": sum(a["relation_check_ns"] for a in attempts),
    }
    phases["target_dependent_overhead"] = max(0, online_ns - sum(phases.values()))
    result = {
        "kind": "n83_width18_fixed_raw_target_choice_portfolio_stage",
        "status": "verified_relation" if relation is not None else "bounded_unknown",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "public_point_onb_raw": protocol["workload"]["public_point_onb_raw"],
        "B": row["B"], "K": row["K"],
        "base_sha256": row["base_sha256"],
        "canonical_x_cache_sha256": row["canonical_x_cache_sha256"],
        "target_choices_planned": protocol["target_choices"],
        "target_choices_attempted": [a["choice"] for a in attempts],
        "raw_target_preimage_count": len(rotated_targets),
        "raw_target_x_sha256": hashlib.sha256(b"".join(
            x.to_bytes(11, "little") for x in target_xs)).hexdigest(),
        "attempts": attempts,
        "verified_relation": relation,
        "online_pdp_wall_ns_exploratory": online_ns,
        "online_pdp_phase_ns": phases,
        "target_independent_kernel_setup_ns": setup_ns,
        "field_multiplier_selfcheck": selfcheck_result,
        "peak_runner_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "timing_tier": protocol["timing_tier"],
        "protocol_sha256": runner.sha(protocol_path),
        "runner_sha256": runner.sha(Path(__file__)),
    }
    output = HERE / "portfolio_ordinary.json"
    runner.save(output, result)
    print(json.dumps({"status": result["status"],
                      "attempted": len(attempts),
                      "online_seconds": online_ns / 1e9}), flush=True)


if __name__ == "__main__":
    main()
