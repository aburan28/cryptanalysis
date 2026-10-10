#!/usr/bin/env python3
"""Bind the native fixed-limb selector replay to source and raw outputs."""

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


def source_name(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def run(label, binary, flag):
    command = [str(binary), flag, str(FIXTURE)]
    process = subprocess.run(command, cwd=ROOT, capture_output=True,
                             text=True, timeout=900, check=False)
    stdout = HERE / f"{label}.stdout.txt"
    stderr = HERE / f"{label}.stderr.txt"
    stdout.write_text(process.stdout)
    stderr.write_text(process.stderr)
    return {"command": command, "exit_code": process.returncode,
            "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
            "stderr_file": stderr.name, "stderr_sha256": sha(stderr)}, [
                fields(line) for line in process.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--native-test-log", type=Path, required=True)
    parser.add_argument("--native-test-exit", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    native_log = args.native_test_log.resolve(strict=True)
    native_exit = args.native_test_exit.resolve(strict=True)
    result_path = HERE / "verification.json"
    if result_path.exists():
        raise SystemExit("verification receipt already exists")
    log = native_log.read_text()
    match = re.search(r"test result: ok\. (\d+) passed; 0 failed;", log)
    problems = []
    if native_exit.read_text().strip() != "0" or not match or int(match.group(1)) != 70:
        problems.append("full native release suite did not pass 70 tests")
    fresh = json.loads((HERE / "fresh-inputs.json").read_text())
    values = [int(value, 16) for value in fresh["scalars_hex"]]
    scalar_hash = hashlib.sha256(b"".join(
        value.to_bytes(32, "big") for value in values)).hexdigest()
    if (fresh["schema"], fresh["seed"], fresh["count"], len(values),
            scalar_hash) != (1, 20261010317, 4096, 4096,
                            fresh["scalar_sha256"]):
        problems.append("fresh scalar law or digest mismatch")
    subgroup_order = int(
        "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
    seen = set()
    for name, expected_hash in fresh["source_sha256"].items():
        path = ROOT / "experiments" / name
        if sha(path) != expected_hash:
            problems.append(f"prior input hash mismatch: {name}")
        seen.update(int(value, 16) % subgroup_order for value in
                    json.loads(path.read_text())["scalars_hex"])
    if len(values) != len(set(values)) or set(values) & seen:
        problems.append("fresh scalar panel overlaps a prior panel")
    reference, left = run("reference-fixture", binary,
                          "--check-scalar-unit-orbit-certified-fixed-fixture")
    candidate, right = run("candidate-fixture", binary,
                          "--check-scalar-unit-orbit-fixed-limb-fixed-fixture")
    for name, record, rows, mode in (
        ("reference", reference, left, "unit_orbit_certified14_fixed"),
        ("candidate", candidate, right, "unit_orbit_fixed_limb14_fixed"),
    ):
        if record["exit_code"] or len(rows) != 129 or any(
            row.get("verified") != "1" or row.get("mode") != mode for row in rows
        ):
            problems.append(f"{name} fixture failed")
    if len(left) == len(right) == 129:
        for index, (a, b) in enumerate(zip(left, right)):
            if {k: v for k, v in a.items() if k != "mode"} != {
                k: v for k, v in b.items() if k != "mode"
            }:
                problems.append(f"fixture case {index} mismatch")
    source_paths = [HERE / name for name in
                    ("PROTOCOL.md", "make_inputs.py", "fresh-inputs.json",
                     "verify_candidate.py")]
    source_paths += [NATIVE / "src/bin/eisenstein_fixed.rs",
                     NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                     FIXTURE, native_log, native_exit]
    result = {"schema": 1, "status": "passed" if not problems else "failed",
              "problems": problems, "platform": platform.platform(),
              "binary_sha256": sha(binary), "native_tests_passed":
                  int(match.group(1)) if match else None,
              "fixture_cases_per_mode": 129,
              "source_sha256": {source_name(p): sha(p) for p in source_paths},
              "runs": {"reference": reference, "candidate": candidate}}
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": problems,
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
