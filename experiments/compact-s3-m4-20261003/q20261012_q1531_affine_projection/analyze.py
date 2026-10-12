#!/usr/bin/env python3
"""Compare the exact projected S3 panel with its frozen Q1528 controls."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1528 = HERE.parent / "q20261012_q1528_gate_elimination"
PERIODIC = re.compile(r"^c \|\s*\d+\s+\d+\s+(\d+)\s*\|", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = json.loads((HERE / "protocol.json").read_text())
    baseline = json.loads((Q1528 / "analysis.json").read_text())
    old = {row["label"]: row for row in baseline["rows"]}
    rows = []
    for label in p["panel_order"]:
        folder = HERE / "runs" / label
        receipt = json.loads((folder / "receipt.json").read_text())
        transformed = p["inputs"][label]
        stdout = (folder / "stdout.txt").read_text(errors="replace")
        periodic = [int(x) for x in PERIODIC.findall(stdout)]
        assert receipt["stdout_sha256"] == sha(folder / "stdout.txt")
        assert receipt["stderr_sha256"] == sha(folder / "stderr.txt")
        assert receipt["status"] in ("SAT_VERIFIED", "WALL_CAP", "CPU_CAP",
                                     "PROCESS_FAILURE", "UNVERIFIED_MODEL",
                                     "INDETERMINATE", "UNSAT")
        rows.append({
            "label": label, "n": 53 if label.startswith("n53") else 83,
            "curve_id": receipt["curve_id"], "status": receipt["status"],
            "baseline_status": old[label]["status"],
            "variables": transformed["variables"],
            "baseline_variables": old[label]["variables"],
            "equations": transformed["equations"],
            "baseline_equations": old[label]["equations"],
            "eliminated_pivots": transformed["eliminated_pivots"],
            "child_user_cpu_seconds": receipt["child_user_cpu_seconds"],
            "baseline_child_user_cpu_seconds": old[label]["child_user_cpu_seconds"],
            "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
            "peak_rss_bytes_darwin": receipt["child_peak_rss_bytes_darwin"],
            "baseline_peak_rss_bytes_darwin": old[label]["peak_rss_bytes_darwin"],
            "periodic_conflicts_lower_bound": max(periodic, default=None),
            "baseline_periodic_conflicts_lower_bound": old[label]["periodic_conflicts_lower_bound"],
            "verified_group_relation": bool(receipt["verification"]),
            "ordinary_verified_relations": receipt["ordinary_verified_relations"],
            "receipt_sha256": sha(folder / "receipt.json"),
        })
    result = {
        "proposal_id": "Q1531", "candidate_id": None, "run_id": None,
        "isogeny": "none", "stage_code": "PDP4sat",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "baseline_q1528_analysis_sha256": sha(Q1528 / "analysis.json"),
        "source_sha256": sha(Path(__file__)),
        "rows": rows,
        "ordinary_verified_relations": sum(x["ordinary_verified_relations"] for x in rows),
        "cost_per_useful_relation": None,
        "complete_n131_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "host_isolation_receipt": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Q1531", len(rows), "cells; ordinary relations",
          result["ordinary_verified_relations"])


if __name__ == "__main__":
    main()
