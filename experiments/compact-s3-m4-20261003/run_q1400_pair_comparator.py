#!/usr/bin/env python3
"""Run one bounded ordinary Q1325-base native quotient-pair comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_BASE = Path("/private/tmp/q1400_n83_q1325_pair_base.bin")
RECEIPT = HERE / "runs/n83_q1400_pair_comparator.json"
STDOUT = HERE / "runs/n83_q1400_pair_comparator.stdout.txt"
STDERR = HERE / "runs/n83_q1400_pair_comparator.stderr.txt"
CHECKED_SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check(base: Path) -> tuple[dict, dict, dict]:
    protocol_path = HERE / "q1400_pair_protocol.json"
    input_path = HERE / "native_inputs/n83_q1400_pair_manifest.json"
    build_path = HERE / "native_q1400_pair_build_receipt.json"
    q1325_path = HERE / "q1325_protocol.json"
    s3_path = HERE / "runs/n83_batch_root_capped_2m.json"
    protocol = json.loads(protocol_path.read_text())
    inputs = json.loads(input_path.read_text())
    build = json.loads(build_path.read_text())
    q1325 = json.loads(q1325_path.read_text())
    s3 = json.loads(s3_path.read_text())
    assert protocol["proposal_id"] == inputs["proposal_id"] == build[
        "proposal_id"] == "Q1400"
    assert protocol["candidate_id"] is inputs["candidate_id"] is build[
        "candidate_id"] is None
    assert protocol["run_id"] is inputs["run_id"] is build["run_id"] is None
    assert protocol["isogeny"] == inputs["isogeny"] == build[
        "isogeny"] == "none"
    assert protocol["curve_id"] == inputs["curve_id"] == build[
        "curve_id"] == q1325["curve"]["curve_id"] == s3["curve_id"]
    assert protocol["workload_id"] == inputs["workload_id"] == q1325[
        "ordinary_workload_id"] == s3["workload_id"]
    assert protocol["factor_base_actual_B"] == inputs[
        "actual_usable_points_B"] == s3["actual_usable_points_B"]
    assert protocol["factor_base_folded_columns_K"] == inputs[
        "folded_columns_K"] == s3["folded_columns_K"]
    assert protocol["factor_base_enumerated_set_sha256"] == inputs[
        "factor_base_enumerated_set_sha256"] == s3[
            "factor_base_enumerated_set_sha256"]
    assert protocol["checks"]["native_input_manifest_sha256"] == sha(input_path)
    assert protocol["checks"]["q1325_protocol_sha256"] == sha(q1325_path)
    assert protocol["checks"]["input_exporter_sha256"] == sha(
        HERE / "export_q1400_pair_inputs.py")
    assert build["stage_protocol_sha256"] == sha(protocol_path)
    assert build["native_source_sha256"] == sha(
        HERE / "native_q1400_pair_comparator.cpp")
    assert build["binary_sha256"] == sha(Path(build["binary_path"]))
    assert inputs["base_binary_sha256"] == sha(base)
    assert inputs["base_binary_bytes"] == base.stat().st_size
    assert inputs["checked_sage_runtime_info_sha256"] == sha(
        HERE / "q1400_sage_runtime_info.json")
    assert s3["status"] == "state_cap_no_relation"
    return protocol, inputs, build


def check_saved(base: Path) -> None:
    protocol, inputs, build = load_and_check(base)
    report = json.loads(RECEIPT.read_text())
    assert report["stage_protocol_sha256"] == sha(HERE / "q1400_pair_protocol.json")
    assert report["input_manifest_sha256"] == sha(
        HERE / "native_inputs/n83_q1400_pair_manifest.json")
    assert report["native_build_receipt_sha256"] == sha(
        HERE / "native_q1400_pair_build_receipt.json")
    assert report["matched_s3_stage_receipt_sha256"] == sha(
        HERE / "runs/n83_batch_root_capped_2m.json")
    assert report["raw_stdout_sha256"] == sha(STDOUT)
    assert report["raw_stderr_sha256"] == sha(STDERR)
    assert report["source_sha256"] == sha(Path(__file__))
    assert report["curve_id"] == inputs["curve_id"] == protocol["curve_id"]
    assert report["workload_id"] == inputs["workload_id"]
    assert report["binary_sha256"] == build["binary_sha256"]
    assert report["candidate_id"] is report["run_id"] is None
    assert report["verified_single_target_dlp"] is False
    assert report["complete_work_log2"] is None
    if report["native_output"] is not None:
        native = json.loads(STDOUT.read_text())
        assert native == report["native_output"]
        assert native["actual_B"] == protocol["factor_base_actual_B"]
        assert native["table_descriptors"] == protocol[
            "point_decomposition"]["table_descriptors"]
        assert native["query_representatives"] == protocol[
            "point_decomposition"]["query_representatives"]
    print(f"PASS {RECEIPT}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    base = args.base.resolve()
    if args.check:
        check_saved(base)
        return
    assert not RECEIPT.exists() and not STDOUT.exists() and not STDERR.exists(), (
        "refusing to overwrite a frozen run")

    # Reproduce the target-independent base conversion through the checked
    # launcher before the measured native workload. This interval is separate.
    export_command = [str(CHECKED_SAGE), "-python",
                      str(HERE / "export_q1400_pair_inputs.py"),
                      "--base-output", str(base), "--check"]
    export_started = time.perf_counter_ns()
    export = subprocess.run(export_command, capture_output=True, text=True,
                            timeout=90, check=False)
    export_ns = time.perf_counter_ns() - export_started
    assert export.returncode == 0, export.stderr
    protocol, inputs, build = load_and_check(base)
    pdp = protocol["point_decomposition"]
    binary = Path(build["binary_path"])
    command = [
        str(binary), str(base),
        *inputs["ordinary_public_target_onb_hex"],
        str(pdp["table_descriptors"]), str(pdp["query_representatives"]),
        str(pdp["table_batch"]), str(pdp["table_step"]),
        str(pdp["table_offset"]), str(pdp["query_step"]),
        str(pdp["query_offset"]), str(pdp["bloom_bits_per_key"]),
        str(pdp["bloom_hashes"]), str(pdp["table_start"]),
        str(pdp["query_start"]), str(pdp["query_workers"]),
        str(pdp["representative_batch"]),
    ]
    wall_started = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["limits"]["external_wall_seconds"], check=False)
        process_wall_ns = time.perf_counter_ns() - wall_started
        stdout, stderr, returncode = (completed.stdout, completed.stderr,
                                      completed.returncode)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        process_wall_ns = time.perf_counter_ns() - wall_started
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        returncode = None
        timed_out = True
    STDOUT.write_text(stdout)
    STDERR.write_text(stderr)
    native = None
    invalid_native_output = False
    if not timed_out and returncode == 0:
        try:
            native = json.loads(stdout)
            invalid_native_output = not all((
                native.get("actual_B") == inputs["actual_usable_points_B"],
                native.get("table_descriptors") == pdp["table_descriptors"],
                native.get("query_representatives") == pdp[
                    "query_representatives"],
                native.get("lifted_query_pairs") == pdp[
                    "lifted_signed_query_pairs"],
                native.get("query_workers") == pdp["query_workers"],
                isinstance(native.get("peak_rss_bytes"), int),
                isinstance(native.get("exact_hit_keys"), int),
            ))
        except (json.JSONDecodeError, TypeError):
            invalid_native_output = True
    status = ("timeout" if timed_out else
              "native_error" if returncode != 0 else
              "invalid_native_output" if invalid_native_output else
              "rss_cap_exceeded" if native["peak_rss_bytes"] >
                  protocol["limits"]["peak_rss_cap_mib"] * 1024 * 1024 else
              "native_exact_hit_unverified" if native["exact_hit_keys"] else
              "no_exact_hit_at_cap")
    report = {
        "kind": "q1400_matched_q1325_native_pair_stage_run",
        "proposal_id": "Q1400",
        "candidate_id": None,
        "run_id": None,
        "curve_id": inputs["curve_id"],
        "workload_id": inputs["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": inputs["actual_usable_points_B"],
        "factor_base_folded_columns_K": inputs["folded_columns_K"],
        "factor_base_enumerated_set_sha256": inputs[
            "factor_base_enumerated_set_sha256"],
        "status": status,
        "native_returncode": returncode,
        "base_export_wall_ns_including_checked_launcher": export_ns,
        "process_wall_ns_including_native_launch": process_wall_ns,
        "native_output": native,
        "table_descriptors_charged": (native["table_descriptors"]
                                      if native else None),
        "target_lifted_pair_queries_charged": (native["lifted_query_pairs"]
                                               if native else None),
        "target_online_seconds_exploratory": (
            native["query_seconds"] + native["exact_replay_seconds"]
            if native else None),
        "peak_rss_bytes": native["peak_rss_bytes"] if native else None,
        "verified_relation_count": 0,
        "natural_relation_yield_rate_estimate": None,
        "field_operation_equivalent_cost": None,
        "cost_per_useful_relation": None,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "comparison_scope": "same exact curve, Q1325 base and ordinary public point as Q1331; pair schedule and 4 GiB RSS cap differ, so wall ratio is not a controlled speedup",
        "command": command,
        "raw_stdout_sha256": sha(STDOUT),
        "raw_stderr_sha256": sha(STDERR),
        "stage_protocol_sha256": sha(HERE / "q1400_pair_protocol.json"),
        "input_manifest_sha256": sha(
            HERE / "native_inputs/n83_q1400_pair_manifest.json"),
        "native_build_receipt_sha256": sha(
            HERE / "native_q1400_pair_build_receipt.json"),
        "matched_s3_stage_receipt_sha256": sha(
            HERE / "runs/n83_batch_root_capped_2m.json"),
        "checked_sage_runtime_info_sha256": sha(
            HERE / "q1400_sage_runtime_info.json"),
        "binary_sha256": build["binary_sha256"],
        "source_sha256": sha(Path(__file__)),
    }
    RECEIPT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "process_wall_ns": process_wall_ns,
                      "native": native and {key: native[key] for key in (
                          "exact_hit_keys", "query_seconds", "peak_rss_bytes")}}))


if __name__ == "__main__":
    main()
