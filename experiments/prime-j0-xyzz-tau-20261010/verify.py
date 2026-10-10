#!/usr/bin/env python3
"""Verify immutable source binding and every XYZZ endomorphism replay point."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from run_replay import BASE, HERE, MODES, parse

ROOT = HERE.parent.parent
SOURCES = (
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "experiments/prime-j0-xyzz-tau-20261010/run_replay.py",
    "experiments/prime-j0-xyzz-tau-20261010/verify.py",
    "experiments/prime-j0-xyzz-tau-20261010/verify_ops.py",
)


def digest(data):
    return sha256(data).hexdigest()


def committed(commit, relative):
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def main():
    source = json.loads((HERE / "source-receipt.json").read_text())
    result = json.loads((HERE / "replay-result.json").read_text())
    freeze = source["source_freeze_commit"]
    assert result["source_freeze_commit"] == freeze
    assert set(source["source_sha256"]) == set(SOURCES)
    for relative, expected in source["source_sha256"].items():
        assert digest(committed(freeze, relative)) == expected, relative
        assert digest((ROOT / relative).read_bytes()) == expected, relative
    assert result["schema"] == 1 and result["timing_class"] == "correctness_only"
    assert source["retained_bytes_by_mode"] == {
        "frontier17_xyzz_tau": 6_615_956, "frontier18_xyzz_tau": 3_994_692}
    for panel, fixture_name in (("fresh4096", "fresh-fixture.json"),
                                ("edges", "edge-fixture.json")):
        fixture_raw = (BASE / fixture_name).read_bytes()
        assert digest(fixture_raw) == result["panels"][panel]["fixture_sha256"]
        cases = json.loads(fixture_raw)["cases"]
        assert len(cases) == (4096 if panel == "fresh4096" else 10)
        for label, (_, mode) in MODES.items():
            output = HERE / f"{panel}-{label}.out.gz"
            compressed = output.read_bytes()
            raw = gzip.decompress(compressed)
            record = result["panels"][panel]["outputs"][label]
            assert digest(compressed) == record["compressed_sha256"]
            assert digest(raw) == record["raw_sha256"]
            lines = raw.decode().splitlines()
            assert len(lines) == record["cases"] == len(cases)
            for index, (line, case) in enumerate(zip(lines, cases)):
                row = parse(line)
                expected = ("identity" if case["expected_identity"] else
                            case["expected_x_hex"] + ":" + case["expected_y_hex"])
                assert row["verified"] == "1" and row["curve"] == "secp256k1"
                assert row["mode"] == mode and row["scalar"] == case["scalar_hex"]
                assert row["point"] == expected, (panel, label, index)
    print("xyzz_tau_merge_verified=1 cases=4096 edges=10 modes=2 source_frozen=1")


if __name__ == "__main__":
    main()
