#!/usr/bin/env python3
"""Verify the frozen 16/17-window field-operation diagnostic."""

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
    compact, reference = counts["frontier16_xyzz_tau"], counts["frontier17_xyzz_tau"]
    assert compact["cases"] == reference["cases"] == 4096
    assert compact["digit_terms"] == 65536
    assert reference["digit_terms"] - compact["digit_terms"] == 4091
    assert reference["mul"] - compact["mul"] == 32718
    assert reference["square"] - compact["square"] == 8179
    assert reference["add"] - compact["add"] == 4085
    assert reference["sub"] - compact["sub"] == 29058
    print("frontier16_ops_verified=1 cases=4096 saved_digit_terms=4091 saved_mul=32718 saved_square=8179")


if __name__ == "__main__":
    main()
