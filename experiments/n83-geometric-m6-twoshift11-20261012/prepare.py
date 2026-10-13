#!/usr/bin/env python3
"""Freeze Q68 on the exact two-coordinate width-11 N83 base."""

import json
import math
from decimal import Decimal, getcontext
from pathlib import Path

from m6 import DIMENSION, HERE, OFFSET, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists(), "refusing to overwrite a frozen protocol"
    paired = HERE.parent / "n83-geometric-m6-validseed11-20261012"
    paired_protocol = paired / "protocol.json"
    paired_result = paired / "width11_m6_ordinary.json"
    prior = json.loads(paired_protocol.read_text())
    assert prior["proposal_id"] == "Q2026101267"
    assert prior["workload_id"] == "df4396f4d8fc"
    assert json.loads(paired_result.read_text())["status"] == "bounded_unknown"
    geometry = runner.ROOT / "experiments/n83-geometric-two-shift11-20261012"
    geometry_path = geometry / "screen.json"
    replay_path = geometry / "independent_sage_replay.json"
    screen = json.loads(geometry_path.read_text())
    replay = json.loads(replay_path.read_text())
    assert screen["status"] == "complete_geometry_screen"
    assert replay["status"] == "PASS"
    assert screen["best_shift_coordinates"] == [26, 38]
    assert screen["best_K"] == 1109 and screen["best_B"] == 184094
    assert OFFSET == (1 << 26) | (1 << 38) and DIMENSION == 11
    base_path = geometry / screen["best_key_file"]
    assert runner.sha(base_path) == screen["best_key_sha256"]
    materialization_path = HERE / "materialization.json"
    materialization = json.loads(materialization_path.read_text())
    assert materialization["status"] == "PASS"
    assert materialization["K"] == screen["best_K"]
    cache_path = HERE / materialization["canonical_x_file"]
    assert runner.sha(cache_path) == materialization["canonical_x_sha256"]
    control_path = HERE / "six_point_control.json"
    shape_path = HERE / "shape.json"
    control = json.loads(control_path.read_text())
    shape = json.loads(shape_path.read_text())
    assert control["status"] == shape["status"] == "PASS"
    assert control["m6_source_sha256"] == shape["m6_source_sha256"] == runner.sha(HERE / "m6.py")
    assert shape["workload_id"] == prior["workload_id"]
    assert shape["target_choice"] == 0
    valid_path = HERE / "valid_seeds.json"
    valid = json.loads(valid_path.read_text())
    assert valid["status"] == "PASS"
    assert valid["valid_seed_count"] == 1109
    bitset_path = HERE / valid["bitset_file"]
    assert runner.sha(bitset_path) == valid["bitset_sha256"]
    assert len(bitset_path.read_bytes()) == 256
    getcontext().prec = 50
    B = screen["best_B"]
    r = prior["workload"]["subgroup_order"]
    moment = Decimal(math.comb(B, 6)) / Decimal(r)
    base_row = {
        "dimension": DIMENSION, "offset_onb_coordinates": OFFSET,
        "K": screen["best_K"], "B": B,
        "base_file": str(base_path.relative_to(runner.ROOT)),
        "base_sha256": runner.sha(base_path),
        "canonical_x_cache_file": str(cache_path.relative_to(runner.ROOT)),
        "canonical_x_cache_sha256": runner.sha(cache_path),
        "six_subset_uniform_target_first_moment": str(moment),
    }
    sources = dict(prior["source_sha256"])
    for path in (HERE / "m6.py", HERE / "materialize.py", HERE / "shape.py",
                 HERE / "valid_seeds.py", HERE / "control.py", HERE / "ordinary.py",
                 Path(__file__)):
        sources[str(path.relative_to(runner.ROOT))] = runner.sha(path)
    protocol = {
        **prior,
        "kind": "n83_two_shift_width11_six_summand_stage_v1",
        "proposal_id": "Q2026101268", "candidate_id": None,
        "comparison_variable": "width-11 affine offset bits 26+38 versus bit 81 on the same public point and solver",
        "method_comparison_parent": "Q2026101267 exact valid-seed six-summand stage",
        "point_decomposition_summands": 6,
        "base_rows": [base_row],
        "target_policy": "fixed first raw cofactor preimage, no target Frobenius rotation in this stage",
        "fixed_target_choice": 0,
        "target_x_onb": shape["target_x_onb"],
        "formula_shape": shape["formula_shape"],
        "valid_seed_bitset_sha256": runner.sha(bitset_path),
        "valid_seeds_receipt_sha256": runner.sha(valid_path),
        "paired_q67_protocol_sha256": runner.sha(paired_protocol),
        "paired_q67_result_sha256": runner.sha(paired_result),
        "two_shift_geometry_sha256": runner.sha(geometry_path),
        "two_shift_replay_sha256": runner.sha(replay_path),
        "cache_materialization_sha256": runner.sha(materialization_path),
        "control_sha256": runner.sha(control_path),
        "shape_sha256": runner.sha(shape_path),
        "source_sha256": sources,
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": B, "K": base_row["K"],
                      "six_subset_first_moment": str(moment)}), flush=True)


if __name__ == "__main__":
    main()
