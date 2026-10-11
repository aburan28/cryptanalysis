#!/usr/bin/env python3
"""Name balanced-S3 N53/N83 stages without claiming a solve-time ratio."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, ROOT, sha

OUT = HERE / "runs/n53_q1410_n83_q1408_balanced_stage_comparison.json"


def identity_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build():
    protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    stage_path = HERE / "runs/n53_q1410_ordinary.json"
    n83_path = HERE / "runs/n83_q1404_q1408_named_stage_comparison.json"
    replay_path = HERE / "runs/n53_q1410_balanced_control_replay.json"
    protocol = json.loads(protocol_path.read_text())
    stage = json.loads(stage_path.read_text())
    n83_comparison = json.loads(n83_path.read_text())
    replay = json.loads(replay_path.read_text())
    n83 = n83_comparison["stage_profiles"][1]
    assert n83["proposal_id"] == "Q1408"
    assert stage["proposal_id"] == protocol["proposal_id"] == "Q1410"
    assert stage["curve_id"] == protocol["curve_id"]
    assert stage["workload_id"] == protocol["ordinary_workload_id"]
    assert stage["factor_base_actual_B"] == protocol["factor_base_actual_B"]
    assert stage["factor_base_folded_columns"] == protocol[
        "factor_base_folded_columns"]
    assert stage["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert stage["protocol_sha256"] == sha(protocol_path)
    assert stage["source_sha256"] == protocol["source_sha256"]
    for source, digest in stage["source_sha256"].items():
        assert digest == sha(ROOT / source)
    assert replay["status"] == "PASS"
    assert replay["ordinary_relation_count"] == 0
    assert stage["complete_solve_work_log2"] is None
    pdp = {**protocol["point_decomposition"],
           "limits_seconds": protocol["limits_seconds"],
           "kernel_seed": protocol["kernel_seed"],
           "source_sha256": protocol["source_sha256"]}
    identity = {"factor_base": protocol["factor_base"],
                "point_decomposition": pdp}
    digest = identity_hash(identity)
    sid = f"PS1N53Ckb1fb{stage['factor_base_actual_B']}PDP4sath{digest[:12]}"
    wid = stage["workload_id"]
    n53 = {
        "proposal_id": "Q1410", "candidate_id": None,
        "stage_config_id": sid, "stage_config_sha256_full": digest,
        "stage_config_hash_input": identity,
        "run_id": f"{sid}W{wid}R1",
        "curve_id": stage["curve_id"], "workload_id": wid,
        "isogeny": "none",
        "ordinary_stage_status": stage["status"],
        "ordinary_target_preimage_wall_seconds_exploratory": stage[
            "target_preimage_wall_seconds"],
        "ordinary_target_pdp_wall_seconds_exploratory": stage[
            "target_pdp_wall_seconds"],
        "ordinary_target_relation_check_wall_seconds_exploratory": stage[
            "target_relation_check_wall_seconds"],
        "ordinary_target_stage_wall_seconds_exploratory": stage[
            "target_dependent_stage_wall_seconds"],
        "observed_verified_relation_count": stage[
            "observed_verified_relation_count"],
        "natural_relation_yield_rate_estimate": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "stage_receipt_sha256": sha(stage_path),
    }
    return {
        "kind": "named_q1410_q1408_cross_degree_balanced_s3_stage_comparison",
        "controlled_algorithm_family": "balanced raw-preimage W-bounded S3 SAT",
        "different_curves_and_factor_bases": True,
        "limits_matched_for_ordinary": (
            protocol["limits_seconds"]["ordinary"] == 120
            and protocol["max_conflicts"] == 1_000_000),
        "stage_profiles": [n53, n83],
        "is_complete_ic_comparison": False,
        "is_controlled_cpu_wall_speedup": False,
        "is_solve_growth_measurement": False,
        "is_natural_relation_yield_estimate": False,
        "complete_solve_work_log2": None,
        "n83_named_comparison_sha256": sha(n83_path),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == content
    else:
        assert not OUT.exists()
        OUT.write_text(content)
    print(json.dumps({"stage_config_ids": [
        row["stage_config_id"] for row in report["stage_profiles"]],
        "complete_solve_work_log2": None}))


if __name__ == "__main__":
    main()
