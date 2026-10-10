#!/usr/bin/env python3
"""Bind grouped-unit U14 correctness and operation counts to frozen inputs."""

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
    exit_file = HERE / f"{label}.exit"
    stdout.write_text(process.stdout)
    stderr.write_text(process.stderr)
    exit_file.write_text(f"{process.returncode}\n")
    return {
        "argv": [str(binary), flag, str(FIXTURE)], "exit_code": process.returncode,
        "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
        "exit_file": exit_file.name, "exit_sha256": sha(exit_file),
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
                 "--benchmark-scalar-unit-orbit-u256-point-fixed-case" if label == "reference"
                 else "--benchmark-scalar-unit-orbit-u256-gauge-fixed-case",
                 str(FIXTURE), "0"],
        "cwd": str(ROOT),
        "exit_code": int(exit_file.read_text().strip()),
        "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
        "max_rss_bytes": int(matches[0]) if matches else None,
        "retained_bytes": int(rows[0]["retained_bytes"]) if len(rows) == 1 and
                          "retained_bytes" in rows[0] else None,
        "fields": rows[0] if len(rows) == 1 else None,
    }


def panel_counts(problems):
    log = (HERE / "gauge-panel.log").read_text()
    matches = re.findall(
        r"gauge_panel_cases=(\d+) reference_beta_products=(\d+) "
        r"gauge_beta_products=(\d+) counts_hex=([0-9a-f]+)", log,
    )
    if ((HERE / "gauge-panel.exit").read_text().strip() != "0" or
            "test result: ok. 1 passed; 0 failed;" not in log or len(matches) != 1):
        problems.append("full scalar and operation-count panel failed")
        return None
    cases, reference, gauge, encoded = matches[0]
    counts = bytes.fromhex(encoded)
    if (int(cases) != 5 + 519 + 8 * 4096 or len(counts) != 2 * int(cases) or
            sum(counts[::2]) != int(reference) or sum(counts[1::2]) != int(gauge) or
            any(a > 14 or b > 2 or b > a for a, b in zip(counts[::2], counts[1::2]))):
        problems.append("per-scalar unit-product counts failed")
    return {"cases": int(cases), "reference_beta_products": int(reference),
            "gauge_beta_products": int(gauge),
            "counts_sha256": hashlib.sha256(counts).hexdigest(),
            "raw_log_sha256": sha(HERE / "gauge-panel.log")}


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
    if (HERE / "native-tests.exit").read_text().strip() != "0" or not match or int(match.group(1)) != 81:
        problems.append("full native release suite did not pass 81 tests")
    fresh = json.loads((HERE / "fresh-inputs.json").read_text())
    values = [int(value, 16) for value in fresh["scalars_hex"]]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in values)).hexdigest()
    if (fresh["schema"], fresh["seed"], fresh["count"], len(values), digest) != (
        1, 20261010727, 4096, 4096, fresh["scalar_sha256"]
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
    counts = panel_counts(problems)
    algebra = json.loads((HERE / "algebra-check.json").read_text())
    if ((HERE / "algebra-check.exit").read_text().strip() != "0" or
            algebra.get("status") != "passed" or
            set(algebra.get("checks", {})) != {
                "beta_nontrivial", "beta_order_three",
                "beta_quadratic_relation", "pi_in_kernel", "pi_norm_equals_p"
            } or not all(algebra["checks"].values())):
        problems.append("exact field algebra check failed")
    reference, left = run("reference-fixture", binary,
                          "--check-scalar-unit-orbit-u256-point-fixed-fixture")
    candidate, right = run("candidate-fixture", binary,
                          "--check-scalar-unit-orbit-u256-gauge-fixed-fixture")
    fixture_cases = json.loads(FIXTURE.read_text())["cases"]
    if len(fixture_cases) != 129:
        problems.append("frozen fixture count differs")
    for name, record, rows, mode in (
        ("reference", reference, left, "unit_orbit_u256_point14_fixed"),
        ("candidate", candidate, right, "unit_orbit_u256_gauge14_fixed"),
    ):
        if record["exit_code"] != 0 or len(rows) != 129 or any(
            row.get("verified") != "1" or row.get("mode") != mode for row in rows
        ):
            problems.append(f"{name} fixture failed")
        for index, (row, case) in enumerate(zip(rows, fixture_cases)):
            expected_point = ("identity" if case["expected_identity"] else
                              case["expected_x_hex"] + ":" + case["expected_y_hex"])
            expected = {"curve": "secp256k1", "base_x": case["base_x_hex"],
                        "base_y": case["base_y_hex"], "scalar": case["scalar_hex"],
                        "point": expected_point}
            if any(row.get(key) != value for key, value in expected.items()):
                problems.append(f"{name} fixture case {index} differs from expected")
    if len(left) == len(right) == 129:
        for index, (a, b) in enumerate(zip(left, right)):
            if {k: v for k, v in a.items() if k != "mode"} != {
                k: v for k, v in b.items() if k != "mode"
            }:
                problems.append(f"fixture case {index} mismatch")
    resources = {
        "reference": resource_run("reference", "unit_orbit_u256_point14_fixed", binary, problems),
        "candidate": resource_run("candidate", "unit_orbit_u256_gauge14_fixed", binary, problems),
    }
    old = resources["reference"]
    new = resources["candidate"]
    if (old["retained_bytes"] != 70_430_960 or
            new["retained_bytes"] != 70_430_960 or
            old["max_rss_bytes"] is None or new["max_rss_bytes"] is None or
            not old["fields"] or not new["fields"] or
            {key: old["fields"].get(key) for key in ("curve", "base_x", "base_y", "scalar", "point")} !=
            {key: new["fields"].get(key) for key in ("curve", "base_x", "base_y", "scalar", "point")}):
        problems.append("paired table or resource accounting mismatch")
    source_paths = [HERE / name for name in (
        "PROTOCOL.md", "PROOF.md", "make_inputs.py", "fresh-inputs.json",
        "check_algebra.py", "algebra-check.json", "algebra-check.stderr.txt",
        "algebra-check.exit",
        "verify_candidate.py", "make_isolated_manifest.py",
        "runpod_correctness.sh",
        "gauge-panel.log", "gauge-panel.exit",
        "native-tests.log", "native-tests.exit",
        "reference-fixture.stdout.txt", "reference-fixture.stderr.txt",
        "reference-fixture.exit", "candidate-fixture.stdout.txt",
        "candidate-fixture.stderr.txt", "candidate-fixture.exit",
        "reference-resource.stdout.txt", "reference-resource.stderr.txt",
        "reference-resource.exit", "candidate-resource.stdout.txt",
        "candidate-resource.stderr.txt", "candidate-resource.exit",
        "reference-resource-sandbox.stdout.txt",
        "reference-resource-sandbox.stderr.txt",
        "reference-resource-sandbox.exit")]
    source_paths += [NATIVE / "src/bin/eisenstein_fixed.rs",
                     NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                     NATIVE / "Cargo.toml", NATIVE / "Cargo.lock",
                     ROOT / "suite/src/ct_bignum.rs", FIXTURE,
                     ROOT / "experiments/prime-j0-u256-point-20261010/PROOF.md"]
    source_paths += [ROOT / "experiments" / name for name in fresh["source_sha256"]]
    pattern = re.compile(r'(?:include_(?:bytes|str)!\(\s*|#\[path\s*=\s*)"([^"]+)"')
    for source in (NATIVE / "src/bin/eisenstein_fixed.rs",
                   NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"):
        source_paths.extend((source.parent / name).resolve(strict=True)
                            for name in pattern.findall(source.read_text()))
    result = {
        "schema": 1, "status": "passed" if not problems else "failed",
        "problems": problems, "platform": platform.platform(),
        "binary_sha256": sha(binary),
        "cpu_speedup_claim": None,
        "isolation_receipt": None,
        "native_tests_passed": int(match.group(1)) if match else None,
        "fixture_cases_per_mode": 129,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in dict.fromkeys(source_paths)},
        "gauge_panel": counts,
        "runs": {"reference": reference, "candidate": candidate},
        "resources": resources,
        "sandbox_resource_attempt": {
            "exit_code": int((HERE / "reference-resource-sandbox.exit").read_text().strip()),
            "stdout_sha256": sha(HERE / "reference-resource-sandbox.stdout.txt"),
            "stderr_sha256": sha(HERE / "reference-resource-sandbox.stderr.txt"),
        },
    }
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "problems": problems,
                      "binary_sha256": result["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
