#!/usr/bin/env python3
"""Validate scalar CLI output against a frozen point fixture and exact mode."""

from hashlib import sha256
import json
from pathlib import Path
import sys


GENERATOR_X = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
GENERATOR_Y = "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
FIELDS = {"verified", "curve", "base_x", "base_y", "scalar", "point", "mode"}


def digest(raw):
    return sha256(raw).hexdigest()


def check_fixture(mode, label, fixture_path, output_bytes, expected_count):
    fixture = fixture_path.read_bytes()
    cases = json.loads(fixture)["cases"]
    lines = output_bytes.decode().splitlines()
    assert len(cases) == len(lines) == expected_count, label
    points = []
    for index, (case, line) in enumerate(zip(cases, lines)):
        tokens = line.split()
        assert all(token.count("=") == 1 for token in tokens), (label, index)
        fields = dict(token.split("=", 1) for token in tokens)
        assert len(tokens) == len(fields) and set(fields) == FIELDS, (label, index)
        assert (fields["verified"], fields["curve"], fields["mode"]) == (
            "1", "secp256k1", mode), (label, index)
        assert (fields["base_x"].lower(), fields["base_y"].lower()) == (
            GENERATOR_X, GENERATOR_Y), (label, index)
        assert fields["scalar"].lower() == case["scalar_hex"].lower(), (label, index)
        expected = ("identity" if case["expected_identity"] else
                    case["expected_x_hex"] + ":" + case["expected_y_hex"])
        assert fields["point"].lower() == expected.lower(), (label, index)
        points.append(fields["point"])
    return {"cases": len(lines), "stdout_sha256": digest(output_bytes),
            "fixture_sha256": digest(fixture),
            "point_stream_sha256": digest("\n".join(points).encode())}


def main():
    assert len(sys.argv) == 5, "usage: verify_fixture.py MODE FIXTURE STDOUT COUNT"
    mode, fixture, output, count = sys.argv[1:]
    result = check_fixture(mode, Path(fixture).stem, Path(fixture),
                           Path(output).read_bytes(), int(count))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
