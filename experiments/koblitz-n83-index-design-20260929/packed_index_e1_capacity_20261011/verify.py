#!/usr/bin/env python3
"""Verify the frozen 29.9M-state packed-index capacity receipt."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "packed_index_e1_cachedxy_cpu_20261011"
INPUTS = PARENT / "adaptive_all_orientations_20261004" / "inputs"
STATE_CAP = 29_900_000
RSS_CAP_MIB = 5_500


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def verify():
    protocol = load("protocol.json")
    manifest = load("stage_manifest.json")
    workload = load("workload.json")
    run = load("run_record.json")
    raw = load("run_packed_cachedxy_29900000.json")
    parent = json.loads((SOURCE / "stage_manifest.json").read_text())

    assert protocol["runner_sha256"] == sha256(HERE / "capacity_probe.py")
    assert protocol["source_sha256"] == sha256(SOURCE / "native_packed_index.rs")
    assert protocol["parent_stage_manifest_sha256"] == sha256(SOURCE / "stage_manifest.json")
    assert protocol["parent_protocol_sha256"] == sha256(SOURCE / "protocol.json")
    assert protocol["bridge_sha256"] == sha256(INPUTS / "n83_onb_poly_bridge.json")
    assert protocol["representatives_sha256"] == sha256(INPUTS / "n83_x_representatives.bin")
    canonical_workload = json.dumps(workload, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")
    workload_id = hashlib.sha256(canonical_workload).hexdigest()[:12]
    assert workload_id == protocol["workload_id"] == manifest["workload_id"] == raw["workload_id"] == run["workload_id"]
    assert protocol["parent_workload_id"] == parent["workload_id"] == "981ac530e67e"
    assert workload["target_count"] == manifest["target_count"] == raw["target_count"] == 1
    assert manifest["target_poly_xy"] == parent["target_poly_xy"] == protocol["public_target_poly_xy"]
    assert manifest["pair_state_cap"] == workload["index_state_law"]["count"] == STATE_CAP
    assert manifest["peak_rss_cap_mib"] == protocol["peak_rss_cap_mib"] == RSS_CAP_MIB
    assert manifest["stage_protocol_sha256"] == sha256(HERE / "protocol.json")

    assert run["status"] == "completed" and run["exit_code"] == 0
    assert run["native_status"] == raw["status"] == "state_cap_no_relation"
    assert run["output_sha256"] == sha256(HERE / "run_packed_cachedxy_29900000.json")
    assert run["protocol_sha256"] == sha256(HERE / "protocol.json")
    assert run["stage_manifest_sha256"] == sha256(HERE / "stage_manifest.json")
    assert run["binary_sha256"] == protocol["binary_sha256"]
    assert raw["native_source_sha256"] == protocol["source_sha256"]
    assert raw["stage_protocol_sha256"] == manifest["stage_protocol_sha256"]
    assert raw["index_mode"] == protocol["index_mode"]
    assert raw["limits"]["pair_state_cap"] == raw["index_pair_states_examined"] == STATE_CAP
    assert raw["limits"]["peak_rss_cap_bytes"] == RSS_CAP_MIB * 1024 * 1024
    assert raw["peak_rss_bytes"] == run["peak_rss_bytes"] <= raw["limits"]["peak_rss_cap_bytes"]
    assert raw["target_states_scanned"] == raw["target_states_prepared"] == STATE_CAP
    assert raw["index_root_x_precomputed"] == raw["index_root_y_precomputed"] == 2 * STATE_CAP
    assert len(raw["lookup_sample"]) == 64
    assert all(entry[1] is not None for entry in raw["lookup_sample"])
    assert raw["native_s3_generator_target_control"]["status"] == "PASS"

    phases = raw["timing_ns"]
    online_ns = int(phases["target_pdp_and_native_check"])
    phase_sum_ns = sum(int(phases[name]) for name in (
        "target_query_preparation", "target_partner_generation", "target_partner_check"))
    assert 0 <= online_ns - phase_sum_ns < online_ns
    assert run["host_isolation_receipt"] is None
    summary = {
        "workload_id": workload_id,
        "status": raw["status"],
        "index_pair_states_examined": raw["index_pair_states_examined"],
        "index_distinct_root_keys": raw["index_distinct_root_keys"],
        "peak_rss_bytes": raw["peak_rss_bytes"],
        "rss_headroom_bytes": raw["limits"]["peak_rss_cap_bytes"] - raw["peak_rss_bytes"],
        "index_build_ns": int(phases["index_build"]),
        "target_online_ns": online_ns,
        "target_phase_residual_ns": online_ns - phase_sum_ns,
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    verify()
