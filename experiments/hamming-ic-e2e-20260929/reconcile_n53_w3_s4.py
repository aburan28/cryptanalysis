#!/usr/bin/env python3
"""Reconcile two retained paired W3/S4 planted runs and their workload labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ARMS = ("fc", "unary")
VERSIONS = ("v1", "v2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode()).hexdigest()


def main():
    data = {}
    for version in VERSIONS:
        root = RUNS / f"n53_w3_s4_planted_{version}"
        data[version] = {arm: json.loads((root / arm / "receipt.json").read_text())
                         for arm in ARMS}
        replay = json.loads((root / "sage_replay.json").read_text())
        assert replay["status"] == "PASS"
        replay_source = (root / "sage_replay_source.py") if version == "v1" \
            else (HERE / "sage_replay_n53_w3_s4.py")
        assert sha(replay_source) == replay["source_sha256"]
        runner_source = (root / "runner_source.py") if version == "v1" \
            else (HERE / "run_n53_w3_s4_planted.py")
        for arm, receipt in data[version].items():
            assert sha(runner_source) == receipt["source_sha256"][str(
                (HERE / "run_n53_w3_s4_planted.py").relative_to(HERE.parents[1]))]
            assert receipt["status"] == "INDETERMINATE"
            assert receipt["pinned_model_verified"] is True
            assert receipt["search_attempt"]["status_lines"] == ["s INDETERMINATE"]
            assert receipt["search_attempt"]["guard"] is None
            assert replay["source_receipt_sha256"][arm] == sha(root / arm / "receipt.json")
        assert data[version]["fc"]["fixture"] == data[version]["unary"]["fixture"]
    canonical_workload = data["v2"]["fc"]["workload"]
    workload_id = canonical_hash(canonical_workload)[:12]
    assert all(data["v2"][arm]["workload_id"] == workload_id for arm in ARMS)
    legacy_id = data["v1"]["fc"]["workload_id"]
    assert legacy_id.startswith("W") and len(legacy_id) == 13
    assert all(data["v1"][arm]["workload_id"] == legacy_id for arm in ARMS)
    rows = []
    for version in VERSIONS:
        for arm in ARMS:
            receipt = data[version][arm]
            assert receipt["fixture"] == data["v2"]["fc"]["fixture"]
            assert receipt["source_geometry_receipt_sha256"] == \
                   data["v2"]["fc"]["source_geometry_receipt_sha256"]
            assert receipt["solver_binary_sha256"] == \
                   data["v2"]["fc"]["solver_binary_sha256"]
            assert receipt["limits"] == data["v2"]["fc"]["limits"]
            assert receipt["search_artifacts"]["system.xcnf"]["raw_sha256"] == \
                   data["v2"][arm]["search_artifacts"]["system.xcnf"]["raw_sha256"]
            rows.append({"version": version, "encoding": arm,
                         "candidate_id": None, "run_id": None,
                         "workload_id": workload_id,
                         "receipt_workload_id": receipt["workload_id"],
                         "status": receipt["status"],
                         "search_solver_wall_ns": receipt["search_attempt"]["solver_wall_ns"],
                         "sampled_peak_child_rss_bytes": receipt["search_attempt"]["sampled_peak_child_rss_bytes"],
                         "formula_xcnf_sha256": receipt["search_artifacts"]["system.xcnf"]["raw_sha256"],
                         "receipt_sha256": sha(RUNS / f"n53_w3_s4_planted_{version}" / arm / "receipt.json")})
    result = {"status": "PASS", "kind": "n53_w3_s4_planted_reconciliation",
              "canonical_workload": canonical_workload,
              "canonical_workload_id": workload_id,
              "v1_schema_note": "The first run's workload_id included an extra W prefix and its executed runner did not store the full workload record. Both source snapshots and all attempt receipts are retained. The frozen fixture, formulas, limits, and solver binary match v2.",
              "rows": rows,
              "advance_to_ordinary_target": False,
              "source_sha256": sha(Path(__file__))}
    path = RUNS / "n53_w3_s4_reconciliation.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "workload_id": workload_id,
                      "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
