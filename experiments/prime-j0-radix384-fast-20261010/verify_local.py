#!/usr/bin/env python3
"""Validate raw fast radix-384 logs and bind them to source and binary hashes."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

from verify_inputs import main as verify_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
EVIDENCE = HERE / "evidence/local"
SOURCE = (
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    *(f"experiments/prime-j0-radix384-fast-20261010/{name}" for name in (
        "PROTOCOL.md", "PROOF.md", "check_algebra.py", "make_inputs.py",
        "fresh-inputs.json", "verify_inputs.py", "verify_local.py",
        "audit_arm64.py", "runpod_correctness.sh", "stage_source.py",
    )),
)
RAW = (
    "native-tests.log", "native-build.log", "division.log", "prior-panel.log",
    "fresh-panel.log", "reference-fixture.log", "fast-fixture.log", "assembly.json",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_map(name):
    return [dict(item.split("=", 1) for item in line.split())
            for line in (EVIDENCE / name).read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = EVIDENCE / "receipt.json"
    if output.exists():
        raise SystemExit("local receipt already exists")
    verify_inputs()
    suite = (EVIDENCE / "native-tests.log").read_text()
    assert "test result: ok. 95 passed; 0 failed;" in suite
    checks = {
        "division.log": r"fast_radix384_division_cases=10595",
        "prior-panel.log": r"fast_radix384_prior_panel_cases=4096",
        "fresh-panel.log": r"fast_radix384_fresh_panel_cases=4096 division_checks=122880",
    }
    for name, pattern in checks.items():
        log = (EVIDENCE / name).read_text()
        assert re.search(pattern, log), name
        assert "test result: ok. 1 passed; 0 failed;" in log, name
    reference = row_map("reference-fixture.log")
    fast = row_map("fast-fixture.log")
    assert len(reference) == len(fast) == 129
    for left, right in zip(reference, fast):
        assert left.pop("mode") == "unit_orbit_u256_radix384_fixed"
        assert right.pop("mode") == "unit_orbit_u256_radix384_fast_fixed"
        assert left == right and left["verified"] == "1"
    assembly = json.loads((EVIDENCE / "assembly.json").read_text())
    counts = assembly["counts"]
    assert counts["multiply_u256_radix384"]["umulh"] + counts["multiply_u256_radix384"]["umull"] == 12
    assert counts["multiply_u256_radix384_fast"]["umulh"] + counts["multiply_u256_radix384_fast"]["umull"] == 4
    assert all(value["udiv"] == 0 for value in counts.values())
    assert assembly["binary_sha256"] == sha(binary)
    record = {
        "schema": 1,
        "timing_class": "correctness_and_static_assembly_only",
        "source_freeze_commit": "5ceb68277c8de04250daf0e0732abc651fb98d34",
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "release": platform.release(),
                 "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
                 "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip()},
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE},
        "raw_sha256": {name: sha(EVIDENCE / name) for name in RAW},
        "binary_sha256": sha(binary),
        "input_scalar_sha256": json.loads((HERE / "fresh-inputs.json").read_text())["scalar_sha256"],
        "suite": {"passed": 95, "failed": 0},
        "division_boundary_cases": 10595,
        "prior_panel_scalars": 4096,
        "fresh_panel": {"scalars": 4096, "division_checks": 122880,
                        "independent_binary_points": 128},
        "fixture": {"paired_points": 129, "verified": True},
        "retained_bytes_each_mode": 24283336,
        "assembly": assembly,
        "cpu_speedup": None,
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"local_receipt=passed binary_sha256={record['binary_sha256']}")


if __name__ == "__main__":
    main()
