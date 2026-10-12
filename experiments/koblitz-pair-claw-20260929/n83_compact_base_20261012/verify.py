#!/usr/bin/env python3
"""Verify exact native parity and full orbit expansion audit receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = PAIR / "n83_fresh_m32_k23859_20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    reference_path = PAIR / "n83_fresh_m32_k23859_20261012/smoke_attempt3_result.json"
    reference = json.loads(reference_path.read_text())
    base_path = PAIR / "n83_base_size_search_20261012/minimal_base_keys_and_logs.bin"
    assert sha(base_path) == parent["factor_base_file_sha256"]
    receipts = []
    results = []
    for attempt in (1, 2, 3):
        suffix = "" if attempt == 1 else f"_attempt{attempt}"
        receipt_path = HERE / f"stage_receipt{suffix}.json"
        result_path = HERE / f"candidate_result{suffix}.json"
        receipt = json.loads(receipt_path.read_text())
        result = json.loads(result_path.read_text())
        assert receipt["status"] == "completed"
        assert receipt["native_returncode"] == 0
        assert receipt["parity_status"] == "PASS"
        assert receipt["parent_protocol_sha256"] == sha(parent_path)
        assert receipt["reference_result_sha256"] == sha(reference_path)
        assert receipt["base_file_sha256"] == sha(base_path)
        assert receipt["candidate_result_sha256"] == sha(result_path)
        for field in receipt["parity_fields"]:
            assert result[field] == reference[field], (attempt, field)
        assert result["peak_rss_bytes"] < reference["peak_rss_bytes"]
        receipts.append(receipt)
        results.append(result)
    assert receipts[0]["compact_source_sha256"] == sha(HERE / "compact_base_v1.inc")
    assert receipts[1]["compact_source_sha256"] == sha(HERE / "compact_base_v2.inc")
    assert receipts[2]["compact_source_sha256"] == sha(HERE / "compact_base.inc")
    assert not receipts[0].get("complete_point_audit", False)
    assert not receipts[1].get("complete_point_audit", False)
    assert receipts[2]["complete_point_audit"]
    assert results[2]["actual_B"] == 3960594
    print("PASS: three exact parity cells; complete 3,960,594-point audit")


if __name__ == "__main__":
    main()
