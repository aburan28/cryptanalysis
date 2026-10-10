#!/usr/bin/env python3
"""Bounded independent NTL parser and modular-unit certificate replay."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
COEFFICIENTS = HERE.parent / "n131_w15_bucket_norm_native_20261010/coefficients.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "verify_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_REMAINDER_CERTIFICATE_CHECK"
    for rel, expected in protocol["sha256"].items():
        assert sha((HERE / rel).resolve()) == expected, rel
    output = HERE / "verify_result.json"
    stdout_path = HERE / "verify.stdout.txt"
    stderr_path = HERE / "verify.stderr.txt"
    assert not output.exists()
    cmd = [str(HERE / "verify_certificate"), str(COEFFICIENTS),
           str(HERE / "certificate_positive.remainder.bin"),
           str(HERE / "certificate_negative.remainder.bin"),
           str(protocol["known_left_output"]), str(protocol["known_right_output"]),
           str(protocol["positive_residual"]), str(output)]
    started = time.monotonic_ns()
    status = "COMPLETE"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        child = subprocess.Popen(cmd, cwd=HERE, stdout=stdout, stderr=stderr)
        try:
            while child.poll() is None:
                if (time.monotonic_ns() - started) / 1e9 > protocol["cap_seconds"]:
                    status = "CENSORED_TIME"
                    child.kill()
                time.sleep(0.1)
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
               "output_sha256": sha(output) if output.exists() else None,
               "stdout_sha256": sha(stdout_path),
               "stderr_sha256": sha(stderr_path),
               "candidate_id": None, "target_count": 0}
    with (HERE / "verify.receipt.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
