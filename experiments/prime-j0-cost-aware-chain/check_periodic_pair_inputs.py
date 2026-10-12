#!/usr/bin/env python3
"""Read-only verification of the frozen disjoint periodic-pair fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from make_inputs import read_fields
from make_periodic_pair_inputs import PRIOR_FIXTURES, SEED
from make_tail_gated_inputs import uniform_scalar


ROOT = Path(__file__).resolve().parent


def check(bench):
    manifest_path = ROOT / "periodic-pair-native-inputs.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "frozen_periodic_pair_native_disjoint_fixture"
    assert manifest["seed"] == SEED and len(manifest["cases"]) == 8
    assert hashlib.sha256((ROOT / "make_periodic_pair_inputs.py").read_bytes()).hexdigest() == \
        manifest["source_sha256"]
    assert len(manifest["excluded_prior_manifests"]) == len(PRIOR_FIXTURES)
    for pinned, name in zip(manifest["excluded_prior_manifests"], PRIOR_FIXTURES):
        assert pinned["name"] == name
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == pinned["sha256"]
    assert hashlib.sha256(bench.read_bytes()).hexdigest() == manifest["reference_binary_sha256"]
    for curve_index, curve in enumerate(("glv-j0-32", "j0-56")):
        excluded = set()
        accepted = set()
        for name in PRIOR_FIXTURES:
            prior = json.loads((ROOT / name).read_text())
            for case in prior["cases"]:
                if case["curve"]["name"] != curve:
                    continue
                raw = (ROOT / case["scalar_file"]).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
                excluded.update(struct.unpack(f"<{len(raw)//8}Q", raw))
        cases = [case for case in manifest["cases"] if case["curve"]["name"] == curve]
        assert [case["point_index"] for case in cases] == [0, 1, 2, 3]
        for case in cases:
            point_index = case["point_index"]
            state = SEED ^ (curve_index << 32) ^ point_index
            expected = []
            while len(expected) < 4096:
                state, value = uniform_scalar(state, case["curve"]["order"])
                if value in excluded or value in accepted:
                    continue
                accepted.add(value)
                expected.append(value)
            path = ROOT / case["scalar_file"]
            raw = path.read_bytes()
            assert len(raw) == 4096 * 8
            assert hashlib.sha256(raw).hexdigest() == case["scalar_file_sha256"]
            assert list(struct.unpack("<4096Q", raw)) == expected
            assert case["excluded_scalar_count"] == len(excluded)
            command = [str(bench), "reference", curve, str(point_index), str(path)]
            process = subprocess.run(command, text=True, capture_output=True)
            assert process.returncode == 0, (command, process.stderr)
            fields = read_fields(process.stdout)
            assert fields["verified"] == "1"
            assert fields["input_digest"] == case["input_digest"]
            assert fields["output_digest"] == case["expected_output_digest"]
            assert fields["base_x"] == case["base_x"]
            assert fields["base_y"] == case["base_y"]
        print(f"{curve}: 16,384 new unique scalars, {len(excluded)} prior scalars excluded")
    print("PASS: eight frozen cases, deterministic law, hashes, disjointness, generic outputs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve())
