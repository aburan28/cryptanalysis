#!/usr/bin/env python3
"""Bind the U14/U15/U16 correctness replay to inputs, source, and raw output."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from make_inputs import COUNT, N, SEED, SOURCES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "experiments/prime-j0-host-replay-20261010"))
import host_replay as replay

MODES = (
    ("u14", "unit_orbit_u256_sector14_fixed", "u256-sector", 64_314_112),
    ("u15", "unit_orbit_u256_sector15_fixed", "u256-sector15", 29_361_680),
    ("u16", "unit_orbit_u256_sector16_fixed", "u256-sector16", 13_283_616),
)


def verify_inputs():
    path = HERE / "fresh-inputs.json"
    record = json.loads(path.read_text())
    values = [int(value, 16) for value in record["scalars_hex"]]
    digest = hashlib.sha256(b"".join(v.to_bytes(32, "big") for v in values)).hexdigest()
    if (record["schema"], record["seed"], record["count"], len(values), digest) != (
            1, SEED, COUNT, COUNT, record["scalar_sha256"]):
        raise ValueError("fresh input law or digest differs")
    if set(record["source_sha256"]) != set(SOURCES):
        raise ValueError("prior input source set differs")
    prior = set()
    for name, expected in record["source_sha256"].items():
        source = ROOT / "experiments" / name
        if replay.sha(source) != expected:
            raise ValueError("prior input source hash differs: " + name)
        prior.update(int(v, 16) % N for v in json.loads(source.read_text())["scalars_hex"])
    reduced = [v % N for v in values]
    if len(set(values)) != COUNT or len(set(reduced)) != COUNT or set(reduced) & prior:
        raise ValueError("fresh scalar overlap or duplicate")
    return record


def verify_suite():
    log = (HERE / "native-tests.log").read_text()
    if (HERE / "native-tests.exit").read_text().strip() != "0":
        raise ValueError("release suite exited nonzero")
    if not re.search(r"test result: ok\. 90 passed; 0 failed;", log):
        raise ValueError("release suite count differs")
    match = re.search(
        r"cache_panel_cases=(\d+) bytes_u14=(\d+) bytes_u15=(\d+) "
        r"bytes_u16=(\d+) counts_hex=([0-9a-f]+)", log)
    if match is None:
        raise ValueError("fresh panel output absent")
    counts = bytes.fromhex(match[5])
    if ([int(match[i]) for i in range(1, 5)] !=
            [4096, 64_314_112, 29_361_680, 13_283_616] or len(counts) != 6 * 4096):
        raise ValueError("fresh panel size or table accounting differs")
    for u14_add, u14_gauge, u15_add, u15_gauge, u16_add, u16_gauge in zip(
            *[counts[i::6] for i in range(6)]):
        if not (u14_add <= 13 and u15_add <= 14 and u16_add <= 15 and
                u14_gauge <= 2 and u15_gauge <= 2 and u16_gauge <= 2):
            raise ValueError("operation count exceeds the format bound")
    return {"cases": 4096, "counts_sha256": hashlib.sha256(counts).hexdigest()}


def run_with_rusage(argv, name):
    stdout = HERE / (name + ".stdout.txt")
    stderr = HERE / (name + ".stderr.txt")
    exit_file = HERE / (name + ".exit")
    start = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err)
        deadline = start + 1800
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                code = os.waitstatus_to_exitcode(status)
                break
            if time.monotonic() >= deadline:
                process.kill()
                _, _, usage = os.wait4(process.pid, 0)
                code = 124
                break
            time.sleep(0.05)
        process.returncode = code
    exit_file.write_text(str(code) + "\n")
    return {
        "argv": [str(arg) for arg in argv], "exit_code": code,
        "stdout_file": stdout.name, "stdout_sha256": replay.sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": replay.sha(stderr),
        "exit_file": exit_file.name, "exit_sha256": replay.sha(exit_file),
        "outer_wall_ms": (time.monotonic() - start) * 1000,
        "max_rss_bytes": usage.ru_maxrss * (1024 if platform.system() == "Linux" else 1),
    }


def resource_record(binary, label, mode, flag, expected_bytes, case):
    argv = [str(binary), f"--benchmark-scalar-unit-orbit-{flag}-fixed-case",
            str(replay.FIXTURE), "0"]
    record = run_with_rusage(argv, label + "-resource")
    row = replay.rows_for(record, HERE, 1)[0]
    replay.verify_row(row, case, mode, timed=True)
    if int(row["retained_bytes"]) != expected_bytes:
        raise ValueError(label + " retained table size differs")
    record["retained_bytes"] = expected_bytes
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = HERE / "verification.json"
    if output.exists():
        raise SystemExit("verification receipt already exists")
    problems = []
    inputs = None
    panel = None
    runs = {}
    resources = {}
    try:
        inputs = verify_inputs()
        panel = verify_suite()
        if (HERE / "native-build.exit").read_text().strip() != "0":
            raise ValueError("release executable build failed")
        fixture = json.loads(replay.FIXTURE.read_text())
        if fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129:
            raise ValueError("fixture schema or count differs")
        rows_by_mode = {}
        for label, mode, flag, size in MODES:
            record = replay.run_record(
                [str(binary), f"--check-scalar-unit-orbit-{flag}-fixed-fixture",
                 str(replay.FIXTURE)], HERE, label + "-fixture")
            rows = replay.rows_for(record, HERE, 129)
            for row, case in zip(rows, fixture["cases"]):
                replay.verify_row(row, case, mode)
            runs[label] = record
            rows_by_mode[label] = rows
            resources[label] = resource_record(binary, label, mode, flag, size,
                                               fixture["cases"][0])
        reference = rows_by_mode["u14"]
        for label in ("u15", "u16"):
            for left, right in zip(reference, rows_by_mode[label]):
                if {k: v for k, v in left.items() if k != "mode"} != {
                        k: v for k, v in right.items() if k != "mode"}:
                    raise ValueError(label + " fixture row differs from U14")
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        problems.append(str(error))
    sources = set(replay.source_paths("sector"))
    sources.update(HERE / name for name in (
        "PROOF.md", "PROTOCOL.md", "ISOLATED_PANEL.md", "make_inputs.py",
        "fresh-inputs.json",
        "verify_candidate.py", "runpod_correctness.sh",
        "make_isolated_manifests.py", "stage_source.py"))
    raw = [HERE / name for name in ("native-tests.log", "native-tests.exit",
                                        "native-build.log", "native-build.exit")]
    for label, _, _, _ in MODES:
        for stage in ("fixture", "resource"):
            for suffix in ("stdout.txt", "stderr.txt", "exit"):
                raw.append(HERE / f"{label}-{stage}.{suffix}")
    receipt = {
        "schema": 1, "status": "passed" if not problems else "failed",
        "problems": problems, "binary": str(binary), "binary_sha256": replay.sha(binary),
        "input_sha256": inputs["scalar_sha256"] if inputs else None,
        "source_sha256": {str(path.relative_to(ROOT)): replay.sha(path)
                          for path in sorted(sources)},
        "raw_sha256": {path.name: replay.sha(path) for path in raw if path.exists()},
        "native_tests_passed": 90 if panel else None,
        "holdout": panel, "fixture_cases_per_mode": 129,
        "runs": runs, "resources": resources,
        "cpu_speedup_claim": None, "isolation_receipt": None,
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "problems": problems,
                      "binary_sha256": receipt["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
