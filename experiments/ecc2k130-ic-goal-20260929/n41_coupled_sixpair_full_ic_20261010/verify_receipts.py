#!/usr/bin/env python3
"""Offline integrity check for canonical identities and paired run receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    manifest = read(HERE / "candidate_manifest.json")
    identity = manifest["identity_record"]
    candidate = manifest["candidate_id"]
    assert candidate.endswith(digest(identity)[:12])
    assert manifest["identity_sha256"] == digest(identity)
    curve = dict(identity["curve"])
    curve_id = curve.pop("curve_id")
    assert curve_id == "EC1N41Ckb1h" + digest({"field": identity["field"],
                                                "curve": curve})[:12]
    source_paths = {
        "collector_python": HERE / "collect.py",
        "collection_join_cpp": HERE / "join.cpp",
        "collection_join_binary": HERE / "join",
        "native_curve_helper_cpp": HERE / "helper_snapshot.cpp",
        "factor_log_audit_sage": HERE / "audit.py",
        "warm_worker_cpp": HERE / "online_worker.cpp",
        "warm_worker_binary": HERE / "online_worker",
        "warm_input_preparer_python": HERE / "prepare_online.py",
        "warm_runner_python": HERE / "online_run.py",
        "online_audit_sage": HERE / "audit_online.py",
        "supplemental_replay_sage": HERE / "supplemental_replay.py",
        "fresh_runner_python": HERE / "fresh/run.py",
        "fresh_online_audit_sage": HERE / "fresh/audit.py",
    }
    for name, path in source_paths.items():
        assert identity["implementation"]["source_and_binary_sha256"][name] == sha(path), name
    source_atoms = read(HERE / "workload.json")["atoms"]
    points = sorted({tuple(item["point"]) for item in source_atoms})
    base = identity["factor_base"]
    assert len(points) == base["actual_usable_points_B"] == 384
    assert base["enumerated_point_set_sha256"] == digest([list(point) for point in points])
    assert base["atom_record_sha256"] == digest(source_atoms)
    assert read(HERE / "sage_audit.json")["status"] == (
        "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS")
    assert read(HERE / "build_replay.json")["status"] == (
        "PASS_VENDORED_SOURCE_REBUILD_AND_FROZEN_TARGET_REPLAY")
    for folder in (HERE, HERE / "fresh"):
        workload = read(folder / "canonical_workload.json")
        comparison = read(folder / "paired_comparison.json")
        assert workload["workload_id"] == digest(workload["identity_record"])[:12]
        assert comparison["candidate_id"] == candidate
        assert comparison["workload_id"] == workload["workload_id"]
        assert comparison["run_id"] == f"{candidate}W{workload['workload_id']}R1"
        assert comparison["target"] == workload["identity_record"]["targets"][0]
        assert comparison["ic"]["independent_sage_replay"]
        assert comparison["rho"]["independent_sage_replay"]
        assert comparison["timing_class"] == "exploratory_unisolated_host"
        assert comparison["promoted_online_speedup"] is None
        assert sum(comparison["ic"]["exclusive_phase_ns"].values()) == comparison["ic"]["online_ns"]
        assert sum(comparison["rho"]["exclusive_phase_ns"].values()) == comparison["rho"]["online_ns"]
        assert abs(comparison["observed_rho_online_ns_div_ic_online_ns"]
                   - comparison["rho"]["online_ns"] / comparison["ic"]["online_ns"]) < 1e-15
        for name, relative in comparison["source_sha256"].items():
            path = (folder if folder != HERE else HERE) / {
                "candidate_manifest": "../candidate_manifest.json" if folder != HERE else "candidate_manifest.json",
                "workload_manifest": "canonical_workload.json",
                "collection": "../collection_result.json" if folder != HERE else "collection_result.json",
                "factor_audit": "../sage_audit.json" if folder != HERE else "sage_audit.json",
                "ic_native": "ic_native.json" if folder != HERE else "online_native.json",
                "rho_native": "rho_native.json",
                "ic_audit": "online_sage_audit.json",
                "rho_audit": "rho_sage_audit.json",
                "sage_audit": "sage_audit.json",
                "protocol": "protocol.json",
                "script": "compare.py",
            }[name]
            assert sha(path) == relative, (folder, name)
    print(json.dumps({"status": "PASS_ALL_N41_SIXPAIR_RECEIPTS",
                      "candidate_id": candidate, "paired_workloads": 2}))


if __name__ == "__main__":
    main()
