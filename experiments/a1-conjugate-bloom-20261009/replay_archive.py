#!/usr/bin/env python3
"""Replay the archived A1 public targets with this source and a fresh cache."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ARCHIVED_SOURCE_SHA256 = "2802db73622e8ead53a7365783d15407bed87f9e7d288edfa4e70d33b43c3e56"
COMPARISON_FIELDS = (
    "status", "recovered_scalar", "attempts", "base_points_checked",
    "nonidentity_differences", "bloom_negative_checks", "bloom_positive_checks",
    "orbit_key_computations", "indexed_hits", "positive_lookup_misses", "hit_event",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(binary, args, output):
    completed = subprocess.run(
        [str(binary), *map(str, args)], capture_output=True, text=True, timeout=600
    )
    output.with_suffix(".stdout").write_text(completed.stdout)
    output.with_suffix(".stderr").write_text(completed.stderr)
    if completed.returncode:
        raise RuntimeError(f"{output.name}: exit {completed.returncode}")
    value = json.loads(completed.stdout)
    write_json(output, value)
    return value


def make_manifest(build, binary, index, bits):
    assert build["status"] == "verified"
    assert build["mode"] == "build-cache"
    assert build["index_sha256"] == digest(index)
    assert build["bits_sha256"] == digest(bits)
    assert build["binary_sha256"] == digest(binary)
    return {
        "status": "verified", "schema_version": 1, "field_degree": 53,
        "pair_index_orbits": build["pair_index_orbits"],
        "bit_count": build["bit_count"], "block_bits": build["block_bits"],
        "block_count": build["block_count"], "byte_count": build["byte_count"],
        "hash_count": build["hash_count"], "salt_one": build["salt_one"],
        "salt_two": build["salt_two"],
        "allocation_alignment_bytes": build["allocation_alignment_bytes"],
        "builder_allocation_pointer_mod64": build["allocation_pointer_mod64"],
        "builder_exhaustive_check": build["builder_exhaustive_check"],
        "index_sha256": build["index_sha256"],
        "bits_sha256": build["bits_sha256"],
        "binary_sha256": build["binary_sha256"],
        "build_wall_ns_exploratory": build["build_wall_ns_exploratory"],
        "exhaustive_check_wall_ns_exploratory":
            build["exhaustive_check_wall_ns_exploratory"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=HERE / "archive")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    archive = args.archive_root.resolve()
    binary = args.binary.resolve()
    output = args.output_dir.resolve()
    results = archive / "results"
    index = results / "a1_packed_enriched_index_r1.bin"
    export = results / "a1_packed_target_export_packed_enriched_r1.json"
    old_source = archive / "a1_orbit_direct_aligned_scanner/src/main.rs"
    assert digest(old_source) == ARCHIVED_SOURCE_SHA256
    assert index.stat().st_size == 4_429_944
    assert binary.is_file()
    output.mkdir(parents=True, exist_ok=False)

    bits = output / "bloom_bits.bin"
    build = run(binary, ["--build-cache", index, bits], output / "cache_build.json")
    manifest = make_manifest(build, binary, index, bits)
    manifest_path = output / "cache_manifest.json"
    write_json(manifest_path, manifest)
    check = run(binary, ["--check-cache", index, bits, manifest_path],
                output / "cache_check.json")
    assert check["all_index_conjugates_positive"] is True
    assert check["allocation_pointer_mod64"] == 0

    work = [
        ("primary", results / "a1_packed_target_workload_packed_enriched_r1.json",
         results / "a1_packed_target_fixture_r1.json",
         results / "a1_orbit_direct_aligned_target_r1.json"),
    ]
    for i in range(24):
        work.append((
            f"target_{i:02d}",
            results / f"a1_orbit_bloom_rep_workload_{i:02d}.json",
            results / f"a1_orbit_bloom_rep_fixture_{i:02d}.json",
            results / f"a1_orbit_direct_aligned_replay_{i:02d}.json",
        ))
    rows = []
    for name, workload, fixture, historical_path in work:
        historical = read_json(historical_path)
        assert historical["source_sha256"] == ARCHIVED_SOURCE_SHA256
        assert historical["status"] == "verified"
        fresh = run(binary, [export, index, workload, fixture, bits, manifest_path],
                    output / f"{name}.json")
        expected = historical["raw_result"]
        compared = {field: fresh[field] == expected[field]
                    for field in COMPARISON_FIELDS}
        row = {
            "name": name, "status": "verified" if all(compared.values()) else "mismatch",
            "matched_fields": compared, "workload_sha256": digest(workload),
            "fixture_sha256": digest(fixture),
            "historical_receipt_sha256": digest(historical_path),
            "fresh_raw_sha256": digest(output / f"{name}.json"),
            "fresh_scalar": fresh["recovered_scalar"],
        }
        rows.append(row)
        write_json(output / "partial_summary.json", rows)
        if row["status"] != "verified":
            raise AssertionError(f"{name}: archived and fresh results differ")

    replay_raw = [read_json(output / f"target_{i:02d}.json") for i in range(24)]
    nonidentity = sum(row["nonidentity_differences"] for row in replay_raw)
    canonicalized = sum(row["orbit_key_computations"] for row in replay_raw)
    sage_primary = results / "a1_orbit_direct_aligned_target_audit_r1.json"
    sage_replay = results / "a1_orbit_direct_aligned_replay_audit_r1.json"
    primary_audit = read_json(sage_primary)
    replay_audit = read_json(sage_replay)
    assert primary_audit["status"] == "completed"
    assert primary_audit["input_sha256"]["direct_native"] == digest(work[0][3])
    assert primary_audit["input_sha256"]["fixture"] == digest(work[0][2])
    assert primary_audit["input_sha256"]["workload"] == digest(work[0][1])
    assert replay_audit["status"] == "completed"
    assert replay_audit["successful_witnesses_verified"] == 24
    for i in range(24):
        _, workload, fixture, historical_path = work[i + 1]
        assert replay_audit["input_sha256"][f"target_{i:02d}_direct_native"] == digest(historical_path)
        assert replay_audit["input_sha256"][f"target_{i:02d}_fixture"] == digest(fixture)
        assert replay_audit["input_sha256"][f"target_{i:02d}_workload"] == digest(workload)
    crypto = (HERE / "../../../crypto").resolve()
    dependency_files = (
        "Cargo.toml", "src/lib.rs", "src/cryptanalysis/mod.rs",
        "src/cryptanalysis/koblitz_fast_arith.rs",
        "src/cryptanalysis/koblitz_index_calculus.rs",
    )
    summary = {
        "status": "verified", "fresh_source_sha256": digest(HERE / "src/main.rs"),
        "fresh_binary_sha256": digest(binary),
        "replayer_sha256": digest(Path(__file__)),
        "cargo_manifest_sha256": digest(HERE / "Cargo.toml"),
        "cargo_lock_sha256": digest(HERE / "Cargo.lock"),
        "crypto_dependency_file_sha256": {
            name: digest(crypto / name) for name in dependency_files},
        "crypto_dependency_git_commit": subprocess.check_output(
            ["git", "-C", str(crypto), "rev-parse", "HEAD"], text=True).strip(),
        "crypto_dependency_dirty_paths": subprocess.check_output(
            ["git", "-C", str(crypto), "status", "--porcelain", "--untracked-files=no"],
            text=True).splitlines(),
        "archive_source_sha256": ARCHIVED_SOURCE_SHA256,
        "index_sha256": digest(index), "export_sha256": digest(export),
        "cache_bits_sha256": digest(bits), "cache_manifest_sha256": digest(manifest_path),
        "fixture_count": len(rows), "matched_count": len(rows), "rows": rows,
        "fresh_replay_nonidentity_differences": nonidentity,
        "fresh_replay_orbit_key_computations": canonicalized,
        "fresh_replay_orbit_key_avoided": nonidentity - canonicalized,
        "historical_sage_primary_audit_sha256": digest(sage_primary),
        "historical_sage_replay_audit_sha256": digest(sage_replay),
        "historical_sage_replay_verified_witnesses": 24,
    }
    write_json(output / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "matched_count": len(rows),
                      "fresh_source_sha256": summary["fresh_source_sha256"],
                      "fresh_binary_sha256": summary["fresh_binary_sha256"]}))


if __name__ == "__main__":
    main()
