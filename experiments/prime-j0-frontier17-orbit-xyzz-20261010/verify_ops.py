#!/usr/bin/env python3
"""Verify the seventeen-window counter patch and exact operation counts."""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
PATTERN = re.compile(
    r"^mode=(\w+) cases=(\d+) point_kernel_add=(\d+) point_kernel_sub=(\d+) "
    r"point_kernel_mul=(\d+) point_kernel_square=(\d+) gauge_rotations=(\d+)$", re.M)


def digest(data):
    return sha256(data).hexdigest()


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    release_log = (HERE / "release-tests.log").read_bytes()
    assert digest(release_log) == receipt["release_test_log_sha256"]
    assert receipt["release_tests_passed"] == 112
    assert b"test result: ok. 112 passed; 0 failed;" in release_log
    assert receipt["retained_bytes"] == 16_930_036
    log_raw = (HERE / "ops-diagnostic.log").read_bytes()
    patch_path = HERE / "ops-diagnostic.patch"
    assert record["source_freeze_commit"] == receipt["source_freeze_commit"]
    assert record["base_source_sha256"] == receipt["source_sha256"][SOURCE]
    assert digest((ROOT / SOURCE).read_bytes()) == record["base_source_sha256"]
    assert digest(log_raw) == record["diagnostic_log_sha256"]
    assert digest(patch_path.read_bytes()) == record["diagnostic_patch_sha256"]
    assert digest((HERE / "fresh-inputs.json").read_bytes()) == record["fresh_input_sha256"]
    assert b"test result: ok. 1 passed; 0 failed;" in log_raw
    with tempfile.TemporaryDirectory(prefix="orbit-tau-ops-") as temporary:
        target = Path(temporary) / SOURCE
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / SOURCE).read_bytes())
        subprocess.run(["git", "apply", str(patch_path.resolve())], cwd=temporary,
                       check=True, capture_output=True)
        assert digest(target.read_bytes()) == record["instrumented_source_sha256"]
    rows = {}
    for match in PATTERN.finditer(log_raw.decode()):
        rows[match.group(1)] = dict(zip(
            ("cases", "point_kernel_add", "point_kernel_sub", "point_kernel_mul",
             "point_kernel_square", "gauge_rotations"),
            map(int, match.groups()[1:])))
    assert rows == record["operations"]
    assert set(rows) == {"frontier19_xyzz", "frontier17_xyzz"}
    old, new = rows["frontier19_xyzz"], rows["frontier17_xyzz"]
    assert old["cases"] == new["cases"] == 4096
    assert old["gauge_rotations"] == new["gauge_rotations"] == 0
    assert old["point_kernel_add"] - new["point_kernel_add"] == 8_187
    assert old["point_kernel_sub"] - new["point_kernel_sub"] == 52_943
    assert old["point_kernel_mul"] - new["point_kernel_mul"] == 65_496
    assert old["point_kernel_square"] - new["point_kernel_square"] == 16_374
    print("frontier17_point_kernel_counts_verified=1 cases=4096 saved_muls=65496 saved_squares=16374")


if __name__ == "__main__":
    main()
