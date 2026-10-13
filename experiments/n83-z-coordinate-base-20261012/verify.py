#!/usr/bin/env python3
"""Read-only integrity and cross-replay audit for the exact z-base census."""

import hashlib
import json
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    census = json.loads((HERE / "census.json").read_text())
    replay = json.loads((HERE / "independent_sage_replay.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    old = json.loads((ROOT / "experiments/n83-geometric-m5-gate-20261012/protocol.json").read_text())
    width12 = next(row for row in old["base_rows"] if row["dimension"] == 12)
    assert protocol["curve_id"] == old["curve_id"]
    assert census["status"] == "complete" and replay["status"] == "PASS"
    assert census["protocol_sha256"] == sha(HERE / "protocol.json")
    assert census["source_sha256"] == sha(HERE / "census.py")
    assert census["roots_file_sha256"] == sha(HERE / "roots.bin")
    assert census["keys_file_sha256"] == sha(HERE / "keys.bin")
    assert replay["census_sha256"] == sha(HERE / "census.json")
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert replay["bridge_sha256"] == sha(
        ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json")
    assert sum(census["root_histogram"].values()) == 2048
    assert census["root_histogram"] == {"0": 0, "1": 2048, "3": 0}
    assert census["raw_x_roots"] == 2048
    assert len((HERE / "roots.bin").read_bytes()) == 11 * 2048
    assert census["raw_x_roots"] - census["subgroup_identities"] - census[
        "signed_frobenius_seed_duplicates"] == census["effective_columns_K"]
    assert len((HERE / "keys.bin").read_bytes()) == 21 * census["effective_columns_K"]
    assert census["actual_subgroup_points_B"] == 166 * census["effective_columns_K"]
    for field in ("effective_columns_K", "actual_subgroup_points_B", "subgroup_identities"):
        assert replay[field] == census[field]
    assert replay["unique_z_values"] == 2048
    assert replay["one_root_cubic_fibers_certified_by_quadratic_trace"] == 2048
    assert width12["K"] == 2130
    assert width12["B"] == 353580
    assert census["effective_columns_K"] < width12["K"]
    assert census["actual_subgroup_points_B"] < width12["B"]
    assert comb(census["actual_subgroup_points_B"], 5) / protocol["subgroup_order"] < (
        comb(width12["B"], 5) / protocol["subgroup_order"])
    assert runtime
    print(json.dumps({
        "status": "PASS",
        "z_K": census["effective_columns_K"],
        "z_B": census["actual_subgroup_points_B"],
        "width12_x_K": width12["K"],
        "width12_x_B": width12["B"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
