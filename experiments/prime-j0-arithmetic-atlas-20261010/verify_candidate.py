#!/usr/bin/env python3
"""Bind arithmetic U14 correctness, table size, and raw outputs to source."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "experiments/prime-j0-host-replay-20261010"))
import host_replay as replay

N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
MODES = replay.COMPARISONS["arithmetic"]["modes"]
EXPECTED_BYTES = replay.COMPARISONS["arithmetic"]["retained_bytes"]


def check_inputs(problems):
    record = json.loads((HERE / "fresh-inputs.json").read_text())
    values = [int(value, 16) for value in record["scalars_hex"]]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in values)).hexdigest()
    if (record["schema"], record["seed"], record["count"], len(values), digest) != (
            1, 20261010128, 4096, 4096, record["scalar_sha256"]):
        problems.append("fresh input law or digest failed")
    seen = set()
    for name, expected in record["source_sha256"].items():
        path = ROOT / "experiments" / name
        if replay.sha(path) != expected:
            problems.append("prior input hash changed: " + name)
        seen.update(int(value, 16) % N for value in json.loads(path.read_text())["scalars_hex"])
    reduced = [value % N for value in values]
    if (len(values) != len(set(values)) or len(reduced) != len(set(reduced)) or
            set(reduced) & seen):
        problems.append("fresh reduced scalar repeated or overlaps prior inputs")
    return record


def check_holdout(problems):
    log = (HERE / "native-holdout.log").read_text()
    match = re.search(
        r"arithmetic_panel_cases=(\d+) retained_reference=(\d+) "
        r"retained_candidate=(\d+) counts_hex=([0-9a-f]+)", log)
    if ((HERE / "native-holdout.exit").read_text().strip() != "0" or
            "test result: ok. 1 passed; 0 failed;" not in log or not match):
        problems.append("holdout native test failed")
        return None
    counts = bytes.fromhex(match[4])
    if (int(match[1]) != 4096 or len(counts) != 8192 or
            int(match[2]) != EXPECTED_BYTES["reference"] or
            int(match[3]) != EXPECTED_BYTES["candidate"] or
            any(a != b or a > 2 for a, b in zip(counts[::2], counts[1::2]))):
        problems.append("holdout counts or table accounting failed")
    return {"cases": int(match[1]), "retained_reference": int(match[2]),
            "retained_candidate": int(match[3]),
            "counts_sha256": hashlib.sha256(counts).hexdigest()}


def read_resource(label, mode, flag, binary, problems):
    stdout = HERE / f"{label}-resource.stdout.txt"
    stderr = HERE / f"{label}-resource.stderr.txt"
    exit_file = HERE / f"{label}-resource.exit"
    rows = [replay.parse_row(line) for line in stdout.read_text().splitlines() if line.strip()]
    matches = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$",
                         stderr.read_text(), flags=re.MULTILINE)
    if exit_file.read_text().strip() != "0" or len(rows) != 1 or len(matches) != 1:
        problems.append(label + " resource run failed")
    else:
        replay.verify_row(rows[0], json.loads(replay.FIXTURE.read_text())["cases"][0],
                          mode, timed=True)
        if int(rows[0]["retained_bytes"]) != EXPECTED_BYTES[label]:
            problems.append(label + " retained table bytes changed")
    return {"argv": ["/usr/bin/time", "-l", str(binary),
                     f"--benchmark-scalar-unit-orbit-{flag}-fixed-case",
                     str(replay.FIXTURE), "0"],
            "cwd": str(ROOT), "exit_code": int(exit_file.read_text().strip()),
            "stdout_file": stdout.name, "stdout_sha256": replay.sha(stdout),
            "stderr_file": stderr.name, "stderr_sha256": replay.sha(stderr),
            "exit_file": exit_file.name, "exit_sha256": replay.sha(exit_file),
            "max_rss_bytes": int(matches[0]) if len(matches) == 1 else None,
            "retained_bytes": int(rows[0]["retained_bytes"]) if len(rows) == 1 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    receipt_path = HERE / "verification.json"
    if receipt_path.exists():
        raise SystemExit("verification receipt already exists")
    problems = []
    inputs = check_inputs(problems)
    suite = (HERE / "native-tests.log").read_text()
    if ((HERE / "native-tests.exit").read_text().strip() != "0" or
            "test result: ok. 83 passed; 0 failed;" not in suite):
        problems.append("83-test release suite failed")
    if (HERE / "native-build.exit").read_text().strip() != "0":
        problems.append("release executable build failed")
    holdout = check_holdout(problems)
    fixture = json.loads(replay.FIXTURE.read_text())
    if fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129:
        problems.append("frozen fixture changed")
    runs = {}
    resources = {}
    paired = {}
    for label, mode, flag in MODES:
        record = replay.run_record(
            [str(binary), f"--check-scalar-unit-orbit-{flag}-fixed-fixture",
             str(replay.FIXTURE)], HERE, label + "-fixture")
        rows = replay.rows_for(record, HERE, 129)
        for index, (row, case) in enumerate(zip(rows, fixture["cases"])):
            replay.verify_row(row, case, mode)
        runs[label] = record
        paired[label] = rows
        resources[label] = read_resource(label, mode, flag, binary, problems)
    for left, right in zip(paired["reference"], paired["candidate"]):
        if {k: v for k, v in left.items() if k != "mode"} != {
                k: v for k, v in right.items() if k != "mode"}:
            problems.append("paired fixture output differs")
            break
    sources = set(replay.source_paths("arithmetic"))
    sources.update([HERE / "PROOF.md", HERE / "verify_candidate.py"])
    source_hashes = {str(path.relative_to(ROOT)): replay.sha(path)
                     for path in sorted(sources)}
    raw_files = [HERE / name for name in (
        "native-holdout-compile-failed.log", "native-holdout-compile-failed.exit",
        "native-holdout.log", "native-holdout.exit",
        "native-tests.log", "native-tests.exit",
        "native-build.log", "native-build.exit")]
    for record in (*runs.values(), *resources.values()):
        raw_files.extend(HERE / record[name] for name in
                         ("stdout_file", "stderr_file", "exit_file"))
    receipt = {
        "schema": 1, "status": "passed" if not problems else "failed",
        "problems": problems, "comparison": "arithmetic",
        "binary": str(binary), "binary_sha256": replay.sha(binary),
        "source_sha256": source_hashes,
        "raw_sha256": {path.name: replay.sha(path) for path in raw_files},
        "native_tests_passed": 83, "fixture_cases_per_mode": 129,
        "input_sha256": inputs["scalar_sha256"],
        "holdout": holdout, "runs": runs, "resources": resources,
        "cpu_speedup_claim": None, "isolation_receipt": None,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "problems": problems,
                      "binary_sha256": receipt["binary_sha256"]}, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
