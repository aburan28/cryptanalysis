#!/usr/bin/env python3
"""Run the Q1401 planted positive control without passing witness metadata."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from run_q1400_pair_comparator import DEFAULT_BASE, HERE, load_and_check


OUT = HERE / "runs/n83_q1401_pair_planted_native.json"
STDOUT = HERE / "runs/n83_q1401_pair_planted_native.stdout.txt"
STDERR = HERE / "runs/n83_q1401_pair_planted_native.stderr.txt"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not OUT.exists() and not STDOUT.exists() and not STDERR.exists(), (
        "refusing to overwrite a frozen run")
    base = DEFAULT_BASE.resolve()
    q1400, inputs, build = load_and_check(base)
    protocol_path = HERE / "q1401_pair_control_protocol.json"
    fixture_path = HERE / "runs/n83_q1401_pair_planted_fixture.json"
    protocol = json.loads(protocol_path.read_text())
    fixture = json.loads(fixture_path.read_text())
    assert protocol["proposal_id"] == fixture["proposal_id"] == "Q1401"
    assert protocol["candidate_id"] is fixture["candidate_id"] is None
    assert protocol["run_id"] is fixture["run_id"] is None
    assert protocol["isogeny"] == fixture["isogeny"] == "none"
    assert protocol["curve_id"] == fixture["curve_id"] == inputs["curve_id"]
    assert protocol["workload_id"] == fixture["workload_id"]
    assert protocol["planted_fixture_sha256"] == sha(fixture_path)
    assert protocol["fixture_source_sha256"] == sha(
        HERE / "make_q1401_pair_control.py")
    assert protocol["q1400_stage_protocol_sha256"] == sha(
        HERE / "q1400_pair_protocol.json")
    assert protocol["q1400_native_build_receipt_sha256"] == sha(
        HERE / "native_q1400_pair_build_receipt.json")
    assert protocol["factor_base_enumerated_set_sha256"] == inputs[
        "factor_base_enumerated_set_sha256"]
    pdp = q1400["point_decomposition"]
    # The native command receives the public target and base, never the
    # table/query witness fields stored in the fixture for later replay.
    command = [
        build["binary_path"], str(base),
        *fixture["target_onb_coordinate_hex"],
        str(pdp["table_descriptors"]), str(pdp["query_representatives"]),
        str(pdp["table_batch"]), str(pdp["table_step"]),
        str(pdp["table_offset"]), str(pdp["query_step"]),
        str(pdp["query_offset"]), str(pdp["bloom_bits_per_key"]),
        str(pdp["bloom_hashes"]), str(pdp["table_start"]),
        str(pdp["query_start"]), str(pdp["query_workers"]),
        str(pdp["representative_batch"]),
    ]
    started = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["limits"]["external_wall_seconds"], check=False)
        wall_ns = time.perf_counter_ns() - started
        stdout, stderr, returncode = (completed.stdout, completed.stderr,
                                      completed.returncode)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        wall_ns = time.perf_counter_ns() - started
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        returncode = None
        timed_out = True
    STDOUT.write_text(stdout)
    STDERR.write_text(stderr)
    native = None
    if not timed_out and returncode == 0:
        try:
            native = json.loads(stdout)
        except json.JSONDecodeError:
            pass
    status = ("timeout" if timed_out else
              "native_error" if returncode != 0 else
              "invalid_native_output" if native is None else
              "rss_cap_exceeded" if native["peak_rss_bytes"] >
                  protocol["limits"]["peak_rss_cap_mib"] * 1024 * 1024 else
              "native_hit_pending_independent_replay" if native[
                  "exact_hit_keys"] > 0 else
              "positive_control_failed_no_hit")
    report = {
        "kind": "q1401_q1325_native_pair_planted_control_run",
        "proposal_id": "Q1401",
        "parent_solver_proposal_id": "Q1400",
        "candidate_id": None,
        "run_id": None,
        "curve_id": fixture["curve_id"],
        "workload_id": fixture["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": inputs["actual_usable_points_B"],
        "factor_base_folded_columns_K": inputs["folded_columns_K"],
        "factor_base_enumerated_set_sha256": inputs[
            "factor_base_enumerated_set_sha256"],
        "status": status,
        "native_returncode": returncode,
        "process_wall_ns_including_native_launch": wall_ns,
        "native_output": native,
        "is_natural_relation_yield_measurement": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "command": command,
        "raw_stdout_sha256": sha(STDOUT),
        "raw_stderr_sha256": sha(STDERR),
        "stage_protocol_sha256": sha(protocol_path),
        "planted_fixture_sha256": sha(fixture_path),
        "q1400_input_manifest_sha256": sha(
            HERE / "native_inputs/n83_q1400_pair_manifest.json"),
        "q1400_native_build_receipt_sha256": sha(
            HERE / "native_q1400_pair_build_receipt.json"),
        "binary_sha256": build["binary_sha256"],
        "source_sha256": sha(Path(__file__)),
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status,
                      "native_exact_hit_keys": native and native[
                          "exact_hit_keys"], "process_wall_ns": wall_ns}))


if __name__ == "__main__":
    main()
