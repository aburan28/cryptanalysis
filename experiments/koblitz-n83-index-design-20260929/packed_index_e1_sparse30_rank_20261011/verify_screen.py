#!/usr/bin/env python3
"""Verify the source-bound sparse30 capacity screen and preserved host stop."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"


def sha256(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            state.update(block)
    return state.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    stage = json.loads((HERE / "stage_manifest.json").read_text())
    candidate = json.loads((HERE / "screen_sparse30_rank16.json").read_text())
    reference = json.loads((HERE / "prior_source_sparse29_reference.json").read_text())
    candidate_guard = json.loads((HERE / "screen_sparse30_rank16.guard.json").read_text())
    interrupted = json.loads((HERE / "screen_sparse29_interruption.json").read_text())
    tests = json.loads((HERE / "test_record.json").read_text())
    report = json.loads((HERE / "screen_report.json").read_text())
    if (protocol["curve_id"] != stage["curve_id"] or
            protocol["workload_id"] != stage["workload_id"] or
            protocol["pair_state_cap"] != stage["pair_state_cap"] or
            protocol["peak_rss_cap_mib"] != stage["peak_rss_cap_mib"] or
            stage["target_count"] != 1):
        raise ValueError("frozen one-target workload differs")
    artifacts = {
        "source": HERE / "native_packed_index.rs",
        "cargo_manifest": HERE / "Cargo.toml",
        "cargo_lock": HERE / "Cargo.lock",
        "stage_manifest": HERE / "stage_manifest.json",
        "bridge": INPUTS / "n83_onb_poly_bridge.json",
        "representatives": INPUTS / "n83_x_representatives.bin",
        "candidate_screen_raw": HERE / "screen_sparse30_rank16.json",
        "prior_source_reference_raw": HERE / "prior_source_sparse29_reference.json",
        "test_record": HERE / "test_record.json",
    }
    for name, path in artifacts.items():
        if sha256(path) != protocol["input_sha256"][name]:
            raise ValueError("frozen artifact differs: " + name)
    if (candidate["index_mode"] != protocol["candidate_mode"] or
            reference["index_mode"] != protocol["reference_mode"] or
            candidate["native_source_sha256"] != protocol["input_sha256"]["source"] or
            reference["native_source_sha256"] != protocol["prior_reference_source_sha256"] or
            candidate["stage_protocol_sha256"] != stage["stage_protocol_sha256"] or
            reference["stage_protocol_sha256"] != stage["stage_protocol_sha256"]):
        raise ValueError("arm identity differs")
    fields = protocol["exact_pair_fields"]
    if len(fields) != 23 or any(candidate.get(name) != reference.get(name) for name in fields):
        raise ValueError("exact paired fields differ")
    certificate = hashlib.sha256(canonical({name: candidate[name] for name in fields})).hexdigest()
    if certificate != protocol["frozen_pair_certificate"]:
        raise ValueError("frozen pair certificate differs")
    if (candidate["lookup_sample"] != reference["lookup_sample"] or
            candidate["operation_counts"] != reference["operation_counts"] or
            candidate["native_s3_generator_target_control"]["status"] != "PASS" or
            candidate["status"] != "state_cap_no_relation" or
            candidate["peak_rss_bytes"] > protocol["peak_rss_cap_mib"] * (1 << 20)):
        raise ValueError("candidate screen correctness or memory differs")
    timing = candidate["timing_ns"]
    total = int(timing["target_pdp_and_native_check"])
    phase_sum = sum(int(timing[name]) for name in (
        "target_query_preparation", "target_partner_generation", "target_partner_check"))
    if total <= 0 or phase_sum > total:
        raise ValueError("candidate phase sum differs")
    if (candidate_guard["exit_code"] != 0 or candidate_guard["guard_stop"] is not None or
            not candidate_guard["raw_result_exists"] or
            candidate_guard["source_sha256"] != protocol["input_sha256"]["source"] or
            interrupted["guard_stop"] != "system_volume_below_1GB" or
            interrupted["raw_result_exists"] or
            tests["status"] != "PASS" or
            tests["source_sha256"] != protocol["input_sha256"]["source"] or
            tests["stdout_sha256"] != sha256(HERE / "test.stdout.txt") or
            tests["stderr_sha256"] != sha256(HERE / "test.stderr.txt") or
            report["controlled_wall_speedup"] is not None):
        raise ValueError("screen guard, test, or status differs")
    print(json.dumps({"status": "CANDIDATE_FULL_CAPACITY_EXACT",
                      "workload_id": protocol["workload_id"],
                      "exact_fields": len(fields),
                      "pair_certificate": certificate,
                      "candidate_root_probes": candidate["root_table_hash_probes"]["target_lookup"],
                      "prior_reference_root_probes": reference["root_table_hash_probes"]["target_lookup"],
                      "samebinary_reference_status": "HOST_DISK_GUARD_STOP",
                      "controlled_wall_speedup": None}, sort_keys=True))


if __name__ == "__main__":
    main()
