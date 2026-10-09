#!/usr/bin/env python3
"""Paired full-index and one-public-target control for a u64 index hasher."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-solver-gates-20261008"
TARGET = PRIOR / "a1_n53_target0.json"
LOGS = PRIOR / "a1_n53_rank_replay.json"
RUNS = HERE / "a1_runs"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(label: str, sequence: int) -> dict:
    binary = HERE / f"{label}_target_probe"
    raw = RUNS / f"{sequence:02d}_{label}.json"
    if raw.exists():
        raise FileExistsError(raw)
    command = ["/usr/bin/time", "-l", str(binary), "closure", "600",
               str(TARGET), str(LOGS), str(raw)]
    started = time.perf_counter_ns()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=180)
        status = "process_complete" if process.returncode == 0 else "process_error"
        stderr = process.stderr
        code = process.returncode
    except subprocess.TimeoutExpired as error:
        status = "timeout_180s"
        stderr = (error.stderr or b"").decode(errors="replace")
        code = None
    elapsed = time.perf_counter_ns() - started
    peak = re.search(r"(\d+)\s+maximum resident set size", stderr)
    payload = json.loads(raw.read_text()) if raw.exists() else None
    return {"label": label, "sequence": sequence, "status": status,
            "exit_code": code, "process_wall_ns_exploratory": elapsed,
            "peak_rss_bytes": int(peak.group(1)) if peak else None,
            "binary_sha256": sha(binary),
            "raw_path": raw.name if raw.exists() else None,
            "raw_sha256": sha(raw) if raw.exists() else None,
            "result": payload, "stderr_tail": stderr[-1000:] if code else None}


def main() -> None:
    output = HERE / "a1_index_bench.json"
    if output.exists():
        raise FileExistsError(output)
    RUNS.mkdir(exist_ok=True)
    rows = []
    for sequence, label in enumerate(("control", "fast", "fast", "control")):
        rows.append(one(label, sequence))
        (HERE / "a1_index_bench.partial.json").write_text(
            json.dumps({"runs": rows}, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"sequence": sequence, "label": label,
                          "status": rows[-1]["status"],
                          "index_ms": rows[-1]["result"].get(
                              "index_build_ms_exploratory") if rows[-1]["result"] else None}),
              flush=True)
    results = [row["result"] for row in rows]
    assert all(row["status"] == "process_complete" for row in rows)
    for key in ("base_hash_blake3", "target_point", "recovered_scalar",
                "witness_indices", "pair_sums", "distinct_pair_x_orbit_keys",
                "duplicate_pair_keys", "lookups"):
        assert len({json.dumps(result[key], sort_keys=True) for result in results}) == 1, key
    assert all(result["status"] == "verified_recovery" for result in results)
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "status": "matched_correctness_pass",
              "timing_class": "exploratory_unisolated",
              "control_source_sha256": sha(HERE / "a1_n53_control/src/bin/target_probe.rs"),
              "fast_source_sha256": sha(HERE / "a1_n53_fast_index/src/bin/target_probe.rs"),
              "shared_arithmetic_sha256": sha(HERE / "a1_n53_control/src/main.rs"),
              "target_sha256": sha(TARGET), "logs_sha256": sha(LOGS),
              "driver_sha256": sha(Path(__file__)), "runs": rows}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
