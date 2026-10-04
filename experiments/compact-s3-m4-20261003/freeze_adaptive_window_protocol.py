#!/usr/bin/env python3
"""Freeze one-target adaptive S3 inversion-window inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha

WINDOW_SCHEDULE = [1, 16, 64, 256, 1024, 4096]


def render():
    parent_path = HERE / "q1330_q1331_batch_root_protocol.json"
    parent = json.loads(parent_path.read_text())
    profiles = []
    output_manifests = []
    for n, proposal, parent_proposal in (
        (53, "Q1333", "Q1330"), (83, "Q1334", "Q1331"),
    ):
        prior = next(row for row in parent["profiles"]
                     if row["field_degree"] == n)
        assert prior["proposal_id"] == parent_proposal
        adaptive_path = HERE / "native_inputs" / f"n{n}_batch_manifest.json"
        adaptive = json.loads(adaptive_path.read_text())
        assert adaptive["workload_id"] == prior["workload_id"]
        profile = dict(prior)
        profile.update({
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "target_count": 1,
            "target_policy": "one frozen ordinary public target; no target batching",
            "target_s3_window_schedule": WINDOW_SCHEDULE,
            "same_window_4096_input_manifest_sha256": sha(adaptive_path),
        })
        profile.pop("s3_batch_size", None)
        profile["index_s3_window_size"] = 4096
        profiles.append(profile)
        output_manifests.append((n, proposal, parent_proposal, adaptive))

    planted_path = HERE / "native_inputs/n83_batch_planted_manifest.json"
    planted = json.loads(planted_path.read_text())
    assert planted["workload_id"] == "c530b6f0b4dd"
    protocol = {
        "kind": "bounded_native_four_summand_s3_adaptive_target_window_protocol",
        "schema_version": 1,
        "status": "frozen_stage_only",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "parent_stage_protocol_sha256": sha(parent_path),
        "native_source_sha256": sha(HERE / "native_s3_root_adaptive.rs"),
        "target_count": 1,
        "target_policy": "one public target point per run; never combine target points",
        "index_s3_window_size": 4096,
        "target_s3_window_schedule": WINDOW_SCHEDULE,
        "point_decomposition": {
            "stage_code": "PDP4root",
            "m": 4,
            "root_kernel": "Montgomery inversion within consecutive target-state windows; window schedule grows 1, 16, 64, 256, 1024, then 4096 states",
            "schedule_scope": "field arithmetic for one target only; no target batching or cross-target state",
            "window_accounting": "charge all prepared states and all inversions/multiplications in a window even if the target relation is found partway through it",
            "verification": parent["point_decomposition"]["verification"],
            "full_pipeline_stages": "unwired",
        },
        "profiles": profiles,
        "planted_control": {
            "proposal_id": "Q1335",
            "parent_solver_proposal_id": "Q1334",
            "parent_planted_control_proposal_id": "Q1329",
            "target_count": 1,
            "target_policy": "one planted public target; correctness and early-hit control only",
            "workload_id": planted["workload_id"],
            "target_s3_window_schedule": WINDOW_SCHEDULE,
            "parent_input_manifest_sha256": sha(planted_path),
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
    protocol_path = HERE / "q1333_q1334_adaptive_window_protocol.json"
    protocol_content = json.dumps(protocol, indent=2) + "\n"
    protocol_digest = hashlib.sha256(protocol_content.encode()).hexdigest()
    output = [(protocol_path, protocol_content)]
    for n, proposal, parent_proposal, source_manifest in output_manifests:
        manifest = dict(source_manifest)
        manifest.update({
            "kind": "exact_native_s3_adaptive_window_input",
            "proposal_id": proposal,
            "parent_solver_proposal_id": parent_proposal,
            "target_count": 1,
            "target_s3_window_schedule": WINDOW_SCHEDULE,
            "stage_protocol_sha256": protocol_digest,
            "same_window_4096_input_manifest_sha256": sha(
                HERE / "native_inputs" / f"n{n}_batch_manifest.json"),
            "source_sha256": sha(Path(__file__)),
        })
        manifest.pop("s3_batch_size", None)
        manifest["index_s3_window_size"] = 4096
        output.append((HERE / "native_inputs" / f"n{n}_adaptive_manifest.json",
                       json.dumps(manifest, indent=2) + "\n"))

    planted_manifest = dict(planted)
    planted_manifest.update({
        "kind": "exact_native_s3_adaptive_planted_control_input",
        "proposal_id": "Q1335",
        "parent_solver_proposal_id": "Q1334",
        "parent_planted_control_proposal_id": "Q1329",
        "target_count": 1,
        "target_s3_window_schedule": WINDOW_SCHEDULE,
        "stage_protocol_sha256": protocol_digest,
        "adaptive_protocol_parent_manifest_sha256": sha(planted_path),
        "source_sha256": sha(Path(__file__)),
    })
    planted_manifest.pop("s3_batch_size", None)
    planted_manifest["index_s3_window_size"] = 4096
    output.append((HERE / "native_inputs/n83_adaptive_planted_manifest.json",
                   json.dumps(planted_manifest, indent=2) + "\n"))
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
    print(json.dumps({"status": "PASS", "proposal_ids": [
        "Q1333", "Q1334", "Q1335"], "target_count_per_run": 1,
        "target_window_schedule": WINDOW_SCHEDULE}))


if __name__ == "__main__":
    main()
