#!/usr/bin/env python3
"""Name the matched Q1410/Q1412 N53 PDP-only comparison with PS1 IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, ROOT, sha


OUT = HERE / "runs/n53_q1410_q1412_named_stage_comparison.json"


def identity_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build():
    parent_protocol_path = HERE / "q1410_balanced_s3_n53_protocol.json"
    q1412_protocol_path = HERE / "q1412_ordered_balanced_n53_protocol.json"
    q1412_stage_path = HERE / "runs/n53_q1412_ordinary.json"
    prior_path = HERE / "runs/n53_q1410_n83_q1408_balanced_stage_comparison.json"
    parent_protocol = json.loads(parent_protocol_path.read_text())
    q1412_protocol = json.loads(q1412_protocol_path.read_text())
    stage = json.loads(q1412_stage_path.read_text())
    prior = json.loads(prior_path.read_text())
    parent = prior["stage_profiles"][0]
    assert parent["proposal_id"] == "Q1410"
    assert parent["curve_id"] == q1412_protocol["curve_id"] == stage[
        "curve_id"] == parent_protocol["curve_id"]
    assert parent["workload_id"] == q1412_protocol[
        "ordinary_workload_id"] == stage["workload_id"]
    assert q1412_protocol["ordinary_public_target"] == [
        str(value) for value in stage["public_target"]]
    assert q1412_protocol["parent_factor_base_proposal_id"] == "Q1301"
    assert q1412_protocol["factor_base_enumerated_set_sha256"] == (
        parent_protocol["factor_base_enumerated_set_sha256"]) == stage[
            "factor_base_enumerated_set_sha256"]
    assert q1412_protocol["factor_base_actual_B"] == parent_protocol[
        "factor_base_actual_B"] == stage["factor_base_actual_B"]
    assert q1412_protocol["factor_base_folded_columns"] == parent_protocol[
        "factor_base_folded_columns"] == stage["factor_base_folded_columns"]
    assert stage["proposal_id"] == "Q1412"
    assert stage["candidate_id"] is stage["run_id"] is None
    assert stage["mode"] == "ordinary"
    assert stage["protocol_sha256"] == sha(q1412_protocol_path)
    assert stage["source_sha256"] == q1412_protocol["source_sha256"]
    assert stage["complete_solve_work_log2"] is None
    for source, digest in stage["source_sha256"].items():
        assert digest == sha(ROOT / source)
    base_record = parent_protocol["factor_base"]
    pdp = {
        **q1412_protocol["point_decomposition"],
        "limits_seconds": q1412_protocol["limits_seconds"],
        "kernel_seed": q1412_protocol["kernel_seed"],
        "source_sha256": q1412_protocol["source_sha256"],
    }
    hash_input = {"factor_base": base_record, "point_decomposition": pdp}
    digest = identity_hash(hash_input)
    sid = (f"PS1N53Ckb1fb{stage['factor_base_actual_B']}"
           f"PDP4sath{digest[:12]}")
    assert sid != parent["stage_config_id"]
    wid = stage["workload_id"]
    new_profile = {
        "proposal_id": "Q1412",
        "candidate_id": None,
        "stage_config_id": sid,
        "run_id": f"{sid}W{wid}R1",
        "curve_id": stage["curve_id"],
        "workload_id": wid,
        "isogeny": "none",
        "stage_config_sha256_full": digest,
        "stage_config_hash_input": hash_input,
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
        "protocol_sha256": sha(q1412_protocol_path),
        "stage_receipt_sha256": sha(q1412_stage_path),
    }
    return {
        "kind": "named_q1410_q1412_matched_n53_pdp_stage_comparison",
        "curve_id": stage["curve_id"],
        "workload_id": wid,
        "factor_base_actual_B": stage["factor_base_actual_B"],
        "factor_base_folded_columns": stage[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": stage[
            "factor_base_enumerated_set_sha256"],
        "controlled_variable": "unordered versus unsigned-sorted four raw leaf x coordinates on identical balanced S3 and Q1301 ordinary input",
        "stage_profiles": [parent, new_profile],
        "is_complete_ic_comparison": False,
        "is_controlled_cpu_wall_speedup": False,
        "is_natural_relation_yield_estimate": False,
        "complete_solve_work_log2": None,
        "prior_named_comparison_sha256": sha(prior_path),
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
        assert not OUT.exists(), "refusing to overwrite frozen comparison"
        OUT.write_text(content)
    print(json.dumps({"stage_config_ids": [
        row["stage_config_id"] for row in report["stage_profiles"]],
        "complete_solve_work_log2": None}))


if __name__ == "__main__":
    main()
