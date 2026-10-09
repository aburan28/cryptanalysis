#!/usr/bin/env python3
"""Read-only verification of frozen corrected rank and independent audit receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first receipt verification")
    first_protocol = load("protocol.json")
    first = load("result.json")
    protocol = load("protocol_v2.json")
    result = load("result_v2.json")
    audit_protocol = load("audit_protocol_v2.json")
    audit = load("sage_audit_v2.json")
    assert first["status"] == "FULL_MIXED_CUBIC_RANK"
    assert first["rank"] == first_protocol["feature_count"] == 13599
    assert first["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert first["source_sha256"]["screen"] == sha(HERE / "screen.py")
    assert result["status"] == "FULL_DISTINCT_COLUMN_MIXED_CUBIC_RANK"
    assert result["error"] is None
    assert result["rank"] == protocol["feature_count"] == 13599
    assert result["coordinate_rank"] == result["coordinate_feature_count"] == 821
    assert result["mixed_excess_nullity"] == 0
    assert result["counts"] == {
        "source_rows_seen": 14702,
        "source_column_rejects": 1056,
        "source_rows_accepted": 13646,
        "extra_draws": 0,
        "extra_duplicate_draws": 0,
        "extra_column_rejects": 0,
        "extra_rows_accepted": 0,
    }
    assert result["counts"]["source_rows_seen"] == (
        result["counts"]["source_column_rejects"] +
        result["counts"]["source_rows_accepted"])
    assert result["peak_rss_bytes"] < protocol["limits"]["rss_bytes"]
    assert result["exploratory_wall_ns"] < protocol["limits"]["wall_seconds"] * 10**9
    assert result["source_sha256"]["protocol"] == sha(HERE / "protocol_v2.json")
    assert result["source_sha256"]["screen_v2"] == sha(HERE / "screen_v2.py")
    assert result["source_sha256"]["screen_v1"] == sha(HERE / "screen.py")
    assert protocol["input_sha256"]["result_v1"] == sha(HERE / "result.json")
    for name, path in protocol["inputs"].items():
        assert protocol["input_sha256"][name] == sha(Path(path))
    assert audit["status"] == "PASS_FULL_EXACT_RANK_WITNESS"
    assert audit["transposed_low_pivot_rank"] == result["rank"]
    assert audit["feature_count"] == result["feature_count"]
    assert audit["exact_group_sums_replayed"] == result["counts"]["source_rows_accepted"]
    assert audit["source_column_rejects"] == result["counts"]["source_column_rejects"]
    assert audit["source_subgroup_points_checked"] == 128
    assert audit["accepted_row_index_sha256"] == result["valid_index_pairs_sha256"]
    assert audit["input_sha256"]["audit_protocol"] == sha(HERE / "audit_protocol_v2.json")
    assert audit["input_sha256"]["audit_source"] == sha(HERE / "sage_audit_v2.py")
    assert audit_protocol["audit_source_sha256"] == sha(HERE / "sage_audit_v2.py")
    for name, path in audit_protocol["inputs"].items():
        assert audit_protocol["input_sha256"][name] == sha(Path(path))
    report = {
        "kind": "n41_distinct_column_mixed_cubic_receipt_verification_v2",
        "status": "PASS",
        "curve_id": result["curve_id"],
        "rank": result["rank"],
        "valid_rows": result["counts"]["source_rows_accepted"],
        "independent_sage_status": audit["status"],
        "v1_scope": "unrestricted cross-pair columns",
        "v2_scope": "four distinct folded columns",
        "source_sha256": {"protocol_v2": sha(HERE / "protocol_v2.json"),
                          "result_v2": sha(HERE / "result_v2.json"),
                          "sage_audit_v2": sha(HERE / "sage_audit_v2.json"),
                          "verify": sha(Path(__file__))},
    }
    with OUTPUT.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "rank": report["rank"],
                      "valid_rows": report["valid_rows"]}, sort_keys=True))


if __name__ == "__main__":
    main()
