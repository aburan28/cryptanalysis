#!/usr/bin/env python3
"""Source and result custody for the N41 coupled-seed search and transfer."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SCREEN = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"
HELPER = GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    screen = json.loads(SCREEN.read_text())
    assert screen["status"] == "complete"
    assert all(len(slot) == 64 for slot in screen["slots"][:6])
    for i, first in enumerate(screen["slot_rotations"][:6]):
        for second in screen["slot_rotations"][i + 1:6]:
            assert screen["pairwise_slot_intersections"][f"{first}_{second}"] == 0
    export = read("w6_export.json")
    assert export["source_sha256"] == {
        "script": sha(HERE / "export_w6.py"), "screen": sha(SCREEN),
        "input": sha(HERE / "w6_input.txt")}
    protocol = read("w6_protocol.json")
    assert protocol["status"] == "FROZEN_BEFORE_N41_W6_PUBLIC_QUERY"
    assert protocol["source_sha256"] == {
        "script": sha(HERE / "freeze_w6.py"),
        "source": sha(HERE / "join_w6.cpp"), "binary": sha(HERE / "join_w6"),
        "helper": sha(HELPER), "export_script": sha(HERE / "export_w6.py"),
        "export_receipt": sha(HERE / "w6_export.json"),
        "screen": sha(SCREEN), "input": sha(HERE / "w6_input.txt"),
        "sage_runtime": sha(HERE / "sage_runtime_info.json")}
    result = read("w6_result.json")
    hit = read("w6_hit.json")
    sage = read("w6_sage_audit.json")
    assert result["status"] == "FOUND_PENDING_SAGE_REPLAY"
    assert result["left_four_states"] == 3167136
    assert result["right_quad_a"] == result["right_quad_b"] == 51840
    assert result["accepted_probes"] == 730852
    assert result["group_hits"] == 5 and result["column_rejects"] == 4
    assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert sage["status"] == "PASS_INDEPENDENT_SAGE_W6_COUPLED_SEED_PUBLIC_RELATION"
    assert sage["replayed_sum"] == protocol["public_target_q"] == hit["raw_sum"]
    assert sage["source_sha256"]["native_hit"] == sha(HERE / "w6_hit.json")
    assert sage["source_sha256"]["native_result"] == sha(HERE / "w6_result.json")
    assert sage["source_sha256"]["script"] == sha(HERE / "sage_audit_w6.py")
    control = read("control_audit.json")
    assert control["status"] == "PASS_EXACT_XCNF_PROJECTION_AND_LIFT"
    projected = read("all_fixed_query/result.json")
    assert projected["status"] == "CENSORED_TIME"
    assert projected["stop_reason"] == "PARENT_WALL_CAP"
    assert projected["model_lines"] == 0 and projected["logged_restarts"] > 0
    assert projected["source_sha256"]["stdout"] == sha(
        HERE / "all_fixed_query/solver.stdout.txt")
    assert projected["source_sha256"]["stderr"] == sha(
        HERE / "all_fixed_query/solver.stderr.txt")
    assert not (HERE / "public_query").exists()
    seed = read("seed_sum_count.json")
    distinct = read("n41_distinct_count.json")
    transfer = read("transfer_w14.json")
    assert seed["status"] == "PASS_EXACT_SEED_SUM_TUPLE_COUNTS"
    assert distinct["status"] == "PASS_EXACT_N41_DISTINCT_COLUMN_TUPLE_COUNT"
    assert transfer["status"] == "PASS_EXPLICIT_W14_PAIR_JOIN_CAPACITY_BOUND"
    assert seed["source_sha256"]["script"] == sha(HERE / "seed_sum_count.py")
    assert distinct["source_sha256"]["script"] == sha(HERE / "n41_distinct_count.py")
    assert transfer["source_sha256"]["script"] == sha(HERE / "transfer_w14.py")
    assert transfer["source_sha256"]["count"] == sha(HERE / "seed_sum_count.json")
    audit = {"status": "PASS_COUPLED_SEED_N41_RESULT_AND_N131_CAPACITY_AUDIT",
             "curve_id": protocol["curve_id"], "public_target_q": protocol["public_target_q"],
             "relation": {"summands": 12, "distinct_columns": 12,
                          "setup_ns": result["setup_ns"],
                          "online_ns": result["online_ns"],
                          "accepted_probes": result["accepted_probes"],
                          "peak_rss_bytes": result["peak_rss_bytes"]},
             "projected_all_fixed_status": projected["status"],
             "source_sha256": {name: sha(HERE / name) for name in (
                 "w6_protocol.json", "w6_export.json", "w6_hit.json",
                 "w6_result.json", "w6_sage_audit.json", "control_audit.json",
                 "all_fixed_query/result.json", "seed_sum_count.json",
                 "n41_distinct_count.json", "transfer_w14.json")}}
    audit["source_sha256"]["script"] = sha(Path(__file__))
    with (HERE / "terminal_audit.json").open("x") as out:
        json.dump(audit, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": audit["status"], "relation": audit["relation"]}))


if __name__ == "__main__":
    main()
