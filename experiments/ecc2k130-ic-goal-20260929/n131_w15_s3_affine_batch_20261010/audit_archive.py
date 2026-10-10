#!/usr/bin/env python3
"""Read-only receipt audit for the frozen affine-batch S3 experiment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_fixedseed_s3_join_20261010"
ROOTS = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010/pair_roots.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    reference = json.loads((PRIOR / "sage_query_result.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    hashes = {"source": sha(HERE / "run.py"), "roots": sha(ROOTS),
              "reference": sha(PRIOR / "sage_query_result.json"),
              "runtime": sha(HERE / "sage_runtime_info.json")}
    assert runtime["status"] == "verified"
    assert protocol["status"] == "FROZEN_AFFINE_BATCH_S3_JOIN"
    assert protocol["source_hashes"] == result["source_hashes"] == hashes
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["status"] == "PASS_AFFINE_BATCH_S3_JOIN"
    assert result["domain_sizes"] == reference["domain_sizes"] == [8176, 8340]
    assert len(result["cases"]) == len(reference["cases"]) == 3
    assert result["reusable_setup_ns"] > 0
    assert result["setup_peak_process_rss_bytes"] < protocol["rss_cap_bytes"]
    for current, old in zip(result["cases"], reference["cases"]):
        assert current["name"] == old["name"]
        assert current["target_reciprocal"] == old["target_reciprocal"]
        assert current["status"] == "COMPLETE"
        assert current["left_outputs_checked"] == 8176
        assert current["batch_inversions"] == 1
        assert current["exceptional_linear_outputs"] == 0
        assert current["trace_compatible_outputs"] == 8176
        assert current["algebraic_hit_coordinate_pairs"] == old["algebraic_hit_coordinate_pairs"]
        assert current["query_ns"] < protocol["per_query_cap_ns"]
        assert current["independent_full_domain_replay_ns"] > 0
        assert current["peak_process_rss_bytes"] < protocol["rss_cap_bytes"]
    exceptional, mismatch = result["edge_controls"]
    assert exceptional["name"] == "exceptional_linear"
    assert exceptional["exceptional_linear_outputs"] == 1
    assert exceptional["full_domain_roots_match"]
    assert mismatch["name"] == "trace_mismatch"
    assert mismatch["trace_compatible_outputs"] == 0
    assert mismatch["full_domain_roots_match"]
    print(json.dumps({"status": "PASS_ARCHIVE_AUDIT", "cases": len(result["cases"]),
                      "full_domain_replays": 5,
                      "query_ns": [row["query_ns"] for row in result["cases"]],
                      "source_sha256": hashes["source"]}, sort_keys=True))


if __name__ == "__main__":
    main()
