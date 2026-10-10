#!/usr/bin/env python3
"""Verify the frozen two-x orbit counter patch and arithmetic tradeoff."""

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
    r"point_kernel_mul=(\d+) point_kernel_square=(\d+) power0=(\d+) "
    r"power1=(\d+) power2=(\d+)$", re.M)
KEYS = ("cases", "point_kernel_add", "point_kernel_sub", "point_kernel_mul",
        "point_kernel_square", "power0", "power1", "power2")


def digest(data):
    return sha256(data).hexdigest()


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    release_log = (HERE / "release-tests.log").read_bytes()
    assert digest(release_log) == receipt["release_test_log_sha256"]
    assert receipt["release_tests_passed"] == 118
    assert b"test result: ok. 118 passed; 0 failed;" in release_log
    assert receipt["retained_bytes_by_mode"] == {
        "frontier17_two_x": 12_804_404,
        "frontier17_xyzz": 16_930_036,
        "frontier18_two_x": 7_561_860,
        "frontier18_xyzz": 9_939_972,
        "xyzz": 5_726_228,
    }
    log_raw = (HERE / "ops-diagnostic.log").read_bytes()
    patch_path = HERE / "ops-diagnostic.patch"
    assert record["source_freeze_commit"] == receipt["source_freeze_commit"]
    assert record["base_source_sha256"] == receipt["source_sha256"][SOURCE]
    assert digest((ROOT / SOURCE).read_bytes()) == record["base_source_sha256"]
    assert digest(log_raw) == record["diagnostic_log_sha256"]
    assert digest(patch_path.read_bytes()) == record["diagnostic_patch_sha256"]
    assert digest((HERE / "fresh-inputs.json").read_bytes()) == record["fresh_input_sha256"]
    assert b"test result: ok. 1 passed; 0 failed;" in log_raw
    with tempfile.TemporaryDirectory(prefix="two-x-ops-") as temporary:
        target = Path(temporary) / SOURCE
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / SOURCE).read_bytes())
        subprocess.run(["git", "apply", str(patch_path.resolve())], cwd=temporary,
                       check=True, capture_output=True)
        assert digest(target.read_bytes()) == record["instrumented_source_sha256"]
    rows = {match.group(1): dict(zip(KEYS, map(int, match.groups()[1:])))
            for match in PATTERN.finditer(log_raw.decode())}
    assert rows == record["operations"]
    assert set(rows) == {"frontier19_xyzz", "frontier18_xyzz", "frontier18_two_x",
                         "frontier17_xyzz", "frontier17_two_x"}
    for name, row in rows.items():
        assert row["cases"] == 4096, name
        if not name.endswith("two_x"):
            assert (row["power0"], row["power1"], row["power2"]) == (0, 0, 0)
    for width in (17, 18):
        full = rows[f"frontier{width}_xyzz"]
        compact = rows[f"frontier{width}_two_x"]
        for key in ("point_kernel_add", "point_kernel_mul", "point_kernel_square"):
            assert compact[key] == full[key], (width, key)
        assert compact["point_kernel_sub"] - full["point_kernel_sub"] == (
            compact["power1"] + compact["power2"]), width
    assert rows["frontier17_xyzz"]["point_kernel_mul"] == 524_256
    assert rows["frontier18_xyzz"]["point_kernel_mul"] == 557_040
    assert rows["frontier19_xyzz"]["point_kernel_mul"] == 589_776
    print("two_x_point_kernel_counts_verified=1 cases=4096 "
          "extra_sub_17=46497 extra_sub_18=49217")


if __name__ == "__main__":
    main()
