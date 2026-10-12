#!/usr/bin/env python3
"""Verify the counter-only patch, raw test log, and exact operation counts."""

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
    assert set(rows) == {"tau_expanded", "orbit_tau"}
    old, fused = rows["tau_expanded"], rows["orbit_tau"]
    assert old["cases"] == fused["cases"] == 4096
    assert old["gauge_rotations"] == old["point_kernel_mul"] - fused["point_kernel_mul"] == 8185
    assert fused["gauge_rotations"] == 0
    for name in ("point_kernel_add", "point_kernel_sub", "point_kernel_square"):
        assert old[name] == fused[name], name
    print("orbit_tau_point_kernel_counts_verified=1 cases=4096 saved_muls=8185")


if __name__ == "__main__":
    main()
