#!/usr/bin/env python3
"""Check every unit-orbit timing CLI case without using its local timings."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(word.split("=", 1) for word in line.split() if "=" in word)


def check(row, output, fmt, retained):
    expected = ("identity" if row["expected_identity"] else
                row["expected_x_hex"] + ":" + row["expected_y_hex"])
    assert output["verified"] == "1"
    assert output["curve"] == "secp256k1"
    assert output["base_x"] == row["base_x_hex"]
    assert output["base_y"] == row["base_y_hex"]
    assert output["scalar"] == row["scalar_hex"]
    assert output["point"] == expected
    assert output["mode"] == f"unit_orbit_windows{fmt}_fixed"
    assert int(output["retained_bytes"]) == retained
    assert float(output["online_ms"]) > 0
    assert float(output["preparation_ms"]) >= 0


def run(argv):
    process = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=1200)
    return [fields(line) for line in process.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    binary = args.binary.resolve(strict=True)
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    prior = json.loads((HERE / "unit-orbit-memory-frontier-verify.json").read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    assert prior["status"] == "passed" and prior["cases"] == 6748
    assert prior["candidate_source_sha256"]["src/bin/eisenstein_fixed/unit_orbit_windows.rs"] == sha(
        HERE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs")
    retained = {int(fmt): value for fmt, value in prior["retained_bytes"].items()}
    for fmt in (14, 15, 16):
        output = run([str(binary), f"--benchmark-scalar-unit-orbit-windows{fmt}-fixed-fixture",
                      str(fixture_path)])
        assert len(output) == len(fixture["cases"]), fmt
        for row, result in zip(fixture["cases"], output):
            check(row, result, fmt, retained[fmt])
        for index in INDICES[:1]:
            single = run([str(binary), f"--benchmark-scalar-unit-orbit-windows{fmt}-fixed-case",
                          str(fixture_path), str(index)])
            assert len(single) == 1
            check(fixture["cases"][index], single[0], fmt, retained[fmt])
    receipt = {
        "schema": 1,
        "status": "passed",
        "formats": [14, 15, 16],
        "fixture_cases_per_format": len(fixture["cases"]),
        "single_case_dispatch_per_format": 1,
        "paired_panel_indices": list(INDICES),
        "retained_bytes": retained,
        "binary_sha256": sha(binary),
        "main_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
        "multiply_source_sha256": sha(HERE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"),
        "fixture_sha256": sha(fixture_path),
        "protocol_sha256": sha(HERE / "UNIT_ORBIT_ISOLATED_TIMING_PROTOCOL.md"),
        "prior_receipt_sha256": sha(HERE / "unit-orbit-memory-frontier-verify.json"),
        "checker_sha256": sha(Path(__file__)),
        "local_online_timing_used": False,
    }
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "fixture_cases_per_format": receipt["fixture_cases_per_format"],
                      "single_case_dispatch_per_format": 1,
                      "local_online_timing_used": False}, sort_keys=True))


if __name__ == "__main__":
    main()
