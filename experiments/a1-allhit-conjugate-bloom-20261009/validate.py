#!/usr/bin/env python3
"""Check source-bound AB/BA receipts, ordered witnesses, and operation counts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIELDS = ("status", "label", "workload_id", "query_stream_id", "actual_usable_B",
          "pair_index_orbits", "pair_index_record_bytes", "pair_index_binary_bytes",
          "query_count", "available_query_count", "stop_criterion",
          "verified_relation_queries", "raw_hit_incidences", "distinct_weighted_rows",
          "initial_rank", "final_rank", "base_points_checked", "relation_events")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(stream, enabled):
    name = f"{stream}_{'on' if enabled else 'off'}"
    data = json.loads((HERE / f"results/{name}.json").read_text())
    raw = data["raw_result"]
    assert data["launch_status"] == "completed" and data["exit_code"] == 0
    assert raw["status"] in ("verified", "censored")
    assert data["filter_enabled"] == raw["conjugate_bloom_enabled"] == enabled
    assert data["collector_source_sha256"] == digest(HERE / "collector/src/main.rs")
    assert data["manifest_sha256"] == digest(HERE / "collector/Cargo.toml")
    assert data["lock_sha256"] == digest(HERE / "collector/Cargo.lock")
    assert data["protocol_sha256"] == digest(HERE / "PROTOCOL.md")
    assert data["runner_sha256"] == digest(HERE / "run_panel.py")
    assert data["export_sha256"] == digest(HERE / "inputs/export.json")
    assert data["index_sha256"] == digest(HERE / "inputs/index.bin")
    assert data["workload_sha256"] == digest(HERE / f"inputs/{stream}.json")
    assert json.loads(data["stdout"]) == raw
    assert sum(raw["collection_phase_ns"].values()) == raw["collection_wall_ns"]
    assert raw["pair_index_orbits"] == 735_000
    assert raw["base_points_checked"] == raw["query_count"] * 12_720
    assert raw["indexed_hits"] == raw["raw_hit_incidences"]
    assert raw["orbit_key_computations"] == raw["indexed_hits"] + raw["exact_lookup_misses"]
    if enabled:
        assert raw["nonidentity_differences"] == (raw["bloom_negative_checks"]
            + raw["bloom_positive_checks"])
        assert raw["bloom_positive_checks"] == raw["orbit_key_computations"]
        assert raw["conjugate_bloom_bytes"] > 0
        assert raw["conjugate_bloom_build_ns_excluded"] > 0
        assert raw["conjugate_bloom_check_ns_excluded"] > 0
    else:
        assert raw["nonidentity_differences"] == raw["orbit_key_computations"]
        assert raw["conjugate_bloom_bytes"] == 0
    return data


def main():
    primary = json.loads((HERE / "inputs/primary.json").read_text())
    disjoint = json.loads((HERE / "inputs/disjoint.json").read_text())
    p = {q["known_scalar"] for q in primary["queries"]}
    d = {q["known_scalar"] for q in disjoint["queries"]}
    assert len(p) == len(d) == 2_048 and not (p & d)
    rows = {}
    binary_hash = None
    for stream in ("primary", "disjoint"):
        off, on = receipt(stream, False), receipt(stream, True)
        if binary_hash is None:
            binary_hash = off["binary_sha256"]
        assert off["binary_sha256"] == on["binary_sha256"] == binary_hash
        ref, candidate = off["raw_result"], on["raw_result"]
        for field in FIELDS:
            assert ref[field] == candidate[field], (stream, field)
        assert ref["nonidentity_differences"] == candidate["nonidentity_differences"]
        assert ref["indexed_hits"] == candidate["indexed_hits"]
        avoided = ref["orbit_key_computations"] - candidate["orbit_key_computations"]
        assert avoided == candidate["bloom_negative_checks"] > 0
        rows[stream] = {"status": ref["status"], "query_count": ref["query_count"],
                        "ordered_incidence_count": ref["raw_hit_incidences"],
                        "rank": ref["final_rank"],
                        "reference_orbit_keys": ref["orbit_key_computations"],
                        "candidate_orbit_keys": candidate["orbit_key_computations"],
                        "avoided_orbit_keys": avoided,
                        "avoided_fraction": avoided / ref["orbit_key_computations"],
                        "filter_bytes": candidate["conjugate_bloom_bytes"],
                        "build_ns_excluded": candidate["conjugate_bloom_build_ns_excluded"],
                        "check_ns_excluded": candidate["conjugate_bloom_check_ns_excluded"],
                        "reference_collection_wall_ns_exploratory": ref["collection_wall_ns"],
                        "candidate_collection_wall_ns_exploratory": candidate["collection_wall_ns"]}
    summary = {"status": "validated", "cpu_isolation": "unverified",
               "crypto_source_revision": off["crypto_source_revision"],
               "binary_sha256": binary_hash, "streams": rows,
               "paired_order": ["primary_off", "primary_on", "disjoint_on", "disjoint_off"]}
    build = json.loads((HERE / "results/clean_build.json").read_text())
    assert build["status"] == "verified"
    assert build["test_exit_code"] == build["build_exit_code"] == 0
    assert build["test_count"] == 1
    assert build["dependency_revision"] == summary["crypto_source_revision"]
    assert build["binary_sha256"] == binary_hash
    assert build["source_sha256"] == digest(HERE / "collector/src/main.rs")
    assert build["manifest_sha256"] == digest(HERE / "collector/Cargo.toml")
    assert build["lock_sha256"] == digest(HERE / "collector/Cargo.lock")
    assert build["test_log_sha256"] == digest(HERE / "results/clean_test.log.gz")
    assert build["build_log_sha256"] == digest(HERE / "results/clean_build.log.gz")
    replay = json.loads((HERE / "results/sage_replay.json").read_text())
    runtime_path = HERE / "results/sage_runtime.json"
    assert replay["status"] == "verified"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert replay["checked_sage_runtime_sha256"] == digest(runtime_path)
    assert replay["checker_sha256"] == digest(HERE / "replay_sage.py")
    assert replay["filter_index_sha256"] == digest(HERE / "inputs/index.bin")
    assert replay["export_sha256"] == digest(HERE / "inputs/export.json")
    for stream in ("primary", "disjoint"):
        checked = replay["per_stream"][stream]
        assert checked["status"] == "verified" and checked["rank"] == 5
        assert checked["ordered_incidences_verified"] == rows[stream]["ordered_incidence_count"]
        assert checked["workload_sha256"] == digest(HERE / f"inputs/{stream}.json")
        assert checked["candidate_receipt_sha256"] == digest(HERE / f"results/{stream}_on.json")
    path = HERE / "results/summary.json"
    if path.exists():
        assert json.loads(path.read_text()) == summary
    else:
        with path.open("x") as output:
            json.dump(summary, output, sort_keys=True, indent=2)
            output.write("\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
