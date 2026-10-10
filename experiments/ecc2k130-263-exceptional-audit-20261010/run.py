#!/usr/bin/env python3
"""Run one hash-bound confirmation of the archived degree-263 map receipt."""

import hashlib
import json
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = json.loads((HERE / "FROZEN.json").read_text())
RUN = HERE / "runs" / "R1"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
ROUTE = Path("experiments/koblitz-polynomial-w-pair-20260925")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(label, command, timeout):
    start = time.perf_counter()
    status = "completed"
    try:
        process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                 timeout=timeout, check=False)
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        status = "timeout"
        stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
    (RUN / f"{label}.stdout").write_bytes(stdout)
    (RUN / f"{label}.stderr").write_bytes(stderr)
    return {
        "command": [str(part) for part in command],
        "exit_code": code,
        "status": status,
        "wall_seconds": time.perf_counter() - start,
        "stdout_sha256": sha256(RUN / f"{label}.stdout"),
        "stderr_sha256": sha256(RUN / f"{label}.stderr"),
    }


def main():
    if RUN.exists():
        raise SystemExit(f"refusing to overwrite {RUN}")
    for name, expected in FROZEN["source_sha256"].items():
        actual = sha256(ROOT / name)
        if actual != expected:
            raise SystemExit(f"frozen source mismatch: {name}: {actual}")
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      text=True).strip()
    if current != FROZEN["base_commit"]:
        # The protocol/runner commit follows the source commit; ancestry
        # is the relevant identity once these files are checked in.
        subprocess.run(["git", "merge-base", "--is-ancestor",
                        FROZEN["base_commit"], current], cwd=ROOT, check=True)
    RUN.mkdir(parents=True)
    steps = {}
    commands = [
        ("runtime", [str(SAGE), "--runtime-info"], 30),
        ("static", ["python3", str(ROUTE / "verify_ecc2k130_263_route_manifest.py")], 30),
        ("sage", [str(SAGE), "-python", str(ROUTE / "sage_verify_ecc2k130_263_exceptional.py"),
                  "--out", str(RUN / "sage_receipt.json")], FROZEN["external_wall_cap_seconds"]),
    ]
    for label, command, timeout in commands:
        steps[label] = execute(label, command, timeout)
        if steps[label]["status"] != "completed" or steps[label]["exit_code"] != 0:
            break
    status = {
        "schema": "ecc2k130-degree263-exceptional-confirmation-run-v1",
        "source_commit": current,
        "frozen_sha256": sha256(HERE / "FROZEN.json"),
        "runner_sha256": sha256(Path(__file__)),
        "steps": steps,
        "sage_receipt_sha256": sha256(RUN / "sage_receipt.json")
        if (RUN / "sage_receipt.json").exists() else None,
    }
    (RUN / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    if len(steps) != 3 or any(step["exit_code"] != 0 for step in steps.values()):
        raise SystemExit("confirmation stopped; inspect preserved raw outputs")
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
