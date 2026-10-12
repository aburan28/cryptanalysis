#!/usr/bin/env python3
"""Verify frozen N83 sparse28 capacity runs and the full partner-root audit."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from restore_crypto_source import ensure_snapshot


HERE = Path(__file__).resolve().parent
ORDER = ("packed_sparse26_compact16_cachedxy",
         "packed_sparse28_compact16_cachedxy",
         "packed_sparse28_compact16_cachedxy",
         "packed_sparse26_compact16_cachedxy")


def sha256(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            state.update(chunk)
    return state.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def verify(inputs):
    ensure_snapshot()
    protocol = load(HERE / "protocol.json")
    manifest = load(HERE / "stage_manifest.json")
    workload = load(HERE / "workload.json")
    summary = load(HERE / "summary.json")
    audit_protocol = load(HERE / "audit_protocol.json")
    audit_manifest = load(HERE / "audit_stage_manifest.json")
    audit_workload = load(HERE / "audit_workload.json")
    audit = load(HERE / "audit_sparse28.json")
    audit_record = load(HERE / "audit.record.json")
    frozen = protocol["input_sha256"]
    for key, path in (("source", HERE / "native_packed_index.rs"),
                      ("cargo_manifest", HERE / "Cargo.toml"),
                      ("cargo_lock", HERE / "Cargo.lock"),
                      ("runner", HERE / "run.py"),
                      ("stage_manifest", HERE / "stage_manifest.json"),
                      ("workload", HERE / "workload.json"),
                      ("bridge", inputs / "n83_onb_poly_bridge.json"),
                      ("representatives", inputs / "n83_x_representatives.bin")):
        assert sha256(path) == frozen[key], key
    assert hashlib.sha256(canonical(workload)).hexdigest()[:12] == "63dd0929cf33"
    assert protocol["workload_id"] == manifest["workload_id"] == summary["workload_id"] == "63dd0929cf33"
    assert manifest["curve_id"] == workload["curve_id"] == protocol["curve_id"]
    assert manifest["target_count"] == 1
    assert manifest["pair_state_cap"] == protocol["pair_state_cap"] == 29_900_000
    assert manifest["peak_rss_cap_mib"] == protocol["peak_rss_cap_mib"] == 5500
    assert protocol["run_order"] == list(ORDER)
    assert summary["protocol_sha256"] == sha256(HERE / "protocol.json")
    assert summary["source_sha256"] == frozen["source"]
    assert summary["invariant_mismatches"] == []
    assert summary["online_speedup"] is None
    rows = []
    raws = []
    for number, mode in enumerate(ORDER, 1):
        stem = "run_{}_{}".format(number, "sparse28" if number in (2, 3) else "sparse26")
        raw_path = HERE / (stem + ".json")
        raw = load(raw_path)
        receipt = load(HERE / (stem + ".record.json"))
        assert receipt["exit_code"] == 0
        assert receipt["raw_sha256"] == sha256(raw_path)
        assert receipt["host"]["binary_sha256"] == frozen["binary"]
        assert receipt["host"]["host_isolation_receipt"] is None
        assert raw["native_source_sha256"] == frozen["source"]
        assert raw["cargo_manifest_sha256"] == frozen["cargo_manifest"]
        assert raw["workload_id"] == protocol["workload_id"]
        assert raw["index_mode"] == mode
        assert raw["status"] == "state_cap_no_relation"
        assert raw["index_pair_states_examined"] == raw["target_states_scanned"] == 29_900_000
        assert raw["peak_rss_bytes"] <= 5500 * 1024 * 1024
        t = raw["timing_ns"]
        residual = int(t["target_pdp_and_native_check"]) - sum(int(t[key]) for key in
                   ("target_query_preparation", "target_partner_generation", "target_partner_check"))
        assert residual >= 0
        row = summary["paired_rows"][number - 1]
        assert row["sequence_number"] == number and row["mode"] == mode
        assert row["raw_sha256"] == receipt["raw_sha256"]
        assert row["target_process_cpu_ns"] == int(t["target_process_cpu"])
        assert row["target_stage_ns"] == int(t["target_pdp_and_native_check"])
        assert row["target_residual_ns"] == residual
        assert row["full_key_probes"] == raw["root_table_hash_probes"]["target_lookup"]
        assert row["root_table_allocated_bytes"] == raw["root_table_allocated_bytes"]
        rows.append(row)
        raws.append(raw)
    assert all(all(raw[key] == raws[0][key] for raw in raws[1:])
               for key in summary["invariant_fields"])
    for mode in ORDER[:2]:
        selected = [row for row in rows if row["mode"] == mode]
        for key, value in summary["medians"][mode].items():
            assert value == statistics.median(row[key] for row in selected), key
    assert summary["medians"][ORDER[0]]["full_key_probes"] == 69_190_310
    assert summary["medians"][ORDER[1]]["full_key_probes"] == 7_415_319
    assert summary["medians"][ORDER[0]]["root_table_allocated_bytes"] == 1_237_818_368
    assert summary["medians"][ORDER[1]]["root_table_allocated_bytes"] == 1_275_567_104
    assert hashlib.sha256(canonical(audit_workload)).hexdigest()[:12] == "981ac530e67e"
    assert audit_manifest["workload_id"] == audit_protocol["workload_id"] == "981ac530e67e"
    for key, path in (("source_sha256", HERE / "native_packed_index.rs"),
                      ("runner_sha256", HERE / "audit.py"),
                      ("stage_manifest_sha256", HERE / "audit_stage_manifest.json"),
                      ("bridge_sha256", inputs / "n83_onb_poly_bridge.json"),
                      ("representatives_sha256", inputs / "n83_x_representatives.bin")):
        assert audit_protocol[key] == sha256(path), key
    assert audit_protocol["binary_sha256"] == frozen["binary"]
    assert audit_record["exit_code"] == 0
    assert audit_record["audit_protocol_sha256"] == sha256(HERE / "audit_protocol.json")
    assert audit_record["raw_sha256"] == sha256(HERE / "audit_sparse28.json")
    assert audit["native_source_sha256"] == frozen["source"]
    assert audit["workload_id"] == audit_protocol["workload_id"]
    assert audit["index_mode"] == audit_protocol["index_mode"]
    assert audit["partner_audit_pairs"] == audit_protocol["expected_partner_audit_pairs"] == 4_000_000
    assert audit["target_partner_roots"] == audit_protocol["expected_partner_roots"] == 8_000_000
    assert audit["peak_rss_bytes"] <= 1024 * 1024 * 1024
    tests = load(HERE / "test_record.json")
    assert tests["exit_code"] == 0 and tests["tests_passed"] == 7
    assert tests["source_sha256"] == frozen["source"]
    assert tests["cargo_manifest_sha256"] == frozen["cargo_manifest"]
    assert tests["cargo_lock_sha256"] == frozen["cargo_lock"]
    assert tests["stdout_sha256"] == sha256(HERE / "test.stdout.txt")
    assert tests["stderr_sha256"] == sha256(HERE / "test.stderr.txt")
    print(json.dumps({"status": "PASS", "capacity_workload_id": protocol["workload_id"],
                      "full_partner_audit_pairs": audit["partner_audit_pairs"],
                      "full_partner_roots": audit["target_partner_roots"],
                      "cpu_pairs_ns_reference_candidate": [[rows[0]["target_process_cpu_ns"],
                                                             rows[1]["target_process_cpu_ns"]],
                                                            [rows[3]["target_process_cpu_ns"],
                                                             rows[2]["target_process_cpu_ns"]]]},
                     sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-root", type=Path, default=HERE.parent /
                        "adaptive_all_orientations_20261004" / "inputs")
    args = parser.parse_args()
    verify(args.inputs_root.resolve(strict=True))
