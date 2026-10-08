#!/usr/bin/env python3
"""Freeze Q1469 ordinary-target panel and exact-oracle execution envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
Q1468 = PARENT / "q1468_n53_pair_oracle"
PROTOCOL = HERE / "protocol.json"
SOURCES = (
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/"
    "make_panel.py",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/"
    "run_panel.py",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/"
    "freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "pair_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "inputs/base_points.txt",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "n53_field.txt",
    "experiments/compact-s3-m4-20261003/protocol.json",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe() -> dict:
    panel = json.loads((HERE / "panel.json").read_text())
    q1468 = json.loads((Q1468 / "protocol.json").read_text())
    assert panel["proposal_id"] == "Q1469"
    assert panel["candidate_id"] is None
    assert panel["isogeny"] == "none"
    assert panel["curve_id"] == q1468["curve_id"]
    assert panel["factor_base_actual_B"] == q1468[
        "factor_base_actual_B"] == 2756
    assert panel["folded_columns_K"] == q1468["folded_columns_K"] == 26
    assert panel["factor_base_enumerated_set_sha256"] == q1468[
        "factor_base_enumerated_set_sha256"]
    assert panel["target_count"] == len(panel["targets"]) == 128
    assert [row["index"] for row in panel["targets"]] == list(range(128))
    assert len({row["workload_id"] for row in panel["targets"]}) == 128
    assert len({tuple(row["public_target"])
                for row in panel["targets"]}) == 128
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    assert sha(Q1468 / "native_oracle") == q1468["binary_sha256"]
    return {
        "kind": "q1469_n53_ordinary_relation_supply_protocol",
        "proposal_id": "Q1469", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": panel["curve_id"], "degree_n": 53,
        "factor_base_actual_B": panel["factor_base_actual_B"],
        "folded_columns_K": panel["folded_columns_K"],
        "factor_base_enumerated_set_sha256": panel[
            "factor_base_enumerated_set_sha256"],
        "panel_workload_id": panel["panel_workload_id"],
        "target_count": panel["target_count"],
        "target_generation_seed": panel["seed"],
        "input_law": panel["input_law"],
        "cache_state": "cold_pair_table_per_target",
        "run_order": [row["index"] for row in panel["targets"]],
        "native_wall_cap_seconds_per_phase": 600,
        "external_safeguard_seconds": 1250,
        "overall_wall_budget_seconds": 3600,
        "stop_rule": (
            "run all 128 targets sequentially in frozen index order, "
            "preserve every found, absent, timeout, and error row; "
            "stop before launching a new target when the overall "
            "3600-second budget is exhausted"),
        "measurement_scope": (
            "secondary natural relation supply, rank, and cost-per-useful-"
            "row diagnostic after Q1468 single-target measurements; "
            "each target gets a fresh target-independent pair table and "
            "its native query interval is recorded separately"),
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "source_sha256": {relative: sha(ROOT / relative)
                          for relative in SOURCES},
        "panel_sha256": sha(HERE / "panel.json"),
        "base_sha256": sha(Q1468 / "inputs/base_points.txt"),
        "field_bridge_sha256": sha(PARENT /
            "q1420_root_theory/n53_field.txt"),
        "binary_sha256": sha(Q1468 / "native_oracle"),
        "q1468_protocol_sha256": sha(Q1468 / "protocol.json"),
        "q1468_compile_receipt_sha256": sha(Q1468 /
            "compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = describe()
    if args.check:
        assert current == json.loads(PROTOCOL.read_text())
        print("Q1469 N53 relation-supply panel protocol: PASS")
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(current, indent=2, sort_keys=True) +
                            "\n")
        print(json.dumps({"proposal_id": "Q1469",
                          "panel_workload_id": current["panel_workload_id"],
                          "target_count": current["target_count"],
                          "protocol_sha256": sha(PROTOCOL)}))


if __name__ == "__main__":
    main()
