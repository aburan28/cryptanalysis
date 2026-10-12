#!/usr/bin/env python3
"""Verify both holdout modes and the independent 129-case candidate fixture."""

from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REFERENCE_MODE = "unit_orbit_u256_sector14_xyzz_gauge_pareto_solinas_fixed"
CANDIDATE_MODE = "unit_orbit_u256_radix943_xyzz_gauge_pareto_solinas_fixed"


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def normalized(value):
    return value.lower().removeprefix("0x")


def verify(fixture_path, output_path, mode):
    cases = json.loads(fixture_path.read_text())["cases"]
    lines = output_path.read_text().splitlines()
    assert len(lines) == len(cases), (output_path, len(lines), len(cases))
    points = []
    for index, (case, line) in enumerate(zip(cases, lines)):
        fields = dict(item.split("=", 1) for item in line.split())
        point = ("identity" if case["expected_identity"] else
                 normalized(case["expected_x_hex"]) + ":" +
                 normalized(case["expected_y_hex"]))
        expected = {"verified": "1", "mode": mode,
                    "scalar": normalized(case["scalar_hex"]),
                    "base_x": normalized(case["base_x_hex"]),
                    "base_y": normalized(case["base_y_hex"]),
                    "point": point}
        for field, value in expected.items():
            assert fields[field] == value, (output_path, index, field)
        points.append(point)
    return {"cases": len(cases), "fixture_sha256": sha(fixture_path),
            "output_sha256": sha(output_path),
            "point_digest": sha256("\n".join(points).encode()).hexdigest()}


def main():
    holdout = HERE / "holdout.json"
    fixture = ROOT / "prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json"
    result = {
        "schema": 1, "status": "verified",
        "holdout_reference": verify(holdout, HERE / "holdout-reference.txt", REFERENCE_MODE),
        "holdout_candidate": verify(holdout, HERE / "holdout-candidate.txt", CANDIDATE_MODE),
        "independent_fixture_candidate": verify(fixture, HERE / "cli-fixture.txt", CANDIDATE_MODE),
        "verifier_sha256": sha(Path(__file__)),
    }
    assert result["holdout_reference"]["point_digest"] == result["holdout_candidate"]["point_digest"]
    assert result["holdout_reference"]["cases"] == result["holdout_candidate"]["cases"] == 512
    assert result["independent_fixture_candidate"]["cases"] == 129
    (HERE / "verify.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("512/512 holdout points matched both modes; 129/129 independent fixture points matched candidate")


if __name__ == "__main__":
    main()
