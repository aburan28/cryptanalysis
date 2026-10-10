#!/usr/bin/env python3
"""Bounded N131 positive/negative resultant remainder certificates."""
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
    protocol_path = HERE / "protocol_certificate.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N131_RESULTANT_CERTIFICATES"
    for rel, expected in protocol["sha256"].items():
        assert sha((HERE / rel).resolve()) == expected, rel
    for case in protocol["cases"]:
        label = case["label"]
        output = HERE / f"certificate_{label}.json"
        remainder = HERE / f"certificate_{label}.remainder.bin"
        stdout_path = HERE / f"certificate_{label}.stdout.txt"
        stderr_path = HERE / f"certificate_{label}.stderr.txt"
        assert not output.exists() and not remainder.exists()
        cmd = [str(HERE / "resultant_certificate"), "131", "15", "13686", "26", "39",
               str(case["residual"]), str(case.get("known_left_output", "-")),
               str(COEFFICIENTS), str(output), str(protocol["cap_seconds"]),
               str(protocol["rss_cap_bytes"]), str(remainder)]
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
        result = {"status": status, "returncode": code,
                  "parent_wall_ns": time.monotonic_ns() - started,
                  "protocol_sha256": sha(protocol_path),
                  "output_sha256": sha(output) if output.exists() else None,
                  "remainder_sha256": sha(remainder) if remainder.exists() else None,
                  "remainder_bytes": remainder.stat().st_size if remainder.exists() else None,
                  "stdout_sha256": sha(stdout_path),
                  "stderr_sha256": sha(stderr_path),
                  "case": label, "candidate_id": None, "target_count": 0}
        with (HERE / f"certificate_{label}.receipt.json").open("x") as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
