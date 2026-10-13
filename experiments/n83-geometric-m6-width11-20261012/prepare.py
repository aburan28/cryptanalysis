#!/usr/bin/env python3
"""Freeze the six-summand width-11 stage on the Q54 public target."""

import json
import math
from decimal import Decimal, getcontext
from pathlib import Path

from m6 import DIMENSION, HERE, OFFSET, PARENT, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    prior_path = PARENT / "protocol.json"
    prior = json.loads(prior_path.read_text())
    assert prior["proposal_id"] == "Q2026101254"
    assert prior["workload_id"] == "df4396f4d8fc"
    width = runner.ROOT / "experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER"
    frontier_path = width / "frontier.json"
    sage_path = width / "independent_sage_replay.json"
    frontier = json.loads(frontier_path.read_text())
    assert frontier["status"] == "complete_geometry_stage"
    assert json.loads(sage_path.read_text())["status"] == "PASS"
    row = next(row for row in frontier["rows"] if row["dimension"] == DIMENSION
               and row["offset_onb_coordinates"] == OFFSET)
    base_path = width / row["canonical_key_file"]
    assert runner.sha(base_path) == row["canonical_key_sha256"]
    materialization_path = HERE / "materialization.json"
    materialization = json.loads(materialization_path.read_text())
    assert materialization["status"] == "PASS"
    assert materialization["K"] == row["folded_columns_K"]
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
    getcontext().prec = 50
    B = row["actual_usable_points_B_before_folding"]
    r = prior["workload"]["subgroup_order"]
    moment = Decimal(math.comb(B, 6)) / Decimal(r)
    base_row = {
        "dimension": DIMENSION, "offset_onb_coordinates": OFFSET,
        "K": row["folded_columns_K"], "B": B,
        "base_file": str(base_path.relative_to(runner.ROOT)),
        "base_sha256": runner.sha(base_path),
        "canonical_x_cache_file": str(cache_path.relative_to(runner.ROOT)),
        "canonical_x_cache_sha256": runner.sha(cache_path),
        "six_subset_uniform_target_first_moment": str(moment),
    }
    sources = dict(prior["source_sha256"])
    for path in (HERE / "m6.py", HERE / "materialize.py", HERE / "shape.py",
                 HERE / "control.py", HERE / "ordinary.py", Path(__file__)):
        sources[str(path.relative_to(runner.ROOT))] = runner.sha(path)
    protocol = {
        **prior,
        "kind": "n83_shifted_width11_six_summand_fixed_slice_stage_v1",
        "proposal_id": "Q2026101266", "candidate_id": None,
        "comparison_variable": "six-summand S3 tree on exact shifted width-11 base versus five-summand Q54 on width-18",
        "method_comparison_parent": "Q2026101254 width-18 Karatsuba",
        "point_decomposition_summands": 6,
        "base_rows": [base_row],
        "leaf_domain": "first leaf is a width-11 affine seed; five other leaves independently select Frobenius powers",
        "target_policy": "fixed first raw cofactor preimage, no target Frobenius rotation in this stage",
        "fixed_target_choice": 0,
        "target_x_onb": shape["target_x_onb"],
        "formula_shape": shape["formula_shape"],
        "width11_frontier_sha256": runner.sha(frontier_path),
        "width11_sage_replay_sha256": runner.sha(sage_path),
        "parent_protocol_sha256": runner.sha(prior_path),
        "parent_result_sha256": runner.sha(PARENT / "width18_ordinary.json"),
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
