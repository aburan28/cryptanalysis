#!/usr/bin/env python3
"""Serially replay the frozen independent point fixture with native mode 138."""

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess

MODE = "unit_orbit_u256_tau_frontier19_fixed"
FLAG = "--check-scalar-unit-orbit-u256-tau-frontier19-fixed-case"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def parse(line):
    return dict(item.split("=", 1) for item in line.split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    fixture = args.fixture.resolve(strict=True)
    cases = json.loads(fixture.read_text())["cases"]
    assert len(cases) == 4096
    binary_hash, fixture_hash = digest(binary), digest(fixture)
    partial = args.output.with_name(args.output.name + ".partial")
    assert not partial.exists() and not args.output.exists()
    with partial.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            for index, case in enumerate(cases):
                command = [str(binary), FLAG, str(fixture), str(index)]
                run = subprocess.run(command, capture_output=True, text=True, timeout=60)
                assert run.returncode == 0, (index, run.stderr)
                lines = run.stdout.splitlines()
                assert len(lines) == 1, (index, lines)
                record = parse(lines[0])
                expected = ("identity" if case["expected_identity"] else
                            case["expected_x_hex"] + ":" + case["expected_y_hex"])
                assert record["verified"] == "1" and record["curve"] == "secp256k1"
                assert record["mode"] == MODE
                assert record["scalar"] == case["scalar_hex"]
                assert record["point"] == expected
                compressed.write((lines[0] + "\n").encode())
                if (index + 1) % 512 == 0:
                    print(f"verified={index + 1}", flush=True)
    assert digest(binary) == binary_hash and digest(fixture) == fixture_hash
    partial.replace(args.output)
    print(json.dumps({"cases": len(cases), "binary_sha256": binary_hash,
                      "fixture_sha256": fixture_hash,
                      "output_sha256": digest(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
