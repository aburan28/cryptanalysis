#!/usr/bin/env python3
"""Run frozen N41 positive and negative quotient-ring controls."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol_n41.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N41_QUOTIENT_CONTROLS"
    for rel, expected in protocol["sha256"].items():
        assert sha((HERE / rel).resolve()) == expected, rel
    for row in protocol["cases"]:
        label = row["label"]
        out = HERE / f"{label}.json"
        stdout_path = HERE / f"{label}.stdout.txt"
        stderr_path = HERE / f"{label}.stderr.txt"
        assert not out.exists()
        cmd = [str(HERE / "quotient"), "41", "6", "2", "20", "25",
               str(row["residual"]), "-", "-", str(out),
               str(protocol["cap_seconds"]), str(protocol["rss_cap_bytes"])]
        started = time.monotonic_ns()
        status = "COMPLETE"
        with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
            child = subprocess.Popen(cmd, cwd=HERE, stdout=stdout, stderr=stderr)
            try:
                while child.poll() is None:
                    if (time.monotonic_ns() - started) / 1e9 > protocol["cap_seconds"]:
                        status = "CENSORED_TIME"
                        child.kill()
                    time.sleep(0.05)
                code = child.wait()
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
        if status == "COMPLETE" and code != 0:
            status = "PRODUCER_FAILURE"
        receipt = {"status": status, "returncode": code,
                   "parent_wall_ns": time.monotonic_ns() - started,
                   "protocol_sha256": sha(HERE / "protocol_n41.json"),
                   "output_sha256": sha(out) if out.exists() else None,
                   "stdout_sha256": sha(stdout_path),
                   "stderr_sha256": sha(stderr_path),
                   "case": label, "candidate_id": None, "target_count": 0}
        with (HERE / f"{label}.receipt.json").open("x") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
