#!/usr/bin/env python3
"""Execute the frozen rotated-source index and unchanged query reader."""

import json

from freeze import HERE, OLD, SUPPORT, sha
from run import run_command, save


def main():
    protocol = json.loads((HERE / "protocol_v2.json").read_text())
    assert protocol["status"] == "FROZEN_ROTATED_GROUP_BATCH_PREPARE_64_SEEDS"
    # The source map is copied from the frozen protocol and verified here.
    paths = {"rotated_source": HERE / "prepare_rotated.cpp",
             "rotated_binary": HERE / "prepare_rotated",
             "freezer": HERE / "freeze_v2.py", "runner": HERE / "run_v2.py",
             "index_audit": HERE / "audit_index.py",
             "compiler_version": HERE / "compiler_version.txt",
             "field_source": HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp",
             "support": SUPPORT,
             "v1_protocol": HERE / "protocol.json", "v1_result": HERE / "result.json",
             "v1_index": HERE / "index.bin",
             "old_index": OLD / "index.bin", "old_query_binary": OLD / "stream",
             "old_query_protocol": OLD / "query_protocol_v2.json",
             "old_positive": OLD / "positive_v2.json",
             "old_negative": OLD / "trace_zero_control_v2.json"}
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths.items()}
    assert not (HERE / "result_v2.json").exists()
    prepare = run_command([str(HERE / "prepare_rotated"), str(SUPPORT),
                           str(HERE / "index_rotated.bin"), str(HERE / "setup_rotated.json"),
                           "1", "64", str(protocol["prepare_cap_seconds"]),
                           str(protocol["rss_cap_bytes"])],
                          protocol["parent_cap_seconds"], "prepare_rotated")
    if prepare["exit_code"] != 0 or not (HERE / "setup_rotated.json").exists():
        save(HERE / "result_v2.json", {"status": "PRODUCER_FAILURE", "prepare": prepare,
             "protocol_sha256": sha(HERE / "protocol_v2.json")})
        raise RuntimeError("rotated group-batch producer failed")
    setup = json.loads((HERE / "setup_rotated.json").read_text())
    assert setup["status"] == "COMPLETE_ROTATED_GROUP_BATCH_PREPARE"
    assert setup["setup_ns"] < protocol["prepare_cap_seconds"]*10**9
    assert setup["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert sha(HERE / "index_rotated.bin") == sha(HERE / "index.bin")
    queries = {}
    for name, target in protocol["query_cases"].items():
        path = HERE / f"{name}_rotated.json"
        row = run_command([str(OLD / "stream"), "query", str(HERE / "index_rotated.bin"),
                           str(SUPPORT), str(target), str(path),
                           str(protocol["query_cap_seconds_per_case"]),
                           str(protocol["rss_cap_bytes"])],
                          protocol["query_cap_seconds_per_case"]+10,
                          f"{name}_rotated")
        if row["exit_code"] != 0 or not path.exists():
            save(HERE / "result_v2.json", {"status": "QUERY_FAILURE", "prepare": prepare,
                 "queries": queries, "failed_query": row,
                 "protocol_sha256": sha(HERE / "protocol_v2.json")})
            raise RuntimeError("unchanged query reader failed")
        actual = json.loads(path.read_text())
        old = json.loads((OLD / ("positive_v2.json" if name == "positive" else
                                  "trace_zero_control_v2.json")).read_text())
        assert actual["status"] == old["status"] == "COMPLETE_PACKED_SEED_QUERY"
        assert actual["hits"] == old["hits"]
        row.update({"query_ns": actual["query_ns"], "hits": len(actual["hits"]),
                    "output_sha256": sha(path)})
        queries[name] = row
    save(HERE / "result_v2.json", {"status": "PASS_ROTATED_GROUP_BATCH_PREPARE_AND_QUERIES",
         "candidate_id": None, "curve_id": protocol["curve_id"],
         "setup": setup, "prepare": prepare, "queries": queries,
         "index_sha256": sha(HERE / "index_rotated.bin"),
         "protocol_sha256": sha(HERE / "protocol_v2.json")})
    print(json.dumps({"status": "PASS_ROTATED_GROUP_BATCH_PREPARE_AND_QUERIES",
                      "setup_seconds": setup["setup_ns"]/1e9,
                      "queries": {name: row["query_ns"]/1e9 for name, row in queries.items()}}))


if __name__ == "__main__":
    main()
