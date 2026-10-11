#!/usr/bin/env python3
"""Verify the frozen sparse24/sparse26 N83 comparison and full root audit."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "adaptive_all_orientations_20261004" / "inputs"
REFERENCE = "packed_sparse24_compact16_cachedxy"
CANDIDATE = "packed_sparse26_compact16_cachedxy"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def tree_digest(root, paths):
    state = hashlib.sha256()
    for path in sorted(paths):
        state.update(str(path.relative_to(root)).encode())
        state.update(b"\0")
        state.update(bytes.fromhex(sha256(path)))
    return state.hexdigest()


def verify():
    protocol = load("protocol.json")
    workload = load("workload.json")
    manifest = load("stage_manifest.json")
    build = load("build_receipt.json")
    summary = load("summary.json")
    audit_protocol = load("audit_protocol.json")
    audit_receipt = load("audit_record.json")
    audit = load("audit_sparse26_cachedxy.json")
    parent = json.loads((HERE.parent / "adaptive_all_orientations_20261004" /
                         "all83_ordinary_manifest.json").read_text())

    inputs = protocol["inputs_sha256"]
    for key, path in (
        ("native_source", HERE / "native_packed_index.rs"),
        ("runner", HERE / "run.py"),
        ("cargo_manifest", HERE / "Cargo.toml"),
        ("cargo_lock", HERE / "Cargo.lock"),
        ("bridge", INPUTS / "n83_onb_poly_bridge.json"),
        ("representatives", INPUTS / "n83_x_representatives.bin"),
    ):
        assert inputs[key] == sha256(path), key
    crypto = HERE / "crypto_source_snapshot"
    assert inputs["crypto_manifest"] == sha256(crypto / "Cargo.toml")
    assert inputs["crypto_source_tree"] == tree_digest(
        crypto, (path for path in crypto.rglob("*") if path.is_file()))
    assert inputs["crypto_rust_source_tree"] == tree_digest(
        crypto, (crypto / "src").rglob("*.rs"))
    assert manifest["stage_protocol_sha256"] == sha256(HERE / "protocol.json")
    workload_id = hashlib.sha256(json.dumps(workload, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:12]
    assert workload_id == protocol["workload_id"] == manifest["workload_id"] == summary["workload_id"]
    assert workload_id == "981ac530e67e"
    assert workload["target_count"] == manifest["target_count"] == 1
    assert manifest["target_poly_xy"] == parent["target_poly_xy"]
    assert manifest["pair_state_cap"] == 2_000_000
    assert manifest["peak_rss_cap_mib"] == 1024
    assert protocol["run_order"] == [REFERENCE, CANDIDATE, CANDIDATE,
                                      REFERENCE, REFERENCE, CANDIDATE]
    assert build["source_sha256"] == inputs["native_source"]
    assert build["protocol_sha256"] == sha256(HERE / "protocol.json")
    assert summary["protocol_sha256"] == sha256(HERE / "protocol.json")
    assert summary["source_sha256"] == inputs["native_source"]
    assert summary["status"] == "validated_stage_comparison"
    assert summary["invariant_mismatches"] == {}

    raws = []
    for number, mode in enumerate(protocol["run_order"], 1):
        stem = f"run_{number}_{mode}"
        raw = load(stem + ".json")
        receipt = load(stem + ".record.json")
        assert receipt["execution_status"] == "completed"
        assert receipt["raw_result_sha256"] == sha256(HERE / (stem + ".json"))
        assert raw["native_source_sha256"] == inputs["native_source"]
        assert raw["workload_id"] == workload_id
        assert raw["index_mode"] == mode
        assert raw["status"] == "state_cap_no_relation"
        assert raw["index_pair_states_examined"] == raw["target_states_scanned"] == 2_000_000
        assert raw["peak_rss_bytes"] <= 1024 * 1024 * 1024
        phases = raw["timing_ns"]
        phase_sum = sum(int(phases[key]) for key in
                        ("target_query_preparation", "target_partner_generation",
                         "target_partner_check"))
        assert phase_sum <= int(phases["target_pdp_and_native_check"])
        raws.append(raw)
    stable_fields = ("curve_id", "workload_id", "factor_base_enumerated_set_sha256",
                     "index_pair_states_examined", "index_satisfiable_s3_states",
                     "index_distinct_root_keys", "target_states_scanned",
                     "target_state_orientations_tested", "status", "relation",
                     "lookup_sample", "native_s3_generator_target_control",
                     "target_table_hits", "target_partner_roots", "target_root_windows")
    assert all(all(raw[key] == raws[0][key] for raw in raws[1:])
               for key in stable_fields)
    assert len(summary["paired_rows"]) == len(raws) == 6
    assert summary["medians"][REFERENCE]["target_lookup_comparisons_or_probes"] == 471_510
    assert summary["medians"][CANDIDATE]["target_lookup_comparisons_or_probes"] == 35_837

    assert audit_protocol["runner_sha256"] == sha256(HERE / "audit.py")
    assert audit_protocol["source_sha256"] == inputs["native_source"]
    assert audit_protocol["binary_sha256"] == build["binary_sha256"]
    assert audit_protocol["stage_manifest_sha256"] == sha256(HERE / "stage_manifest.json")
    assert audit_receipt["status"] == "completed" and audit_receipt["exit_code"] == 0
    assert audit_receipt["audit_protocol_sha256"] == sha256(HERE / "audit_protocol.json")
    assert audit_receipt["raw_sha256"] == sha256(HERE / "audit_sparse26_cachedxy.json")
    assert audit["native_source_sha256"] == inputs["native_source"]
    assert audit["workload_id"] == workload_id
    assert audit["index_mode"] == audit_protocol["index_mode"]
    assert audit["status"] == "state_cap_no_relation"
    assert audit["partner_audit_pairs"] == audit_protocol["expected_partner_audit_pairs"] == 4_000_000
    assert audit["target_partner_roots"] == audit_protocol["expected_partner_roots"] == 8_000_000
    assert audit["lookup_sample"] == raws[0]["lookup_sample"]
    assert audit["peak_rss_bytes"] <= 1024 * 1024 * 1024
    assert build["host_isolation_receipt"] is None

    cpu_pairs = []
    for i in (0, 2, 4):
        pair = raws[i:i + 2]
        reference = next(raw for raw in pair if raw["index_mode"] == REFERENCE)
        candidate = next(raw for raw in pair if raw["index_mode"] == CANDIDATE)
        cpu_pairs.append([int(reference["timing_ns"]["target_process_cpu"]),
                          int(candidate["timing_ns"]["target_process_cpu"])])
    print(json.dumps({"status": "PASS", "workload_id": workload_id,
                      "full_partner_audit_pairs": audit["partner_audit_pairs"],
                      "full_partner_roots": audit["target_partner_roots"],
                      "cpu_pairs_ns_reference_candidate": cpu_pairs}, sort_keys=True))


if __name__ == "__main__":
    verify()
