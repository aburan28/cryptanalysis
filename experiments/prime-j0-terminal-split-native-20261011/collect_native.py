#!/usr/bin/env python3
"""Run and bind the focused native correctness replay."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess


HERE = Path(__file__).resolve().parent
WINDOW = Path("src/bin/eisenstein_fixed/unit_orbit_windows.rs")
TEST = "split_terminal_selector_matches_frozen_panel_and_binary_points"
PATTERN = re.compile(
    r"split_terminal_native_cases=(\d+) point_proxy=(\d+) terms=(\d+) "
    r"splits=(\d+) retained_bytes=(\d+)"
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crate", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--materialization-receipt", type=Path, required=True)
    args = parser.parse_args()
    crate = args.crate.resolve()
    binary = args.binary.resolve()
    material = json.loads(args.materialization_receipt.read_bytes())
    assert material["status"] == "materialized"
    assert digest(crate / WINDOW) == material["window_sha256"]
    assert digest(crate / "split-terminal-inputs.json") == material["input_sha256"]
    assert digest(crate / "split-terminal-paths.jsonl") == material["certificate_sha256"]
    log = HERE / "native-targeted.log"
    output = HERE / "native-targeted-check.json"
    if log.exists() or output.exists():
        raise SystemExit("refusing to overwrite native correctness receipt")
    run = subprocess.run([str(binary), TEST, "--nocapture"], cwd=crate,
                         capture_output=True, text=True, timeout=900)
    log.write_text(run.stdout + run.stderr)
    match = PATTERN.search(log.read_text())
    measured = tuple(map(int, match.groups())) if match else None
    passed = run.returncode == 0 and measured == \
        (4096, 609671, 54528, 1280, 67108816) and \
        "test result: ok. 1 passed; 0 failed" in log.read_text()
    receipt = {
        "schema": 1,
        "status": "passed" if passed else "failed",
        "test": TEST,
        "exit_code": run.returncode,
        "measured": measured,
        "crate_window_sha256": digest(crate / WINDOW),
        "binary_sha256": digest(binary),
        "input_sha256": digest(crate / "split-terminal-inputs.json"),
        "certificate_sha256": digest(crate / "split-terminal-paths.jsonl"),
        "materialization_receipt_sha256": digest(args.materialization_receipt),
        "collector_sha256": digest(Path(__file__)),
        "log_sha256": digest(log),
        "platform": platform.platform(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "timing_class": "correctness only; host isolation unverified",
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
