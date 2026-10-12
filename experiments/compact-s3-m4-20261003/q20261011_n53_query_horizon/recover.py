#!/usr/bin/env python3
"""Recover Q1456 receipt from preserved native output after SSD ENOSPC."""
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
    out = HERE / "native_measurement.json"
    assert not out.exists()
    freeze = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    raw_file = HERE / "native_raw.json"
    raw = json.loads(raw_file.read_text())
    exported = json.loads((PRIOR / "export_receipt.json").read_text())
    prior = json.loads((FULL / "native_measurement.json").read_text())
    assert raw["status"] == "completed_query_cap"
    assert raw["query_samples_processed"] == freeze["query_count"] == 5000000
    assert raw["table_states_generated"] == protocol["point_decomposition"]["table_states"]
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert freeze["native_source_sha256"] == sha(HERE / "native_sweep.cpp")
    assert freeze["field_source_sha256"] == sha(PRIOR / "native_field53.hpp")
    assert freeze["q1455_measurement_sha256"] == sha(FULL / "native_measurement.json")
    assert freeze["q1454_export_receipt_sha256"] == sha(PRIOR / "export_receipt.json")
    assert exported["target_x_hex"] == freeze["public_target"][0]
    assert exported["target_y_hex"] == freeze["public_target"][1]
    assert raw["table_distinct_keys"] == prior["table_distinct_keys"]
    assert raw["peak_rss_bytes"] <= protocol["limits"]["peak_rss_mib"] * 1048576
    raw.update({"proposal_id": "Q1456", "candidate_id": None, "run_id": None,
                "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
                "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
                "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
                "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
                "freeze_sha256": sha(HERE / "freeze.json"),
                "build_receipt_sha256": sha(HERE / "build_receipt.json"),
                "raw_sha256": sha(raw_file),
                "recovery_source_sha256": sha(Path(__file__)),
                "receipt_write_status": "recovered_from_native_raw_after_enospc",
                "launcher_wall_ns": None,
                "charged_pair_add_attempts": raw["table_states_generated"] +
                    2*raw["query_samples_processed"] - raw["query_skipped_identity_pairs"],
                "complete_solve_work_log2": None,
                "degree131_challenge_gap_bits": None})
    out.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")
    print("RECOVERED", raw["query_samples_processed"], len(raw["matches"]))


if __name__ == "__main__":
    main()
