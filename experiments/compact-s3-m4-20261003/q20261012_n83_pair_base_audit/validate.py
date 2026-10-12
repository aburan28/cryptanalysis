#!/usr/bin/env python3
"""Verify Q1494 exact-base membership and paired target-root agreement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import audit

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol, frozen, result = (load(HERE / n) for n in
                                ("protocol.json", "freeze.json", "result.json"))
    assert protocol["proposal_id"] == frozen["proposal_id"] == result[
        "proposal_id"] == "Q1494"
    assert all(sha(HERE / n) == h for n, h in frozen["files_sha256"].items())
    assert result["freeze_sha256"] == sha(HERE / "freeze.json")
    assert result["source_sha256"] == sha(HERE / "audit.py")
    assert sha(audit.KEYS) == frozen["base_key_file_sha256"]
    assert sha(audit.Q1493 / "result.json") == frozen[
        "q1493_result_sha256"]
    raw = audit.KEYS.read_bytes()
    keys = {int.from_bytes(raw[i:i + 21], "little")
            for i in range(0, len(raw), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = audit.CountedOnb(83)
    curve = audit.Curve(onb)
    orbit = audit.OrbitKey(onb)
    assert len(result["rows"]) == 40
    for row in result["rows"]:
        assert row["pair_receipt_sha256"] == frozen[
            "pair_receipts"][str(row["phase"])]
        assert len(row["leaves"]) == 2
        for leaf in row["leaves"]:
            x = onb.fromCoords(leaf["coords"])
            raw_point = curve.pointFromX(x) if x else None
            projected = curve.mul(raw_point, 4) if raw_point is not None else None
            assert leaf["rational_lift"] == (raw_point is not None)
            assert leaf["projected_identity"] == (raw_point is not None and
                                                    projected is None)
            key = orbit.canonical(projected)[0] if projected is not None else None
            assert leaf["projected_orbit_key"] == key
            assert leaf["exact_base_member"] == (key in keys if key is not None
                                                 else False)
            assert leaf["filter_field_api_entries"] == sum(
                leaf["filter_field_api_calls"].values())
            assert leaf["subgroup_replay_field_api_entries"] == sum(
                leaf["subgroup_replay_field_api_calls"].values())
        assert row["both_usable"] == all(
            leaf["exact_base_member"] for leaf in row["leaves"])
    assert result["all_usable_match_selected_target_v_root"]
    assert result["all_usable_match_holdout_target_v_root"]
    assert sum(r["both_usable"] for r in result["rows"]) == 8
    assert result["complete_n131_solve_work_log2"] is None
    print("PASS Q1494", len(result["rows"]), 8)


if __name__ == "__main__":
    main()
