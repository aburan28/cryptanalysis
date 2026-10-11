#!/usr/bin/env python3
"""Recompute Q1473 math and custody, excluding fresh audit-wall samples."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import audit as q1473_audit

HERE = Path(__file__).resolve().parent
RESULT = HERE / "audit_result.json"
VERIFICATION = HERE / "verification.json"
TIMING_KEYS = (
    "matrix_build_rank_wall_ns_exploratory",
    "matrix_solve_wall_ns_exploratory",
    "scalar_replay_wall_ns_exploratory",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    archived = json.loads(RESULT.read_text())
    assert protocol["source_sha256"]["experiments/compact-s3-m4-20261003/"
                                     "q1473_n53_rank_collection/audit.py"] == \
           sha(HERE / "audit.py")
    assert archived["auditor_source_sha256"] == sha(HERE / "audit.py")
    assert archived["protocol_sha256"] == sha(HERE / "protocol.json")
    recomputed = q1473_audit.audit()
    for key in TIMING_KEYS:
        measured = archived.pop(key)
        assert measured is None or isinstance(measured, int) and measured > 0
        recomputed.pop(key)
    assert recomputed == archived
    return {
        "kind": "q1473_n53_deterministic_replay_verification",
        "status": "passed", "proposal_id": "Q1473",
        "candidate_id": None, "isogeny": "none",
        "verified_relation_count": archived["status_counts"]["found"],
        "new_novel_rank": archived["new_novel_rank"],
        "combined_rank": archived["combined_rank"],
        "held_out_scalar_recovered": archived[
            "held_out_scalar_recovered"] is not None,
        "fresh_audit_wall_fields_excluded_from_exact_replay": list(TIMING_KEYS),
        "audit_result_sha256": sha(RESULT),
        "receipt_sha256": sha(HERE / "runs/primary/receipt.json"),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "verifier_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = verify()
    if args.emit:
        assert not VERIFICATION.exists(), "refuse overwrite"
        VERIFICATION.write_text(json.dumps(result, sort_keys=True,
                                           indent=2) + "\n")
    else:
        assert result == json.loads(VERIFICATION.read_text())
    print(json.dumps({"status": result["status"],
                      "rank": result["combined_rank"],
                      "held_out_recovered": result[
                          "held_out_scalar_recovered"]}), flush=True)


if __name__ == "__main__":
    main()
