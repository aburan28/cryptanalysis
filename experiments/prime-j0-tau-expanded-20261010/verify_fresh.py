#!/usr/bin/env python3
"""Verify the post-freeze tau-preexpanded replay and its source binding."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from make_inputs import COUNT, SEED, SOURCES, N

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MODES = {
    "expanded": "unit_orbit_u256_tau_frontier19_expanded_fixed",
    "orbit_x": "unit_orbit_u256_tau_frontier19_orbit_x_fixed",
    "frontier19": "unit_orbit_u256_tau_frontier19_fixed",
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def committed(commit, path):
    relative = path.relative_to(ROOT)
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def main():
    receipt_raw = (HERE / "source-receipt.json").read_bytes()
    result = json.loads((HERE / "fresh-result.json").read_text())
    receipt = json.loads(receipt_raw)
    inputs_raw = (HERE / "fresh-inputs.json").read_bytes()
    fixture_raw = (HERE / "fresh-fixture.json").read_bytes()
    inputs, fixture = json.loads(inputs_raw), json.loads(fixture_raw)
    assert (inputs["seed"], inputs["count"], len(inputs["scalars_hex"])) == (
        SEED, COUNT, COUNT)
    assert SEED == 20261010141
    assert len(fixture["cases"]) == result["cases"] == COUNT
    assert digest(inputs_raw) == result["input_sha256"] == fixture["input_sha256"]
    assert digest(fixture_raw) == result["fixture_sha256"]
    values = [int(text, 16) for text in inputs["scalars_hex"]]
    assert inputs["scalar_sha256"] == result["scalar_sha256"] == digest(
        b"".join(value.to_bytes(32, "big") for value in values))
    reduced = [value % N for value in values]
    assert len(set(reduced)) == COUNT
    seen = set()
    assert set(inputs["source_sha256"]) == set(SOURCES)
    for name in SOURCES:
        raw = (ROOT / "experiments" / name).read_bytes()
        assert inputs["source_sha256"][name] == digest(raw), name
        seen.update(int(value, 16) % N for value in json.loads(raw)["scalars_hex"])
    assert not set(reduced) & seen

    frozen = result["source_freeze_commit"]
    assert frozen == "4b563c866"
    for name in ("source-receipt.json", "native-tau-expanded-delta.patch",
                 "make_inputs.py", "make_fresh_fixture.py", "verify_inputs.py"):
        path = HERE / name
        assert committed(frozen, path) == path.read_bytes(), name
    patch = (HERE / "native-tau-expanded-delta.patch").read_bytes()
    assert digest(patch) == receipt["delta_patch_sha256"] == result["delta_patch_sha256"]
    assert result["retained_bytes"] == receipt["retained_bytes"] == 2_916_756
    assert result["timing_class"] == "correctness_only"
    assert result["execution_method"] == "native_cli_whole_fixture"
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
            record = parse(line)
            case = fixture["cases"][index]
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert record["verified"] == "1" and record["curve"] == "secp256k1"
            assert record["mode"] == mode
            assert record["scalar"] == case["scalar_hex"] == inputs["scalars_hex"][index]
            assert record["point"] == expected
            points[label].append(record["point"])
    assert points["expanded"] == points["orbit_x"] == points["frontier19"]
    print("tau_expanded_fresh_verified=1 cases=4096 paired_reference=1 source_frozen=1")


if __name__ == "__main__":
    main()
