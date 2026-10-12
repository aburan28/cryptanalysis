#!/usr/bin/env python3
"""Check the native U14 XYZZ path against independent secp256k1 fixtures."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "prime-j0-secp256k1-native"
ORDER = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
MODE = "unit_orbit_u14_xyzz_fixed"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output_path = args.output.resolve()
    raw_path = output_path.with_name(output_path.stem + "-raw.jsonl")
    benchmark_path = output_path.with_name(output_path.stem + "-benchmark-raw.txt")
    if output_path.exists() or raw_path.exists() or benchmark_path.exists():
        raise SystemExit("output already exists")

    binary = args.binary.resolve(strict=True)
    fixture_path = UPSTREAM / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    cases = fixture["cases"]
    assert fixture["schema"] == 1 and len(cases) == 129
    generator = cases[0]["base_x_hex"] + ":" + cases[0]["base_y_hex"]
    extras = [("0", "identity"), ("1", generator),
              (format(ORDER, "x"), "identity"),
              (format(ORDER + 1, "x"), generator)]
    scalars = [row["scalar_hex"] for row in cases] + [scalar for scalar, _ in extras]
    process = subprocess.run(
        [str(binary), "--scalar-unit-orbit-u14-xyzz-fixed"],
        input="".join(scalar + "\n" for scalar in scalars),
        text=True, capture_output=True, timeout=1200, check=True,
    )
    lines = process.stdout.splitlines()
    assert len(lines) == len(scalars), (len(lines), len(scalars), process.stderr[-1000:])
    results = [json.loads(line) for line in lines]
    for index, (row, result) in enumerate(zip(cases, results)):
        expected = ("identity" if row["expected_identity"] else
                    row["expected_x_hex"] + ":" + row["expected_y_hex"])
        assert result["point"] == expected, (index, result["point"], expected)
    for index, ((_, expected), result) in enumerate(zip(extras, results[len(cases):])):
        assert result["point"] == expected, ("extra", index, result["point"], expected)
    retained_bytes = results[0]["retained_bytes"]
    assert isinstance(retained_bytes, int) and retained_bytes > 0
    for index, result in enumerate(results):
        assert result["mode"] == MODE, index
        assert result["retained_bytes"] == retained_bytes, index
        assert isinstance(result["generic_additions"], int), index
        assert 0 <= result["generic_additions"] <= 13, index
    assert sum(row["generic_additions"] for row in results[:len(cases)]) == 1677

    benchmark = subprocess.run(
        [str(binary), "--benchmark-scalar-unit-orbit-u14-xyzz-fixed-case",
         str(fixture_path), "0"],
        text=True, capture_output=True, timeout=1200, check=True,
    )
    fields = dict(part.split("=", 1) for part in benchmark.stdout.split()
                  if "=" in part)
    first = cases[0]
    assert fields["verified"] == "1" and fields["mode"] == MODE
    assert fields["curve"] == "secp256k1"
    assert fields["scalar"] == first["scalar_hex"]
    assert fields["base_x"] == first["base_x_hex"]
    assert fields["base_y"] == first["base_y_hex"]
    assert fields["point"] == results[0]["point"]
    assert int(fields["retained_bytes"]) == retained_bytes
    assert float(fields["online_ms"]) > 0
    assert float(fields["preparation_ms"]) >= 0
    raw_path.write_text(process.stdout)
    benchmark_path.write_text(benchmark.stdout)
    source_paths = [HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "build.rs",
                    HERE / "README.md", HERE / "PROTOCOL.md",
                    HERE / "U14_REPLAY_PROTOCOL.md",
                    HERE / "src/main.rs", HERE / "src/xyzz_append.rs",
                    HERE / "src/unit_orbit_append.rs", HERE / "check_native_xyzz.py",
                    UPSTREAM / "src/bin/eisenstein_fixed.rs",
                    UPSTREAM / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                    HERE.parent.parent / "suite/src/ct_bignum.rs"]
    receipt = {
        "schema": 1,
        "status": "passed",
        "fixture_cases": len(cases),
        "boundary_scalars": ["0", "1", "n", "n+1"],
        "generic_additions_fixture_total": 1677,
        "retained_bytes": retained_bytes,
        "binary_sha256": digest(binary),
        "fixture_sha256": digest(fixture_path),
        "raw_output_sha256": digest(raw_path),
        "benchmark_dispatch_cases": 1,
        "benchmark_raw_sha256": digest(benchmark_path),
        "source_sha256": {str(path.relative_to(HERE.parent.parent)): digest(path)
                          for path in source_paths},
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "cpu_timing_used": False,
    }
    output_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "passed", "fixture_cases": len(cases),
                      "boundary_cases": len(extras),
                      "generic_additions_fixture_total": 1677}, sort_keys=True))


if __name__ == "__main__":
    main()
