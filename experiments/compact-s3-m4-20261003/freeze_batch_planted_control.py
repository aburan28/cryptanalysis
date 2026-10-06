#!/usr/bin/env python3
"""Freeze Q1332 N83 batch-root correctness control on Q1329's target."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


def render():
    fixture_path = HERE / "runs/n83_q1329_planted_fixture.json"
    fixture = json.loads(fixture_path.read_text())
    parent_path = HERE / "native_inputs/n83_planted_control_manifest.json"
    parent = json.loads(parent_path.read_text())
    batch_path = HERE / "q1330_q1331_batch_root_protocol.json"
    batch = json.loads(batch_path.read_text())
    assert fixture["proposal_id"] == parent["proposal_id"] == "Q1329"
    assert fixture["workload_id"] == parent["workload_id"]
    assert fixture["curve_id"] == parent["curve_id"]
    assert fixture["is_natural_yield_measurement"] is False
    assert parent["orientations_per_state"] == 83
    batch_profile = next(row for row in batch["profiles"]
                         if row["field_degree"] == 83)
    assert batch_profile["proposal_id"] == "Q1331"
    assert batch_profile["s3_batch_size"] == 4096
    assert batch_profile["curve_id"] == parent["curve_id"]
    assert batch_profile["factor_base_actual_B"] == parent[
        "actual_usable_points_B"]
    assert batch_profile["factor_base_folded_columns_K"] == parent[
        "representative_count_K"]
    protocol = {
        "kind": "n83_s3_batch_root_planted_four_leaf_control_protocol",
        "schema_version": 1,
        "status": "frozen_planted_control_only",
        "proposal_id": "Q1332",
        "parent_solver_proposal_id": "Q1331",
        "parent_planted_control_proposal_id": "Q1329",
        "parent_factor_base_proposal_id": "Q1325",
        "candidate_id": None,
        "run_id": None,
        "curve_id": fixture["curve_id"],
        "workload_id": fixture["workload_id"],
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4root",
        "s3_batch_size": 4096,
        "target_orientations_per_state": 83,
        "pair_state_cap": 2000000,
        "peak_rss_cap_mib": 1024,
        "is_natural_yield_measurement": False,
        "solver_receives_witness_or_index_positions": False,
        "planted_fixture_sha256": sha(fixture_path),
        "parent_manifest_sha256": sha(parent_path),
        "batch_protocol_sha256": sha(batch_path),
        "native_source_sha256": sha(HERE / "native_s3_root.rs"),
        "complete_work_log2": None,
    }
    protocol_path = HERE / "q1332_batch_planted_control_protocol.json"
    protocol_content = json.dumps(protocol, indent=2) + "\n"
    manifest = dict(parent)
    manifest.update({
        "kind": "exact_native_s3_batch_planted_control_input",
        "proposal_id": "Q1332",
        "parent_solver_proposal_id": "Q1331",
        "parent_planted_control_proposal_id": "Q1329",
        "s3_batch_size": 4096,
        "stage_protocol_sha256": hashlib.sha256(
            protocol_content.encode()).hexdigest(),
        "planted_fixture_sha256": sha(fixture_path),
        "parent_manifest_sha256": sha(parent_path),
        "source_sha256": sha(Path(__file__)),
    })
    manifest_path = HERE / "native_inputs/n83_batch_planted_manifest.json"
    return ((protocol_path, protocol_content),
            (manifest_path, json.dumps(manifest, indent=2) + "\n"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = render()
    for path, content in output:
        if args.check:
            assert path.read_text() == content
        else:
            assert not path.exists()
            path.write_text(content)
    print(json.dumps({"status": "PASS", "proposal_id": "Q1332"}))


if __name__ == "__main__":
    main()
