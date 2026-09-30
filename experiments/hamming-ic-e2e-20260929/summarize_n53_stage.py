#!/usr/bin/env python3
"""Audit and summarize the frozen N53 ordinary and planted PDP pairs."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs/n53_scale_v1"
NAMES = ("fc", "unary", "fc_planted", "unary_planted")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archived_xcnf_sha(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    receipts = {}
    for name in NAMES:
        folder = RUN / name
        receipt = json.loads((folder / "receipt.json").read_text())
        assert receipt["candidate_id"] is None
        assert archived_xcnf_sha(folder / "system.xcnf.gz") == receipt["xcnf_sha256"]
        for relative, expected in receipt["source_sha256"].items():
            assert sha(ROOT / relative) == expected
        assert receipt["status"] == "EXTERNAL_WATCHDOG"
        assert receipt["attempt"]["guard"] == "external_watchdog"
        assert receipt["attempt"]["exit_code"] == -9
        assert receipt["model_xcnf_verified"] is False
        assert receipt["group_lift"] is None
        receipts[name] = receipt
    for first, second in (("fc", "unary"), ("fc_planted", "unary_planted")):
        a, b = receipts[first], receipts[second]
        assert a["target"] == b["target"]
        assert a["workload_id"] == b["workload_id"]
        assert a["factor_base"]["projected_set_sha256"] == b["factor_base"]["projected_set_sha256"]
        assert a["limits"] == b["limits"]
    replay = json.loads((RUN / "sage_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["runtime_info_sha256"] == sha(RUN / "sage_runtime_info.json")
    assert replay["source_sha256"] == sha(HERE / "sage_replay_n53.py")
    rows = []
    for name in NAMES:
        item = receipts[name]
        rows.append({"arm": name, "encoding": item["encoding"],
                     "target_kind": item.get("target_kind", "ordinary_subgroup_point"),
                     "target": item["target"], "workload_id": item["workload_id"],
                     "status": item["status"],
                     "verified_decompositions": 0,
                     "solver_wall_ns": item["attempt"]["solver_wall_ns"],
                     "sampled_peak_solver_rss_bytes": item["attempt"]["sampled_peak_child_rss_bytes"],
                     "variables": item["formula"]["variables"],
                     "cnf_clauses": item["formula"]["cnf_clauses"],
                     "xor_rows": item["formula"]["xor_rows"],
                     "and_gates": item["formula"]["and_gates"],
                     "limits": item["limits"],
                     "xcnf_sha256": item["xcnf_sha256"]})
    first = receipts["fc"]
    summary = {
        "kind": "n53_fc_hamming_vs_unary_bounded_pdp_stage",
        "candidate_id": None,
        "curve_id": first["curve_id"],
        "factor_base": first["factor_base"],
        "ordinary_workload_id": first["workload_id"],
        "planted_workload_id": receipts["fc_planted"]["workload_id"],
        "ordinary_target": first["target"],
        "planted_target": receipts["fc_planted"]["target"],
        "rows": rows,
        "independent_sage_replay": replay,
        "ordinary_verified_decompositions": 0,
        "planted_verified_decompositions": 0,
        "relations": None, "relation_rank": None,
        "target_log": None, "ic_online_wall_ns": None,
        "rho_online_wall_ns": None, "online_speedup": None,
        "advance_to_n83": False,
        "claim_boundary": "All PDP attempts were externally censored; no solved-query rate or IC-vs-rho speedup follows."}
    (RUN / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "verified_decompositions": 0,
                      "advance_to_n83": False}, sort_keys=True))


if __name__ == "__main__":
    main()
