#!/usr/bin/env python3
"""Freeze the rotated-source preparation before its 64-seed run."""

import hashlib
import json
from pathlib import Path

from freeze import HERE, OLD, SUPPORT, NATIVE, sha


def main():
    protocol = HERE / "protocol_v2.json"
    assert not protocol.exists()
    v1 = json.loads((HERE / "result.json").read_text())
    assert v1["status"] == "PASS_GROUP_BATCH_PREPARE_AND_QUERIES"
    paths = {"rotated_source": HERE / "prepare_rotated.cpp",
             "rotated_binary": HERE / "prepare_rotated",
             "freezer": HERE / "freeze_v2.py", "runner": HERE / "run_v2.py",
             "index_audit": HERE / "audit_index.py",
             "compiler_version": HERE / "compiler_version.txt",
             "field_source": NATIVE, "support": SUPPORT,
             "v1_protocol": HERE / "protocol.json", "v1_result": HERE / "result.json",
             "v1_index": HERE / "index.bin",
             "old_index": OLD / "index.bin", "old_query_binary": OLD / "stream",
             "old_query_protocol": OLD / "query_protocol_v2.json",
             "old_positive": OLD / "positive_v2.json",
             "old_negative": OLD / "trace_zero_control_v2.json"}
    record = {"status": "FROZEN_ROTATED_GROUP_BATCH_PREPARE_64_SEEDS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b", "candidate_id": None,
              "seed_first": 1, "seed_last": 64, "workers": 1,
              "prepare_cap_seconds": 120, "parent_cap_seconds": 130,
              "query_cap_seconds_per_case": 30, "rss_cap_bytes": 4*1024**3,
              "query_cases": json.loads((OLD / "query_protocol_v2.json").read_text())["target_z"],
              "source_sha256": {name: sha(path) for name, path in paths.items()}}
    with protocol.open("x") as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": record["status"], "sources": len(paths)}))


if __name__ == "__main__":
    main()
