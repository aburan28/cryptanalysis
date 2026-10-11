#!/usr/bin/env python3
"""Freeze one-target fused-root-kernel comparison inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


def render():
    parent_path = HERE / "q1333_q1334_adaptive_window_protocol.json"
    parent = json.loads(parent_path.read_text())
    profiles = []
    manifests = []
    for n, proposal, parent_proposal in (
        (53, "Q1336", "Q1333"), (83, "Q1337", "Q1334"),
    ):
        previous = next(row for row in parent["profiles"]
                        if row["field_degree"] == n)
        assert previous["proposal_id"] == parent_proposal
        input_path = HERE / "native_inputs" / f"n{n}_adaptive_manifest.json"
        input_manifest = json.loads(input_path.read_text())
        assert input_manifest["workload_id"] == previous["workload_id"]
        profile = dict(previous)
        profile.update({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "fused_root_kernel": "regular d calculation uses c*a^2/(a*ps), removing one charged field multiply per regular S3 root",
            "parent_adaptive_input_manifest_sha256": sha(input_path),
        })
        profiles.append(profile)
        manifests.append((n, proposal, parent_proposal, input_manifest))

    planted_path = HERE / "native_inputs/n83_adaptive_planted_manifest.json"
    planted = json.loads(planted_path.read_text())
    protocol = {
        "kind": "bounded_native_four_summand_s3_fused_root_stage_protocol",
        "schema_version": 1,
        "status": "frozen_stage_only",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "parent_stage_protocol_sha256": sha(parent_path),
        "native_source_sha256": sha(HERE / "native_s3_root_fast.rs"),
        "target_count": 1,
        "target_policy": "one target point per run; no target batching",
        "index_s3_window_size": parent["index_s3_window_size"],
        "target_s3_window_schedule": parent["target_s3_window_schedule"],
        "point_decomposition": {
            "stage_code": "PDP4root",
            "m": 4,
            "kernel_change": "for regular S3 equations, compute d = c*a^2/(a*ps) from the already inverted combined denominator; this replaces three multiplications with two",
            "single_target_schedule": "same 1, 16, 64, 256, 1024, then 4096 state schedule as the matched adaptive control",
            "workload_scope": "one frozen target point per independent run",
            "verification": parent["point_decomposition"]["verification"],
            "full_pipeline_stages": "unwired",
        },
        "profiles": profiles,
        "planted_control": {
            "proposal_id": "Q1338",
            "parent_solver_proposal_id": "Q1337",
            "parent_planted_control_proposal_id": "Q1329",
            "target_count": 1,
            "workload_id": planted["workload_id"],
            "target_s3_window_schedule": parent[
                "target_s3_window_schedule"],
            "parent_adaptive_input_manifest_sha256": sha(planted_path),
            "is_natural_relation_yield_measurement": False,
        },
        "claim_gate": {
            "ordinary_n53_relation_is_complete_dlp": False,
            "ordinary_n83_no_hit_proves_unsupported_target": False,
            "planted_control_estimates_natural_yield": False,
            "unisolated_stage_ratio_is_speedup_claim": False,
            "degree131_complete_solve_exponent": None,
            "degree131_challenge_allowed": False,
        },
    }
    protocol_path = HERE / "q1336_q1337_fast_root_protocol.json"
    protocol_content = json.dumps(protocol, indent=2) + "\n"
    protocol_digest = hashlib.sha256(protocol_content.encode()).hexdigest()
    outputs = [(protocol_path, protocol_content)]
    for n, proposal, parent_proposal, source_manifest in manifests:
        manifest = dict(source_manifest)
        manifest.update({
            "kind": "exact_native_s3_fused_root_input",
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "stage_protocol_sha256": protocol_digest,
            "parent_adaptive_input_manifest_sha256": sha(
                HERE / "native_inputs" / f"n{n}_adaptive_manifest.json"),
            "source_sha256": sha(Path(__file__)),
        })
        outputs.append((HERE / "native_inputs" / f"n{n}_fast_manifest.json",
                        json.dumps(manifest, indent=2) + "\n"))

    planted_manifest = dict(planted)
    planted_manifest.update({
        "kind": "exact_native_s3_fused_root_planted_control_input",
        "proposal_id": "Q1338",
        "parent_solver_proposal_id": "Q1337",
        "parent_planted_control_proposal_id": "Q1329",
        "stage_protocol_sha256": protocol_digest,
        "parent_adaptive_input_manifest_sha256": sha(planted_path),
        "source_sha256": sha(Path(__file__)),
    })
    outputs.append((HERE / "native_inputs/n83_fast_planted_manifest.json",
                    json.dumps(planted_manifest, indent=2) + "\n"))
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = render()
    for path, content in outputs:
        if args.check:
            assert path.read_text() == content
        else:
            assert not path.exists()
            path.write_text(content)
    print(json.dumps({"status": "PASS", "proposal_ids": [
        "Q1336", "Q1337", "Q1338"], "target_count_per_run": 1}))


if __name__ == "__main__":
    main()
