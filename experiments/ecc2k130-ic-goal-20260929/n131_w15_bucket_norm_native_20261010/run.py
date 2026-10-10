#!/usr/bin/env python3
"""Bounded one-worker native norm run with frozen source and input checks."""
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_NATIVE_NORM_RUN"
    for rel, wanted in protocol["sha256"].items():
        path = (HERE / rel).resolve()
        assert digest(path) == wanted, rel
    assert not (HERE / "result.json").exists()
    assert not (HERE / "coefficients.tsv").exists()
    cmd = [str(HERE / "norm"), str(protocol["seed"]),
           str(HERE / "coefficients.tsv"),
           str(protocol["wall_cap_seconds"]), str(protocol["rss_cap_bytes"])]
    started = time.monotonic_ns()
    terminal = None
    with (HERE / "run.stdout.txt").open("x") as stdout, (HERE / "run.stderr.txt").open("x") as stderr:
        child = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, cwd=HERE)
        try:
            while child.poll() is None:
                elapsed = (time.monotonic_ns() - started) / 1e9
                if elapsed > protocol["wall_cap_seconds"]:
                    terminal = "CENSORED_TIME"
                    child.kill()
                time.sleep(0.05)
            returncode = child.wait()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    elapsed_ns = time.monotonic_ns() - started
    peaks = [int(value) for value in re.findall(r"peak_rss=(\d+)",
             (HERE / "run.stdout.txt").read_text())]
    peak = max(peaks) if peaks else None
    if terminal is None:
        terminal = "COMPLETE" if returncode == 0 else "PRODUCER_FAILURE"
    result = {"status": terminal, "returncode": returncode,
              "parent_wall_ns": elapsed_ns, "native_reported_peak_rss_bytes": peak,
              "stdout_sha256": digest(HERE / "run.stdout.txt"),
              "stderr_sha256": digest(HERE / "run.stderr.txt"),
              "protocol_sha256": digest(PROTOCOL),
              "coefficients_sha256": digest(HERE / "coefficients.tsv")
              if (HERE / "coefficients.tsv").exists() else None,
              "source_sha256": protocol["sha256"],
              "candidate_id": None, "target_count": 0}
    with (HERE / "result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
