#!/usr/bin/env python3
"""Replay scalar boundary points through XYZZ and Jacobian modes."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
MODES = {
    "frontier17_two_x": "--check-scalar-unit-orbit-u256-tau-frontier17-two-x-xyzz-fixed-fixture",
    "frontier17_xyzz": "--check-scalar-unit-orbit-u256-tau-frontier17-orbit-xyzz-fixed-fixture",
    "frontier18_two_x": "--check-scalar-unit-orbit-u256-tau-frontier18-two-x-xyzz-fixed-fixture",
    "frontier18_xyzz": "--check-scalar-unit-orbit-u256-tau-frontier18-orbit-xyzz-fixed-fixture",
    "xyzz": "--check-scalar-unit-orbit-u256-tau-frontier19-xyzz-fixed-fixture",
}


def digest(data):
    return sha256(data).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    binary = Path(sys.argv[1]).resolve(strict=True)
    fixture_path = HERE / "edge-fixture.json"
    fixture_raw = fixture_path.read_bytes()
    cases = json.loads(fixture_raw)["cases"]
    assert len(cases) == 10
    outputs = {}
    points = {}
    for label, flag in MODES.items():
        target = HERE / f"edges-{label}.out"
        assert not target.exists()
        run = subprocess.run([str(binary), flag, str(fixture_path)],
                             capture_output=True, timeout=30)
        assert run.returncode == 0 and not run.stderr, (label, run.stderr[-2000:])
        lines = run.stdout.decode().splitlines()
        assert len(lines) == len(cases)
        points[label] = []
        for line, case in zip(lines, cases):
            row = parse(line)
            expected = ("identity" if case["expected_identity"] else
                        case["expected_x_hex"] + ":" + case["expected_y_hex"])
            assert row["scalar"] == case["scalar_hex"] and row["point"] == expected
            assert row["verified"] == "1"
            points[label].append(row["point"])
        target.write_bytes(run.stdout)
        outputs[label] = {"cases": len(lines), "raw_sha256": digest(run.stdout)}
    assert all(stream == points["xyzz"] for stream in points.values())
    receipt = {"schema": 1, "fixture_sha256": digest(fixture_raw),
               "binary_sha256": digest(binary.read_bytes()), "outputs": outputs,
               "timing_class": "correctness_only"}
    (HERE / "edge-result.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("two_x_orbit_edges_verified=10 modes=5")


if __name__ == "__main__":
    main()
