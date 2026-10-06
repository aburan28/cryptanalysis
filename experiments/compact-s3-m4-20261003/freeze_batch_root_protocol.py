#!/usr/bin/env python3
"""Freeze matched Q1330/Q1331 batch-inversion root stage inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha

BATCH_SIZE = 4096


def render():
    parent_path = HERE / "q1327_q1328_native_root_protocol.json"
    parent = json.loads(parent_path.read_text())
    assert parent["point_decomposition"]["stage_code"] == "PDP4root"
    profiles = []
    manifests = []
    for n, proposal, parent_proposal in (
        (53, "Q1330", "Q1327"), (83, "Q1331", "Q1328"),
    ):
        previous = next(row for row in parent["profiles"]
                        if row["field_degree"] == n)
        assert previous["proposal_id"] == parent_proposal
        ordinary_path = HERE / "native_inputs" / f"n{n}_manifest.json"
        ordinary = json.loads(ordinary_path.read_text())
        assert ordinary["proposal_id"] == parent_proposal
        assert ordinary["curve_id"] == previous["curve_id"]
        assert ordinary["workload_id"] == previous["workload_id"]
        assert ordinary["actual_usable_points_B"] == previous[
            "factor_base_actual_B"]
        assert ordinary["representative_count_K"] == previous[
            "factor_base_folded_columns_K"]
        profile = dict(previous)
        profile.update({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "s3_batch_size": BATCH_SIZE,
            "target_orientations_per_state": 1,
            "ordinary_input_manifest_sha256": sha(ordinary_path),
        })
        profiles.append(profile)
        manifests.append((n, proposal, parent_proposal, ordinary))
    protocol = {
        "kind": "bounded_native_four_summand_s3_batch_inversion_stage_protocol",
        "schema_version": 1,
        "status": "frozen_stage_only",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "parent_stage_protocol_sha256": sha(parent_path),
        "native_source_sha256": sha(HERE / "native_s3_root.rs"),
        "point_decomposition": {
            "stage_code": "PDP4root",
            "m": 4,
            "chain": parent["point_decomposition"]["chain"],
            "index": parent["point_decomposition"]["index"],
            "target_query": parent["point_decomposition"]["target_query"],
            "root_kernel": "Montgomery batch inversion across up to 4096 independent S3 equations in index and target phases; one inversion and 3(k-1) charged field multiplications for k nonzero denominators",
            "batch_policy": "consecutive indexed states in frozen order; target-dependent preparation of a complete block is charged even when a hit occurs early in the block",
            "root_table": parent["point_decomposition"]["root_table"],
            "verification": parent["point_decomposition"]["verification"],
            "operation_accounting": "separate setup, index, and target counts including batch-inversion multiplications, inversions, extra prepared target states, failures, and native relation checks; no common operation-equivalent calibration",
            "full_pipeline_stages": "unwired",
        },
        "profiles": profiles,
        "claim_gate": {
            "n53_verified_relation_is_complete_dlp": False,
            "n83_no_hit_proves_unsupported_target": False,
            "unisolated_wall_ratio_is_speedup_claim": False,
            "degree131_complete_solve_exponent": None,
            "degree131_challenge_allowed": False,
        },
    }
    protocol_path = HERE / "q1330_q1331_batch_root_protocol.json"
    protocol_content = json.dumps(protocol, indent=2) + "\n"
    digest = hashlib.sha256(protocol_content.encode()).hexdigest()
    output = [(protocol_path, protocol_content)]
    for n, proposal, parent_proposal, ordinary in manifests:
        manifest = dict(ordinary)
        manifest.update({
            "kind": "exact_native_s3_batch_root_input",
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "s3_batch_size": BATCH_SIZE,
            "stage_protocol_sha256": digest,
            "ordinary_input_manifest_sha256": profiles[
                0 if n == 53 else 1]["ordinary_input_manifest_sha256"],
            "source_sha256": sha(Path(__file__)),
        })
        output.append((HERE / "native_inputs" / f"n{n}_batch_manifest.json",
                       json.dumps(manifest, indent=2) + "\n"))
    return output


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
    print(json.dumps({"status": "PASS", "proposal_ids": ["Q1330", "Q1331"],
                      "batch_size": BATCH_SIZE}))


if __name__ == "__main__":
    main()
