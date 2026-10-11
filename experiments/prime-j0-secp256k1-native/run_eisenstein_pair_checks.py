#!/usr/bin/env python3
"""Check both fixed-generator scalar binaries without recording CPU timings."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import lazy_tau_screen as curve


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(word.split("=", 1) for word in line.split() if "=" in word)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path,
                        default=HERE / "eisenstein-pair-fixture.json")
    parser.add_argument("--conventional", type=Path,
                        default=HERE / "target/release/prime-j0-secp256k1-native-replay")
    parser.add_argument("--eisenstein", type=Path,
                        default=HERE / "target/release/eisenstein_fixed")
    args = parser.parse_args()
    fixture_path = args.fixture.resolve(strict=True)
    conventional = args.conventional.resolve(strict=True)
    eisenstein = args.eisenstein.resolve(strict=True)
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1
    assert fixture["reference_sha256"] == sha(HERE / "lazy_tau_screen.py")
    assert fixture["generator_sha256"] == sha(HERE / "make_eisenstein_pair_fixture.py")
    for index, case in enumerate(fixture["cases"]):
        assert case["index"] == index
        scalar = int(case["scalar_hex"], 16)
        point = curve.point_multiply(scalar % curve.ORDER)
        assert point == (int(case["expected_x_hex"], 16),
                         int(case["expected_y_hex"], 16))
        expected = f"{case['expected_x_hex']}:{case['expected_y_hex']}"
        commands = [
            [str(conventional), "--check-generator-case", "cached_projective",
             str(fixture_path), str(index)],
            [str(eisenstein), "--check-scalar-w2-case",
             str(fixture_path), str(index)],
        ]
        for command in commands:
            result = subprocess.run(command, text=True, capture_output=True,
                                    check=True, timeout=30)
            parsed = fields(result.stdout.strip())
            assert "online_ms" not in parsed
            assert parsed["verified"] == "1"
            assert parsed["curve"] == "secp256k1"
            assert parsed["base_x"] == case["base_x_hex"]
            assert parsed["base_y"] == case["base_y_hex"]
            assert parsed["scalar"] == case["scalar_hex"]
            assert parsed["point"] == expected, (index, command[0], parsed)
    print(json.dumps({
        "schema": 1, "status": "passed", "cases": len(fixture["cases"]),
        "checked_outputs": 2 * len(fixture["cases"]),
        "fixture_sha256": sha(fixture_path),
        "conventional_sha256": sha(conventional),
        "eisenstein_sha256": sha(eisenstein),
        "checker_sha256": sha(Path(__file__)),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
