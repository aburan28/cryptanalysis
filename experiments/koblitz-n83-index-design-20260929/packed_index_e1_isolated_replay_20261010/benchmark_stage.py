#!/usr/bin/env python3
"""Adapt a frozen N83 root-index stage run to the isolated benchmark service."""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PAIR_FIELDS = (
    "curve_id", "workload_id", "factor_base_enumerated_set_sha256",
    "input_representatives_sha256", "target_count",
    "index_pair_states_examined", "index_satisfiable_s3_states",
    "index_distinct_root_keys", "root_table_slots_or_records",
    "root_table_allocated_bytes", "target_states_scanned",
    "target_state_orientations_tested", "target_partner_roots",
    "target_table_hits", "target_root_windows", "lookup_sample",
    "relation", "status", "native_s3_generator_target_control",
    "verified_single_target_dlp",
)
ARM_FIELDS = PAIR_FIELDS + (
    "index_mode", "operation_counts", "root_table_hash_probes",
    "native_source_sha256", "cargo_manifest_sha256",
    "stage_protocol_sha256",
)
MODES = ("packed_bucket22", "packed_bucket22_fastcanon")


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "manifest", "protocol", "bridge", "reps", "expected"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=MODES)
    args = parser.parse_args()

    stage = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    expected = json.loads(args.expected.read_text())
    if digest(args.reps) != stage["representatives_file_sha256"]:
        raise ValueError("representative input digest differs from the frozen manifest")
    if digest(args.bridge) != protocol["inputs_sha256"]["bridge"]:
        raise ValueError("bridge input digest differs from the frozen protocol")
    if digest(args.protocol) != stage["stage_protocol_sha256"]:
        raise ValueError("stage protocol digest differs from the frozen manifest")
    if expected["index_mode"] != args.mode:
        raise ValueError("expected result belongs to another mode")
    if expected["native_source_sha256"] != protocol["inputs_sha256"]["native_source"]:
        raise ValueError("expected result belongs to another native source")
    if stage["target_count"] != 1 or stage["pair_state_cap"] != 2_000_000:
        raise ValueError("unexpected target count or pair-state cap")

    with tempfile.TemporaryDirectory(prefix="n83-e1-isolated-") as folder:
        raw_path = Path(folder) / "native_result.json"
        command = [str(args.binary), str(args.manifest), str(args.bridge),
                   str(args.reps), str(stage["pair_state_cap"]),
                   str(stage["peak_rss_cap_mib"]), args.mode, str(raw_path)]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise RuntimeError("native stage returned exit code " + str(completed.returncode))
        raw_bytes = raw_path.read_bytes()
        result = json.loads(raw_bytes)

    mismatches = [name for name in ARM_FIELDS if result.get(name) != expected.get(name)]
    if mismatches:
        raise ValueError("frozen stage mismatch: " + ", ".join(mismatches))
    if result["native_s3_generator_target_control"]["status"] != "PASS":
        raise ValueError("native control failed")
    if result["status"] != "state_cap_no_relation":
        raise ValueError("unexpected bounded-stage status")
    if result["peak_rss_bytes"] > stage["peak_rss_cap_mib"] * (1 << 20):
        raise ValueError("stage exceeded the frozen RSS cap")
    online_ns = int(result["timing_ns"]["target_pdp_and_native_check"])
    if online_ns <= 0:
        raise ValueError("missing positive native target-stage interval")
    certificate = hashlib.sha256(canonical({name: result[name] for name in PAIR_FIELDS})).hexdigest()

    # The isolated service preserves stdout verbatim. The raw result remains
    # replayable even though the per-run temporary file is removed.
    print("raw_result_json_base64=" + base64.b64encode(raw_bytes).decode("ascii"))
    print("verified=1 stage_verified=1 online_ms={:.6f} curve_id={} workload_id={} "
          "input_sha256={} status={} indexed_states={} target_states={} "
          "pair_certificate={} native_source_sha256={} raw_result_sha256={}".format(
              online_ns / 1e6, result["curve_id"], result["workload_id"],
              result["input_representatives_sha256"], result["status"],
              result["index_pair_states_examined"], result["target_states_scanned"],
              certificate, result["native_source_sha256"], hashlib.sha256(raw_bytes).hexdigest()))


if __name__ == "__main__":
    main()
