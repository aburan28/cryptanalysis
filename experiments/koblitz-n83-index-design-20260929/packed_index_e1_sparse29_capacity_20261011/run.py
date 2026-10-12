#!/usr/bin/env python3
"""Replay the frozen N83 sparse28/sparse29 capacity comparison."""

import argparse
import hashlib
import json
import platform
import resource
import statistics
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODES = ("packed_sparse28_compact16_cachedxy",
         "packed_sparse29_compact16_cachedxy",
         "packed_sparse29_compact16_cachedxy",
         "packed_sparse28_compact16_cachedxy")
EXPECTED_SOURCE = "d9cbef74955d120b0c8051da30a3d391a802ebd342d2bb289ccfbcfe1230bfe5"
EXPECTED_WORKLOAD = "63dd0929cf33"
CAP = 29_900_000
RSS_MIB = 5500


def sha256(path):
    state = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            state.update(chunk)
    return state.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--inputs-root", type=Path, default=HERE.parent /
                        "adaptive_all_orientations_20261004" / "inputs")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    inputs = args.inputs_root.resolve(strict=True)
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    manifest = json.loads((HERE / "stage_manifest.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert hashlib.sha256(canonical(workload)).hexdigest()[:12] == EXPECTED_WORKLOAD
    assert manifest["workload_id"] == EXPECTED_WORKLOAD
    assert manifest["curve_id"] == workload["curve_id"]
    assert manifest["target_count"] == 1
    assert manifest["pair_state_cap"] == CAP
    assert manifest["peak_rss_cap_mib"] == RSS_MIB
    assert sha256(HERE / "native_packed_index.rs") == EXPECTED_SOURCE
    assert sha256(reps) == workload["representatives_file_sha256"]
    assert json.loads(bridge.read_text())["curve_id"] == manifest["curve_id"]
    protocol = {
        "kind": "n83_e1_sparse29_capacity_protocol",
        "proposal_id": "Q2026101133",
        "candidate_id": None,
        "curve_id": manifest["curve_id"],
        "workload_id": EXPECTED_WORKLOAD,
        "run_order": list(MODES),
        "pair_state_cap": CAP,
        "peak_rss_cap_mib": RSS_MIB,
        "host_isolation_receipt": None,
        "timing_boundary": "target-dependent query preparation through last partner check, after index and cached x/y preparation",
        "comparison_variable": "28 versus 29 SplitMix64 bucket bits in the same exact sparse root directory and binary",
        "input_sha256": {
            "source": sha256(HERE / "native_packed_index.rs"),
            "binary": sha256(binary),
            "cargo_manifest": sha256(HERE / "Cargo.toml"),
            "cargo_lock": sha256(HERE / "Cargo.lock"),
            "runner": sha256(HERE / "run.py"),
            "stage_manifest": sha256(HERE / "stage_manifest.json"),
            "workload": sha256(HERE / "workload.json"),
            "bridge": sha256(bridge),
            "representatives": sha256(reps),
        },
    }
    if (HERE / "protocol.json").exists():
        assert json.loads((HERE / "protocol.json").read_text()) == protocol
    else:
        save(HERE / "protocol.json", protocol)
    if args.freeze_only:
        print("frozen_protocol=" + str(HERE / "protocol.json"))
        return
    host = {"platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version(),
            "binary_sha256": protocol["input_sha256"]["binary"],
            "host_isolation_receipt": None}
    rows = []
    raws = []
    for number, mode in enumerate(MODES, 1):
        stem = "run_{}_{}".format(number, "sparse29" if number in (2, 3) else "sparse28")
        raw_path = HERE / (stem + ".json")
        record_path = HERE / (stem + ".record.json")
        if raw_path.exists() or record_path.exists():
            raise RuntimeError("run output already exists: " + stem)
        command = [str(binary), str(HERE / "stage_manifest.json"), str(bridge),
                   str(reps), str(CAP), str(RSS_MIB), mode, str(raw_path)]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter_ns()
        completed = subprocess.run(command, text=True, capture_output=True, timeout=900)
        elapsed = time.perf_counter_ns() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        (HERE / (stem + ".stdout.txt")).write_text(completed.stdout)
        (HERE / (stem + ".stderr.txt")).write_text(completed.stderr)
        record = {"sequence_number": number, "mode": mode,
                  "exit_code": completed.returncode, "outer_elapsed_ns": elapsed,
                  "child_user_cpu_ns": round((after.ru_utime - before.ru_utime) * 1e9),
                  "child_system_cpu_ns": round((after.ru_stime - before.ru_stime) * 1e9),
                  "raw_sha256": sha256(raw_path) if raw_path.exists() else None,
                  "host": host}
        save(record_path, record)
        if completed.returncode:
            raise RuntimeError(stem + " failed; raw failure retained")
        raw = json.loads(raw_path.read_text())
        assert raw["native_source_sha256"] == EXPECTED_SOURCE
        assert raw["workload_id"] == EXPECTED_WORKLOAD
        assert raw["index_mode"] == mode
        assert raw["target_states_scanned"] == CAP
        assert raw["peak_rss_bytes"] <= RSS_MIB * 1024 * 1024
        t = raw["timing_ns"]
        residual = int(t["target_pdp_and_native_check"]) - sum(int(t[key]) for key in
                   ("target_query_preparation", "target_partner_generation", "target_partner_check"))
        assert residual >= 0
        rows.append({"sequence_number": number, "mode": mode, "status": raw["status"],
                     "target_process_cpu_ns": int(t["target_process_cpu"]),
                     "target_stage_ns": int(t["target_pdp_and_native_check"]),
                     "target_query_preparation_ns": int(t["target_query_preparation"]),
                     "target_partner_generation_ns": int(t["target_partner_generation"]),
                     "target_partner_check_ns": int(t["target_partner_check"]),
                     "target_residual_ns": residual,
                     "index_build_cpu_ns": int(t["index_build_process_cpu"]),
                     "full_key_probes": raw["root_table_hash_probes"]["target_lookup"],
                     "root_table_allocated_bytes": raw["root_table_allocated_bytes"],
                     "peak_rss_bytes": raw["peak_rss_bytes"], "raw_sha256": record["raw_sha256"]})
        raws.append(raw)
        print(stem + " " + raw["status"], flush=True)
    stable = ("curve_id", "workload_id", "factor_base_enumerated_set_sha256",
              "input_representatives_sha256", "target_count", "status", "relation",
              "lookup_sample", "index_pair_states_examined",
              "index_satisfiable_s3_states", "index_distinct_root_keys",
              "root_table_slots_or_records", "target_states_prepared",
              "target_states_scanned", "target_state_orientations_prepared",
              "target_state_orientations_tested", "target_partner_roots",
              "target_table_hits", "target_root_windows", "partner_audit_pairs",
              "native_s3_generator_target_control", "operation_counts",
              "verified_single_target_dlp")
    mismatches = [key for key in stable if any(raw[key] != raws[0][key] for raw in raws[1:])]
    summary = {"kind": "n83_e1_sparse29_capacity_comparison",
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "curve_id": manifest["curve_id"], "workload_id": EXPECTED_WORKLOAD,
               "source_sha256": EXPECTED_SOURCE,
               "protocol_sha256": sha256(HERE / "protocol.json"),
               "paired_rows": rows, "invariant_fields": list(stable),
               "invariant_mismatches": mismatches,
               "medians": {mode: {field: statistics.median(row[field] for row in rows if row["mode"] == mode)
                         for field in ("target_process_cpu_ns", "target_stage_ns", "index_build_cpu_ns",
                                       "full_key_probes", "root_table_allocated_bytes", "peak_rss_bytes")}
                         for mode in MODES[:2]},
               "cpu_timing_claim": "exploratory; host isolation receipt absent",
               "online_speedup": None}
    save(HERE / "summary.json", summary)
    if mismatches:
        raise RuntimeError("exact invariants differ: " + ", ".join(mismatches))
    print(json.dumps({"status": "validated_stage_comparison", "medians": summary["medians"]}))


if __name__ == "__main__":
    main()
