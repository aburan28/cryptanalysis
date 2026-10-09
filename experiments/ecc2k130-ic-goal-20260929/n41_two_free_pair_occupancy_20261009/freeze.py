#!/usr/bin/env python3
"""Freeze the first exact N41 two-free-pair occupancy experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROOT = HERE.parents[2]
GEOMETRY = HERE / "geometry_snapshot.json"
ARITHMETIC = HERE / "arithmetic_snapshot.py"
PROTOCOL = HERE / "protocol.json"
ORIGINAL_GEOMETRY = GOAL / "n131_w18_four_pairs/screen.json"
ORIGINAL_ARITHMETIC = (ROOT.parent / "crypto/research/sat_factor_base_review_20260908"
                       / "autolab_orbit_extract_20260924/independent_replay.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if PROTOCOL.exists():
        raise FileExistsError("preserve the first frozen protocol")
    if sha(GEOMETRY) != sha(ORIGINAL_GEOMETRY) or sha(ARITHMETIC) != sha(ORIGINAL_ARITHMETIC):
        raise ValueError("input snapshot differs from its audited source")
    record = json.loads(GEOMETRY.read_text())
    n41 = record["n41"]
    n131 = record["n131"]
    if (n41["curve_id"] != "EC1N41Ckb1h7d5e80d3c4d0" or
            n131["curve_id"] != "EC1N131Ckb1h136f03e58c98" or
            n41["slot_rotations"] != [0, 0, 10, 10, 20, 20, 30, 30] or
            len(n41["point_rows_by_unique_rotation"]) != 4):
        raise ValueError("input geometry is not the fixed four-pair policy")
    protocol = {
        "kind": "n41_two_free_pair_occupancy_and_n131_fixed_prefix_bound_v1",
        "status": "FROZEN_DIAGNOSTIC",
        "curve_id": n41["curve_id"],
        "n131_curve_id": n131["curve_id"],
        "public_target_q": n41["public_target_q"],
        "subgroup_order": int(n41["subgroup_order"]),
        "pair_rotations": [0, 10, 20, 30],
        "suffix_pair_positions": [2, 3],
        "prefix_pair_positions": [0, 1],
        "per_pair_domain_states_expected": 1956,
        "process_rss_cap_bytes": 4 * 1024**3,
        "total_wall_cap_seconds": 600,
        "audit_wall_cap_seconds": 600,
        "max_saved_witnesses": 64,
        "geometry_sha256": sha(GEOMETRY),
        "arithmetic_sha256": sha(ARITHMETIC),
        "run_source_sha256": sha(HERE / "run.py"),
        "audit_source_sha256": sha(HERE / "audit.py"),
        "freeze_source_sha256": sha(Path(__file__)),
        "input_source_sha256": {"original_geometry": sha(ORIGINAL_GEOMETRY),
                                "original_arithmetic": sha(ORIGINAL_ARITHMETIC)},
        "target_fixture_policy": "the frozen public point is supplied without its scalar; no witness or scalar is loaded into the producer",
        "accounting": "suffix index is target independent; target-dependent interval starts before public-point subgroup check and includes the full prefix residual scan",
        "claim_boundary": "exact smaller-field occupancy and a uniform-target fixed-prefix lower bound; not an N131 relation or complete IC candidate",
    }
    with PROTOCOL.open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"protocol_sha256": sha(PROTOCOL),
                      "curve_id": protocol["curve_id"],
                      "n131_curve_id": protocol["n131_curve_id"]}, sort_keys=True))


if __name__ == "__main__":
    main()
