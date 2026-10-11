#!/usr/bin/env python3
"""Verify exact native test coverage across the interrupted run and shards."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent


def digest(raw):
    return sha256(raw).hexdigest()


def names(raw):
    return {
        name.decode() for name in
        re.findall(rb"^test (.+) \.\.\. ok$", raw, re.MULTILINE)
    }


def load_receipt(name):
    path = HERE / name
    return json.loads(path.read_bytes()), digest(path.read_bytes())


def checked_archive(name, receipt):
    archive = (HERE / name).read_bytes()
    assert digest(archive) == receipt["raw_log_archive_sha256"]
    raw = gzip.decompress(archive)
    assert digest(raw) == receipt["raw_log_sha256"]
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    args = parser.parse_args()
    native = args.native_root.resolve()
    material, material_hash = load_receipt("native-materialization.json")
    for category in ("generated_sha256", "assets_sha256"):
        for name, expected in material[category].items():
            assert digest((native / name).read_bytes()) == expected, name

    first, first_hash = load_receipt("native-full-attempt1-check.json")
    assert first["status"] == "incomplete" and first["exit_code"] == 101
    assert first["collector_sha256"] == digest((HERE / "collect_full.py").read_bytes())
    first_log = checked_archive("native-full-attempt1.log.gz", first)
    first_names = names(first_log)
    assert len(first_names) == first["tests_passed"] == 101
    match = re.search(
        rb"Running unittests .*\((target/release/deps/eisenstein_fixed-[0-9a-f]+)\)",
        first_log,
    )
    assert match is not None
    binary = native / match.group(1).decode()
    binary_hash = digest(binary.read_bytes())
    assert binary_hash == first["binary_sha256"]

    hybrid, hybrid_hash = load_receipt("native-hybrid-isolate-check.json")
    assert hybrid["status"] == "passed" and hybrid["exit_code"] == 0
    assert hybrid["binary_sha256"] == binary_hash
    hybrid_log = (HERE / "native-hybrid-isolate.log").read_bytes()
    assert digest(hybrid_log) == hybrid["raw_log_sha256"]
    assert names(hybrid_log) == {hybrid["test"]}

    shard_names = []
    shard_hashes = []
    for index, expected_count in ((0, 21), (1, 20)):
        shard, receipt_hash = load_receipt(f"native-shard-{index}-check.json")
        assert shard["status"] == "passed" and shard["exit_code"] == 0
        assert shard["shard_index"] == index and shard["all_tests"] == 143
        assert shard["binary_sha256"] == binary_hash
        assert shard["source_materialization_sha256"] == material_hash
        assert shard["first_receipt_sha256"] == first_hash
        assert shard["hybrid_receipt_sha256"] == hybrid_hash
        assert shard["sharder_sha256"] == digest((HERE / "run_native_shard.py").read_bytes())
        raw = checked_archive(f"native-shard-{index}.log.gz", shard)
        passed = names(raw)
        assert passed == set(shard["selected_tests"]) == set(shard["passed_tests"])
        assert len(passed) == expected_count
        assert f"test result: ok. {expected_count} passed; 0 failed;".encode() in raw
        shard_names.append(passed)
        shard_hashes.append(receipt_hash)

    groups = [first_names, {hybrid["test"]}] + shard_names
    assert sum(map(len, groups)) == len(set().union(*groups)) == 143
    listed = subprocess.check_output([str(binary), "--list"], text=True)
    all_names = {
        line.removesuffix(": test") for line in listed.splitlines()
        if line.endswith(": test")
    }
    assert set().union(*groups) == all_names
    receipt = {
        "schema": 1,
        "status": "complete_sharded_coverage",
        "tests_passed": 143,
        "first_attempt_exit_code": first["exit_code"],
        "coverage_counts": [len(group) for group in groups],
        "all_names_sha256": digest("\n".join(sorted(all_names)).encode()),
        "binary_sha256": binary_hash,
        "materialization_sha256": material_hash,
        "first_receipt_sha256": first_hash,
        "hybrid_receipt_sha256": hybrid_hash,
        "shard_receipt_sha256": shard_hashes,
        "verifier_sha256": digest(Path(__file__).read_bytes()),
    }
    (HERE / "native-suite-coverage.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "tests_passed", "coverage_counts")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
