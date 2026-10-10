#!/usr/bin/env python3
"""Check frozen sources, exact prefix panel, and independent Sage replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_polynomial_pair_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    protocol = load(HERE / "protocol.json")
    assert protocol["status"] == "FROZEN_HIGH_PREFIX"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    result = load(HERE / "result.json")
    assert result["status"] == "COMPLETE_HIGH_PREFIX_PANEL"
    assert result["curve_id"] == protocol["curve_id"]
    assert result["panel"] == protocol["free_low_bit_widths"]
    assert result["sha256"]["source"] == sha(HERE / "run.py")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["prefix"] == sha(HERE / "prefix.py")
    assert result["sha256"]["inputs"] == sha(SOURCE / "inputs.json")
    assert result["total_wall_ns"] < protocol["wall_cap_seconds"]*10**9
    assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["total_wall_ns"] >= result["setup_ns"] + result["query_panel_ns"]
    assert len(result["rows"]) == 64*len(result["panel"])
    assert len(result["full_output_comparisons"]) == 64
    for b in result["panel"]:
        rows = [row for row in result["rows"] if row["free_low_bits"] == b]
        assert len(rows) == 64
        assert len([row for row in rows if row["kind"] == "positive"]) == 32
        assert len([row for row in rows if row["kind"] == "uniform_field"]) == 32
        mask = result["invariant_masks"][str(b)]
        for row in rows:
            assert row["invariant_rows"] == bin(mask).count("1")
            assert row["nullity"] == 41-row["projected_rank"]
            assert row["coefficient_vectors_tested"] <= 256
            assert row["fixed_sum_calls"] <= row["coefficient_vectors_tested"]
            assert row["status"] in ("INCONSISTENT_HIGH", "RANK_FALLBACK",
                                     "COMPLETE_NO_PAIR", "COMPLETE_PAIRS")
            if row["status"] in ("INCONSISTENT_HIGH", "RANK_FALLBACK"):
                assert not row["pairs"]
            if row["status"] == "RANK_FALLBACK":
                assert row["nullity"] > protocol["max_projected_nullity"]
            elif row["status"] in ("COMPLETE_PAIRS", "COMPLETE_NO_PAIR"):
                assert row["coefficient_vectors_tested"] == 1 << row["nullity"]
            if row["kind"] == "positive" and row["status"] != "RANK_FALLBACK":
                assert row["expected_pair"] in row["pairs"]
        if b <= 35:
            assert all(row["status"] != "RANK_FALLBACK" for row in rows)
            assert all(row["pairs"] for row in rows if row["kind"] == "positive")
            assert all(not row["pairs"] for row in rows if row["kind"] == "uniform_field")
    at35 = [row for row in result["rows"] if row["free_low_bits"] == 35]
    assert len([row for row in at35 if row["kind"] == "positive" and
                row["expected_pair"] in row["pairs"]]) == 32
    assert len([row for row in at35 if row["kind"] == "uniform_field" and
                row["pairs"]]) == 0
    audit = load(HERE / "sage_audit.json")
    assert audit["status"] == "PASS_SAGE_HIGH_PREFIX_AUDIT"
    assert audit["invariant_masks_recomputed"] == len(result["panel"])
    assert audit["positive_raw_groups_replayed"] == 32
    assert audit["sha256"]["source"] == sha(HERE / "sage_audit.py")
    assert audit["sha256"]["runtime"] == sha(HERE / "sage_runtime_info.json")
    assert audit["sha256"]["result"] == sha(HERE / "result.json")
    assert audit["sha256"]["inputs"] == sha(SOURCE / "inputs.json")
    assert (HERE / "run_stderr.txt").stat().st_size == 0
    assert (HERE / "audit_stderr.txt").stat().st_size == 0
    print("PASS_W14_HIGH_PREFIX_INVERSE")


if __name__ == "__main__":
    main()
