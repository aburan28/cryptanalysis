#!/usr/bin/env python3
"""Freeze fresh ordinary N53 points for a shared-table rank collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from run_probe import curves, field  # noqa: E402

SEED = 14730053
COUNT = 256


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def workload_id(value: dict) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()[:12]


def render() -> tuple[dict, bytes]:
    parent = json.loads((PARENT / "protocol.json").read_text())
    profile = next(row for row in parent["profiles"] if row["curve"][
        "curve_id"] == "EC1N53Ckb1hf77aab617904")
    c = profile["curve"]
    q1469 = json.loads((PARENT /
        "q1469_n53_yield_panel/panel.json").read_text())
    q1468 = json.loads((PARENT /
        "q1468_n53_pair_oracle/protocol.json").read_text())
    assert q1469["factor_base_actual_B"] == 2756
    assert q1469["folded_columns_K"] == 26
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(c["generator"])
    modulus = c["subgroup_order"]
    assert curve.onCurve(generator)
    assert curve.mul(generator, modulus) is None
    seen = {tuple(row["public_target"]) for row in q1469["targets"]}
    seen.update(tuple(row["public_target"])
                for row in q1468["workloads"].values())
    rng = random.Random(SEED)
    targets = []
    lines = [f"Q1473TARGETS1 53 {COUNT}"]
    for index in range(COUNT):
        while True:
            scalar = rng.randrange(1, modulus)
            point = curve.mul(generator, scalar)
            if point not in seen:
                break
        seen.add(point)
        record = {
            "curve_id": c["curve_id"],
            "subgroup_order": modulus,
            "public_target": list(point),
            "input_law": "seeded_uniform_nonzero_scalar_times_frozen_generator",
            "panel_seed": SEED,
            "panel_index": index,
            "cache_state": "warm_shared_pair_table_256_targets",
        }
        targets.append({"index": index, "public_target": list(point),
                        "workload_id": workload_id(record)})
        lines.append(f"{index} {int(onb.toCoords(point[0])):x} "
                     f"{int(onb.toCoords(point[1])):x}")
    aggregate = {
        "curve_id": c["curve_id"], "subgroup_order": modulus,
        "target_points": [row["public_target"] for row in targets],
        "input_law": "seeded_uniform_nonzero_scalar_times_frozen_generator",
        "seed": SEED, "target_count": COUNT,
        "cache_state": "one_cold_pair_table_then_256_warm_queries",
    }
    panel = {
        "kind": "q1473_n53_warm_table_rank_panel",
        "proposal_id": "Q1473", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": c["curve_id"],
        "curve_manifest_sha256": profile["curve_manifest_sha256"],
        "degree_n": 53, "subgroup_order": modulus,
        "generator": list(generator),
        "factor_base_actual_B": q1469["factor_base_actual_B"],
        "folded_columns_K": q1469["folded_columns_K"],
        "factor_base_enumerated_set_sha256": q1469[
            "factor_base_enumerated_set_sha256"],
        "input_law": aggregate["input_law"], "seed": SEED,
        "target_count": COUNT, "cache_state": aggregate["cache_state"],
        "panel_workload_id": workload_id(aggregate),
        "prior_q1469_panel_workload_id": q1469["panel_workload_id"],
        "targets": targets,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    return panel, ("\n".join(lines) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    panel, targets = render()
    panel_path, targets_path = HERE / "panel.json", HERE / "targets.txt"
    if args.check:
        assert panel == json.loads(panel_path.read_text())
        assert targets == targets_path.read_bytes()
    else:
        assert not panel_path.exists() and not targets_path.exists()
        panel_path.write_text(json.dumps(panel, sort_keys=True, indent=2) +
                              "\n")
        targets_path.write_bytes(targets)
    print(json.dumps({"status": "pass", "target_count": COUNT,
                      "panel_workload_id": panel["panel_workload_id"],
                      "targets_sha256": sha(targets_path)}), flush=True)


if __name__ == "__main__":
    main()
