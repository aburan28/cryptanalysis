#!/usr/bin/env python3
"""Validate frozen Q1454 native input, table work, matches and replay."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from export import INPUT_DIR as EXPORTED_INPUT_DIR, frozen_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT_DIR = HERE / "inputs" if (HERE / "inputs").is_dir() else EXPORTED_INPUT_DIR


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    exported = json.loads((HERE / "export_receipt.json").read_text())
    built = json.loads((HERE / "build_receipt.json").read_text())
    measured = json.loads((HERE / "native_measurement.json").read_text())
    replay = json.loads((HERE / "independent_replay.json").read_text())
    control = json.loads((HERE / "native_field_control.json").read_text())
    assert freeze == frozen_inputs()
    assert control["status"] == "PASS"
    assert control["header_sha256"] == built["native_field53_sha256"]
    assert control["field_cases"] == 1000 and control["group_key_cases"] == 208
    assert measured["freeze_sha256"] == exported["freeze_sha256"] == built[
        "freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["export_receipt_sha256"] == sha(HERE / "export_receipt.json")
    assert measured["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert measured["native_binary_sha256"] == built["binary_sha256"]
    assert measured["raw_measurement_sha256"] == sha(HERE / "native_raw.json")
    for name, record in exported["files"].items():
        path = INPUT_DIR / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    assert measured["curve_id"] == replay["curve_id"] == protocol["curve_id"]
    assert measured["workload_id"] == replay["workload_id"] == protocol["workload_id"]
    assert measured["isogeny"] == replay["isogeny"] == "none"
    assert replay["status"] == "PASS"
    assert replay["measurement_sha256"] == sha(HERE / "native_measurement.json")
    assert replay["factor_base_enumerated_set_sha256"] == protocol[
        "factor_base_enumerated_set_sha256"]
    assert measured["table_states_generated"] == (measured["table_distinct_keys"] +
        measured["table_same_key_repeats"] + measured["table_skipped_identity_pairs"])
    assert measured["charged_pair_add_attempts"] == (measured[
        "table_states_generated"] + 2 * measured["query_samples_processed"] -
        measured["query_skipped_identity_pairs"])
    assert measured["query_samples_processed"] <= protocol[
        "point_decomposition"]["query_sample_cap"]
    if measured["status"] == "completed_query_cap":
        assert measured["table_states_generated"] == protocol[
            "point_decomposition"]["table_states"]
        assert measured["query_samples_processed"] == protocol[
            "point_decomposition"]["query_sample_cap"]
    for cap in protocol["point_decomposition"]["table_caps"]:
        if cap > measured["table_states_generated"]:
            continue
        prefix = measured["prefix_table"][str(cap)]
        assert prefix["distinct_keys"] + prefix["same_key_repeats"] + prefix[
            "identity_pairs"] == cap
        assert replay["cap_results"][str(cap)]["candidate_matches"] == measured[
            "cap_query"][str(cap)]["candidate_descriptors"]
        assert replay["cap_results"][str(cap)]["augmented_rank"] <= replay[
            "cap_results"][str(cap)]["distinct_quotient_rows"]
    assert measured["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    assert all(value >= 0 for value in measured["phase_wall_ns"].values())
    print("PASS Q1454", measured["status"], measured["table_states_generated"],
          measured["query_samples_processed"],
          {cap: value["augmented_rank"] for cap, value in replay["cap_results"].items()})


if __name__ == "__main__":
    main()
