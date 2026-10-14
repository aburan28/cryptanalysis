#!/usr/bin/env python3
"""Check frozen identities and the full-base canonical x receipt."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101248"
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert protocol["run_order"] == ["reference", "cycle_table"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(ROOT / protocol["key_file"]) == protocol["key_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(ROOT / "experiments/n83-geometric-width15-16-20261012/frontier.json") == protocol[
        "parent_frontier_sha256"]
    assert sha(ROOT / "experiments/n83-geometric-width15-16-20261012/independent_sage_replay.json") == protocol[
        "parent_sage_replay_sha256"]
    record = json.loads((HERE / "result.json").read_text())
    assert record["kind"] == "n83_full_base_canonical_x_lookup_result"
    assert record["status"] == "PASS"
    assert record["curve_id"] == protocol["curve_id"]
    assert record["K"] == record["checked_keys"] == protocol["K"]
    assert record["first_mismatch_index"] is None
    assert record["distinct_x_count"] == protocol["K"]
    assert record["B"] == protocol["B"]
    assert record["run_order"] == protocol["run_order"]
    assert record["protocol_sha256"] == sha(protocol_path)
    assert record["key_sha256"] == protocol["key_sha256"]
    assert record["reference_digest_sha256"] == record[
        "cycle_table_digest_sha256"]
    assert record["reference_ns_exploratory"] > 0
    assert record["cycle_table_ns_exploratory"] > 0
    assert record["timing_tier"] == "exploratory_local_unisolated"
    materialization_path = HERE / "materialization.json"
    if materialization_path.exists():
        materialization = json.loads(materialization_path.read_text())
        assert materialization["status"] == "PASS"
        assert materialization["K"] == protocol["K"]
        assert materialization["B"] == protocol["B"]
        assert materialization["key_sha256"] == protocol["key_sha256"]
        assert materialization["protocol_sha256"] == sha(protocol_path)
        assert materialization["lookup_result_sha256"] == sha(HERE / "result.json")
        assert materialization["source_sha256"]["materialize.py"] == sha(
            HERE / "materialize.py")
        assert materialization["source_sha256"]["fast_x.py"] == sha(
            HERE / "fast_x.py")
        cache = HERE / materialization["canonical_x_file"]
        assert cache.name == "d16_canonical_x.bin"
        assert cache.stat().st_size == 11 * protocol["K"]
        assert materialization["canonical_x_bytes"] == cache.stat().st_size
        assert materialization["canonical_x_sha256"] == sha(cache)
        assert materialization["canonical_x_sha256"] == record[
            "reference_digest_sha256"]
    print(json.dumps({"status": "PASS", "K": record["K"],
                      "equal_digest": True,
                      "reference_seconds": record[
                          "reference_ns_exploratory"] / 1e9,
                      "cycle_table_seconds": record[
                          "cycle_table_ns_exploratory"] / 1e9}))


if __name__ == "__main__":
    main()
