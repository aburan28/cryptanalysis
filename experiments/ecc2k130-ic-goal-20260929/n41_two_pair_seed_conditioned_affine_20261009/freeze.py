#!/usr/bin/env python3
"""Freeze the N41 seed-conditioned affine completion screen."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
CENSUS = GOAL / "n41_two_free_pair_occupancy_20261009"
SIGN = GOAL / "n41_two_pair_sign_orbit_x_support_20261009"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = {
        "geometry": CENSUS / "geometry_snapshot.json",
        "arithmetic": CENSUS / "arithmetic_snapshot.py",
        "census_result": CENSUS / "result.json",
        "census_sage_audit": CENSUS / "audit.json",
        "sign_source": SIGN / "run.py",
        "sign_protocol": SIGN / "protocol.json",
        "sign_result": SIGN / "result.json",
        "sign_sage_audit": SIGN / "audit.json",
        "producer": HERE / "run.py",
        "auditor": HERE / "audit.py",
    }
    protocol = {
        "kind": "n41_two_pair_seed_conditioned_affine_x_rank",
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "suffix_pair_rotations": [20, 30],
        "seed_sum_values": list(range(1, 64)),
        "feature_encoding": "41-bit row: bit 0 constant one; bits 1..40 are polynomial-basis x bits 1..40; subgroup x bit 0 must vanish",
        "full_affine_rank": 41,
        "expected_seed_sum_pair_bins": 3969,
        "expected_sign_orbits": 1583568,
        "producer_wall_cap_seconds": 300,
        "audit_wall_cap_seconds": 300,
        "rss_cap_bytes": 4 * 1024**3,
        "workers": 1,
        "candidate_id": None,
        "run_id": None,
        "source_sha256": {key: sha(path) for key, path in files.items()},
        "decision_rule": "An affine seed-conditioned feasibility filter exists on this exact N41 policy only in bins of rank below 41; each such equation must be checked against the entire bin before use. Full rank in every bin rejects this candidate family.",
    }
    with (HERE / "protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(sha(HERE / "protocol.json"))


if __name__ == "__main__":
    main()
