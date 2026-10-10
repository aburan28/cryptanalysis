#!/usr/bin/env python3
"""Verify the frozen deferred-tau counter patch and exact bucket overhead."""

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
    r"point_kernel_mul=(\d+) point_kernel_square=(\d+)$", re.M)
KEYS = ("cases", "point_kernel_add", "point_kernel_sub", "point_kernel_mul",
        "point_kernel_square")


def digest(data):
    return sha256(data).hexdigest()


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    release_log = (HERE / "release-tests.log").read_bytes()
    assert digest(release_log) == receipt["release_test_log_sha256"]
    assert receipt["release_tests_passed"] == 122
    assert b"test result: ok. 122 passed; 0 failed;" in release_log
    assert receipt["retained_bytes_by_mode"] == {
        "frontier17_bucket": 6_615_956,
        "frontier17_two_x": 12_804_404,
        "frontier18_bucket": 3_994_692,
        "frontier18_two_x": 7_561_860,
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
    with tempfile.TemporaryDirectory(prefix="bucket-two-x-ops-") as temporary:
        target = Path(temporary) / SOURCE
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / SOURCE).read_bytes())
        subprocess.run(["git", "apply", str(patch_path.resolve())], cwd=temporary,
                       check=True, capture_output=True)
        assert digest(target.read_bytes()) == record["instrumented_source_sha256"]
    rows = {match.group(1): dict(zip(KEYS, map(int, match.groups()[1:])))
            for match in PATTERN.finditer(log_raw.decode())}
    assert rows == record["operations"]
    assert set(rows) == {"frontier19_xyzz", "frontier18_two_x", "frontier18_bucket",
                         "frontier17_two_x", "frontier17_bucket"}
    for row in rows.values():
        assert row["cases"] == 4096
    per_scalar = {"point_kernel_add": 6, "point_kernel_sub": 3,
                  "point_kernel_mul": 12, "point_kernel_square": 4}
    for width in (17, 18):
        full = rows[f"frontier{width}_two_x"]
        bucket = rows[f"frontier{width}_bucket"]
        for key, count in per_scalar.items():
            assert bucket[key] - full[key] == 4096 * count, (width, key)
    assert rows["frontier19_xyzz"]["point_kernel_mul"] == 589_728
    assert rows["frontier17_bucket"]["point_kernel_mul"] == 573_424
    assert rows["frontier18_bucket"]["point_kernel_mul"] == 606_200
    print("deferred_tau_point_kernel_counts_verified=1 cases=4096 "
          "extra_mul_per_scalar=12 extra_square_per_scalar=4")


if __name__ == "__main__":
    main()
