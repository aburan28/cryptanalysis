#!/usr/bin/env python3
"""Replay the two-bucket tau candidate and retain source-bound output."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native"
FIXTURE = NATIVE / "tau6-comb13-bench-fixture.json"
INPUTS = ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(part.split("=", 1) for part in line.split() if "=" in part)


def execute(label, argv, env=None):
    completed = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=900, check=False)
    stdout = HERE / f"{label}.stdout.txt"
    stderr = HERE / f"{label}.stderr.txt"
    stdout.write_text(completed.stdout)
    stderr.write_text(completed.stderr)
    return {
        "command": argv,
        "exit_code": completed.returncode,
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "stdout_file": stdout.name,
        "stderr_file": stderr.name,
    }, completed.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    target_dir = args.target_dir.resolve(strict=True)
    fixture = json.loads(FIXTURE.read_text())
    inputs = json.loads(INPUTS.read_text())
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    assert len(fixture["cases"]) == 129
    assert len(scalars) == 519
    assert hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == inputs["scalar_sha256"]

    sources = [
        HERE / "PROTOCOL.md", HERE / "screen.py", HERE / "atlas.bin",
        HERE / "screen-result.json", HERE / "verify_candidate.py", INPUTS,
        ROOT / "experiments/prime-j0-tau-bucket-orbits-20261009/atlas.bin",
        NATIVE / "Cargo.toml", NATIVE / "Cargo.lock",
        NATIVE / "src/bin/eisenstein_fixed.rs",
        NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        ROOT / "suite/src/ct_bignum.rs", FIXTURE,
    ]
    result = {
        "schema": 1,
        "status": "running",
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources},
        "binary_sha256": None,
        "platform": {"architecture": platform.machine(), "system": platform.platform(),
                     "rustc": subprocess.run(["rustc", "--version"], capture_output=True,
                                            text=True, check=True).stdout.strip()},
        "fixture_cases": 129,
        "fresh_and_boundary_cases": 519,
        "independent_fresh_points_in_native_test": 128,
        "scalar_input_sha256": inputs["scalar_sha256"],
        "cpu_timing_used": False,
        "runs": {},
        "problems": [],
    }
    screen = json.loads((HERE / "screen-result.json").read_text())
    if (screen.get("seed_count_per_row") != 93_777 or
            screen.get("point_entries") != 1_219_101 or
            screen.get("under_90_mib_cap") is not True or
            screen.get("scalar_reconstructions") != 519 or
            screen.get("input_sha256") != inputs["scalar_sha256"] or
            screen.get("atlas_file_sha256") != sha(HERE / "atlas.bin") or
            screen.get("screen_source_sha256") != sha(HERE / "screen.py")):
        result["problems"].append("mathematical screen or atlas differs")
    output = HERE / "verification.json"
    try:
        environment = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))
        build_command = ["cargo", "build", "--offline", "--locked", "--release",
                         "--manifest-path", str(NATIVE / "Cargo.toml"),
                         "--bin", "eisenstein_fixed"]
        build_record, _ = execute("release-build", build_command, environment)
        result["runs"]["release_build"] = build_record
        if build_record["exit_code"]:
            result["problems"].append("release build failed")
        result["binary_sha256"] = sha(binary)
        test_command = ["cargo", "test", "--offline", "--locked", "--release",
                        "--manifest-path", str(NATIVE / "Cargo.toml"),
                        "--bin", "eisenstein_fixed", "--", "--test-threads=1"]
        test_record, test_stdout = execute("native-tests", test_command, environment)
        result["runs"]["native_tests"] = test_record
        passed_match = re.search(r"test result: ok\. (\d+) passed; 0 failed", test_stdout)
        result["native_tests_passed"] = int(passed_match.group(1)) if passed_match else None
        if test_record["exit_code"] or result["native_tests_passed"] != 66:
            result["problems"].append("native tests failed")
        for label, flag, mode in (
            ("reference-fixture", "--check-scalar-unit-orbit-windows14-fixed-fixture",
             "unit_orbit_windows14_fixed"),
            ("candidate-fixture", "--check-scalar-unit-orbit-tau-pair-fixed-fixture",
             "unit_orbit_tau_pair_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE)])
            result["runs"][label] = record
            lines = [fields(line) for line in stdout.splitlines() if line.strip()]
            if record["exit_code"] or len(lines) != 129 or any(
                row.get("verified") != "1" or row.get("mode") != mode
                for row in lines
            ):
                result["problems"].append(f"{label} failed")
            result["runs"][label]["parsed_cases"] = len(lines)
        reference = [fields(line) for line in (HERE / "reference-fixture.stdout.txt").read_text().splitlines()]
        candidate = [fields(line) for line in (HERE / "candidate-fixture.stdout.txt").read_text().splitlines()]
        comparable = ("curve", "base_x", "base_y", "scalar", "point", "verified")
        if len(reference) != len(candidate) or any(
            tuple(a.get(key) for key in comparable) != tuple(b.get(key) for key in comparable)
            for a, b in zip(reference, candidate)
        ):
            result["problems"].append("fixture outputs differ")
        for label, flag, mode in (
            ("reference-case", "--benchmark-scalar-unit-orbit-windows14-fixed-case",
             "unit_orbit_windows14_fixed"),
            ("candidate-case", "--benchmark-scalar-unit-orbit-tau-pair-fixed-case",
             "unit_orbit_tau_pair_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE), "0"])
            result["runs"][label] = record
            rows = [fields(line) for line in stdout.splitlines() if line.strip()]
            if record["exit_code"] or len(rows) != 1 or any(
                rows[0].get(key) is None for key in ("online_ms", "preparation_ms", "retained_bytes")
            ) or rows[0].get("mode") != mode or rows[0].get("verified") != "1":
                result["problems"].append(f"{label} dispatch failed")
            if rows:
                result["runs"][label]["retained_bytes"] = rows[0].get("retained_bytes")
        reference_bytes = result["runs"]["reference-case"].get("retained_bytes")
        candidate_bytes = result["runs"]["candidate-case"].get("retained_bytes")
        if (reference_bytes != "78470208" or candidate_bytes is None or
                int(candidate_bytes) >= 90 * (1 << 20)):
            result["problems"].append("retained payload differs from resource gate")
        result["status"] = "passed" if not result["problems"] else "failed"
    except Exception as exc:
        result["problems"].append(f"{type(exc).__name__}: {exc}")
        result["status"] = "failed"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": result["problems"],
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
