#!/usr/bin/env python3
"""Bind four-limb U14 point-backend correctness to frozen inputs and output."""

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


def resource_run(label, expected_mode, binary, problems):
    stdout = HERE / f"{label}-resource.stdout.txt"
    stderr = HERE / f"{label}-resource.stderr.txt"
    exit_file = HERE / f"{label}-resource.exit"
    rows = [fields(line) for line in stdout.read_text().splitlines() if line.strip()]
    matches = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$",
                         stderr.read_text(), flags=re.MULTILINE)
    if (exit_file.read_text().strip() != "0" or len(rows) != 1 or
            rows[0].get("verified") != "1" or
            rows[0].get("mode") != expected_mode or len(matches) != 1):
        problems.append(f"{label} resource case failed")
    return {
        "argv": ["/usr/bin/time", "-l", str(binary),
                 "--benchmark-scalar-unit-orbit-direct-limb-fixed-case" if label == "reference"
                 else "--benchmark-scalar-unit-orbit-u256-point-fixed-case",
                 str(FIXTURE.relative_to(ROOT)), "0"],
        "cwd": str(ROOT),
        "exit_code": int(exit_file.read_text().strip()),
        "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
        "max_rss_bytes": int(matches[0]) if matches else None,
        "retained_bytes": int(rows[0]["retained_bytes"]) if len(rows) == 1 and
                          "retained_bytes" in rows[0] else None,
        "fields": rows[0] if len(rows) == 1 else None,
    }


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
    if (HERE / "native-tests.exit").read_text().strip() != "0" or not match or int(match.group(1)) != 79:
        problems.append("full native release suite did not pass 79 tests")
    fresh = json.loads((HERE / "fresh-inputs.json").read_text())
    values = [int(value, 16) for value in fresh["scalars_hex"]]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in values)).hexdigest()
    if (fresh["schema"], fresh["seed"], fresh["count"], len(values), digest) != (
        1, 20261010726, 4096, 4096, fresh["scalar_sha256"]
    ):
        problems.append("fresh scalar law or digest mismatch")
    if any(value < 0 or value >= (1 << 256) for value in values):
        problems.append("fresh scalar outside unsigned 256-bit input law")
    seen = set()
    for name, expected in fresh["source_sha256"].items():
        path = ROOT / "experiments" / name
        if sha(path) != expected:
            problems.append(f"prior input hash mismatch: {name}")
        seen.update(int(value, 16) % N for value in json.loads(path.read_text())["scalars_hex"])
    reduced_values = [value % N for value in values]
    if len(values) != len(set(values)) or len(reduced_values) != len(set(reduced_values)) or set(reduced_values) & seen:
        problems.append("fresh scalar panel overlaps prior inputs")
    algebra = json.loads((HERE / "algebra-check.json").read_text())
    if ((HERE / "algebra-check.exit").read_text().strip() != "0" or
            algebra.get("status") != "passed" or
            set(algebra.get("checks", {})) != {
                "beta_nontrivial", "beta_order_three",
                "beta_quadratic_relation", "pi_in_kernel", "pi_norm_equals_p"
            } or not all(algebra["checks"].values())):
        problems.append("exact field algebra check failed")
    reference, left = run("reference-fixture", binary,
                          "--check-scalar-unit-orbit-direct-limb-fixed-fixture")
    candidate, right = run("candidate-fixture", binary,
                          "--check-scalar-unit-orbit-u256-point-fixed-fixture")
    for name, record, rows, mode in (
        ("reference", reference, left, "unit_orbit_direct_limb14_fixed"),
        ("candidate", candidate, right, "unit_orbit_u256_point14_fixed"),
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
    resources = {
        "reference": resource_run("reference", "unit_orbit_direct_limb14_fixed", binary, problems),
        "candidate": resource_run("candidate", "unit_orbit_u256_point14_fixed", binary, problems),
    }
    old = resources["reference"]
    new = resources["candidate"]
    if (old["retained_bytes"] != 78_470_208 or
            new["retained_bytes"] != 70_430_960 or
            old["max_rss_bytes"] is None or new["max_rss_bytes"] is None or
            not old["fields"] or not new["fields"] or
            {key: old["fields"].get(key) for key in ("curve", "base_x", "base_y", "scalar", "point")} !=
            {key: new["fields"].get(key) for key in ("curve", "base_x", "base_y", "scalar", "point")}):
        problems.append("paired table or resource accounting mismatch")
    source_paths = [HERE / name for name in (
        "PROTOCOL.md", "PROOF.md", "make_inputs.py", "fresh-inputs.json",
        "check_algebra.py", "algebra-check.json", "algebra-check.exit",
        "verify_candidate.py",
        "make_isolated_manifest.py", "runpod_correctness.sh",
        "native-tests.log", "native-tests.exit",
        "reference-resource.stdout.txt", "reference-resource.stderr.txt",
        "reference-resource.exit", "candidate-resource.stdout.txt",
        "candidate-resource.stderr.txt", "candidate-resource.exit")]
    source_paths += [NATIVE / "src/bin/eisenstein_fixed.rs",
                     NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                     ROOT / "suite/src/ct_bignum.rs", FIXTURE]
    result = {
        "schema": 1, "status": "passed" if not problems else "failed",
        "problems": problems, "platform": platform.platform(),
        "binary_sha256": sha(binary),
        "cpu_speedup_claim": None,
        "isolation_receipt": None,
        "native_tests_passed": int(match.group(1)) if match else None,
        "fixture_cases_per_mode": 129,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
        "runs": {"reference": reference, "candidate": candidate},
        "resources": resources,
    }
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": problems,
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
