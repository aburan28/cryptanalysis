#!/usr/bin/env python3
"""Verify and seal the complete N83 W4 geometry/replay run artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_full_w4_protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run: Path) -> None:
    run = run.resolve()
    protocol = json.loads(PROTOCOL.read_text())
    started = json.loads((run / "started.json").read_text())
    geometry = json.loads((run / "geometry.json").read_text())
    replay = json.loads((run / "sage_replay.json").read_text())
    assert started["protocol_sha256"] == geometry["protocol_sha256"] == sha(PROTOCOL)
    assert started["source_sha256"] == geometry["source_sha256"] == sha(HERE / "sage_measure_n83_full_w4.py")
    assert geometry["helper_source_sha256"] == sha(HERE / "sage_measure_n83_next_geometry.py")
    assert geometry["status"] == "EXACT_GEOMETRY_PASS" and replay["status"] == "PASS"
    assert geometry["curve_id"] == replay["curve_id"] == protocol["curve_id"]
    assert replay["geometry_sha256"] == sha(run / "geometry.json")
    assert replay["representatives_sha256"] == sha(run / "representatives.json")
    assert replay["replay_source_sha256"] == sha(HERE / "sage_replay_n83_full_w4.py")
    assert replay["projected_point_set_sha256"] == geometry["projected_point_set_sha256"]
    assert replay["normal_basis_rank"] == 83
    assert replay["w4_mask_orbits_replayed"] == geometry["w4_mask_orbits"] == 22140
    final = geometry["checkpoints"][-1]
    assert replay["actual_usable_projected_points_B"] == final["actual_usable_projected_points_B"] == 1936390
    assert replay["effective_signed_frobenius_columns"] == final["effective_signed_frobenius_columns"] == 11665
    assert geometry["w4_duplicate_projected_orbits"] == geometry["w4_identity_projections"] == 0
    producer_out = json.loads((run / "producer.stdout.txt").read_text())
    replay_out = json.loads((run / "replay.stdout.txt").read_text())
    assert producer_out["status"] == "EXACT_GEOMETRY_PASS"
    assert replay_out["status"] == "PASS"
    assert (run / "producer.stderr.txt").read_bytes() == b""
    assert (run / "replay.stderr.txt").read_bytes() == b""
    assert geometry["timing_ms_exploratory"]["whole_sage_process_from_main"] < 1000 * protocol["external_wall_limit_seconds"]
    assert replay["replay_wall_ms"] < 1000 * protocol["external_wall_limit_seconds"]
    files = sorted(path.name for path in run.iterdir() if path.is_file() and path.name != "receipt.json")
    run_arg = "experiments/hamming-ic-e2e-20260929/runs/n83_full_w4_geometry_v1"
    command_prefix = ["/opt/homebrew/bin/timeout", str(protocol["external_wall_limit_seconds"]),
                      "/Volumes/SSD990/cryptanalysis/sage", "-python"]
    receipt = {
        "schema_version": 1,
        "kind": "n83_complete_w4_geometry_receipt",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "candidate_id": None,
        "producer_exit_code": 0,
        "replay_exit_code": 0,
        "external_wall_limit_seconds_per_job": protocol["external_wall_limit_seconds"],
        "environment": {"TMPDIR": "/Volumes/SSD990/llm/tmp"},
        "producer_argv": command_prefix + [
            "experiments/hamming-ic-e2e-20260929/sage_measure_n83_full_w4.py", run_arg],
        "replay_argv": command_prefix + [
            "experiments/hamming-ic-e2e-20260929/sage_replay_n83_full_w4.py", run_arg],
        "receipt_source_sha256": sha(Path(__file__)),
        "file_sha256": {name: sha(run / name) for name in files},
        "claim_boundary": protocol["claim_boundary"],
    }
    (run / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "files": len(files)}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: finalize_n83_full_w4.py run_directory")
    main(Path(sys.argv[1]))
