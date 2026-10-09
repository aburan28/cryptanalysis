#!/usr/bin/env python3
"""Run one solver child and capture its peak RSS from a fresh interpreter."""

from __future__ import annotations

import json
import resource
import subprocess
import sys
from pathlib import Path

from run_panel import sha

HERE = Path(__file__).resolve().parent


def main() -> None:
    name, pair = sys.argv[1], int(sys.argv[2])
    assert name in ("reference", "bloom") and pair in (1, 2, 3)
    manifest = json.loads((HERE / f"{name}_manifest.json").read_text())
    bound = manifest["candidate_freeze"]
    assert sha(Path(bound["source_path"])) == bound["source_sha256"]
    assert sha(Path(bound["binary_path"])) == bound["binary_sha256"]
    stem = f"M{pair}_{name}"
    output = HERE / "memory_runs" / f"{stem}.jsonl"
    stdout = HERE / "memory_runs" / f"{stem}.stdout"
    stderr = HERE / "memory_runs" / f"{stem}.stderr"
    command = [bound["binary_path"], "53", "0", "244", "20260928",
               str(HERE / "target_point.json"), str(output), "14"]
    status = "verified"
    code = None
    with stdout.open("wb") as out, stderr.open("wb") as err:
        try:
            completed = subprocess.run(command, stdout=out, stderr=err,
                                       check=False, timeout=20)
            code = completed.returncode
            if code != 0:
                status = "process_failure"
        except subprocess.TimeoutExpired:
            status = "timeout"
    rss_raw = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    row = {
        "variant": name, "pair": pair, "status": status,
        "process_exit_code": code,
        "ru_maxrss_raw": rss_raw,
        "ru_maxrss_unit": "bytes" if sys.platform == "darwin" else "kilobytes",
        "binary_sha256": bound["binary_sha256"],
        "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
    }
    if status == "verified":
        run = json.loads(output.read_text())
        assert run["group_verified"] is True
        row["output_sha256"] = sha(output)
        row["recovered_scalar"] = run["recovered_scalar"]
    (HERE / "memory_runs" / f"{stem}.receipt.json").write_text(
        json.dumps(row, sort_keys=True, indent=2) + "\n")
    print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
