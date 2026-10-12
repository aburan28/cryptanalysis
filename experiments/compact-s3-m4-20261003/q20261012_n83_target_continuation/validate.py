#!/usr/bin/env python3
"""Check the Q1492 finite continuation and independently re-evaluate S3."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import target_continue as continuation

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol, frozen, result = (load(HERE / n) for n in
                                ("protocol.json", "freeze.json", "result.json"))
    assert protocol["proposal_id"] == frozen["proposal_id"] == result[
        "proposal_id"] == "Q1492"
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["source_sha256"] == sha(HERE / "target_continue.py")
    assert sha(continuation.Q1491 / "drive_receipt.json") == frozen[
        "q1491_drive_sha256"]
    assert len(result["rows"]) == len(frozen["pair_receipts"])
    module = continuation.oracle()
    onb = module.CountedOnb(83)
    from chain_s3 import evaluate_s3
    for row in result["rows"]:
        key = f"{row['input']}_phase{row['phase']}"
        assert row["first_pair_receipt_sha256"] == frozen[
            "pair_receipts"][key]
        first = load(continuation.Q1491 / "runs" / key / "receipt.json")
        assert row["first_pair_root_count"] == module.replay_pair(
            onb, first["first_pair_bits"])["root_count"]
        assert row["target_branch_count"] == 4 * row["first_pair_root_count"]
        seen = {(b["root_index"], b["target_preimage_index"])
                for b in row["target_branches"]}
        assert len(seen) == row["target_branch_count"]
        for branch in row["target_branches"]:
            u = onb.fromCoords(branch["u_coords"])
            t = onb.fromCoords(branch["target_x_coords"])
            assert branch["v_root_count"] == len(branch["v_coords"])
            assert len(set(branch["v_coords"])) == len(branch["v_coords"])
            for coords in branch["v_coords"]:
                v = onb.fromCoords(coords)
                assert evaluate_s3(onb, u, t, v) == 0
            assert branch["field_api_entries"] == sum(
                branch["field_api_calls"].values())
        assert row["target_branches_with_v_roots"] == sum(
            bool(b["v_coords"]) for b in row["target_branches"])
        assert row["target_total_v_roots"] == sum(
            len(b["v_coords"]) for b in row["target_branches"])
        assert row["target_field_api_entries"] == sum(
            b["field_api_entries"] for b in row["target_branches"])
    assert result["complete_n131_solve_work_log2"] is None
    print("PASS Q1492", len(result["rows"]), result["summary"])


if __name__ == "__main__":
    main()
