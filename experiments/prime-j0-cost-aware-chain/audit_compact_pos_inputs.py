#!/usr/bin/env python3
"""Read-only replay of compact-pos fixture generation and disjointness."""

import hashlib
import json
from pathlib import Path
import struct

from make_compact_pos_inputs import PRIOR_FIXTURES, ROOT, SEED
from make_tail_gated_inputs import uniform_scalar


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fixture = json.loads((ROOT / "compact-pos-inputs.json").read_text())
    assert fixture["status"] == "frozen_compact_pos_disjoint_fixture"
    assert fixture["seed"] == SEED and len(fixture["cases"]) == 8
    assert fixture["source_sha256"] == sha256(ROOT / "make_compact_pos_inputs.py")
    assert [entry["name"] for entry in fixture["excluded_prior_manifests"]] == list(PRIOR_FIXTURES)
    for entry in fixture["excluded_prior_manifests"]:
        assert entry["sha256"] == sha256(ROOT / entry["name"])
    for curve_index, name in enumerate(("glv-j0-32", "j0-56")):
        excluded = set()
        accepted = set()
        for manifest_name in PRIOR_FIXTURES:
            prior = json.loads((ROOT / manifest_name).read_text())
            for case in prior["cases"]:
                if case["curve"]["name"] != name:
                    continue
                path = ROOT / case["scalar_file"]
                raw = path.read_bytes()
                assert sha256(path) == case["scalar_file_sha256"]
                excluded.update(struct.unpack(f"<{len(raw)//8}Q", raw))
        cases = [case for case in fixture["cases"] if case["curve"]["name"] == name]
        assert [case["point_index"] for case in cases] == [0, 1, 2, 3]
        for case in cases:
            state = SEED ^ (curve_index << 32) ^ case["point_index"]
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
            assert sha256(path) == case["scalar_file_sha256"]
            assert list(struct.unpack("<4096Q", raw)) == expected
            assert case["excluded_scalar_count"] == len(excluded)
            assert case["reference_status"] == 0 and not case["reference_stderr"]
            assert f"output_digest={case['expected_output_digest']}" in case["reference_stdout"]
    print("compact-pos fixture audit: PASS (32,768 disjoint scalars, 8 reference outputs)")


if __name__ == "__main__":
    main()
