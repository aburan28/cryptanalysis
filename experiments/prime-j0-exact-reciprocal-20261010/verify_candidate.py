#!/usr/bin/env python3
"""Bind native reciprocal-selector replay to source, inputs, and raw outputs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native"
FIXTURE = NATIVE / "tau6-comb13-bench-fixture.json"


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fields(line):
    return dict(part.split("=", 1) for part in line.split() if "=" in part)


def execute(label, command):
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                         timeout=900, check=False)
    stdout = HERE / f"{label}.stdout.txt"
    stderr = HERE / f"{label}.stderr.txt"
    stdout.write_text(run.stdout)
    stderr.write_text(run.stderr)
    return {"command": command, "exit_code": run.returncode,
            "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
            "stderr_file": stderr.name, "stderr_sha256": sha(stderr)}, run.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--native-test-log", type=Path, required=True)
    parser.add_argument("--native-test-exit", type=Path, required=True)
    args = parser.parse_args()
    if (HERE / "verification.json").exists():
        raise SystemExit("verification receipt already exists")
    binary = args.binary.resolve(strict=True)
    native_log = args.native_test_log.resolve(strict=True)
    native_exit = args.native_test_exit.resolve(strict=True)
    screen = json.loads((HERE / "screen-result.json").read_text())
    native_source = str((NATIVE / "src/bin/eisenstein_fixed.rs").relative_to(ROOT))
    if screen.get("status") != "passed" or any(
        sha(ROOT / name) != digest for name, digest in screen["source_sha256"].items()
        if name != native_source
    ):
        raise SystemExit("theorem screen input or audit source differs")
    sources = [HERE / "PROTOCOL.md", HERE / "screen.py", HERE / "fresh-inputs.json",
               HERE / "screen-result.json", HERE / "verify_candidate.py", FIXTURE,
               NATIVE / "Cargo.toml", NATIVE / "Cargo.lock",
               NATIVE / "src/bin/eisenstein_fixed.rs",
               NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
               ROOT / "suite/src/ct_bignum.rs",
               ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json",
               ROOT / "experiments/prime-j0-tau-bucket-orbits-20261009/atlas.bin",
               ROOT / "experiments/prime-j0-tau-pair-buckets-20261009/atlas.bin"]
    result = {"schema": 1, "status": "running", "problems": [],
              "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources},
              "binary_sha256": sha(binary), "cpu_timing_used": False,
              "screen_reference_source_sha256": screen["source_sha256"][native_source],
              "platform": {"system": platform.platform(), "architecture": platform.machine(),
                           "rustc": subprocess.run(["rustc", "--version"],
                                                    capture_output=True, text=True,
                                                    check=True).stdout.strip()},
              "runs": {}}
    try:
        log = native_log.read_text()
        exit_code = int(native_exit.read_text().strip())
        match = re.search(r"test result: ok\. (\d+) passed; 0 failed;", log)
        result["runs"]["native_tests"] = {
            "command": ["cargo", "test", "--offline", "--locked", "--release",
                        "--manifest-path", str(NATIVE / "Cargo.toml"),
                        "--bin", "eisenstein_fixed", "--", "--test-threads=2"],
            "environment": {"CARGO_TARGET_DIR": str(binary.parent.parent)},
            "exit_code": exit_code, "combined_output_file": native_log.name,
            "combined_output_sha256": sha(native_log),
            "exit_file": native_exit.name, "exit_file_sha256": sha(native_exit),
            "passed": int(match.group(1)) if match else None}
        if exit_code != 0 or not match or int(match.group(1)) != 68:
            result["problems"].append("full native suite did not pass")
        for label, flag, mode in (
            ("reference-fixture", "--check-scalar-unit-orbit-word14-fixed-fixture",
             "unit_orbit_word14_fixed"),
            ("candidate-fixture", "--check-scalar-unit-orbit-reciprocal-fixed-fixture",
             "unit_orbit_reciprocal14_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE)])
            rows = [fields(line) for line in stdout.splitlines() if line.strip()]
            record["parsed_cases"] = len(rows)
            result["runs"][label] = record
            if record["exit_code"] or len(rows) != 129 or any(
                row.get("mode") != mode or row.get("verified") != "1" for row in rows
            ):
                result["problems"].append(f"{label} failed")
        left = [fields(line) for line in (HERE / "reference-fixture.stdout.txt").read_text().splitlines()]
        right = [fields(line) for line in (HERE / "candidate-fixture.stdout.txt").read_text().splitlines()]
        common = ("curve", "base_x", "base_y", "scalar", "point", "verified")
        if len(left) != len(right) or any(
            tuple(a.get(key) for key in common) != tuple(b.get(key) for key in common)
            for a, b in zip(left, right)
        ):
            result["problems"].append("fixture points differ")
        for label, flag, mode in (
            ("reference-case", "--benchmark-scalar-unit-orbit-word14-fixed-case",
             "unit_orbit_word14_fixed"),
            ("candidate-case", "--benchmark-scalar-unit-orbit-reciprocal-fixed-case",
             "unit_orbit_reciprocal14_fixed"),
        ):
            record, stdout = execute(label, [str(binary), flag, str(FIXTURE), "0"])
            rows = [fields(line) for line in stdout.splitlines() if line.strip()]
            result["runs"][label] = record
            if (record["exit_code"] or len(rows) != 1 or
                    rows[0].get("mode") != mode or rows[0].get("verified") != "1" or
                    rows[0].get("retained_bytes") != "78470208" or
                    not rows[0].get("online_ms")):
                result["problems"].append(f"{label} dispatch failed")
        if sha(binary) != result["binary_sha256"]:
            result["problems"].append("binary changed during replay")
        if any(sha(ROOT / name) != digest
               for name, digest in result["source_sha256"].items()):
            result["problems"].append("source changed during replay")
        result["status"] = "passed" if not result["problems"] else "failed"
    except Exception as exc:
        result["status"] = "failed"
        result["problems"].append(f"{type(exc).__name__}: {exc}")
    (HERE / "verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": result["problems"],
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
