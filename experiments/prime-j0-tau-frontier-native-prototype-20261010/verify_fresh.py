#!/usr/bin/env python3
"""Verify both native outputs against the frozen independent fresh fixture."""

import gzip
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = {
    "frontier17": "unit_orbit_u256_tau_frontier17_fixed",
    "tau384": "unit_orbit_u256_tau384_matching_fixed",
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    result = json.loads((HERE / "fresh-result.json").read_text())
    inputs_raw = (HERE / "fresh-inputs.json").read_bytes()
    fixture_raw = (HERE / "fresh-fixture.json").read_bytes()
    inputs = json.loads(inputs_raw)
    fixture = json.loads(fixture_raw)
    assert inputs["seed"] == 20261010138
    assert inputs["count"] == len(inputs["scalars_hex"]) == 4096
    assert len(fixture["cases"]) == 4096
    assert digest(inputs_raw) == result["input_sha256"] == fixture["input_sha256"]
    assert digest(fixture_raw) == result["fixture_sha256"]
    assert digest((HERE / "make_fresh_fixture.py").read_bytes()) == result["fixture_generator_sha256"]
    assert digest((HERE / "native-frontier17.patch").read_bytes()) == result["patch_sha256"]
    points = {}
    for label, mode in MODES.items():
        compressed = (HERE / f"fresh4096-{label}.out.gz").read_bytes()
        raw = gzip.decompress(compressed)
        hashes = result["outputs"][label]
        assert digest(compressed) == hashes["compressed_sha256"]
        assert digest(raw) == hashes["raw_sha256"]
        lines = raw.decode().splitlines()
        assert len(lines) == hashes["verified_cases"] == 4096
        points[label] = []
        for index, line in enumerate(lines):
            record = parse(line)
            case = fixture["cases"][index]
            assert record["verified"] == "1" and record["curve"] == "secp256k1"
            assert record["mode"] == mode
            assert record["scalar"] == case["scalar_hex"] == inputs["scalars_hex"][index]
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert record["point"] == expected
            points[label].append(record["point"])
    assert points["frontier17"] == points["tau384"]
    print("fresh_frontier17_verified=1 cases=4096 paired_reference=1")


if __name__ == "__main__":
    main()
