#!/usr/bin/env python3
"""Validate the frozen Q1452 measurement and independent replay receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    measured = json.loads((HERE / "measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    terminal = json.loads((HERE / "exit-status.json").read_text())
    assert terminal["exit_code"] == 0
    assert measured["status"] == "wall_cap"
    assert measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["source_sha256"] == sha(HERE / "run.py")
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    for file, expected in freeze["sources_sha256"].items():
        assert sha(HERE.parents[2] / file) == expected, file
    assert replay["status"] == "PASS"
    assert replay["measurement_sha256"] == sha(HERE / "measurement.json")
    assert replay["verified_relation_occurrences"] == measured[
        "verified_relation_occurrences"]
    assert replay["independent_augmented_rank"] == measured["augmented_rank"]
    assert replay["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert measured["table_states_generated"] == protocol[
        "point_decomposition"]["table_states"]
    assert measured["table_distinct_keys"] + measured[
        "table_same_key_repeats"] + measured[
        "table_skipped_identity_pairs"] == measured["table_states_generated"]
    assert measured["query_samples_processed"] <= protocol[
        "point_decomposition"]["query_sample_cap"]
    assert measured["curve_id"] == protocol["curve_id"] == replay["curve_id"]
    assert measured["workload_id"] == protocol["workload_id"] == replay[
        "workload_id"]
    assert measured["isogeny"] == protocol["isogeny"] == "none"
    assert all(value >= 0 for value in measured["phase_wall_ns"].values())
    total = sum(measured["phase_wall_ns"].values())
    assert total >= protocol["limits"]["external_wall_seconds"] * 1_000_000_000
    assert measured["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    print(f"PASS Q1452 {measured['table_states_generated']} states, "
          f"{measured['query_samples_processed']} queries, "
          f"{measured['augmented_rank']} rank, {total / 1e9:.3f} s")


if __name__ == "__main__":
    main()
