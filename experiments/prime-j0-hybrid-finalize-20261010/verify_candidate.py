#!/usr/bin/env python3
"""Bind hybrid-finalizer correctness to frozen inputs, source, and raw output."""

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
N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(part.split("=", 1) for part in line.split() if "=" in part)


def run(label, binary, flag):
    process = subprocess.run([str(binary), flag, str(FIXTURE)], cwd=ROOT,
                             capture_output=True, text=True, timeout=900)
    stdout = HERE / f"{label}.stdout.txt"
    stderr = HERE / f"{label}.stderr.txt"
    stdout.write_text(process.stdout)
    stderr.write_text(process.stderr)
    return {
        "argv": [str(binary), flag, str(FIXTURE)], "exit_code": process.returncode,
        "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
    }, [fields(line) for line in process.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    receipt = HERE / "verification.json"
    if receipt.exists():
        raise SystemExit("verification receipt already exists")
    problems = []
    log = (HERE / "native-tests.log").read_text()
    match = re.search(r"test result: ok\. (\d+) passed; 0 failed;", log)
    if (HERE / "native-tests.exit").read_text().strip() != "0" or not match or int(match.group(1)) != 72:
        problems.append("full native release suite did not pass 72 tests")
    fresh = json.loads((HERE / "fresh-inputs.json").read_text())
    values = [int(value, 16) for value in fresh["scalars_hex"]]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in values)).hexdigest()
    if (fresh["schema"], fresh["seed"], fresh["count"], len(values), digest) != (
        1, 20261010423, 4096, 4096, fresh["scalar_sha256"]
    ):
        problems.append("fresh scalar law or digest mismatch")
    seen = set()
    for name, expected in fresh["source_sha256"].items():
        path = ROOT / "experiments" / name
        if sha(path) != expected:
            problems.append(f"prior input hash mismatch: {name}")
        seen.update(int(value, 16) % N for value in json.loads(path.read_text())["scalars_hex"])
    if len(values) != len(set(values)) or set(values) & seen:
        problems.append("fresh scalar panel overlaps prior inputs")
    reference, left = run("reference-fixture", binary,
                          "--check-scalar-unit-orbit-fixed-limb-fixed-fixture")
    candidate, right = run("candidate-fixture", binary,
                          "--check-scalar-unit-orbit-hybrid-fixed-fixture")
    for name, record, rows, mode in (
        ("reference", reference, left, "unit_orbit_fixed_limb14_fixed"),
        ("candidate", candidate, right, "unit_orbit_hybrid14_fixed"),
    ):
        if record["exit_code"] != 0 or len(rows) != 129 or any(
            row.get("verified") != "1" or row.get("mode") != mode for row in rows
        ):
            problems.append(f"{name} fixture failed")
    if len(left) == len(right) == 129:
        for index, (a, b) in enumerate(zip(left, right)):
            if {k: v for k, v in a.items() if k != "mode"} != {
                k: v for k, v in b.items() if k != "mode"
            }:
                problems.append(f"fixture case {index} mismatch")
    source_paths = [HERE / name for name in (
        "PROTOCOL.md", "make_inputs.py", "fresh-inputs.json", "verify_candidate.py",
        "native-tests.log", "native-tests.exit")]
    source_paths += [NATIVE / "src/bin/eisenstein_fixed.rs",
                     NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                     ROOT / "suite/src/ct_bignum.rs", FIXTURE]
    result = {
        "schema": 1, "status": "passed" if not problems else "failed",
        "problems": problems, "platform": platform.platform(),
        "binary_sha256": sha(binary),
        "native_tests_passed": int(match.group(1)) if match else None,
        "fixture_cases_per_mode": 129,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        "runs": {"reference": reference, "candidate": candidate},
    }
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": problems,
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
