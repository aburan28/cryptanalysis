#!/usr/bin/env python3
"""Verify the sparse26 N83 capacity run against the committed sparse24 receipt."""

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "packed_index_e1_sparse26_cachedxy_cpu_20261011"
REFERENCE = (PARENT / "packed_index_e1_capacity_20261011" /
             "run_packed_cachedxy_29900000.json")
REFERENCE_COMMIT = "b3287843e"
REFERENCE_REPO_PATH = ("experiments/koblitz-n83-index-design-20260929/"
                       "packed_index_e1_capacity_20261011/"
                       "run_packed_cachedxy_29900000.json")
REFERENCE_SHA256 = "19341c67bb113c9d5b80b44f1ea22d3d687405c246eb34dde463a55dbabea7b4"
INPUTS = PARENT / "adaptive_all_orientations_20261004" / "inputs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def reference():
    if REFERENCE.is_file():
        data = REFERENCE.read_bytes()
    else:
        repo = HERE.parents[2]
        data = subprocess.check_output(
            ["git", "show", f"{REFERENCE_COMMIT}:{REFERENCE_REPO_PATH}"], cwd=repo)
    assert hashlib.sha256(data).hexdigest() == REFERENCE_SHA256
    return json.loads(data)


def verify():
    protocol = load("protocol.json")
    manifest = load("stage_manifest.json")
    workload = load("workload.json")
    record = load("run_record.json")
    raw = load("run_sparse26_cachedxy_29900000.json")
    old = reference()
    parent = json.loads((SOURCE / "stage_manifest.json").read_text())
    assert protocol["runner_sha256"] == digest(HERE / "capacity_probe.py")
    assert protocol["source_sha256"] == digest(SOURCE / "native_packed_index.rs")
    assert protocol["parent_stage_manifest_sha256"] == digest(SOURCE / "stage_manifest.json")
    assert protocol["parent_protocol_sha256"] == digest(SOURCE / "protocol.json")
    assert protocol["bridge_sha256"] == digest(INPUTS / "n83_onb_poly_bridge.json")
    assert protocol["representatives_sha256"] == digest(INPUTS / "n83_x_representatives.bin")
    workload_id = hashlib.sha256(json.dumps(workload, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:12]
    assert workload_id == protocol["workload_id"] == manifest["workload_id"] == raw["workload_id"] == record["workload_id"] == old["workload_id"]
    assert workload_id == "63dd0929cf33"
    assert protocol["parent_workload_id"] == parent["workload_id"] == "981ac530e67e"
    assert manifest["target_count"] == raw["target_count"] == workload["target_count"] == 1
    assert manifest["target_poly_xy"] == parent["target_poly_xy"]
    assert manifest["pair_state_cap"] == workload["index_state_law"]["count"] == 29_900_000
    assert manifest["peak_rss_cap_mib"] == protocol["peak_rss_cap_mib"] == 5500
    assert manifest["stage_protocol_sha256"] == digest(HERE / "protocol.json")
    assert record["status"] == "completed" and record["exit_code"] == 0
    assert record["output_sha256"] == digest(HERE / "run_sparse26_cachedxy_29900000.json")
    assert record["protocol_sha256"] == digest(HERE / "protocol.json")
    assert record["stage_manifest_sha256"] == digest(HERE / "stage_manifest.json")
    assert record["binary_sha256"] == protocol["binary_sha256"]
    assert raw["native_source_sha256"] == protocol["source_sha256"]
    assert raw["stage_protocol_sha256"] == manifest["stage_protocol_sha256"]
    assert raw["index_mode"] == protocol["index_mode"]
    assert raw["status"] == record["native_status"] == "state_cap_no_relation"
    assert raw["limits"]["pair_state_cap"] == raw["index_pair_states_examined"] == 29_900_000
    assert raw["limits"]["peak_rss_cap_bytes"] == 5500 * 1024 * 1024
    assert raw["peak_rss_bytes"] == record["peak_rss_bytes"] <= raw["limits"]["peak_rss_cap_bytes"]
    assert raw["target_states_scanned"] == raw["target_states_prepared"] == 29_900_000
    assert raw["index_root_x_precomputed"] == raw["index_root_y_precomputed"] == 59_800_000
    assert len(raw["lookup_sample"]) == 64
    assert raw["native_s3_generator_target_control"]["status"] == "PASS"
    assert record["host_isolation_receipt"] is None
    fields = ("curve_id", "workload_id", "target_count",
              "factor_base_enumerated_set_sha256", "index_pair_states_examined",
              "index_satisfiable_s3_states", "index_distinct_root_keys",
              "target_states_scanned", "target_partner_roots", "target_table_hits",
              "status", "relation", "lookup_sample", "native_s3_generator_target_control")
    assert all(raw[key] == old[key] for key in fields)
    phases = raw["timing_ns"]
    target_ns = int(phases["target_pdp_and_native_check"])
    phase_sum = sum(int(phases[key]) for key in
                    ("target_query_preparation", "target_partner_generation",
                     "target_partner_check"))
    assert 0 <= target_ns - phase_sum < target_ns
    print(json.dumps({
        "status": "PASS", "workload_id": workload_id,
        "index_pair_states": raw["index_pair_states_examined"],
        "peak_rss_bytes": raw["peak_rss_bytes"],
        "rss_headroom_bytes": raw["limits"]["peak_rss_cap_bytes"] - raw["peak_rss_bytes"],
        "sparse24_full_key_probes": old["root_table_hash_probes"]["target_lookup"],
        "sparse26_full_key_probes": raw["root_table_hash_probes"]["target_lookup"],
        "target_process_cpu_ns": int(phases["target_process_cpu"]),
        "target_phase_residual_ns": target_ns - phase_sum,
    }, sort_keys=True))


if __name__ == "__main__":
    verify()
