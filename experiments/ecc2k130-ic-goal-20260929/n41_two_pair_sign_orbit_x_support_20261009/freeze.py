#!/usr/bin/env python3
"""Freeze the exact sign-orbit certificate before its producer executes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n41_two_free_pair_occupancy_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = {
        "kind": "n41_two_pair_sign_orbit_x_support",
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "pair_rotations": [0, 10, 20, 30],
        "public_target_q": [1458168294740, 1672312028033],
        "source_sha256": {
            "geometry": sha(PARENT / "geometry_snapshot.json"),
            "arithmetic": sha(PARENT / "arithmetic_snapshot.py"),
            "census_result": sha(PARENT / "result.json"),
            "census_sage_audit": sha(PARENT / "audit.json"),
            "producer": sha(HERE / "run.py"),
            "auditor": sha(HERE / "audit.py"),
        },
        "expected": {
            "per_rotation_points": 64,
            "per_rotation_pair_states": 1956,
            "valid_suffix_assignments": 3167136,
            "unique_suffix_group_sums": 3167136,
            "duplicate_suffix_group_sums": 0,
        },
        "producer_wall_cap_seconds": 120,
        "audit_wall_cap_seconds": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "candidate_id": None,
        "run_id": None,
        "scope": "exact sign involution and x-fiber support for the frozen N41 two-free-pair domain; no N131 execution or performance transfer",
    }
    with (HERE / "protocol.json").open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(sha(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
