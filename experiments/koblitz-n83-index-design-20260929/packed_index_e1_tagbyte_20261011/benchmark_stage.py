#!/usr/bin/env python3
"""Replay either N83 sparse28 arm and verify the frozen full-capacity target stage."""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "packed_index_e1_sparse28_capacity_20261011"
MODES = ("packed_sparse28_compact16_cachedxy",
         "packed_sparse28_tagbyte_cachedxy")
PAIR_FIELDS = (
    "curve_id", "workload_id", "factor_base_enumerated_set_sha256",
    "input_representatives_sha256", "target_count",
    "index_pair_states_examined", "index_satisfiable_s3_states",
    "index_distinct_root_keys", "root_table_slots_or_records",
    "target_states_scanned", "target_states_prepared",
    "target_state_orientations_prepared", "target_state_orientations_tested",
    "target_partner_roots", "target_table_hits", "target_root_windows",
    "lookup_sample", "partner_audit_pairs", "relation", "status",
    "native_s3_generator_target_control", "verified_single_target_dlp",
    "operation_counts",
)


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
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bridge", required=True, type=Path)
    parser.add_argument("--reps", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=MODES)
    args = parser.parse_args()
    stage = json.loads(args.manifest.read_text())
    reference = json.loads((BASE / "run_2_sparse28.json").read_text())
    parent = json.loads((BASE / "protocol.json").read_text())
    if (stage["target_count"] != 1 or stage["pair_state_cap"] != 29_900_000 or
            stage["peak_rss_cap_mib"] != 5500 or
            stage["workload_id"] != "63dd0929cf33" or
            reference["index_mode"] != MODES[0]):
        raise ValueError("unexpected full-capacity workload or reference")
    if digest(args.manifest) != parent["input_sha256"]["stage_manifest"]:
        raise ValueError("stage manifest digest changed")
    if digest(args.bridge) != parent["input_sha256"]["bridge"]:
        raise ValueError("bridge digest changed")
    if digest(args.reps) != parent["input_sha256"]["representatives"]:
        raise ValueError("representative digest changed")
    source_sha256 = digest(HERE / "native_packed_index.rs")
    cargo_sha256 = digest(HERE / "Cargo.toml")
    with tempfile.TemporaryDirectory(prefix="n83-e1-tagbyte-") as folder:
        raw_path = Path(folder) / "native_result.json"
        command = [str(args.binary), str(args.manifest), str(args.bridge),
                   str(args.reps), "29900000", "5500", args.mode, str(raw_path)]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise RuntimeError("native stage returned exit code " +
                               str(completed.returncode))
        raw_bytes = raw_path.read_bytes()
    result = json.loads(raw_bytes)
    mismatches = [name for name in PAIR_FIELDS
                  if result.get(name) != reference.get(name)]
    if mismatches:
        raise ValueError("full-capacity correctness mismatch: " +
                         ", ".join(mismatches))
    if (result["native_source_sha256"] != source_sha256 or
            result["cargo_manifest_sha256"] != cargo_sha256 or
            result["index_mode"] != args.mode or
            result["native_s3_generator_target_control"]["status"] != "PASS" or
            result["peak_rss_bytes"] > 5500 * (1 << 20)):
        raise ValueError("source, mode, control, or memory receipt differs")
    tag_bytes = result["root_table_tag_byte_allocated_bytes"]
    if (args.mode == MODES[0] and tag_bytes != 0 or
            args.mode == MODES[1] and tag_bytes == 0):
        raise ValueError("sidecar allocation differs from selected mode")
    timing = result["timing_ns"]
    online_ns = int(timing["target_pdp_and_native_check"])
    phase_ns = sum(int(timing[name]) for name in
                   ("target_query_preparation", "target_partner_generation",
                    "target_partner_check"))
    if online_ns <= 0 or phase_ns > online_ns:
        raise ValueError("target-stage timing interval is incomplete")
    certificate = hashlib.sha256(canonical(
        {name: result[name] for name in PAIR_FIELDS})).hexdigest()
    print("raw_result_json_base64=" + base64.b64encode(raw_bytes).decode("ascii"))
    print("verified=1 stage_verified=1 online_ms={:.6f} curve_id={} workload_id={} "
          "input_sha256={} status={} indexed_states={} target_states={} "
          "pair_certificate={} native_source_sha256={} raw_result_sha256={}".format(
              online_ns / 1e6, result["curve_id"], result["workload_id"],
              result["input_representatives_sha256"], result["status"],
              result["index_pair_states_examined"], result["target_states_scanned"],
              certificate, result["native_source_sha256"],
              hashlib.sha256(raw_bytes).hexdigest()))


if __name__ == "__main__":
    main()
