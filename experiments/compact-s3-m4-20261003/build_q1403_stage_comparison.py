#!/usr/bin/env python3
"""Give Q1325/Q1403's matched N83 PDP measurements canonical PS1 labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


OUT = HERE / "runs/n83_q1325_q1403_named_stage_comparison.json"


def identity_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def stage_profile(proposal_id, protocol, stage, base_record, pdp_record,
                  protocol_path, stage_path):
    hash_input = {
        "factor_base": base_record,
        "point_decomposition": pdp_record,
    }
    digest = identity_hash(hash_input)
    sid = (f"PS1N83Ckb1fb{stage['factor_base_actual_B']}"
           f"PDP4sath{digest[:12]}")
    wid = stage["workload_id"]
    assert len(wid) == 12 and all(c in "0123456789abcdef" for c in wid)
    assert stage["mode"] == "ordinary"
    assert stage["candidate_id"] is stage["run_id"] is None
    assert stage["curve_id"] == protocol["curve_id"]
    assert stage["factor_base_actual_B"] == base_record[
        "actual_usable_points_B_before_folding"]
    assert stage["factor_base_folded_columns"] == base_record[
        "signed_frobenius_columns"]
    assert stage["factor_base_enumerated_set_sha256"] == base_record[
        "enumerated_set_sha256"]
    assert stage["complete_solve_work_log2"] is None
    return {
        "proposal_id": proposal_id,
        "candidate_id": None,
        "stage_config_id": sid,
        "run_id": f"{sid}W{wid}R1",
        "curve_id": stage["curve_id"],
        "workload_id": wid,
        "isogeny": "none",
        "stage_config_sha256_full": digest,
        "stage_config_hash_input": hash_input,
        "ordinary_stage_status": stage["status"],
        "ordinary_target_pdp_wall_seconds_exploratory": stage[
            "target_pdp_wall_seconds"],
        "observed_verified_relation_count": stage[
            "observed_verified_relation_count"],
        "natural_relation_yield_rate_estimate": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "stage_receipt_sha256": sha(stage_path),
    }


def build():
    q1325_protocol_path = HERE / "q1325_protocol.json"
    q1403_protocol_path = HERE / "q1403_ordered_q1325_protocol.json"
    q1325_stage_path = HERE / "runs/n83_q1325_ordinary.json"
    q1403_stage_path = HERE / "runs/n83_q1403_ordinary.json"
    q1325_protocol = json.loads(q1325_protocol_path.read_text())
    q1403_protocol = json.loads(q1403_protocol_path.read_text())
    q1325_stage = json.loads(q1325_stage_path.read_text())
    q1403_stage = json.loads(q1403_stage_path.read_text())
    assert q1325_protocol["proposal_id"] == "Q1325"
    assert q1403_protocol["proposal_id"] == "Q1403"
    assert q1403_protocol["parent_factor_base_proposal_id"] == "Q1325"
    assert q1325_protocol["curve"]["curve_id"] == q1403_protocol[
        "curve_id"] == q1325_stage["curve_id"] == q1403_stage["curve_id"]
    assert q1325_protocol["ordinary_workload_id"] == q1403_protocol[
        "ordinary_workload_id"] == q1325_stage["workload_id"] == q1403_stage[
            "workload_id"]
    assert q1325_stage["public_target"] == q1403_stage["public_target"]
    assert q1325_stage["factor_base_enumerated_set_sha256"] == q1403_stage[
        "factor_base_enumerated_set_sha256"]
    assert q1325_stage["factor_base_actual_B"] == q1403_stage[
        "factor_base_actual_B"]
    assert q1325_stage["factor_base_folded_columns"] == q1403_stage[
        "factor_base_folded_columns"]
    assert q1325_stage["target_pdp_wall_seconds"] is not None
    assert q1403_stage["target_pdp_wall_seconds"] is not None
    base_record = q1325_protocol["factor_base"]
    sources = q1403_protocol["source_sha256"]
    for source, digest in sources.items():
        assert digest == sha(HERE / source)
    assert q1325_stage["projected_source_sha256"] == sources[
        "chain_s3_projected_sparse.py"]
    assert q1325_stage["runner_source_sha256"] == sources[
        "run_q1325_full_weight5_probe.py"]
    assert q1403_stage["source_sha256"] == sources

    q1325_pdp = {
        **q1325_protocol["point_decomposition"],
        "raw_leaf_order": "none",
        "source_sha256": {
            source: sources[source] for source in (
                "chain_s3.py", "chain_s3_factored.py",
                "chain_s3_projected_sparse.py",
                "run_q1325_full_weight5_probe.py",
                "run_group_add_probe.py",
            )
        },
    }
    q1403_pdp = {
        **q1403_protocol["point_decomposition"],
        "limits_seconds": q1403_protocol["limits_seconds"],
        "raw_leaf_order": "unsigned_normal_basis_x_ascending",
        "source_sha256": sources,
    }
    q1325_profile = stage_profile(
        "Q1325", {"curve_id": q1325_protocol["curve"]["curve_id"]},
        q1325_stage, base_record, q1325_pdp,
        q1325_protocol_path, q1325_stage_path)
    q1403_profile = stage_profile(
        "Q1403", q1403_protocol, q1403_stage, base_record, q1403_pdp,
        q1403_protocol_path, q1403_stage_path)
    assert q1325_profile["stage_config_id"] != q1403_profile[
        "stage_config_id"]
    return {
        "kind": "named_q1325_q1403_matched_n83_pdp_stage_comparison",
        "curve_id": q1325_stage["curve_id"],
        "workload_id": q1325_stage["workload_id"],
        "factor_base_actual_B": q1325_stage["factor_base_actual_B"],
        "factor_base_folded_columns": q1325_stage[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": q1325_stage[
            "factor_base_enumerated_set_sha256"],
        "controlled_variable": "raw leaf ordering in compact implicit-base S3 SAT",
        "stage_profiles": [q1325_profile, q1403_profile],
        "is_complete_ic_comparison": False,
        "is_controlled_cpu_wall_speedup": False,
        "is_natural_relation_yield_estimate": False,
        "complete_solve_work_log2": None,
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
