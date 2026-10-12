#!/usr/bin/env python3
"""Replay every GLV10 benchmark case against the frozen generator fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_fields(line):
    return dict(item.split("=", 1) for item in line.split() if "=" in item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--unit-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    binary = args.binary.resolve(strict=True)
    unit_receipt = args.unit_receipt.resolve(strict=True)
    prior = json.loads(unit_receipt.read_text())
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    source = HERE / "src/bin/eisenstein_fixed.rs"
    module = HERE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    if (prior["status"] != "passed" or prior["formats"] != [14, 15, 16] or
            prior["fixture_cases_per_format"] != 129 or
            prior["binary_sha256"] != sha(binary) or
            prior["main_source_sha256"] != sha(source) or
            prior["multiply_source_sha256"] != sha(module) or
            prior["fixture_sha256"] != sha(fixture_path) or
            prior["protocol_sha256"] != sha(HERE / "UNIT_ORBIT_ISOLATED_TIMING_PROTOCOL.md") or
            prior["checker_sha256"] != sha(HERE / "check_unit_orbit_isolated_cli.py") or
            fixture["schema"] != 1 or len(fixture["cases"]) != 129):
        raise SystemExit("U14/U15/U16 receipt or fixture differs from this binary")
    for index, row in enumerate(fixture["cases"]):
        assert row["index"] == index
        command = [str(binary), "--benchmark-scalar-glv-comb10-fixed-case",
                   str(fixture_path), str(index)]
        process = subprocess.run(command, capture_output=True, text=True,
                                 check=True, timeout=1200)
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        assert len(lines) == 1, index
        result = output_fields(lines[0])
        expected = ("identity" if row["expected_identity"] else
                    row["expected_x_hex"] + ":" + row["expected_y_hex"])
        assert result["verified"] == "1"
        assert result["mode"] == "glv_comb10_fixed"
        assert result["curve"] == "secp256k1"
        assert result["base_x"] == row["base_x_hex"]
        assert result["base_y"] == row["base_y_hex"]
        assert result["scalar"] == row["scalar_hex"]
        assert result["point"] == expected
        assert float(result["online_ms"]) > 0
    receipt = {
        "schema": 1,
        "status": "passed",
        "method": "glv_comb10_fixed",
        "fixture_cases": len(fixture["cases"]),
        "paired_panel_indices": list(INDICES),
        "binary_sha256": sha(binary),
        "main_source_sha256": sha(source),
        "multiply_source_sha256": sha(module),
        "fixture_sha256": sha(fixture_path),
        "unit_receipt_sha256": sha(unit_receipt),
        "protocol_sha256": sha(HERE / "UNIT_ORBIT_GLV_ISOLATED_PROTOCOL.md"),
        "checker_sha256": sha(Path(__file__)),
        "local_online_timing_used": False,
    }
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "passed", "fixture_cases": len(fixture["cases"]),
                      "local_online_timing_used": False}, sort_keys=True))


if __name__ == "__main__":
    main()
