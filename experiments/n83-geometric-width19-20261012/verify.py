#!/usr/bin/env python3
"""Audit the exact width-19 geometry and independent Sage replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-width17-18-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["kind"] == "n83_exact_shifted_geometric_width19_protocol"
    assert protocol["dimensions"] == [19]
    assert protocol["offsets"] == [1 << 81]
    assert sha(PARENT / "frontier.json") == protocol[
        "parent_width18_frontier_sha256"]
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    receipt_path = HERE / "frontier.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "complete_geometry_stage"
    assert receipt["curve_id"] == protocol["curve_id"]
    assert len(receipt["rows"]) == 1
    assert receipt["source_sha256"]["runner"] == sha(HERE / "run.py")
    assert receipt["source_sha256"]["protocol"] == sha(protocol_path)
    assert receipt["source_sha256"]["sage_runtime_info"] == sha(runtime_path)
    row = receipt["rows"][0]
    assert row["dimension"] == 19
    assert row["seed_x_count"] == 524288
    assert row["valid_lifts"] + row["invalid_or_zero_lifts"] == 524288
    assert row["folded_columns_K"] == row["valid_lifts"] - row[
        "identity_projections"] - row["duplicate_orbit_seeds"]
    assert row["actual_usable_points_B_before_folding"] == 166 * row[
        "folded_columns_K"]
    assert row["full_pair_root_states"] == 83 * row[
        "folded_columns_K"] ** 2
    assert row["root_plus_cached_xy_payload_bytes"] == 96 * row[
        "full_pair_root_states"]
    path = HERE / row["canonical_key_file"]
    assert path.stat().st_size == 21 * row["folded_columns_K"]
    assert sha(path) == row["canonical_key_sha256"]
    replay = json.loads((HERE / "independent_sage_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["source_receipt_sha256"] == sha(receipt_path)
    assert replay["verifier_sha256"] == sha(HERE / "verify_sage.py")
    assert len(replay["results"]) == 1
    assert replay["results"][0]["full_seed_replay"] is True
    assert replay["results"][0]["K"] == row["folded_columns_K"]
    assert replay["results"][0]["B"] == row[
        "actual_usable_points_B_before_folding"]
    print(json.dumps({"status": "PASS", "dimension": 19,
                      "B": row["actual_usable_points_B_before_folding"],
                      "K": row["folded_columns_K"]}, sort_keys=True))


if __name__ == "__main__":
    main()
