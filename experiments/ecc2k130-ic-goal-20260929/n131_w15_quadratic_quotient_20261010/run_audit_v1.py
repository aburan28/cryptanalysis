#!/usr/bin/env python3
"""Run the checked-Sage independent remainder audit with a wall cap."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "audit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_RESULTANT_SAGE_AUDIT"
    for rel, expected in protocol["sha256"].items():
        assert sha((HERE / rel).resolve()) == expected, rel
    assert not (HERE / "audit_result.json").exists()
    started = time.monotonic_ns()
    status = "COMPLETE"
    stdout_path = HERE / "audit.stdout.txt"
    stderr_path = HERE / "audit.stderr.txt"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        child = subprocess.Popen([str(SAGE), "-python", str(HERE / "audit_sage.py")],
                                 cwd=HERE, stdout=stdout, stderr=stderr)
        try:
            while child.poll() is None:
                if (time.monotonic_ns() - started) / 1e9 > protocol["cap_seconds"]:
                    status = "CENSORED_TIME"
                    child.kill()
                time.sleep(0.2)
            code = child.wait()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    if status == "COMPLETE" and code != 0:
        status = "PRODUCER_FAILURE"
    receipt = {"status": status, "returncode": code,
               "parent_wall_ns": time.monotonic_ns() - started,
               "protocol_sha256": sha(protocol_path),
               "output_sha256": sha(HERE / "audit_result.json")
               if (HERE / "audit_result.json").exists() else None,
               "stdout_sha256": sha(stdout_path),
               "stderr_sha256": sha(stderr_path),
               "candidate_id": None, "target_count": 0}
    with (HERE / "audit.receipt.json").open("x") as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
