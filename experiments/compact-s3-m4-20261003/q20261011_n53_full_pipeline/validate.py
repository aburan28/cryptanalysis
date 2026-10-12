#!/usr/bin/env python3
"""Validate Q1457 frozen setup, native receipt, and independent log replay."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent / "q20261011_n53_native_pair"
HORIZON = HERE.parent / "q20261011_n53_query_horizon"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["prepare_source_sha256"] == sha(HERE / "prepare.py")
    assert freeze["native_source_sha256"] == sha(HERE / "native_sweep.cpp")
    assert freeze["field_source_sha256"] == sha(PAIR / "native_field53.hpp")
    assert freeze["q1456_freeze_sha256"] == sha(HORIZON / "freeze.json")
    assert build["freeze_sha256"] == measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["source_sha256"] == sha(HERE / "native_sweep.cpp")
    assert measured["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert measured["raw_sha256"] == sha(HERE / "native_raw.json")
    assert replay["measurement_sha256"] == sha(HERE / "native_measurement.json")
    assert replay["source_sha256"] == sha(HERE / "verify.py")
    assert measured["status"] == "completed_query_cap" and replay["status"] == "PASS"
    assert measured["query_samples_processed"] == freeze["query_count"] == 30000000
    assert measured["table_states_generated"] == protocol["point_decomposition"]["table_states"]
    assert measured["charged_pair_add_attempts"] == (
        measured["table_states_generated"]+2*measured["query_samples_processed"]
        -measured["query_skipped_identity_pairs"])
    assert replay["verified_relation_occurrences"] == len(measured["matches"])
    assert replay["matrix_rank"] <= protocol["factor_base_folded_columns_K"]
    ranks = [replay["rank_checkpoints"][str(checkpoint)]["rank"]
             for checkpoint in protocol["point_decomposition"]["query_checkpoints"]]
    assert ranks == sorted(ranks) and ranks[-1] == replay["matrix_rank"]
    if replay["factor_base_log_status"] == "solved_and_replayed":
        assert replay["matrix_rank"] == protocol["relation_linear_algebra"]["rank_goal"]
        assert replay["replayed_log_columns"] == len(replay["factor_base_logs"]) == replay["matrix_rank"]
    else:
        assert replay["factor_base_log_status"] == "rank_incomplete"
        assert replay["factor_base_logs"] is None and replay["replayed_log_columns"] == 0
    assert all(record["candidate_id"] is None and record["run_id"] is None
               for record in (protocol,freeze,measured,replay))
    assert protocol["isogeny"] == freeze["isogeny"] == measured["isogeny"] == replay["isogeny"] == "none"
    print("PASS Q1457",replay["matrix_rank"],"/",protocol["factor_base_folded_columns_K"])


if __name__=="__main__":main()
