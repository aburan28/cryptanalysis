#!/usr/bin/env python3
"""Freeze Q1455 full quotient-index source, fixtures, point and prior rows."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1454 = PARENT / "q20261011_n53_native_pair"
Q1452 = PARENT / "q20261011_n53_full_pair_orbits_accounted"
FREEZE = HERE / "freeze.json"
SOURCES = [Path(__file__), HERE / "native_sweep.cpp", HERE / "build.py",
           HERE / "run.py", Q1454 / "native_field53.hpp"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_inputs() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    export = json.loads((Q1454 / "export_receipt.json").read_text())
    prior = json.loads((Q1454 / "native_measurement.json").read_text())
    full = json.loads((Q1452 / "measurement.json").read_text())
    assert protocol["curve_id"] == export["curve_id"] == prior["curve_id"] == full["curve_id"]
    assert protocol["workload_id"] == export["workload_id"] == prior["workload_id"] == full["workload_id"]
    assert protocol["isogeny"] == export["isogeny"] == prior["isogeny"] == full["isogeny"] == "none"
    assert protocol["factor_base_actual_B"] == export["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == export["factor_base_folded_columns_K"]
    assert protocol["factor_base_enumerated_set_sha256"] == export[
        "factor_base_enumerated_set_sha256"]
    assert protocol["point_decomposition"]["query_sample_cap"] == prior[
        "query_samples_processed"]
    assert protocol["point_decomposition"]["table_caps"][0] == prior[
        "table_states_generated"]
    assert protocol["point_decomposition"]["table_states"] == full[
        "table_states_generated"]
    for name, record in export["files"].items():
        path = Q1454 / "inputs" / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    return {"protocol_sha256": sha(HERE / "protocol.json"),
            "q1454_export_receipt_sha256": sha(Q1454 / "export_receipt.json"),
            "q1454_measurement_sha256": sha(Q1454 / "native_measurement.json"),
            "q1452_measurement_sha256": sha(Q1452 / "measurement.json"),
            "input_files_sha256": {name: record["sha256"]
                                   for name, record in export["files"].items()},
            "target_x_hex": export["target_x_hex"],
            "target_y_hex": export["target_y_hex"],
            "sources_sha256": {str(path.relative_to(ROOT)): sha(path) for path in SOURCES}}


def main() -> None:
    assert not FREEZE.exists()
    FREEZE.write_text(json.dumps(frozen_inputs(), indent=2, sort_keys=True) + "\n")
    print("FROZEN", FREEZE)


if __name__ == "__main__":
    main()
