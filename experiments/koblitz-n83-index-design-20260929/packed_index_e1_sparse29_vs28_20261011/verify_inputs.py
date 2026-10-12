#!/usr/bin/env python3
"""Verify the frozen same-source sparse28/sparse29 N83 stage inputs."""

import hashlib
import json
from pathlib import Path

from benchmark_stage import PAIR_FIELDS, canonical, digest

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"


def load(path):
    return json.loads(path.read_text())


def verify():
    protocol = load(HERE / "comparison_protocol.json")
    tier = load(HERE / "tier1_protocol.json")
    stage = load(HERE / "stage_manifest.json")
    reference = load(HERE / "screen_sparse28.json")
    candidate = load(HERE / "screen_sparse29.json")
    record = load(HERE / "screen_sparse29.record.json")
    tests = load(HERE / "test_record.json")
    sources = {
        "source": HERE / "native_packed_index.rs",
        "cargo_manifest": HERE / "Cargo.toml",
        "cargo_lock": HERE / "Cargo.lock",
        "stage_manifest": HERE / "stage_manifest.json",
        "bridge": INPUTS / "n83_onb_poly_bridge.json",
        "representatives": INPUTS / "n83_x_representatives.bin",
        "reference_screen_raw": HERE / "screen_sparse28.json",
        "candidate_screen_raw": HERE / "screen_sparse29.json",
        "test_record": HERE / "test_record.json",
    }
    if any(digest(path) != protocol["input_sha256"][name]
           for name, path in sources.items()):
        raise ValueError("frozen source or input hash differs")
    if (digest(HERE / "comparison_protocol.json") != tier["parent_protocol_sha256"] or
            protocol["curve_id"] != tier["curve_id"] != stage["curve_id"] or
            protocol["workload_id"] != tier["workload_id"] != stage["workload_id"] or
            protocol["pair_state_cap"] != stage["pair_state_cap"] != 29_900_000 or
            protocol["peak_rss_cap_mib"] != stage["peak_rss_cap_mib"] != 5500 or
            protocol["reference_mode"] != tier["reference_mode"] or
            protocol["candidate_mode"] != tier["candidate_mode"] or
            protocol["prior_reference_source_sha256"] != protocol["input_sha256"]["source"]):
        raise ValueError("comparison identity or stage cap differs")
    if (len(protocol["exact_pair_fields"]) != 23 or
            tuple(protocol["exact_pair_fields"]) != PAIR_FIELDS or
            any(reference.get(field) != candidate.get(field) for field in PAIR_FIELDS)):
        raise ValueError("23-field exact result differs")
    certificate = hashlib.sha256(canonical({name: reference[name] for name in PAIR_FIELDS})).hexdigest()
    if certificate != protocol["frozen_pair_certificate"] != tier["expected_result"]:
        raise ValueError("first-witness pair certificate differs")
    for mode, raw in ((protocol["reference_mode"], reference),
                      (protocol["candidate_mode"], candidate)):
        timing = raw["timing_ns"]
        online = int(timing["target_pdp_and_native_check"])
        phases = sum(int(timing[name]) for name in
                     ("target_query_preparation", "target_partner_generation", "target_partner_check"))
        if (raw["index_mode"] != mode or
                raw["native_source_sha256"] != protocol["input_sha256"]["source"] or
                raw["status"] != "state_cap_no_relation" or
                raw["native_s3_generator_target_control"]["status"] != "PASS" or
                raw["index_pair_states_examined"] != 29_900_000 or
                raw["target_states_scanned"] != 29_900_000 or
                raw["peak_rss_bytes"] > 5500 * (1 << 20) or
                phases > online or online <= 0):
            raise ValueError("frozen arm correctness, cap, or phase differs")
    if (record["exit_code"] != 0 or record["status"] != "COMPLETE_EXACT" or
            record["raw_result_sha256"] != digest(HERE / "screen_sparse29.json") or
            record["stdout_sha256"] != digest(HERE / "screen_sparse29.stdout.txt") or
            record["stderr_sha256"] != digest(HERE / "screen_sparse29.stderr.txt") or
            record["source_sha256"] != protocol["input_sha256"]["source"] or
            tests["status"] != "PASS" or
            tests["source_sha256"] != protocol["input_sha256"]["source"] or
            tests["stdout_sha256"] != digest(HERE / "test.stdout.txt") or
            tests["stderr_sha256"] != digest(HERE / "test.stderr.txt")):
        raise ValueError("local screen or release-test receipt differs")
    return {"status": "BOTH_FULL_CAPACITY_EXACT", "pair_certificate": certificate,
            "reference_probes": reference["root_table_hash_probes"]["target_lookup"],
            "candidate_probes": candidate["root_table_hash_probes"]["target_lookup"]}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
