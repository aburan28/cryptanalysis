#!/usr/bin/env python3
"""Bind frozen inputs, exact outcomes, monitor receipts, and Sage replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n41_diagonal_double_norm_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol = read(HERE / "protocol.json")
    monitor_protocol = read(HERE / "monitor_protocol_v2.json")
    transfer_protocol = read(HERE / "transfer_protocol.json")
    assert protocol["status"] == monitor_protocol["status"] == transfer_protocol["status"] == "FROZEN_BEFORE_RUN"
    paths = {"batch": HERE / "batch.py", "freeze": HERE / "freeze.py",
             "prior_run": PRIOR / "run.py", "prior_input": PRIOR / "input.json",
             "prior_protocol": PRIOR / "protocol.json", "prior_result": PRIOR / "result.json",
             "geometry": BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
             "base": BASE / "run_n41_disjoint_s5_sat.py",
             "pair_oracle": BASE.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py",
             "runtime": HERE / "sage_runtime_info.json"}
    assert {key: sha(path) for key, path in paths.items()} == protocol["source_sha256"]
    assert monitor_protocol["monitor_sha256"] == sha(HERE / "monitor_v2.py")
    assert monitor_protocol["protocol_sha256"] == sha(HERE / "protocol.json")
    assert transfer_protocol["source_sha256"]["transfer"] == sha(HERE / "transfer.py")
    prior = read(PRIOR / "result.json")
    assert prior["status"] == "PARTIAL"
    assert [case["status"] for case in prior["cases"]] == ["CENSORED_TIME"]*2
    audit = read(HERE / "sage_audit.json")
    assert audit["status"] == "PASS" and audit["source_sha256"] == sha(HERE / "sage_audit.py")
    assert audit["public_exact_group_hits"] == 0
    cases = []
    for name in ("positive", "public"):
        result_path = HERE / f"{name}_result.json"
        result = read(result_path)
        assert result["status"] == "COMPLETE"
        assert result["protocol_sha256"] == sha(HERE / "protocol.json")
        assert result["source_sha256"] == sha(HERE / "batch.py")
        assert result["online_wall_ns"] < protocol["online_wall_cap_seconds"]*10**9
        assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
        assert all(lift["right_resultant_ns"] + lift["global_gcd_ns"]
                   <= result["online_wall_ns"] for lift in result["lifts"])
        if name == "positive":
            assert len(result["lifts"]) == 1
            assert result["lifts"][0]["global_common_degree"] == 1
            assert result["lifts"][0]["exact_hits"] == 1
            receipt = read(HERE / "positive_attach_monitor.json")
            failure = read(HERE / "monitor_v1_failure.json")
            assert receipt["status"] == "COMPLETE" and receipt["monitor_attached_after_worker_start"]
            assert receipt["result_sha256"] == sha(result_path)
            assert failure["status"] == "MONITOR_FAILURE_AFTER_CHILD_LAUNCH"
            assert failure["monitor_protocol_sha256"] == sha(HERE / "monitor_protocol.json")
        else:
            assert len(result["lifts"]) == 2
            assert [lift["global_common_degree"] for lift in result["lifts"]] == [0, 0]
            receipt = read(HERE / "public_monitor.json")
            assert receipt["status"] == "COMPLETE" and receipt["online_clock_observed"]
            assert receipt["sampled_peak_process_tree_rss_bytes"] < protocol["rss_cap_bytes"]
            assert receipt["worker_result_sha256"] == sha(result_path)
            assert receipt["monitor_protocol_sha256"] == sha(HERE / "monitor_protocol_v2.json")
            assert audit["public_result_sha256"] == sha(result_path)
        cases.append({"case": name, "online_wall_ns": result["online_wall_ns"],
                      "global_gcd_degrees": [x["global_common_degree"] for x in result["lifts"]],
                      "exact_hits": sum(x["exact_hits"] for x in result["lifts"]),
                      "receipt_sha256": sha(result_path)})
    transfer = read(HERE / "transfer_result.json")
    assert transfer["status"] == "PASS_EXACT_DENSE_LEFT_BOUND"
    assert transfer["protocol_sha256"] == sha(HERE / "transfer_protocol.json")
    assert transfer["exact_global_left_degree"] == 268419072
    assert transfer["minimum_dense_left_bytes"] > protocol["rss_cap_bytes"]
    result = {"status": "PASS", "candidate_id": None,
              "cases": cases,
              "positive_sage_group_replay": audit["positive_distinct_columns"] == 4,
              "public_sage_group_hits": audit["public_exact_group_hits"],
              "n131_dense_left_minimum_bytes": transfer["minimum_dense_left_bytes"],
              "source_sha256": sha(Path(__file__)),
              "sage_audit_sha256": sha(HERE / "sage_audit.json"),
              "transfer_result_sha256": sha(HERE / "transfer_result.json")}
    with (HERE / "audit.json").open("x") as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
