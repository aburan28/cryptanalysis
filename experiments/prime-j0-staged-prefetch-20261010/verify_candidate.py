#!/usr/bin/env python3
"""Build, replay, and bind the staged U14 candidate to its exact sources."""

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
    return {"command": argv, "exit_code": completed.returncode,
            "stdout_file": stdout.name, "stderr_file": stderr.name,
            "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}, completed.stdout


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
    assert len(fixture["cases"]) == 129 and len(scalars) == 519
    assert hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest() == inputs["scalar_sha256"]
    sources = [HERE / "PROTOCOL.md", HERE / "verify_candidate.py", INPUTS, FIXTURE,
               NATIVE / "Cargo.toml", NATIVE / "Cargo.lock",
               NATIVE / "src/bin/eisenstein_fixed.rs",
               NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
               ROOT / "suite/src/ct_bignum.rs",
               ROOT / "experiments/prime-j0-tau-bucket-orbits-20261009/atlas.bin",
               ROOT / "experiments/prime-j0-tau-pair-buckets-20261009/atlas.bin"]
    result = {"schema": 1, "status": "running", "problems": [],
              "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources},
              "binary_sha256": None, "cpu_timing_used": False,
              "scalar_input_sha256": inputs["scalar_sha256"],
              "platform": {"architecture": platform.machine(),
                           "system": platform.platform(),
                           "rustc": subprocess.run(["rustc", "--version"], capture_output=True,
                                                  text=True, check=True).stdout.strip()},
              "runs": {}}
    try:
        environment = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))
        command = ["cargo", "build", "--offline", "--locked", "--release",
                   "--manifest-path", str(NATIVE / "Cargo.toml"), "--bin", "eisenstein_fixed"]
        build, _ = execute("release-build", command, environment)
        result["runs"]["release_build"] = build
        if build["exit_code"]:
            result["problems"].append("release build failed")
        result["binary_sha256"] = sha(binary)
        command = ["cargo", "test", "--offline", "--locked", "--release",
                   "--manifest-path", str(NATIVE / "Cargo.toml"), "--bin", "eisenstein_fixed",
                   "--", "--test-threads=1"]
        tests, stdout = execute("native-tests", command, environment)
        result["runs"]["native_tests"] = tests
        match = re.search(r"test result: ok\. (\d+) passed; 0 failed", stdout)
        result["native_tests_passed"] = int(match.group(1)) if match else None
        if tests["exit_code"] or result["native_tests_passed"] != 67:
            result["problems"].append("native release tests failed")
        for label, flag, mode in (
            ("reference-fixture", "--check-scalar-unit-orbit-word14-fixed-fixture",
             "unit_orbit_word14_fixed"),
            ("candidate-fixture", "--check-scalar-unit-orbit-staged-fixed-fixture",
             "unit_orbit_staged14_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE)])
            rows = [fields(line) for line in stdout.splitlines() if line.strip()]
            record["parsed_cases"] = len(rows)
            result["runs"][label] = record
            if record["exit_code"] or len(rows) != 129 or any(
                row.get("verified") != "1" or row.get("mode") != mode for row in rows
            ):
                result["problems"].append(f"{label} failed")
        reference = [fields(line) for line in (HERE / "reference-fixture.stdout.txt").read_text().splitlines()]
        candidate = [fields(line) for line in (HERE / "candidate-fixture.stdout.txt").read_text().splitlines()]
        comparable = ("curve", "base_x", "base_y", "scalar", "point", "verified")
        if len(reference) != len(candidate) or any(
            tuple(a.get(key) for key in comparable) != tuple(b.get(key) for key in comparable)
            for a, b in zip(reference, candidate)
        ):
            result["problems"].append("fixture outputs differ")
        for label, flag, mode in (
            ("reference-case", "--benchmark-scalar-unit-orbit-word14-fixed-case",
             "unit_orbit_word14_fixed"),
            ("candidate-case", "--benchmark-scalar-unit-orbit-staged-fixed-case",
             "unit_orbit_staged14_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE), "0"])
            rows = [fields(line) for line in stdout.splitlines() if line.strip()]
            result["runs"][label] = record
            if record["exit_code"] or len(rows) != 1 or any(
                rows[0].get(key) is None
                for key in ("online_ms", "preparation_ms", "retained_bytes")
            ) or rows[0].get("mode") != mode or rows[0].get("verified") != "1":
                result["problems"].append(f"{label} dispatch failed")
            if rows:
                record["retained_bytes"] = rows[0].get("retained_bytes")
        if (result["runs"]["reference-case"].get("retained_bytes") != "78470208" or
                result["runs"]["candidate-case"].get("retained_bytes") != "78470208"):
            result["problems"].append("retained table payload changed")
        if any(sha(ROOT / name) != digest
               for name, digest in result["source_sha256"].items()):
            result["problems"].append("source changed during verification")
        result["status"] = "passed" if not result["problems"] else "failed"
    except Exception as exc:
        result["problems"].append(f"{type(exc).__name__}: {exc}")
        result["status"] = "failed"
    (HERE / "verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": result["problems"],
                      "native_tests_passed": result.get("native_tests_passed"),
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
