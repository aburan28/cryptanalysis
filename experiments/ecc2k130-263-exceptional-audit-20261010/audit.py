#!/usr/bin/env python3
"""Check source identity, route binding, and every semantic replay field."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs" / "R1"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925"
TIMING = {"construction_wall_seconds", "forward_kernel_wall_seconds",
          "dual_kernel_wall_seconds", "total_wall_seconds"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = json.loads((HERE / "FROZEN.json").read_text())
    status = json.loads((RUN / "status.json").read_text())
    assert status["frozen_sha256"] == sha256(HERE / "FROZEN.json")
    assert status["runner_sha256"] == sha256(HERE / "run.py")
    for name, expected in frozen["source_sha256"].items():
        assert sha256(ROOT / name) == expected, name
    for label in ("runtime", "static", "sage"):
        step = status["steps"][label]
        assert step["status"] == "completed" and step["exit_code"] == 0, label
        for stream in ("stdout", "stderr"):
            assert step[f"{stream}_sha256"] == sha256(RUN / f"{label}.{stream}"), label
    assert status["sage_receipt_sha256"] == sha256(RUN / "sage_receipt.json")
    runtime = json.loads((RUN / "runtime.stdout").read_text())
    assert runtime, "checked Sage runtime receipt is empty"
    static = json.loads((RUN / "static.stdout").read_text())
    assert static["route_id"] == frozen["route_id"]
    assert static["artifact_hashes_match"] is True
    archived = json.loads((ROUTE / "ecc2k130_degree263_exceptional_replay.json").read_text())
    replay = json.loads((RUN / "sage_receipt.json").read_text())
    assert set(archived) == set(replay)
    assert {k: v for k, v in replay.items() if k not in TIMING} == {
        k: v for k, v in archived.items() if k not in TIMING}
    assert replay["status"] == "verified" and replay["candidate_id"] is None
    assert replay["forward_nonzero_kernel_points_mapped_to_infinity"] == frozen[
        "expected_forward_nonzero_kernel_points"]
    assert replay["dual_nonzero_kernel_points_mapped_to_infinity"] == frozen[
        "expected_reverse_nonzero_kernel_points"]
    assert replay["source_infinity_to_target_infinity"]
    assert replay["target_infinity_to_dual_infinity"]
    assert replay["rational_order_two_composition"]
    assert replay["ordinary_subgroup_wrapper_and_dual_composition"]
    assert replay["ordinary_quadratic_extension_wrapper_agrees"]
    print(json.dumps({
        "status": "PASS_SEMANTIC_REPLAY",
        "route_id": frozen["route_id"],
        "forward_kernel_points": replay["forward_nonzero_kernel_points_mapped_to_infinity"],
        "dual_kernel_points": replay["dual_nonzero_kernel_points_mapped_to_infinity"],
        "archived_receipt_sha256": sha256(ROUTE / "ecc2k130_degree263_exceptional_replay.json"),
        "replay_receipt_sha256": sha256(RUN / "sage_receipt.json"),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
