#!/usr/bin/env python3
"""Verify paired Q1493 root continuations against the S3 polynomial."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import paired

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol, frozen, result = (load(HERE / n) for n in
                                ("protocol.json", "freeze.json", "result.json"))
    assert protocol["proposal_id"] == frozen["proposal_id"] == result[
        "proposal_id"] == "Q1493"
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["source_sha256"] == sha(HERE / "paired.py")
    assert len(result["rows"]) == 80
    module = paired.prior.oracle()
    onb = module.CountedOnb(83)
    from chain_s3 import evaluate_s3
    for row in result["rows"]:
        assert row["first_pair_receipt_sha256"] == frozen[
            "pair_receipts"][str(row["phase"])]
        target = load(Path(frozen["targets"][row["target"]]["path"]))
        assert sha(Path(frozen["targets"][row["target"]]["path"])) == frozen[
            "targets"][row["target"]]["sha256"]
        assert row["target_workload_id"] == target["workload_id"]
        assert len(row["target_branches"]) == 4 * row[
            "first_pair_root_count"]
        for branch in row["target_branches"]:
            assert branch["target_x_coords"] == target[
                "raw_preimage_x_coordinates"][branch["target_preimage_index"]]
            u = onb.fromCoords(branch["u_coords"])
            t = onb.fromCoords(branch["target_x_coords"])
            for coords in branch["v_coords"]:
                v = onb.fromCoords(coords)
                assert evaluate_s3(onb, u, t, v) == 0
            assert branch["field_api_entries"] == sum(
                branch["field_api_calls"].values())
        assert row["target_v_root_count"] == sum(
            len(b["v_coords"]) for b in row["target_branches"])
        assert row["target_field_api_entries"] == sum(
            b["field_api_entries"] for b in row["target_branches"])
    for name in ("selected", "holdout"):
        assert sum(result["summary"][f"{name}_{count}"][
            "pairs_with_target_v_roots"] for count in
            protocol["flip_counts"]) == sum(
            bool(r["target_v_root_count"]) for r in result["rows"]
            if r["target"] == name)
    assert result["complete_n131_solve_work_log2"] is None
    print("PASS Q1493", len(result["rows"]))


if __name__ == "__main__":
    main()
