#!/usr/bin/env python3
"""Freeze Q1473 inputs and source custody before ordinary measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
PROTOCOL = HERE / "protocol.json"
SOURCE_PATHS = [
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/pair_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/inputs/base_points.txt",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/panel.json",
    "experiments/compact-s3-m4-20261003/q1469_n53_yield_panel/audit_panel.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/batch_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/build.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/make_panel.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/check_controls.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/run_batch.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/audit.py",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/panel.json",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/targets.txt",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/control_targets.txt",
    "experiments/compact-s3-m4-20261003/q1473_n53_rank_collection/control_result.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render() -> dict:
    panel = json.loads((HERE / "panel.json").read_text())
    prior = json.loads((PARENT /
        "q1469_n53_yield_panel/panel_audit.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    assert panel["proposal_id"] == "Q1473"
    assert panel["candidate_id"] is None
    assert panel["isogeny"] == "none"
    assert prior["status"] == control["status"] == "passed"
    assert prior["final_relation_matrix_rank"] == 13
    assert prior["rows"][1]["status"] == "found"
    assert control["binary_sha256"] == sha(HERE / "batch_oracle")
    return {
        "kind": "q1473_n53_warm_table_rank_protocol",
        "proposal_id": "Q1473", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "measurement_scope": "secondary seeded ordinary rank collection with one cold pair table and 256 warm queries; all target-query failures charged; no isolated CPU speedup claim",
        "curve_id": panel["curve_id"], "degree_n": 53,
        "curve_manifest_sha256": panel["curve_manifest_sha256"],
        "factor_base_actual_B": panel["factor_base_actual_B"],
        "folded_columns_K": panel["folded_columns_K"],
        "factor_base_enumerated_set_sha256": panel[
            "factor_base_enumerated_set_sha256"],
        "panel_workload_id": panel["panel_workload_id"],
        "target_count": panel["target_count"],
        "input_law": panel["input_law"],
        "target_generation_seed": panel["seed"],
        "cache_state": panel["cache_state"],
        "held_out_q1469_index": 1,
        "run_order": list(range(panel["target_count"])),
        "native_wall_cap_seconds_per_phase": 600,
        "external_safeguard_seconds": 3600,
        "stop_rule": "one setup and all 256 targets in frozen order; preserve found, absent, censored, failure and raw output; no result-based early stop",
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE_PATHS},
        "binary_sha256": sha(HERE / "batch_oracle"),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "q1469_panel_audit_sha256": sha(PARENT /
                                      "q1469_n53_yield_panel/panel_audit.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = render()
    if args.emit:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(result, sort_keys=True, indent=2) +
                            "\n")
    else:
        assert result == json.loads(PROTOCOL.read_text())
    print(json.dumps({"status": "pass",
                      "panel_workload_id": result["panel_workload_id"],
                      "protocol_sha256": sha(PROTOCOL)}), flush=True)


if __name__ == "__main__":
    main()
