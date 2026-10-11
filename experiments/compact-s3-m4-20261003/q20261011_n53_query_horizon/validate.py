#!/usr/bin/env python3
"""Validate Q1456 source, input, measurement, replay, and accounting links."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "q20261011_n53_native_pair"
FULL = HERE.parent / "q20261011_n53_native_full"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    freeze = json.loads((HERE / "freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    query_audit = json.loads((HERE / "query_prefix_audit.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    earlier = json.loads((FULL / "native_measurement.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["native_source_sha256"] == sha(HERE / "native_sweep.cpp")
    assert freeze["field_source_sha256"] == sha(PRIOR / "native_field53.hpp")
    assert freeze["run_source_sha256"] == sha(HERE / "run.py")
    assert freeze["q1454_export_receipt_sha256"] == sha(PRIOR / "export_receipt.json")
    assert freeze["q1455_measurement_sha256"] == sha(FULL / "native_measurement.json")
    assert build["freeze_sha256"] == measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert measured["raw_sha256"] == sha(HERE / "native_raw.json")
    assert measured["recovery_source_sha256"] == sha(HERE / "recover.py")
    assert replay["measurement_sha256"] == analysis["measurement_sha256"] == sha(HERE / "native_measurement.json")
    assert analysis["independent_replay_sha256"] == sha(HERE / "independent_replay.json")
    assert analysis["query_prefix_audit_sha256"] == sha(HERE / "query_prefix_audit.json")
    assert query_audit["source_sha256"] == sha(HERE / "audit_queries.py")
    assert query_audit["query_sha256"] == freeze["query_file_sha256"]
    assert query_audit["identity_pair_prefix_counts"]["5000000"] == measured["query_skipped_identity_pairs"]
    assert measured["status"] == "completed_query_cap" and replay["status"] == "PASS"
    assert measured["query_samples_processed"] == freeze["query_count"] == 5000000
    assert measured["table_states_generated"] == protocol["point_decomposition"]["table_states"]
    assert measured["charged_pair_add_attempts"] == (
        measured["table_states_generated"] + 2*measured["query_samples_processed"]
        - measured["query_skipped_identity_pairs"])
    assert [match for match in measured["matches"] if match[0] <= 1500000] == earlier["matches"]
    assert replay["cap_results"]["1500000"]["augmented_rank"] == 21
    assert analysis["query_horizons"][-1]["augmented_rank"] == replay["cap_results"]["5000000"]["augmented_rank"]
    assert analysis["best_measured_query_cap_for_pair_adds_per_rank_row"] in protocol["point_decomposition"]["query_caps"]
    assert all(record["candidate_id"] is None and record["run_id"] is None
               for record in (protocol, measured, replay, analysis))
    assert all(record["complete_solve_work_log2"] is None
               for record in (protocol, measured, analysis))
    print("PASS Q1456", measured["query_samples_processed"],
          replay["cap_results"]["5000000"]["augmented_rank"])


if __name__ == "__main__":
    main()
