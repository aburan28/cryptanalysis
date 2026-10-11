#!/usr/bin/env python3
"""Measure Q1461 one-target native lookup after frozen reusable preparation."""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMP = Path("/private/tmp/q1461_n53_target")
PAIR = HERE.parent / "q20261011_n53_native_pair"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "native_measurement.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    public = json.loads((HERE / "public_target.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert public["workload_id"] == freeze["workload_id"]
    assert sha(HERE / "public_target.json") == freeze["public_target_sha256"]
    binary = Path(build["binary_path"])
    assert sha(binary) == build["binary_sha256"]
    for name, record in exported["files"].items():
        if name == "queries.bin":
            continue
        assert sha(TEMP / name) == record["sha256"]
    assert sha(TEMP / "queries.bin") == freeze["query_file_sha256"]
    target = public["target_onb_xy"]
    command = [str(binary), str(TEMP), format(target[0], "x"),
               format(target[1], "x"), str(protocol["factor_base_actual_B"]),
               str(protocol["factor_base_folded_columns_K"]),
               str(protocol["point_decomposition"]["target_query_cap"]),
               str(protocol["point_decomposition"]["table_states"]),
               str(protocol["limits"]["native_wall_seconds"])]
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(command, capture_output=True,
                                timeout=protocol["limits"]["external_wall_seconds"])
        timed_out = False
        stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout, stderr, returncode = error.stdout or b"", error.stderr or b"", None
    launcher_wall_ns = time.perf_counter_ns() - started
    (HERE / "native_raw.json").write_bytes(stdout)
    (HERE / "native_stderr.txt").write_bytes(stderr)
    data = None
    if not timed_out and returncode == 0:
        data = json.loads(stdout)
        assert data["status"] in ("first_match", "completed_query_cap",
                                  "wall_cap_during_queries", "wall_cap_during_table")
        assert data["table_states_generated"] <= protocol["point_decomposition"]["table_states"]
        assert data["query_samples_processed"] <= protocol["point_decomposition"]["target_query_cap"]
        assert data["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    output = {"proposal_id": "Q1461", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "workload_id": public["workload_id"],
              "public_target_onb_xy": target,
              "status": data["status"] if data is not None else "PRODUCER_FAILURE",
              "native": data, "timed_out": timed_out, "return_code": returncode,
              "launcher_wall_ns_exploratory": launcher_wall_ns,
              "freeze_sha256": sha(HERE / "freeze.json"),
              "build_receipt_sha256": sha(HERE / "build_receipt.json"),
              "public_target_sha256": sha(HERE / "public_target.json"),
              "raw_sha256": sha(HERE / "native_raw.json"),
              "stderr_sha256": sha(HERE / "native_stderr.txt"),
              "runner_sha256": sha(Path(__file__)),
              "charged_pair_add_attempts": (data["table_states_generated"] +
                    2 * data["query_samples_processed"] -
                    data["query_skipped_identity_pairs"]) if data is not None else None,
              "target_query_pair_add_attempts": (
                    2 * data["query_samples_processed"] -
                    data["query_skipped_identity_pairs"]) if data is not None else None,
              "single_target_online_ns": None,
              "complete_solve_work_log2": None}
    (HERE / "native_measurement.json").write_text(json.dumps(output, indent=2,
                                                            sort_keys=True) + "\n")
    print("Q1461", output["status"],
          data["query_samples_processed"] if data is not None else None,
          len(data["matches"]) if data is not None else 0)


if __name__ == "__main__":
    main()
