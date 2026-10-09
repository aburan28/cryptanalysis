#!/usr/bin/env python3
"""Run frozen, alternating one-target rotation/sparse-canonical pairs."""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ORDERS = (("reference", "sparse"), ("sparse", "reference"),
          ("reference", "sparse"), ("sparse", "reference"),
          ("reference", "sparse"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(record: dict) -> dict:
    return {key: value for key, value in record.items()
            if key not in {"timing_ms", "peak_rss_bytes"}}


def main() -> None:
    freeze = json.loads((HERE / "freeze_receipt.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert freeze["workload_id"] == workload["workload_id"] == "c3929365e014"
    assert freeze["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert freeze["target_sha256"] == sha(HERE / "target_point.json")
    manifests = {name: json.loads((HERE / f"{name}_manifest.json").read_text())
                 for name in ("reference", "sparse")}
    for name, manifest in manifests.items():
        assert freeze["variants"][name]["manifest_sha256"] == sha(HERE / f"{name}_manifest.json")
        bound = manifest["candidate_freeze"]
        assert bound["workload_id"] == workload["workload_id"]
        assert sha(Path(bound["source_path"])) == bound["source_sha256"]
        assert sha(Path(bound["binary_path"])) == bound["binary_sha256"]
        assert sha(HERE / "target_point.json") == bound["target_sha256"]
    RUNS.mkdir(exist_ok=True)
    rows_path = RUNS / "panel_rows.jsonl"
    if rows_path.exists():
        raise RuntimeError("panel_rows.jsonl exists; preserve the first run")
    rows = []
    with rows_path.open("w") as row_file:
        for pair_no, order in enumerate(ORDERS, 1):
            pair_records = {}
            for position, name in enumerate(order, 1):
                bound = manifests[name]["candidate_freeze"]
                stem = f"R{pair_no}_{name}"
                result_path = RUNS / f"{stem}.jsonl"
                stdout_path = RUNS / f"{stem}.stdout"
                stderr_path = RUNS / f"{stem}.stderr"
                cmd = [bound["binary_path"], "53", "0", "244", "20260928",
                       str(HERE / "target_point.json"), str(result_path), "14"]
                started = time.perf_counter_ns()
                with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                    try:
                        completed = subprocess.run(cmd, stdout=out, stderr=err,
                                                   check=False, timeout=30)
                        exit_code = completed.returncode
                    except subprocess.TimeoutExpired:
                        exit_code = 124
                elapsed_ns = time.perf_counter_ns() - started
                row = {
                    "candidate_id": manifests[name]["candidate_id"],
                    "workload_id": workload["workload_id"],
                    "run_id": f'{manifests[name]["candidate_id"]}W{workload["workload_id"]}R{pair_no}',
                    "pair": pair_no, "position": position, "variant": name,
                    "process_exit_code": exit_code, "process_wall_cap_s": 30,
                    "process_wall_ns": elapsed_ns,
                    "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
                }
                if exit_code == 0:
                    lines = result_path.read_text().splitlines()
                    assert len(lines) == 1
                    record = json.loads(lines[0])
                    phases = record["timing_ms"]
                    assert abs(phases["target_online_phase_sum"] -
                               phases["target_online_after_reusable_setup"]) < 0.02
                    assert record["group_verified"] is True
                    row.update({
                        "status": "verified",
                        "output_sha256": sha(result_path),
                        "semantic_sha256": hashlib.sha256(json.dumps(
                            normalized(record), sort_keys=True,
                            separators=(",", ":")).encode()).hexdigest(),
                        "online_ms": phases["target_online_after_reusable_setup"],
                        "setup_ms": phases["reusable_setup_total"],
                        "index_build_ms": phases["index_build"],
                        "sampled_peak_rss_bytes": record["peak_rss_bytes"],
                        "target_relation_probes": record["target_relation_probes"],
                        "rank_attempts": record["rank_attempts"],
                        "rank_state_probes": record["rank_state_probes"],
                        "recovered_scalar": record["recovered_scalar"],
                    })
                    pair_records[name] = record
                else:
                    row["status"] = "timeout" if exit_code == 124 else "process_failure"
                row_file.write(json.dumps(row, sort_keys=True) + "\n")
                row_file.flush()
                rows.append(row)
                if exit_code != 0:
                    raise RuntimeError(f"{stem} exited {exit_code}; raw logs retained")
            assert normalized(pair_records["reference"]) == normalized(pair_records["sparse"]), (
                f"pair {pair_no} changed witness or result sequence")

    paired = []
    for pair_no in range(1, len(ORDERS) + 1):
        reference = next(row for row in rows if row["pair"] == pair_no and row["variant"] == "reference")
        sparse = next(row for row in rows if row["pair"] == pair_no and row["variant"] == "sparse")
        paired.append(reference["online_ms"] / sparse["online_ms"])
    summary = {
        "status": "verified",
        "controlled_online_speedup": None,
        "timing_status": "exploratory_unisolated_host",
        "orders": ORDERS, "pairs": len(ORDERS),
        "reference_online_median_ms": statistics.median(row["online_ms"] for row in rows if row["variant"] == "reference"),
        "sparse_online_median_ms": statistics.median(row["online_ms"] for row in rows if row["variant"] == "sparse"),
        "median_paired_reference_over_sparse": statistics.median(paired),
        "paired_ratios": paired,
        "semantic_sha256": rows[0]["semantic_sha256"],
        "rows_sha256": sha(rows_path),
        "freeze_sha256": sha(HERE / "freeze_receipt.json"),
    }
    (HERE / "panel_summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
