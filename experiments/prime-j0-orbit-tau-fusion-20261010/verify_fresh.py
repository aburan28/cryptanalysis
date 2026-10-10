#!/usr/bin/env python3
"""Verify source binding and every independently computed fresh point."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from make_inputs import COUNT, N, SEED, SOURCES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODES = {
    "orbit_tau": "unit_orbit_u256_tau_frontier19_orbit_tau_fixed",
    "expanded": "unit_orbit_u256_tau_frontier19_expanded_fixed",
}


def digest(data):
    return sha256(data).hexdigest()


def committed(commit, relative):
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    receipt = json.loads((HERE / "source-receipt.json").read_text())
    result = json.loads((HERE / "fresh-result.json").read_text())
    inputs_raw = (HERE / "fresh-inputs.json").read_bytes()
    fixture_raw = (HERE / "fresh-fixture.json").read_bytes()
    inputs, fixture = json.loads(inputs_raw), json.loads(fixture_raw)
    freeze = receipt["source_freeze_commit"]
    assert result["source_freeze_commit"] == freeze
    for relative, expected in receipt["source_sha256"].items():
        assert digest((ROOT / relative).read_bytes()) == expected, relative
        assert digest(committed(freeze, relative)) == expected, relative
    for name in ("make_inputs.py", "make_fresh_fixture.py", "run_fresh.py", "verify_fresh.py"):
        relative = f"experiments/prime-j0-orbit-tau-fusion-20261010/{name}"
        assert committed(freeze, relative) == (ROOT / relative).read_bytes(), name
    assert receipt["retained_bytes"] == result["retained_bytes"] == 5_726_228
    assert result["timing_class"] == "correctness_only"
    assert inputs["seed"] == SEED == 20261010142
    assert len(inputs["scalars_hex"]) == inputs["count"] == result["cases"] == COUNT == 4096
    assert digest(inputs_raw) == result["input_sha256"] == fixture["input_sha256"]
    assert digest(fixture_raw) == result["fixture_sha256"]
    assert fixture["reference_source_sha256"] == digest((
        ROOT / "experiments/prime-j0-tau-power16-20261010/verify_group.py").read_bytes())
    assert len(fixture["cases"]) == COUNT
    values = [int(text, 16) for text in inputs["scalars_hex"]]
    assert inputs["scalar_sha256"] == result["scalar_sha256"] == digest(
        b"".join(value.to_bytes(32, "big") for value in values))
    reduced = {value % N for value in values}
    assert len(reduced) == COUNT
    assert set(inputs["source_sha256"]) == set(SOURCES)
    seen = set()
    for name in SOURCES:
        raw = (ROOT / "experiments" / name).read_bytes()
        assert inputs["source_sha256"][name] == digest(raw), name
        seen.update(int(text, 16) % N for text in json.loads(raw)["scalars_hex"])
    assert not reduced & seen
    points = {}
    for label, mode in MODES.items():
        compressed = (HERE / f"fresh4096-{label}.out.gz").read_bytes()
        raw = gzip.decompress(compressed)
        hashes = result["outputs"][label]
        assert digest(compressed) == hashes["compressed_sha256"]
        assert digest(raw) == hashes["raw_sha256"]
        lines = raw.decode().splitlines()
        assert len(lines) == hashes["verified_cases"] == COUNT
        points[label] = []
        for index, line in enumerate(lines):
            row = parse(line)
            case = fixture["cases"][index]
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert row["verified"] == "1" and row["curve"] == "secp256k1"
            assert row["mode"] == mode
            assert row["scalar"] == case["scalar_hex"] == inputs["scalars_hex"][index]
            assert row["point"] == expected, (label, index)
            points[label].append(row["point"])
    assert points["orbit_tau"] == points["expanded"]
    print("orbit_tau_fresh_verified=1 cases=4096 paired_reference=1 source_frozen=1")


if __name__ == "__main__":
    main()
