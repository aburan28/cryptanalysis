#!/usr/bin/env python3
"""Check the frozen target, preserved failed attempt, and completed smoke."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    fixture_path = HERE / "target_fixture.json"
    sage_path = HERE / "independent_sage_target_check.json"
    assert sha(fixture_path) == protocol["target_fixture_sha256"]
    sage = json.loads(sage_path.read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["target_fixture_sha256"] == sha(fixture_path)
    first = json.loads((HERE / "smoke_receipt.json").read_text())
    assert first["status"] == "native_failure" and first["native_returncode"] != 0
    assert "ECC2K83_CANDIDATE_TMPDIR is required" in first["native_stderr"]
    second = json.loads((HERE / "smoke_attempt2_receipt.json").read_text())
    result_path = HERE / "smoke_attempt2_result.json"
    result = json.loads(result_path.read_text())
    assert second["status"] == "completed" and second["native_returncode"] == 0
    assert second["native_result_sha256"] == sha(result_path)
    assert second["protocol_sha256"] == sha(protocol_path)
    assert first["workload_id"] == second["workload_id"] == protocol["workload_id"]
    assert result["actual_B"] == protocol["actual_usable_points_B_before_folding"]
    assert result["table_descriptors"] == 1 << 20
    assert result["query_representatives"] == 1 << 18
    assert result["bloom_bits_per_key"] == protocol["workload"]["bits_per_key"]
    assert result["bloom_hashes"] == protocol["workload"]["hashes"]
    assert result["exact_hit_queries"] == len(result["hits"])
    assert result["bloom_positive_queries"] == (
        result["false_positive_queries"] + result["exact_hit_queries"])
    assert result["peak_rss_bytes"] < protocol["workload"]["memory_cap_bytes"]
    third = json.loads((HERE / "smoke_attempt3_receipt.json").read_text())
    third_result_path = HERE / "smoke_attempt3_result.json"
    third_result = json.loads(third_result_path.read_text())
    assert third["status"] == "completed" and third["native_returncode"] == 0
    assert third["native_result_sha256"] == sha(third_result_path)
    for key in ("actual_B", "table_descriptors", "query_representatives",
                "bloom_bits_per_key", "bloom_hashes", "bloom_positive_queries",
                "false_positive_queries", "exact_hit_queries", "hits"):
        assert third_result[key] == result[key]
    assert math.gcd(protocol["workload"]["table_step"], protocol[
        "pair_rank_domain"]) == 1
    assert protocol["pair_rank_domain"] - protocol["workload"][
        "table_descriptors"] - protocol["workload"][
            "query_representatives_per_wave"] * protocol["workload"][
                "query_wave_count"] == protocol["pair_rank_margin"]
    print("PASS: target, failed attempt, completed smoke, exact capacity")


if __name__ == "__main__":
    main()
