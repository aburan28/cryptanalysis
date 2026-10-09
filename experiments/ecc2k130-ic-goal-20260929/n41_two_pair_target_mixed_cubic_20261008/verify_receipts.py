#!/usr/bin/env python3
"""Check frozen source/data hashes and independent rank receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def check_arm(stem: str, feature_count: int) -> dict:
    suffix = "_y" if stem == "y" else ""
    protocol_file = HERE / f"protocol{suffix}.json"
    result_file = HERE / f"result{suffix}.json"
    audit_file = HERE / f"audit{suffix}.json"
    protocol = json.loads(protocol_file.read_text())
    result = json.loads(result_file.read_text())
    audit = json.loads(audit_file.read_text())
    assert protocol["feature_count"] == result["feature_count"] == audit["feature_count"] == feature_count
    assert result["status"] == "FULL_RANK" and audit["status"] == "PASS_FULL_RANK"
    assert result["rank"] == audit["independent_rank"] == feature_count
    assert len(result["pivotal_row_indices"]) == audit["witness_rows_replayed"] == feature_count
    assert result["source_sha256"]["protocol"] == sha(protocol_file)
    producer_name = "screen_y" if suffix else "screen"
    auditor_name = "audit_y" if suffix else "audit"
    assert result["source_sha256"][producer_name] == sha(HERE / f"{producer_name}.py")
    assert audit["source_sha256"][auditor_name] == sha(HERE / f"{auditor_name}.py")
    result_key = "screen_y_result" if suffix else "screen_result"
    assert audit["source_sha256"][result_key] == sha(result_file)
    assert audit["source_sha256"]["prior_rows"] == protocol["input_rows_sha256"]
    assert audit["source_sha256"]["prior_sage_audit"] == protocol["input_sage_audit_sha256"]
    return {
        "status": "PASS_FULL_RANK",
        "feature_count": feature_count,
        "rank": feature_count,
        "source_sha256": {
            "protocol": sha(protocol_file),
            "producer": sha(HERE / f"{producer_name}.py"),
            "auditor": sha(HERE / f"{auditor_name}.py"),
            "result": sha(result_file),
            "audit": sha(audit_file),
        },
    }


def main() -> None:
    output = HERE / "verification.json"
    if output.exists():
        raise FileExistsError("preserve first receipt verification")
    x = check_arm("x", 2819)
    y = check_arm("y", 2908)
    prior = read("protocol.json")
    rows_path = (HERE / prior["input_rows"]).resolve()
    prior_audit_path = (HERE / prior["input_sage_audit"]).resolve()
    assert sha(rows_path) == prior["input_rows_sha256"]
    assert sha(prior_audit_path) == prior["input_sage_audit_sha256"]
    report = {
        "kind": "n41_two_pair_target_mixed_cubic_receipt_verification",
        "status": "PASS",
        "x": x,
        "y": y,
        "shared_dependency_sha256": {
            "screen_py_used_by_y": sha(HERE / "screen.py"),
            "audit_py_used_by_y": sha(HERE / "audit.py"),
            "prior_rows": sha(rows_path),
            "prior_sage_audit": sha(prior_audit_path),
        },
        "verifier_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": "PASS", "x_rank": x["rank"], "y_rank": y["rank"]}))


if __name__ == "__main__":
    main()
