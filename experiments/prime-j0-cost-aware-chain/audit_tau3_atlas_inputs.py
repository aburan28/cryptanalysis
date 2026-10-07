#!/usr/bin/env python3
"""Read-only replay of the prospective tau3 atlas fixture and exclusions."""

import hashlib
import json
from pathlib import Path
import struct

from make_tau3_atlas_inputs import PRIOR_FIXTURES, ROOT, SEED
from make_tail_gated_inputs import uniform_scalar


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest = json.loads((ROOT / "tau3-atlas-inputs.json").read_text())
    assert manifest["status"] == "frozen_tau3_atlas_disjoint_fixture"
    assert manifest["seed"] == SEED and len(manifest["cases"]) == 8
    assert manifest["source_sha256"] == sha256(
        (ROOT / "make_tau3_atlas_inputs.py").read_bytes())
    assert [entry["name"] for entry in manifest["excluded_prior_manifests"]] == list(PRIOR_FIXTURES)
    for entry in manifest["excluded_prior_manifests"]:
        assert entry["sha256"] == sha256((ROOT / entry["name"]).read_bytes())
    for curve_index, curve_name in enumerate(("glv-j0-32", "j0-56")):
        excluded = set()
        accepted = set()
        for name in PRIOR_FIXTURES:
            prior = json.loads((ROOT / name).read_text())
            for case in prior["cases"]:
                if case["curve"]["name"] != curve_name:
                    continue
                raw = (ROOT / case["scalar_file"]).read_bytes()
                assert sha256(raw) == case["scalar_file_sha256"]
                excluded.update(struct.unpack(f"<{len(raw)//8}Q", raw))
        cases = [case for case in manifest["cases"] if case["curve"]["name"] == curve_name]
        assert [case["point_index"] for case in cases] == [0, 1, 2, 3]
        for case in cases:
            state = SEED ^ (curve_index << 32) ^ case["point_index"]
            expected = []
            while len(expected) < 4096:
                state, scalar = uniform_scalar(state, case["curve"]["order"])
                if scalar in excluded or scalar in accepted:
                    continue
                accepted.add(scalar)
                expected.append(scalar)
            raw = (ROOT / case["scalar_file"]).read_bytes()
            assert len(raw) == 4096 * 8
            assert sha256(raw) == case["scalar_file_sha256"]
            assert list(struct.unpack("<4096Q", raw)) == expected
            assert case["excluded_scalar_count"] == len(excluded)
            assert case["reference_status"] == 0 and not case["reference_stderr"]
            assert f"output_digest={case['expected_output_digest']}" in case["reference_stdout"]
    print("tau3 atlas fixture audit: PASS (32,768 disjoint scalars, 8 generic outputs)")


if __name__ == "__main__":
    main()
