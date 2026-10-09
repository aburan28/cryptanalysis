#!/usr/bin/env python3
"""Run capped fresh-interpreter RSS pairs and retain all statuses."""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

from run_panel import normalized, sha

HERE = Path(__file__).resolve().parent
ORDERS = (("reference", "bloom"), ("bloom", "reference"),
          ("reference", "bloom"))


def main() -> None:
    directory = HERE / "memory_runs"
    if directory.exists():
        raise RuntimeError("memory_runs exists; preserve the first panel")
    directory.mkdir()
    rows = []
    for pair, order in enumerate(ORDERS, 1):
        for name in order:
            stem = f"M{pair}_{name}"
            worker_stdout = directory / f"{stem}.worker.stdout"
            worker_stderr = directory / f"{stem}.worker.stderr"
            with worker_stdout.open("wb") as out, worker_stderr.open("wb") as err:
                try:
                    completed = subprocess.run(
                        [sys.executable, str(HERE / "memory_worker.py"), name, str(pair)],
                        stdout=out, stderr=err, check=False, timeout=30)
                    outer_status = "completed" if completed.returncode == 0 else "worker_failure"
                except subprocess.TimeoutExpired:
                    outer_status = "worker_timeout"
            receipt = directory / f"{stem}.receipt.json"
            row = json.loads(receipt.read_text()) if receipt.exists() else {
                "variant": name, "pair": pair, "status": outer_status}
            row["outer_status"] = outer_status
            row["worker_stdout_sha256"] = sha(worker_stdout)
            row["worker_stderr_sha256"] = sha(worker_stderr)
            rows.append(row)
            with (directory / "panel_rows.jsonl").open("a") as file:
                file.write(json.dumps(row, sort_keys=True) + "\n")
    assert all(row["status"] == "verified" and row["outer_status"] == "completed" for row in rows)
    assert all(row["ru_maxrss_unit"] == rows[0]["ru_maxrss_unit"] for row in rows)
    for pair in range(1, 4):
        reference = json.loads((directory / f"M{pair}_reference.jsonl").read_text())
        bloom = json.loads((directory / f"M{pair}_bloom.jsonl").read_text())
        assert normalized(reference) == normalized(bloom)
    result = {
        "status": "verified",
        "protocol_sha256": sha(HERE / "MEMORY_PROTOCOL.md"),
        "rows_sha256": sha(directory / "panel_rows.jsonl"),
        "pairs": 3,
        "unit": rows[0]["ru_maxrss_unit"],
        "reference_median_peak_rss_raw": statistics.median(
            row["ru_maxrss_raw"] for row in rows if row["variant"] == "reference"),
        "bloom_median_peak_rss_raw": statistics.median(
            row["ru_maxrss_raw"] for row in rows if row["variant"] == "bloom"),
    }
    (HERE / "memory_summary.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
