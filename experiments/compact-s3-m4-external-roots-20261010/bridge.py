#!/usr/bin/env python3
"""Bind returned control witnesses to independently replayed Sage receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    q1419 = read(PARENT / "q1419_partial_pin/protocol.json")
    runtime = read(HERE / "sage_runtime_info.json")
    assert runtime["status"] == "verified"
    rows = []
    for n, replay_name, source_name in (
        (53, "n53_q1410_balanced_control_replay.json",
         "verify_q1410_n53_balanced.py"),
        (83, "n83_q1408_balanced_control_replay.json",
         "verify_q1408_balanced_control.py"),
    ):
        profile = q1419["profiles"][str(n)]
        new = read(HERE / "runs" / f"n{n}.json")
        fixture_path = ROOT / profile["fixture_receipt"]["path"]
        fixture = read(fixture_path)
        replay_path = PARENT / "runs" / replay_name
        replay = read(replay_path)
        assert replay["status"] == "PASS"
        assert replay["source_sha256"] == sha(PARENT / source_name)
        assert new["status"] == "SAT"
        assert new["curve_id"] == replay["curve_id"] == profile["curve_id"]
        assert new["public_target"] == profile["public_target"]
        assert new["factor_base_enumerated_set_sha256"] == (
            replay["factor_base_enumerated_set_sha256"])
        assert replay["factor_base_enumerated_set_sha256"] == (
            profile["factor_base_enumerated_set_sha256"])
        assert new["relation"]["raw_leaf_x"] == fixture["fixture"][
            "raw_leaf_x"]
        assert new["relation"]["status"] == "verified_four_point_relation"
        if n == 53:
            assert replay["locked_receipt_sha256"] == sha(fixture_path)
            assert new["relation"]["signs"] == fixture["fixture"]["signs"]
            assert replay["verified_locked_control_relation_count"] == 1
        else:
            assert replay["locked_stage_sha256"] == sha(fixture_path)
            assert new["relation"]["signs"] == [1, 1, 1, 1]
            assert replay["raw_and_public_sums_verified"]
            assert replay["four_distinct_columns"]
            assert replay["four_projected_leaves_in_exact_q1325_base"]
        rows.append({"field_degree_n": n, "same_archived_witness": True,
                     "checked_sage_replay_sha256": sha(replay_path),
                     "fixture_sha256": sha(fixture_path),
                     "new_run_sha256": sha(HERE / "runs" / f"n{n}.json")})
    return {"schema": "q20261010131600-sage-bridge-v1",
            "proposal_id": "Q20261010131600", "status": "PASS",
            "checked_launcher_runtime_info_sha256": sha(
                HERE / "sage_runtime_info.json"),
            "source_sha256": sha(Path(__file__)), "rows": rows}


if __name__ == "__main__":
    out = HERE / "sage_bridge.json"
    assert not out.exists()
    out.write_text(json.dumps(build(), sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "controls": 2}))
