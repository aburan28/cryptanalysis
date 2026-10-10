#!/usr/bin/env python3
"""Bounded parent for the frozen native index and unchanged stream reader."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from freeze import HERE, OLD, SUPPORT, sha, sources


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def run_command(command, limit, label):
    started = time.monotonic_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=limit, check=False)
        code, stdout, stderr, stopped = (completed.returncode, completed.stdout,
                                         completed.stderr, False)
    except subprocess.TimeoutExpired as error:
        code = None
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        stopped = True
    elapsed = time.monotonic_ns()-started
    (HERE / f"{label}.stdout.txt").write_text(stdout)
    (HERE / f"{label}.stderr.txt").write_text(stderr)
    return {"command": command, "exit_code": code, "parent_timeout": stopped,
            "parent_wall_ns": elapsed,
            "stdout_sha256": sha(HERE / f"{label}.stdout.txt"),
            "stderr_sha256": sha(HERE / f"{label}.stderr.txt")}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_GROUP_BATCH_PREPARE_64_SEEDS"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert not (HERE / "result.json").exists()
    prepare = run_command([str(HERE / "prepare"), str(SUPPORT),
                           str(HERE / "index.bin"), str(HERE / "setup.json"),
                           "1", "64", str(protocol["prepare_cap_seconds"]),
                           str(protocol["rss_cap_bytes"])],
                          protocol["parent_cap_seconds"], "prepare")
    if prepare["exit_code"] != 0 or not (HERE / "setup.json").exists():
        save(HERE / "result.json", {"status": "PRODUCER_FAILURE", "prepare": prepare,
             "protocol_sha256": sha(HERE / "protocol.json")})
        raise RuntimeError("native group-batch preparation failed")
    setup = json.loads((HERE / "setup.json").read_text())
    assert setup["status"] == "COMPLETE_GROUP_BATCH_PREPARE"
    assert setup["setup_ns"] < protocol["prepare_cap_seconds"]*10**9
    assert setup["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    queries = {}
    for name, target in protocol["query_cases"].items():
        path = HERE / f"{name}.json"
        row = run_command([str(OLD / "stream"), "query", str(HERE / "index.bin"),
                           str(SUPPORT), str(target), str(path),
                           str(protocol["query_cap_seconds_per_case"]),
                           str(protocol["rss_cap_bytes"])],
                          protocol["query_cap_seconds_per_case"]+10, name)
        if row["exit_code"] != 0 or not path.exists():
            save(HERE / "result.json", {"status": "QUERY_FAILURE", "prepare": prepare,
                 "queries": queries, "failed_query": row,
                 "protocol_sha256": sha(HERE / "protocol.json")})
            raise RuntimeError("unchanged query reader failed")
        actual = json.loads(path.read_text())
        old_path = OLD / ("positive_v2.json" if name == "positive" else
                          "trace_zero_control_v2.json")
        old = json.loads(old_path.read_text())
        assert actual["status"] == old["status"] == "COMPLETE_PACKED_SEED_QUERY"
        assert actual["hits"] == old["hits"]
        assert actual["left_entries_checked"] == old["left_entries_checked"]
        row.update({"query_ns": actual["query_ns"], "hits": len(actual["hits"]),
                    "output_sha256": sha(path)})
        queries[name] = row
    save(HERE / "result.json", {"status": "PASS_GROUP_BATCH_PREPARE_AND_QUERIES",
         "candidate_id": None, "curve_id": protocol["curve_id"],
         "setup": setup, "prepare": prepare, "queries": queries,
         "index_sha256": sha(HERE / "index.bin"),
         "protocol_sha256": sha(HERE / "protocol.json")})
    print(json.dumps({"status": "PASS_GROUP_BATCH_PREPARE_AND_QUERIES",
                      "setup_seconds": setup["setup_ns"]/1e9,
                      "queries": {name: row["query_ns"]/1e9 for name, row in queries.items()}}))


if __name__ == "__main__":
    main()
