#!/usr/bin/env python3
"""Validate the committed A1 replay receipts against their source and inputs."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "archive"
REPLAY = HERE / "replay"
FIELDS = (
    "status", "recovered_scalar", "attempts", "base_points_checked",
    "nonidentity_differences", "bloom_negative_checks", "bloom_positive_checks",
    "orbit_key_computations", "indexed_hits", "positive_lookup_misses", "hit_event",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    summary = read(REPLAY / "summary.json")
    assert summary["status"] == "verified"
    assert summary["matched_count"] == summary["fixture_count"] == 25
    assert summary["fresh_source_sha256"] == digest(HERE / "src/main.rs")
    assert summary["archive_source_sha256"] == digest(
        ARCHIVE / "a1_orbit_direct_aligned_scanner/src/main.rs")
    assert summary["replayer_sha256"] == digest(HERE / "replay_archive.py")
    assert summary["cargo_manifest_sha256"] == digest(HERE / "Cargo.toml")
    assert summary["cargo_lock_sha256"] == digest(HERE / "Cargo.lock")
    clean = read(HERE / "clean_crypto_build.json")
    assert clean["status"] == "verified"
    assert clean["candidate_source_sha256"] == digest(HERE / "src/main.rs")
    assert clean["candidate_manifest_sha256"] == digest(HERE / "Cargo.toml")
    assert clean["candidate_lock_sha256"] == digest(HERE / "Cargo.lock")
    assert clean["fixture_sha256"] == digest(HERE / "fixtures/single_hit.json")
    assert summary["index_sha256"] == digest(
        ARCHIVE / "results/a1_packed_enriched_index_r1.bin")
    assert summary["export_sha256"] == digest(
        ARCHIVE / "results/a1_packed_target_export_packed_enriched_r1.json")
    assert summary["cache_manifest_sha256"] == digest(REPLAY / "cache_manifest.json")
    manifest = read(REPLAY / "cache_manifest.json")
    build = read(REPLAY / "cache_build.json")
    check = read(REPLAY / "cache_check.json")
    assert manifest["binary_sha256"] == summary["fresh_binary_sha256"]
    assert manifest["bits_sha256"] == summary["cache_bits_sha256"]
    assert build["bits_sha256"] == summary["cache_bits_sha256"]
    assert check["all_index_conjugates_positive"] is True
    assert check["allocation_pointer_mod64"] == 0

    nonidentity = 0
    canonicalized = 0
    for i, row in enumerate(summary["rows"]):
        name = "primary" if i == 0 else f"target_{i - 1:02d}"
        assert row["name"] == name and row["status"] == "verified"
        assert all(row["matched_fields"].values())
        raw_path = REPLAY / f"{name}.json"
        raw = read(raw_path)
        assert row["fresh_raw_sha256"] == digest(raw_path)
        assert json.loads((REPLAY / f"{name}.stdout").read_text()) == raw
        if i == 0:
            stem = "a1_packed_target"
            workload = ARCHIVE / f"results/{stem}_workload_packed_enriched_r1.json"
            fixture = ARCHIVE / f"results/{stem}_fixture_r1.json"
            historical = ARCHIVE / "results/a1_orbit_direct_aligned_target_r1.json"
        else:
            j = i - 1
            workload = ARCHIVE / f"results/a1_orbit_bloom_rep_workload_{j:02d}.json"
            fixture = ARCHIVE / f"results/a1_orbit_bloom_rep_fixture_{j:02d}.json"
            historical = ARCHIVE / f"results/a1_orbit_direct_aligned_replay_{j:02d}.json"
            nonidentity += raw["nonidentity_differences"]
            canonicalized += raw["orbit_key_computations"]
        assert row["workload_sha256"] == digest(workload)
        assert row["fixture_sha256"] == digest(fixture)
        assert row["historical_receipt_sha256"] == digest(historical)
        prior = read(historical)
        assert prior["source_sha256"] == summary["archive_source_sha256"]
        assert all(raw[field] == prior["raw_result"][field] for field in FIELDS)
        assert row["fresh_scalar"] == raw["recovered_scalar"]

    assert nonidentity == summary["fresh_replay_nonidentity_differences"]
    assert canonicalized == summary["fresh_replay_orbit_key_computations"]
    assert nonidentity - canonicalized == summary["fresh_replay_orbit_key_avoided"]
    sage_primary = ARCHIVE / "results/a1_orbit_direct_aligned_target_audit_r1.json"
    sage_replay = ARCHIVE / "results/a1_orbit_direct_aligned_replay_audit_r1.json"
    assert digest(sage_primary) == summary["historical_sage_primary_audit_sha256"]
    assert digest(sage_replay) == summary["historical_sage_replay_audit_sha256"]
    assert read(sage_replay)["successful_witnesses_verified"] == 24
    sage_new = read(HERE / "sage_replay_result.json")
    assert sage_new["status"] == "verified"
    assert sage_new["source_sha256"] == digest(HERE / "sage_replay.py")
    assert sage_new["fixture_sha256"] == digest(HERE / "fixtures/single_hit.json")
    assert sage_new["recovered_scalar"] == read(REPLAY / "primary.json")["recovered_scalar"]
    assert read(HERE / "sage_runtime_info.json")["status"] == "verified"
    print(json.dumps({"status": "verified", "matched_schedules": 25,
                      "orbit_key_avoided": nonidentity - canonicalized,
                      "checked_sage_fixture": True}))


if __name__ == "__main__":
    main()
