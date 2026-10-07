#!/usr/bin/env python3
"""Archive the Q1484 R1 ENOSPC failure from its durable checkpoint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "r1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1484"
    rows = [json.loads(line) for line in (RUN / "progress.jsonl").read_text(
        ).splitlines()]
    assert rows and all(rows[i]["processed_raw_x_orbits"] ==
                        (i + 1) * protocol["limits"][
                            "progress_interval_raw_orbits"]
                        for i in range(len(rows)))
    checkpoint = rows[-1]
    flags = RUN / "status_flags.partial"
    expected_bytes = checkpoint["processed_raw_x_orbits"] // 4
    assert flags.stat().st_size == expected_bytes
    assert not (RUN / "status_flags.bin").exists()
    assert not (RUN / "receipt.json").exists()
    # The final attempted chunk was not acknowledged in progress.jsonl.
    # Its in-memory state and operation counts are not recoverable.
    record = {
        "kind": "q1484_r1_postmortem_infrastructure_failure",
        "proposal_id": "Q1484", "attempt_id": "Q1484R1",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": protocol["curve_id"],
        "status": "infrastructure_failure",
        "observed_error": "OSError: [Errno 28] No space left on device",
        "observed_failure_site": "enumerate_n131.py emit_progress: status_flags.partial write",
        "process_exit_code": 1,
        "durable_checkpoint_processed_raw_x_orbits": checkpoint[
            "processed_raw_x_orbits"],
        "durable_checkpoint_unique_projected_orbits_so_far": checkpoint[
            "unique_projected_orbits_so_far"],
        "durable_checkpoint_elapsed_seconds_exploratory": checkpoint[
            "elapsed_seconds_exploratory"],
        "partial_status_bitmap_bytes": expected_bytes,
        "partial_status_bitmap_sha256": sha(flags),
        "progress_jsonl_sha256": sha(RUN / "progress.jsonl"),
        "protocol_sha256": sha(protocol_path),
        "source_sha256": sha(HERE / "enumerate_n131.py"),
        "record_source_sha256": sha(Path(__file__)),
        "record_provenance": "postmortem from captured traceback and durable files; not emitted by failed process",
        "actual_usable_B": None, "folded_K": None,
        "enumerated_set_sha256": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    output = RUN / "failure.json"
    assert not output.exists(), "refuse overwrite"
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": record["status"],
                      "checkpoint": expected_bytes * 4,
                      "sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
