#!/usr/bin/env python3
"""Validate Q1462 input bindings and conditional action accounting."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "analysis.json").read_text())
    assert result["status"] == "CONDITIONAL_MODEL_REPRICED"
    assert result["candidate_id"] is None and result["run_id"] is None
    assert result["isogeny"] == "none"
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["source_sha256"] == sha(HERE / "analyze.py")
    assert result["q1447_measurement_sha256"] == sha(PARENT / "q20261011_weight7_screen/measurement.json")
    assert result["q1457_replay_sha256"] == sha(PARENT / "q20261011_n53_full_pipeline/independent_replay.json")
    assert result["q1461_native_source_sha256"] == sha(PARENT / "q20261011_n53_fresh_target/native_first.cpp")
    assert result["curve_id"] == protocol["curve_id"]
    assert result["conditional_B"] == 2 * 131 * result["conditional_K"]
    assert result["full_table_states"] == 131 * result["conditional_K"]**2
    assert result["unrestricted_optimum_exceeds_full_table_by_bits"] > 10
    rows = result["table_size_search"]
    assert len(rows) == len(protocol["table_size_fractions_of_full"])
    assert [row["table_fraction"] for row in rows] == protocol["table_size_fractions_of_full"]
    assert [row["counted_pair_add_attempts_log2"] for row in rows] == sorted(
        row["counted_pair_add_attempts_log2"] for row in rows)
    assert math.isclose(rows[0]["counted_pair_add_attempts_log2"],
                        result["conditional_full_table_counted_pair_add_attempts_log2"])
    assert math.isclose(result["conditional_gap_above_2pow61_pair_add_bits"],
                        rows[0]["counted_pair_add_attempts_log2"] - 61)
    assert result["complete_solve_work_log2"] is None
    assert result["degree131_complete_solve_challenge_gap_bits"] is None
    print("PASS Q1462", rows[0]["counted_pair_add_attempts_log2"])


if __name__ == "__main__":
    main()
