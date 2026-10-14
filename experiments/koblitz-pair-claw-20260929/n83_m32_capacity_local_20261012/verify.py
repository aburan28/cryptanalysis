#!/usr/bin/env python3
"""Verify the source-bound M32 capacity receipt, including bounded failures."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent
ROOT = PAIR.parents[1]
TERMINAL = {"completed", "rss_watchdog_cap_reached", "timeout",
            "rss_monitor_failure", "native_failure", "build_failure"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    parent_path = (HERE / protocol["parent_protocol"]).resolve()
    assert sha(parent_path) == protocol["parent_protocol_sha256"]
    parent = json.loads(parent_path.read_text())
    assert parent["workload_id"] == protocol["workload_id"]
    assert parent["factor_base_orbits_K"] == protocol["K"]
    assert parent["target_public_point_onb_raw"] == protocol[
        "public_target_onb_raw"]
    key_path = PAIR / "n83_base_size_search_20261012/minimal_base_keys_and_logs.bin"
    assert sha(key_path) == protocol["base_file_sha256"]
    record = json.loads((HERE / "run_record.json").read_text())
    assert record["status"] in TERMINAL, record["status"]
    assert record["protocol_sha256"] == sha(protocol_path)
    assert record["parent_protocol_sha256"] == sha(parent_path)
    assert record["base_file_sha256"] == sha(key_path)
    assert record["driver_sha256"] == sha(HERE / "run.py")
    for relative, digest in record["source_sha256"].items():
        assert sha(ROOT / relative) == digest
    assert record["workload_id"] == protocol["workload_id"]
    assert record["rss_cap_bytes"] == protocol["rss_cap_bytes"]
    assert record["rss_sample_interval_ms"] == protocol[
        "rss_watchdog_sample_ms"]
    assert record["timeout_seconds"] == protocol["timeout_seconds"]
    if record["status"] == "build_failure":
        assert record["build_returncode"] != 0
        print("PASS: source-bound terminal build failure")
        return
    assert record["build_returncode"] == 0
    assert record["native_stdout_sha256"] == sha(HERE / "native.stdout.txt")
    assert record["native_stderr_sha256"] == sha(HERE / "native.stderr.txt")
    assert math.gcd(protocol["table_step"], 83 * protocol["K"] * (
        protocol["K"] - 1)) == 1
    max_sampled = record["max_sampled_rss_bytes"]
    assert 0 < max_sampled
    if record["status"] == "completed":
        result_path = HERE / "native_result.json"
        result = json.loads(result_path.read_text())
        assert record["native_returncode"] == 0
        assert record["native_wall_seconds"] <= protocol["timeout_seconds"]
        assert max_sampled < protocol["rss_cap_bytes"]
        assert record["native_result_sha256"] == sha(result_path)
        assert result["actual_B"] == protocol["B"]
        assert result["table_descriptors"] == protocol["M"]
        assert result["query_representatives"] == protocol["Q"]
        assert result["bloom_bits_per_key"] == protocol["bits_per_key"]
        assert result["bloom_hashes"] == protocol["hashes"]
        assert result["bloom_bytes"] == 8053129216
        assert result["peak_rss_bytes"] <= protocol["rss_cap_bytes"]
        assert result["bloom_positive_queries"] == (
            result["false_positive_queries"] + result["exact_hit_queries"])
        assert result["exact_hit_queries"] == len(result["hits"])
    else:
        assert record["native_returncode"] != 0
        assert record["status"] != "rss_watchdog_cap_reached" or (
            max_sampled >= protocol["rss_cap_bytes"])
    print(f"PASS: {record['status']}, max sampled RSS {max_sampled}")


if __name__ == "__main__":
    main()
