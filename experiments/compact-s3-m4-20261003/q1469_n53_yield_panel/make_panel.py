#!/usr/bin/env python3
"""Freeze 128 seeded ordinary N53 subgroup targets for relation supply."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from run_probe import curves, field  # noqa: E402

PANEL = HERE / "panel.json"
SEED = 14690053
COUNT = 128


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def workload_id(value: dict) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()[:12]


def render() -> dict:
    parent = json.loads((PARENT / "protocol.json").read_text())
    profile = next(row for row in parent["profiles"] if row["curve"][
        "curve_id"] == "EC1N53Ckb1hf77aab617904")
    c = profile["curve"]
    assert c["subgroup_order"] == 21044858204113
    assert c["cofactor"] == 428
    q1468 = json.loads((PARENT /
        "q1468_n53_pair_oracle/protocol.json").read_text())
    assert q1468["curve_id"] == c["curve_id"]
    assert q1468["factor_base_actual_B"] == 2756
    assert q1468["folded_columns_K"] == 26
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(c["generator"])
    assert curve.onCurve(generator)
    assert curve.mul(generator, c["subgroup_order"]) is None
    excluded = {tuple(row["public_target"])
                for row in q1468["workloads"].values()}
    rng = random.Random(SEED)
    seen = set(excluded)
    targets = []
    for index in range(COUNT):
        while True:
            scalar = rng.randrange(1, c["subgroup_order"])
            point = curve.mul(generator, scalar)
            assert point is not None
            if point not in seen:
                break
        seen.add(point)
        assert curve.onCurve(point)
        assert curve.mul(point, c["subgroup_order"]) is None
        record = {
            "curve_id": c["curve_id"],
            "subgroup_order": c["subgroup_order"],
            "public_target": [int(point[0]), int(point[1])],
            "input_law": "seeded_uniform_nonzero_scalar_times_frozen_generator",
            "panel_seed": SEED, "panel_index": index,
            "cache_state": "cold_pair_table_for_this_one_target",
        }
        targets.append({
            "index": index,
            "public_target": record["public_target"],
            "workload_id": workload_id(record),
        })
    aggregate = {
        "curve_id": c["curve_id"],
        "subgroup_order": c["subgroup_order"],
        "target_points": [row["public_target"] for row in targets],
        "input_law": "seeded_uniform_nonzero_scalar_times_frozen_generator",
        "seed": SEED, "target_count": COUNT,
        "cache_state": "cold_pair_table_per_target",
    }
    return {
        "kind": "q1469_n53_ordinary_relation_supply_panel",
        "proposal_id": "Q1469", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": c["curve_id"], "curve_manifest_sha256": profile[
            "curve_manifest_sha256"],
        "degree_n": 53, "subgroup_order": c["subgroup_order"],
        "generator": list(generator),
        "factor_base_actual_B": q1468["factor_base_actual_B"],
        "folded_columns_K": q1468["folded_columns_K"],
        "factor_base_enumerated_set_sha256": q1468[
            "factor_base_enumerated_set_sha256"],
        "input_law": aggregate["input_law"],
        "seed": SEED, "target_count": COUNT,
        "cache_state": aggregate["cache_state"],
        "panel_workload_id": workload_id(aggregate),
        "targets": targets,
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = render()
    if args.check:
        assert current == json.loads(PANEL.read_text())
    else:
        assert not PANEL.exists(), "refuse overwrite"
        PANEL.write_text(json.dumps(current, indent=2, sort_keys=True) +
                         "\n")
    print(json.dumps({"status": "pass", "target_count": COUNT,
                      "panel_workload_id": current["panel_workload_id"]}),
          flush=True)


if __name__ == "__main__":
    main()
