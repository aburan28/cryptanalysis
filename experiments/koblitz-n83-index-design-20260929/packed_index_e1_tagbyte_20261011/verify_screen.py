#!/usr/bin/env python3
"""Verify the frozen sidecar screen, test receipt, and Tier 1 protocol."""

import hashlib
import json
from pathlib import Path

from benchmark_stage import PAIR_FIELDS, canonical, digest
from screen import MODES, SAME_FIELDS


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "packed_index_e1_sparse28_capacity_20261011"
SCREEN = HERE / "screen_2m"


def load(path):
    return json.loads(path.read_text())


def verify():
    tier = load(HERE / "tier1_protocol.json")
    protocol_path = SCREEN / "protocol.json"
    protocol = load(protocol_path)
    summary = load(SCREEN / "summary.json")
    test = load(HERE / "test_record.json")
    source = digest(HERE / "native_packed_index.rs")
    cargo = digest(HERE / "Cargo.toml")
    if (source != tier["source_sha256"] or
            cargo != tier["cargo_manifest_sha256"] or
            source != protocol["source_sha256"] or
            cargo != protocol["cargo_manifest_sha256"] or
            digest(HERE / "Cargo.lock") != protocol["cargo_lock_sha256"] or
            digest(HERE / "screen.py") != protocol["runner_sha256"] or
            digest(HERE / "test.stdout.txt") != test["stdout_sha256"] or
            digest(HERE / "test.stderr.txt") != test["stderr_sha256"] or
            test["source_sha256"] != source or
            test["cargo_manifest_sha256"] != cargo or
            test["tests_passed"] != 8 or test["tests_failed"] != 0 or
            test["exit_code"] != 0):
        raise ValueError("source, runner, or test receipt differs")
    if (protocol["order"] != list(MODES) or
            protocol["pair_state_cap"] != 2_000_000 or
            protocol["peak_rss_cap_mib"] != 1024 or
            summary["protocol_sha256"] != digest(protocol_path) or
            summary["parity_fields"] != list(SAME_FIELDS) or
            len(summary["runs"]) != 4):
        raise ValueError("short-screen protocol or summary differs")
    raws = []
    for index, mode in enumerate(MODES, 1):
        raw_path = SCREEN / f"run_{index}.json"
        raw = load(raw_path)
        record = load(SCREEN / f"run_{index}.record.json")
        row = summary["runs"][index - 1]
        if (record["exit_code"] != 0 or
                record["mode"] != mode or
                record["raw_sha256"] != digest(raw_path) or
                record["protocol_sha256"] != digest(protocol_path) or
                raw["index_mode"] != mode or
                raw["native_source_sha256"] != source or
                raw["cargo_manifest_sha256"] != cargo or
                raw["workload_id"] != protocol["workload_id"] or
                raw["peak_rss_bytes"] > 1024 * (1 << 20) or
                int(raw["timing_ns"]["target_process_cpu"]) !=
                row["target_stage_cpu_ns"] or
                int(raw["timing_ns"]["target_pdp_and_native_check"]) !=
                row["target_stage_wall_ns"] or
                raw["root_table_hash_probes"]["target_lookup"] !=
                row["target_record_probes"] or
                raw["root_table_tag_byte_allocated_bytes"] !=
                row["root_table_tag_byte_allocated_bytes"]):
            raise ValueError(f"short-screen run {index} differs")
        raws.append(raw)
    for field in SAME_FIELDS:
        if any(raw[field] != raws[0][field] for raw in raws[1:]):
            raise ValueError("short-screen parity differs: " + field)
    probes = [raw["root_table_hash_probes"]["target_lookup"] for raw in raws]
    if probes != [2995, 2087, 2087, 2995]:
        raise ValueError("record-probe reduction differs")
    if (raws[0]["root_table_tag_byte_allocated_bytes"] != 0 or
            raws[1]["root_table_tag_byte_allocated_bytes"] != 4_194_304):
        raise ValueError("sidecar capacity differs")

    parent_path = BASE / "protocol.json"
    full = load(BASE / "run_2_sparse28.json")
    certificate = hashlib.sha256(canonical(
        {field: full[field] for field in PAIR_FIELDS})).hexdigest()
    if (digest(parent_path) != tier["parent_protocol_sha256"] or
            full["workload_id"] != tier["workload_id"] or
            certificate != tier["expected_result"] or
            certificate != tier["expected_fields"]["pair_certificate"] or
            tier["expected_fields"]["native_source_sha256"] != source or
            (tier["reference_mode"], tier["candidate_mode"]) !=
            (MODES[0], MODES[1])):
        raise ValueError("Tier 1 certificate differs")
    audit = HERE / "full_audit_local"
    audit_protocol_path = audit / "protocol.json"
    audit_raw_path = audit / "raw.json"
    audit_protocol = load(audit_protocol_path)
    audit_record = load(audit / "record.json")
    audit_raw = load(audit_raw_path)
    audit_summary = load(audit / "summary.json")
    if (audit_protocol["source_sha256"] != source or
            audit_protocol["cargo_manifest_sha256"] != cargo or
            audit_protocol["cargo_lock_sha256"] != digest(HERE / "Cargo.lock") or
            audit_protocol["runner_sha256"] != digest(HERE / "full_audit.py") or
            audit_protocol["reference_sha256"] != digest(BASE / "run_2_sparse28.json") or
            audit_protocol["workload_id"] != tier["workload_id"] or
            audit_record["status"] != "COMPLETED" or
            audit_record["exit_code"] != 0 or
            audit_record["protocol_sha256"] != digest(audit_protocol_path) or
            audit_record["raw_sha256"] != digest(audit_raw_path) or
            audit_raw["native_source_sha256"] != source or
            audit_raw["cargo_manifest_sha256"] != cargo or
            audit_raw["index_mode"] != MODES[1] or
            audit_raw["peak_rss_bytes"] > 5500 * (1 << 20) or
            any(audit_raw[field] != full[field] for field in PAIR_FIELDS)):
        raise ValueError("full-capacity audit receipt or parity differs")
    phase_ns = sum(int(audit_raw["timing_ns"][name]) for name in
                   ("target_query_preparation", "target_partner_generation",
                    "target_partner_check"))
    if (audit_summary["status"] != "PASS" or
            audit_summary["protocol_sha256"] != digest(audit_protocol_path) or
            audit_summary["raw_sha256"] != digest(audit_raw_path) or
            audit_summary["pair_certificate"] != certificate or
            audit_summary["reference_record_probes"] != 7_415_319 or
            audit_summary["candidate_record_probes"] != 6_068_644 or
            audit_summary["candidate_tag_byte_allocated_bytes"] != 67_108_864 or
            audit_summary["candidate_target_process_cpu_ns"] !=
            int(audit_raw["timing_ns"]["target_process_cpu"]) or
            audit_summary["candidate_phase_residual_ns"] !=
            int(audit_raw["timing_ns"]["target_pdp_and_native_check"]) - phase_ns):
        raise ValueError("full-capacity summary differs")
    return {"status": "PASS", "tests": 8, "screen_runs": 4,
            "reference_probes": probes[0], "candidate_probes": probes[1],
            "full_reference_probes": audit_summary["reference_record_probes"],
            "full_candidate_probes": audit_summary["candidate_record_probes"],
            "tier1_workload_id": tier["workload_id"]}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
