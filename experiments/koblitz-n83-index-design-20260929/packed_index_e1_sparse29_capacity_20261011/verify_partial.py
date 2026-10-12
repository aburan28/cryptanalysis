#!/usr/bin/env python3
"""Verify three preserved sparse29 panel runs and the host-resource stop."""

import hashlib
import json
from pathlib import Path

from restore_crypto_source import ensure_snapshot
from run import CAP, EXPECTED_SOURCE, EXPECTED_WORKLOAD, MODES, RSS_MIB, canonical, sha256


HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"
STEMS = ("run_1_sparse28", "run_2_sparse29", "run_3_sparse29")
STABLE = (
    "curve_id", "workload_id", "factor_base_enumerated_set_sha256",
    "input_representatives_sha256", "target_count", "status", "relation",
    "lookup_sample", "index_pair_states_examined", "index_satisfiable_s3_states",
    "index_distinct_root_keys", "root_table_slots_or_records",
    "target_states_prepared", "target_states_scanned",
    "target_state_orientations_prepared", "target_state_orientations_tested",
    "target_partner_roots", "target_table_hits", "target_root_windows",
    "partner_audit_pairs", "native_s3_generator_target_control",
    "operation_counts", "verified_single_target_dlp",
)


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    ensure_snapshot()
    workload = load("workload.json")
    manifest = load("stage_manifest.json")
    protocol = load("protocol.json")
    stop = load("interruption.json")
    tests = load("test_record.json")
    assert hashlib.sha256(canonical(workload)).hexdigest()[:12] == EXPECTED_WORKLOAD
    assert protocol["workload_id"] == manifest["workload_id"] == EXPECTED_WORKLOAD
    assert protocol["run_order"] == list(MODES)
    assert manifest["pair_state_cap"] == CAP and manifest["peak_rss_cap_mib"] == RSS_MIB
    assert protocol["input_sha256"]["source"] == EXPECTED_SOURCE
    for name, path in (
        ("source", HERE / "native_packed_index.rs"),
        ("runner", HERE / "run.py"),
        ("cargo_manifest", HERE / "Cargo.toml"),
        ("cargo_lock", HERE / "Cargo.lock"),
        ("stage_manifest", HERE / "stage_manifest.json"),
        ("workload", HERE / "workload.json"),
        ("bridge", INPUTS / "n83_onb_poly_bridge.json"),
        ("representatives", INPUTS / "n83_x_representatives.bin"),
    ):
        assert sha256(path) == protocol["input_sha256"][name], name
    assert stop["protocol_sha256"] == sha256(HERE / "protocol.json")
    assert stop["panel_complete"] is False and stop["controlled_wall_speedup"] is None
    assert stop["interrupted_run"] == "run_4_sparse28"
    assert stop["interruption_exit_code"] == 130
    assert not (HERE / "run_4_sparse28.json").exists()
    assert tests["status"] == "PASS" and tests["passed"] == 7 and tests["failed"] == 0
    assert tests["source_sha256"] == EXPECTED_SOURCE
    assert tests["test_stdout_sha256"] == sha256(HERE / "test.stdout.txt")
    assert tests["test_stderr_sha256"] == sha256(HERE / "test.stderr.txt")

    raws = []
    for number, stem in enumerate(STEMS, 1):
        raw_path = HERE / (stem + ".json")
        raw = load(stem + ".json")
        receipt = load(stem + ".record.json")
        assert stop["completed_runs"][number - 1] == {
            "stem": stem, "raw_sha256": sha256(raw_path)}
        assert receipt["exit_code"] == 0 and receipt["raw_sha256"] == sha256(raw_path)
        assert receipt["mode"] == raw["index_mode"] == MODES[number - 1]
        assert receipt["host"]["binary_sha256"] == protocol["input_sha256"]["binary"]
        assert receipt["host"]["host_isolation_receipt"] is None
        assert raw["native_source_sha256"] == EXPECTED_SOURCE
        assert raw["workload_id"] == EXPECTED_WORKLOAD
        assert raw["status"] == "state_cap_no_relation"
        assert raw["index_pair_states_examined"] == raw["target_states_scanned"] == CAP
        assert raw["peak_rss_bytes"] <= RSS_MIB * 1024 * 1024
        assert raw["native_s3_generator_target_control"]["status"] == "PASS"
        timing = raw["timing_ns"]
        assert int(timing["target_pdp_and_native_check"]) >= sum(
            int(timing[name]) for name in ("target_query_preparation",
                                            "target_partner_generation",
                                            "target_partner_check"))
        raws.append(raw)
    assert all(all(raw[field] == raws[0][field] for raw in raws[1:])
               for field in STABLE)
    print(json.dumps({"status": "PARTIAL_HOST_RESOURCE_STOP",
                      "completed_runs": len(raws), "exact_invariants": len(STABLE),
                      "workload_id": EXPECTED_WORKLOAD}, sort_keys=True))


if __name__ == "__main__":
    main()
