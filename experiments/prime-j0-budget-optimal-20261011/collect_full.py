#!/usr/bin/env python3
"""Bind the complete native Rust suite to its source, assets, and raw log."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess


HERE = Path(__file__).resolve().parent
TEST = "budget_optimal_tau_cover_matches_disjoint_holdout_and_binary_points"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    args = parser.parse_args()
    native = args.native_root.resolve()
    material = json.loads((HERE / "native-materialization.json").read_bytes())
    for category in ("generated_sha256", "assets_sha256"):
        for name, expected in material[category].items():
            assert digest((native / name).read_bytes()) == expected, name

    raw = (HERE / "native-full.log").read_bytes()
    log = raw.decode()
    assert "running 143 tests" in log
    assert f"test unit_orbit_windows::tests::{TEST} ... ok" in log
    assert "test result: ok. 143 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out" in log
    assert len(re.findall(r"^test .+ \.\.\. ok$", log, re.MULTILINE)) == 143
    match = re.search(
        r"Running unittests .*\((target/release/deps/eisenstein_fixed-[0-9a-f]+)\)",
        log)
    assert match is not None
    binary = native / match.group(1)
    assert binary.is_file()

    archive = gzip.compress(raw, mtime=0)
    (HERE / "native-full.log.gz").write_bytes(archive)
    receipt = {
        "schema": 1,
        "status": "passed",
        "tests_passed": 143,
        "tests_failed": 0,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "binary_sha256": digest(binary.read_bytes()),
        "generated_sha256": {
            name: digest((native / name).read_bytes())
            for name in material["generated_sha256"]
        },
        "assets_sha256": {
            name: digest((native / name).read_bytes())
            for name in material["assets_sha256"]
        },
        "raw_log_sha256": digest(raw),
        "raw_log_archive_sha256": digest(archive),
        "collector_sha256": digest(Path(__file__).read_bytes()),
    }
    (HERE / "native-full-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({key: receipt[key] for key in
                      ("status", "tests_passed", "binary_sha256",
                       "raw_log_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
