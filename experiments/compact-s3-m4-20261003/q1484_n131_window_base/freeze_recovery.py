#!/usr/bin/env python3
"""Freeze Q1484 R2 checkpoint replay, source, and checked runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R1 = HERE / "runs" / "r1"
OUT = HERE / "recovery_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render() -> dict:
    design = json.loads((HERE / "design_recovery.json").read_text())
    parent = json.loads((HERE / "protocol.json").read_text())
    failure = json.loads((R1 / "failure.json").read_text())
    progress = [json.loads(line) for line in (R1 /
        "progress.jsonl").read_text().splitlines()]
    preflight = json.loads((HERE / "r2_preflight.json").read_text())
    runtime = json.loads((HERE / "r2_sage_runtime_info.json").read_text())
    assert design["proposal_id"] == parent["proposal_id"] == (
        failure["proposal_id"]) == preflight["proposal_id"] == "Q1484"
    assert design["attempt_id"] == preflight["attempt_id"] == "Q1484R2"
    assert parent["curve_id"] == design["curve_id"] == failure["curve_id"]
    assert failure["status"] == "infrastructure_failure"
    assert preflight["status"] == "PASS"
    assert runtime["status"] == "verified"
    assert preflight["r2_enumerator_source_sha256"] == sha(
        HERE / "enumerate_n131_r2.py")
    assert preflight["source_sha256"] == sha(
        HERE / "preflight_recovery.py")
    assert preflight["runtime_info_sha256"] == sha(
        HERE / "r2_sage_runtime_info.json")
    assert preflight["r1_failure_sha256"] == sha(R1 / "failure.json")
    assert preflight["r1_partial_bitmap_sha256"] == sha(R1 /
                                                        "status_flags.partial")
    checkpoint = failure["durable_checkpoint_processed_raw_x_orbits"]
    keys = failure["durable_checkpoint_unique_projected_orbits_so_far"]
    assert progress[-1]["processed_raw_x_orbits"] == checkpoint
    assert progress[-1]["unique_projected_orbits_so_far"] == keys
    assert preflight["r1_prefix_raw_orbits"] == checkpoint
    assert (R1 / "status_flags.partial").stat().st_size == checkpoint // 4
    assert checkpoint < parent["raw_x_orbits_formula"]
    assert design["limits"]["max_wall_seconds"] == parent["limits"][
        "max_wall_seconds"]
    assert design["limits"]["max_peak_rss_bytes"] == parent["limits"][
        "max_peak_rss_bytes"]
    assert design["limits"]["progress_interval_raw_orbits"] == parent[
        "limits"]["progress_interval_raw_orbits"]
    return {
        "kind": "q1484_frozen_r2_checkpoint_replay",
        "proposal_id": "Q1484", "attempt_id": "Q1484R2",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"],
        "nominal_window_dimension_d": 27,
        "raw_x_orbits_formula": parent["raw_x_orbits_formula"],
        "actual_usable_B": None, "folded_K": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_recovery_sha256": sha(HERE / "design_recovery.json"),
        "parent_protocol_sha256": sha(HERE / "protocol.json"),
        "parent_enumerator_source_sha256": sha(HERE /
                                                "enumerate_n131.py"),
        "r1_failure_sha256": sha(R1 / "failure.json"),
        "r1_progress_sha256": sha(R1 / "progress.jsonl"),
        "r1_partial_bitmap_sha256": sha(R1 / "status_flags.partial"),
        "r1_checkpoint_processed_raw_x_orbits": checkpoint,
        "r1_checkpoint_unique_projected_orbits": keys,
        "r2_source_sha256": sha(HERE / "enumerate_n131_r2.py"),
        "r2_auditor_source_sha256": sha(HERE / "verify_archive_r2.py"),
        "r2_preflight_source_sha256": sha(HERE /
                                          "preflight_recovery.py"),
        "r2_preflight_sha256": sha(HERE / "r2_preflight.json"),
        "runtime_info_sha256": sha(HERE /
                                   "r2_sage_runtime_info.json"),
        "freeze_source_sha256": sha(Path(__file__)),
        "scratch_realpath": "/private/tmp/q1484-n131-r2-20261007",
        "limits": design["limits"],
        "claim_scope": design["claim_scope"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = render()
    if args.check:
        assert result == json.loads(OUT.read_text())
    else:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"attempt_id": "Q1484R2",
                      "checkpoint": result[
                          "r1_checkpoint_processed_raw_x_orbits"],
                      "status": "checked" if args.check else "frozen"},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
