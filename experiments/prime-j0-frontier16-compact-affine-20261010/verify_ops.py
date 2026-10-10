#!/usr/bin/env python3
"""Verify the compact affine operation-count patch and matched panel."""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile

from verify import HERE, ROOT, committed

SOURCE = "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
PATTERN = re.compile(
    r"mode=(\S+) cases=(\d+) digit_terms=(\d+) point_kernel_add=(\d+) "
    r"point_kernel_sub=(\d+) point_kernel_mul=(\d+) point_kernel_square=(\d+)"
)
FIELDS = ("cases", "digit_terms", "add", "sub", "mul", "square")


def digest(data):
    return sha256(data).hexdigest()


def main():
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    freeze = receipt["source_freeze_commit"]
    base = committed(freeze, SOURCE)
    assert record["schema"] == 1 and record["timing_class"] == "operation_count_only"
    assert record["source_freeze_commit"] == freeze
    assert digest(base) == record["base_source_sha256"] == receipt["source_sha256"][SOURCE]
    assert digest((ROOT / SOURCE).read_bytes()) == record["base_source_sha256"]
    patch = HERE / "ops-diagnostic.patch"
    assert digest(patch.read_bytes()) == record["patch_sha256"]
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / SOURCE
        target.parent.mkdir(parents=True)
        target.write_bytes(base)
        subprocess.run(["git", "apply", str(patch.resolve())], cwd=temporary,
                       check=True, capture_output=True)
        assert digest(target.read_bytes()) == record["instrumented_source_sha256"]
    log = (HERE / "ops-diagnostic.log").read_bytes()
    assert digest(log) == record["log_sha256"]
    assert b"test result: ok. 1 passed; 0 failed;" in log
    counts = {
        match.group(1): dict(zip(FIELDS, map(int, match.groups()[1:])))
        for match in PATTERN.finditer(log.decode())
    }
    assert counts == record["counts"]
    assert digest((HERE / "fresh-inputs.json").read_bytes()) == record["input_sha256"]
    compact, two_x = counts["frontier16_compact_affine"], counts["frontier16_xyzz_tau"]
    seventeen = counts["frontier17_xyzz_tau"]
    assert compact["cases"] == two_x["cases"] == seventeen["cases"] == 4096
    assert compact["digit_terms"] == two_x["digit_terms"] == 65535
    assert compact["add"] == two_x["add"] and compact["square"] == two_x["square"]
    assert compact["mul"] - two_x["mul"] == two_x["sub"] - compact["sub"] == 43746
    assert seventeen["digit_terms"] - compact["digit_terms"] == 4094
    assert compact["mul"] - seventeen["mul"] == 10976
    assert seventeen["square"] - compact["square"] == 8191
    assert receipt["retained_bytes_by_mode"]["frontier16_xyzz_tau"] - \
        receipt["retained_bytes_by_mode"]["frontier16_compact_affine"] == 3450048
    print("compact_affine_ops_verified=1 cases=4096 saved_bytes=3450048 extra_mul=43746 saved_sub=43746")


if __name__ == "__main__":
    main()
