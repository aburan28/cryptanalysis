#!/usr/bin/env python3
"""Verify the replayed field-operation counter patch and matched counts."""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile

from verify import HERE, ROOT, committed

SOURCE = "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
PATTERN = re.compile(
    r"mode=(\S+) cases=(\d+) point_kernel_add=(\d+) point_kernel_sub=(\d+) "
    r"point_kernel_mul=(\d+) point_kernel_square=(\d+)"
)


def digest(data):
    return sha256(data).hexdigest()


def main():
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    freeze = receipt["source_freeze_commit"]
    base = committed(freeze, SOURCE)
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
    counts = {match.group(1): dict(zip(
        ("cases", "add", "sub", "mul", "square"),
        map(int, match.groups()[1:])))
        for match in PATTERN.finditer(log.decode())}
    assert counts == record["counts"]
    inputs = HERE.parent / "prime-j0-tau-bucket-two-x-20261010/fresh-inputs.json"
    assert digest(inputs.read_bytes()) == record["input_sha256"]
    for width in (17, 18):
        old, direct = counts[f"frontier{width}_direct"], counts[f"frontier{width}_xyzz_tau"]
        assert old["cases"] == direct["cases"] == 4096
        assert old["add"] == direct["add"] and old["sub"] == direct["sub"]
        assert old["mul"] - direct["mul"] == 4096
        assert old["square"] == direct["square"]
    assert record["timing_class"] == "operation_count_only"
    print("xyzz_tau_ops_verified=1 cases=4096 saved_mul_per_scalar=1 saved_square_per_scalar=0")


if __name__ == "__main__":
    main()
