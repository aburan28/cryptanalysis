#!/usr/bin/env python3
"""Replay archived formulas and verify the bounded-query receipt."""

import gzip
import hashlib
import json
from pathlib import Path

import prepare

HERE = Path(__file__).resolve().parent
profile = prepare.load("n131_diagonal_sparse_profile_for_terminal_audit", HERE / "profile.py")
query = prepare.load("n131_diagonal_sparse_query_for_terminal_audit", HERE / "query.py")


def decompressed_sha(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def main():
    control = json.loads((HERE / "control.json").read_text())
    construction = json.loads((HERE / "profile.json").read_text())
    replay = json.loads((HERE / "sage_audit.json").read_text())
    protocol = json.loads((HERE / "query_protocol_v2.json").read_text())
    result_dir = HERE / "public_query_v2"
    result = json.loads((result_dir / "result.json").read_text())
    assert construction["status"] == "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
    assert replay["status"] == "PASS_INDEPENDENT_SAGE_N131_DIAGONAL_GROUP_REPLAY"
    assert protocol["status"] == "FROZEN_BEFORE_UNPINNED_PUBLISHED_QUERY_V2"
    assert protocol["source_sha256"] == {name: prepare.sha(path)
                                           for name, path in query.sources().items()}
    assert protocol["preserved_failure_sha256"] == prepare.sha(HERE / "public_query/failure_v1.json")
    assert result["sha256"]["protocol"] == prepare.sha(HERE / "query_protocol_v2.json")
    assert construction["formula"]["uncompressed_sha256"] == decompressed_sha(HERE / "constructed.xcnf.gz")
    assert result["formula"]["sha256"] == decompressed_sha(result_dir / "system.xcnf.gz")
    _, _, _, _, curve, _, _ = prepare.old.source()
    assert query.public_target(curve) == tuple(result["target_q"])
    assert result["target_q"] == protocol["target_q"]
    assert result["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == "SOLVER_WALL_CAP"
    assert not result["solver_status_lines"] and result["model_lines"] == 0
    assert 0 < result["phase_seconds"]["query_wall"] <= protocol["online_wall_cap_seconds"] + 1
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    stdout = result_dir / "solver.stdout.txt"
    stderr = result_dir / "solver.stderr.txt"
    assert result["sha256"]["stdout"] == prepare.sha(stdout)
    assert result["sha256"]["stderr"] == prepare.sha(stderr)
    assert stderr.stat().st_size == 0
    log = stdout.read_text()
    assert "c rst " in log and "s SATISFIABLE" not in log and "s UNSATISFIABLE" not in log
    assert result["verified_relations"] == result["useful_rank"] == 0
    record = {"status": "PASS_FROZEN_ARTIFACT_AND_CAPPED_SEARCH_AUDIT",
              "curve_id": protocol["curve_id"],
              "constructed_target_q": control["target_q"],
              "published_target_q": result["target_q"],
              "constructed_formula_sha256": construction["formula"]["uncompressed_sha256"],
              "published_formula_sha256": result["formula"]["sha256"],
              "solver_active_search": True,
              "published_query_status": result["status"],
              "source_sha256": {"script": prepare.sha(__file__),
                                "query_protocol": prepare.sha(HERE / "query_protocol_v2.json"),
                                "query_result": prepare.sha(result_dir / "result.json"),
                                "sage_audit": prepare.sha(HERE / "sage_audit.json")}}
    prepare.save(HERE / "terminal_audit.json", record)
    print(json.dumps({"status": record["status"],
                      "published_query_status": result["status"]}))


if __name__ == "__main__":
    main()
