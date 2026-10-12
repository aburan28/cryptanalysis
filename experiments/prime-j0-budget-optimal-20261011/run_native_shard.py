#!/usr/bin/env python3
"""Complete the native suite after an interrupted single-process attempt."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import time


HERE = Path(__file__).resolve().parent
HYBRID = "unit_orbit_windows::tests::hybrid_finalizer_matches_parent_and_fresh_points"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    parser.add_argument("index", type=int, choices=(0, 1))
    args = parser.parse_args()
    native = args.native_root.resolve()
    first = json.loads((HERE / "native-full-attempt1-check.json").read_bytes())
    hybrid = json.loads((HERE / "native-hybrid-isolate-check.json").read_bytes())
    assert first["status"] == "incomplete" and first["exit_code"] == 101
    assert hybrid["status"] == "passed" and hybrid["test"] == HYBRID
    log = gzip.decompress((HERE / "native-full-attempt1.log.gz").read_bytes())
    assert digest(log) == first["raw_log_sha256"]
    passed = set(re.findall(rb"^test (.+) \.\.\. ok$", log, re.MULTILINE))
    passed = {name.decode() for name in passed}
    assert len(passed) == first["tests_passed"] == 101
    assert HYBRID not in passed

    match = re.search(
        rb"Running unittests .*\((target/release/deps/eisenstein_fixed-[0-9a-f]+)\)",
        log,
    )
    assert match is not None
    binary = native / match.group(1).decode()
    binary_hash = digest(binary.read_bytes())
    assert binary_hash == first["binary_sha256"] == hybrid["binary_sha256"]
    listed = subprocess.check_output([str(binary), "--list"], text=True)
    all_names = {
        line.removesuffix(": test") for line in listed.splitlines()
        if line.endswith(": test")
    }
    assert len(all_names) == 143
    assert passed | {HYBRID} <= all_names
    remaining = sorted(all_names - passed - {HYBRID})
    assert len(remaining) == 41
    selected = set(remaining[args.index::2])
    skipped = sorted(all_names - selected)
    command = [str(binary), "--exact", "--test-threads=1"]
    for name in skipped:
        command.extend(("--skip", name))

    raw_path = HERE / f"native-shard-{args.index}.log"
    start = time.monotonic()
    with raw_path.open("wb") as output:
        try:
            result = subprocess.run(command, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=900)
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
    outer_s = time.monotonic() - start
    raw = raw_path.read_bytes()
    actual = {
        name.decode() for name in
        re.findall(rb"^test (.+) \.\.\. ok$", raw, re.MULTILINE)
    }
    complete = (
        exit_code == 0 and actual == selected
        and f"test result: ok. {len(selected)} passed; 0 failed;".encode() in raw
    )
    archive = gzip.compress(raw, mtime=0)
    archive_path = HERE / f"native-shard-{args.index}.log.gz"
    archive_path.write_bytes(archive)
    assert gzip.decompress(archive) == raw
    receipt = {
        "schema": 1,
        "status": "passed" if complete else "incomplete",
        "exit_code": exit_code,
        "outer_elapsed_s": outer_s,
        "shard_index": args.index,
        "all_tests": len(all_names),
        "selected_tests": sorted(selected),
        "passed_tests": sorted(actual),
        "binary_sha256": binary_hash,
        "source_materialization_sha256": digest(
            (HERE / "native-materialization.json").read_bytes()),
        "first_receipt_sha256": digest(
            (HERE / "native-full-attempt1-check.json").read_bytes()),
        "hybrid_receipt_sha256": digest(
            (HERE / "native-hybrid-isolate-check.json").read_bytes()),
        "raw_log_sha256": digest(raw),
        "raw_log_archive_sha256": digest(archive),
        "sharder_sha256": digest(Path(__file__).read_bytes()),
    }
    (HERE / f"native-shard-{args.index}-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "shard_index", "exit_code", "all_tests")},
                     sort_keys=True))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
