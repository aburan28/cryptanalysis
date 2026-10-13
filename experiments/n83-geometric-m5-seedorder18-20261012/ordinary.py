#!/usr/bin/env python3
"""Measure seed-ordered N83 target decomposition on the frozen Q54 point."""

import json
import time
from pathlib import Path

from ordered import HERE, N, build, runner, selfcheck


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101265"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["fixed_target_choice"] == 0
    for relative, digest in protocol["source_sha256"].items():
        assert runner.sha(runner.ROOT / relative) == digest, relative
    assert runner.sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    onb = runner.field.Onb(N)
    correctness = selfcheck(onb)
    curve = runner.curves.Curve(onb)
    orbit = runner.OrbitKey(onb)
    order = protocol["workload"]["subgroup_order"]
    public = tuple(protocol["workload"]["public_point_onb_raw"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    row = protocol["base_rows"][0]
    assert row["dimension"] == 18
    setup_started = time.perf_counter_ns()
    kernel, _, _ = runner.kernel_of_cofactor(curve, onb, order, 4, 141783)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(kernel) == 4
    parent_here = runner.HERE
    parent_builder = runner.build_affine_formula

    def ordered_builder(dimension, offset, target_xs, field, target_choice=0):
        assert dimension == 18 and offset == 1 << 81
        assert target_choice == 0 and len(target_xs) == 332
        runner.build_affine_formula = parent_builder
        try:
            return build(field, target_xs[0], target_choice)[:3]
        finally:
            runner.build_affine_formula = ordered_builder

    runner.HERE = HERE
    runner.build_affine_formula = ordered_builder
    try:
        runner.one_base(protocol, row, onb, curve, order, public, kernel, orbit)
    finally:
        runner.HERE = parent_here
        runner.build_affine_formula = parent_builder
    output = HERE / "width18_ordinary.json"
    result = json.loads(output.read_text())
    result["kind"] = "n83_width18_seed_ordered_free_leaves_five_summand_stage"
    result["runner_sha256"] = runner.sha(Path(__file__))
    result["ordered_source_sha256"] = runner.sha(HERE / "ordered.py")
    result["field_multiplier_selfcheck"] = correctness
    runner.save(output, result)
    runner.save(HERE / "run_summary.json", {
        "kind": "n83_width18_seed_ordered_free_leaves_stage_summary",
        "protocol_sha256": runner.sha(protocol_path),
        "target_independent_kernel_setup_ns": setup_ns,
        "run_order": [18],
        "result_sha256": {"18": runner.sha(output)},
    })


if __name__ == "__main__":
    main()
