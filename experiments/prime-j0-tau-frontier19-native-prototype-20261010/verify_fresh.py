#!/usr/bin/env python3
"""Verify both native streams against the post-freeze independent fixture."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODES = {
    "frontier19": "unit_orbit_u256_tau_frontier19_fixed",
    "frontier17": "unit_orbit_u256_tau_frontier17_fixed",
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def committed(commit, path):
    relative = path.relative_to(ROOT)
    return subprocess.run(["git", "show", f"{commit}:{relative}"],
                          cwd=ROOT, check=True, capture_output=True).stdout


def main():
    result = json.loads((HERE / "fresh-result.json").read_text())
    receipt = json.loads((HERE / "receipt.json").read_text())
    inputs_raw = (HERE / "fresh-inputs.json").read_bytes()
    fixture_raw = (HERE / "fresh-fixture.json").read_bytes()
    inputs, fixture = json.loads(inputs_raw), json.loads(fixture_raw)
    assert inputs["seed"] == 20261010139
    assert inputs["count"] == len(inputs["scalars_hex"]) == 4096
    assert len(fixture["cases"]) == result["cases"] == 4096
    assert digest(inputs_raw) == result["input_sha256"] == fixture["input_sha256"]
    assert inputs["scalar_sha256"] == result["scalar_sha256"]
    assert digest(fixture_raw) == result["fixture_sha256"]
    assert result["binary_sha256"] == receipt["binary_sha256"]
    assert result["frontier19_delta_patch_sha256"] == receipt["frontier19_delta_patch_sha256"]
    assert result["timing_class"] == "correctness_only"
    assert result["execution_method"] == "native_cli_whole_fixture"
    frozen = result["source_freeze_commit"]
    for name, key in (("make_inputs.py", "input_generator_sha256"),
                      ("make_fresh_fixture.py", "fixture_generator_sha256"),
                      ("native-frontier19-delta.patch", "frontier19_delta_patch_sha256")):
        path = HERE / name
        raw = path.read_bytes()
        assert digest(raw) == result[key]
        assert committed(frozen, path) == raw

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
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert record["verified"] == "1" and record["curve"] == "secp256k1"
            assert record["mode"] == mode
            assert record["scalar"] == case["scalar_hex"] == inputs["scalars_hex"][index]
            assert record["point"] == expected
            points[label].append(record["point"])
    assert points["frontier19"] == points["frontier17"]
    print("fresh_frontier19_verified=1 cases=4096 paired_reference=1")


if __name__ == "__main__":
    main()
