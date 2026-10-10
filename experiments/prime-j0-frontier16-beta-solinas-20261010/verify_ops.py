#!/usr/bin/env python3
"""Verify the Solinas counter patch and source-level product accounting."""

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
    r"point_kernel_sub=(\d+) point_kernel_generic_mul=(\d+) "
    r"point_kernel_square=(\d+) point_kernel_solinas_mul=(\d+) "
    r"source_limb_products=(\d+)"
)
FIELDS = ("cases", "digit_terms", "add", "sub", "generic_mul", "square",
          "solinas_mul", "source_limb_products")


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
    assert set(counts) == {"frontier16_beta_solinas", "frontier16_compact_affine",
                           "frontier16_xyzz_tau", "frontier17_xyzz_tau"}
    for count in counts.values():
        assert count["cases"] == 4096
        assert count["source_limb_products"] == (
            36 * (count["generic_mul"] + count["square"])
            + 23 * count["solinas_mul"])
    solinas, compact = counts["frontier16_beta_solinas"], counts["frontier16_compact_affine"]
    assert solinas["digit_terms"] == compact["digit_terms"] == 65536
    assert all(solinas[key] == compact[key] for key in ("add", "sub", "square"))
    assert compact["generic_mul"] - solinas["generic_mul"] == solinas["solinas_mul"] == 43743
    assert compact["source_limb_products"] - solinas["source_limb_products"] == 568659
    assert receipt["retained_bytes_by_mode"]["frontier16_beta_solinas"] - \
        receipt["retained_bytes_by_mode"]["frontier16_compact_affine"] == 96
    print("solinas_ops_verified=1 cases=4096 solinas_calls=43743 saved_source_products=568659")


if __name__ == "__main__":
    main()
