#!/usr/bin/env python3
"""Verify raw local correctness logs and write their immutable receipt."""

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
BINARY = ROOT / "experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed"
SOURCE = (
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "experiments/prime-j0-radix384-20261010/PROTOCOL.md",
    "experiments/prime-j0-radix384-20261010/PROOF.md",
    "experiments/prime-j0-radix384-20261010/check_algebra.py",
    "experiments/prime-j0-radix384-20261010/make_inputs.py",
    "experiments/prime-j0-radix384-20261010/fresh-inputs.json",
)
RAW = (
    "radix384-native-build.log", "radix384-native-tests.log",
    "radix384-atlas.log", "radix384-panel.log",
    "radix384-fixture.log", "radix384-u15-fixture.log",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(name):
    return [dict(part.split("=", 1) for part in line.split())
            for line in (EVIDENCE / name).read_text().splitlines()]


def main():
    receipt = EVIDENCE / "receipt.json"
    if receipt.exists():
        raise SystemExit("local receipt already exists")
    verify_inputs()
    suite = (EVIDENCE / "radix384-native-tests.log").read_text()
    assert "test result: ok. 92 passed; 0 failed;" in suite
    atlas = (EVIDENCE / "radix384-atlas.log").read_text()
    panel = (EVIDENCE / "radix384-panel.log").read_text()
    match = re.search(r"radix384_residues=(\d+) table_slots=(\d+) retained_bytes=(\d+)", atlas)
    assert match and tuple(map(int, match.groups())) == (147456, 368670, 24283336)
    assert "test result: ok. 1 passed; 0 failed;" in atlas
    match = re.search(r"radix384_panel_cases=(\d+) retained_bytes=(\d+) addition_histogram=\[([^]]+)\]", panel)
    assert match and tuple(map(int, match.groups()[:2])) == (4096, 24283336)
    histogram = [int(value.strip()) for value in match[3].split(",")]
    assert histogram == [0] * 13 + [1, 4095]
    assert "test result: ok. 1 passed; 0 failed;" in panel
    reference = rows("radix384-u15-fixture.log")
    candidate = rows("radix384-fixture.log")
    assert len(reference) == len(candidate) == 129
    for left, right in zip(reference, candidate):
        assert left.pop("mode") == "unit_orbit_u256_sector15_fixed"
        assert right.pop("mode") == "unit_orbit_u256_radix384_fixed"
        assert left == right and left["verified"] == "1"
    record = {
        "schema": 1,
        "timing_class": "correctness_only",
        "source_freeze_commit": "9fee6b4c144a2daf476d98ed92c25dc8973bff57",
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "release": platform.release(),
                 "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
                 "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip()},
        "source_sha256": {name: sha(ROOT / name) for name in SOURCE},
        "raw_sha256": {name: sha(EVIDENCE / name) for name in RAW},
        "binary_sha256": sha(BINARY),
        "input_scalar_sha256": json.loads((HERE / "fresh-inputs.json").read_text())["scalar_sha256"],
        "suite": {"passed": 92, "failed": 0},
        "atlas": {"residues": 147456, "point_slots": 368670,
                  "retained_bytes": 24283336},
        "panel": {"scalars": 4096, "addition_histogram": histogram,
                  "independent_binary_points": 128},
        "fixture": {"paired_points": 129, "verified": True},
        "cpu_speedup": None,
    }
    receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"local_receipt=passed binary_sha256={record['binary_sha256']}")


if __name__ == "__main__":
    main()
