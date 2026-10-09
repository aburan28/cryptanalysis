#!/usr/bin/env python3
"""Freeze the exact mixed-cubic family and immutable N41 inputs before rank work."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_two_pair_mask_decoder_rank_20261008"
OCCUPANCY = GOAL / "n41_two_free_pair_occupancy_20261009"
OUTPUT = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("preserve first frozen protocol")
    inputs = {
        "decoded_rows": SOURCE / "decoded_rows.json",
        "holdout_rows": SOURCE / "holdout_rows.json",
        "geometry": OCCUPANCY / "geometry_snapshot.json",
        "arithmetic": OCCUPANCY / "arithmetic_snapshot.py",
    }
    if not all(path.is_file() for path in inputs.values()):
        raise FileNotFoundError("required exact-row evidence missing")
    protocol = {
        "kind": "n41_two_pair_mixed_cubic_seed_coordinate_rank_v1",
        "status": "FROZEN",
        "proposal_id": "Q20261009225800",
        "candidate_id": None, "run_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "pair_rotations": [20, 30],
        "target_count": 1,
        "inputs": {key: str(path) for key, path in inputs.items()},
        "input_sha256": {key: sha(path) for key, path in inputs.items()},
        "screen_sha256": sha(HERE / "screen.py"),
        "freeze_sha256": sha(Path(__file__)),
        "sample_count": 16384,
        "feature_count": 13599,
        "feature_order": "constant; lexicographic combinations of 52 input bits of degree one and two; lexicographic cubic triples containing at least one of the first 12 seed-sum bits; inputs are s2[0:6], s3[0:6], x(sum)[1:41]",
        "decision_rule": "If full feature nullity equals coordinate-only quadratic nullity, no universal mixed equation exists in the frozen family. A positive excess is a candidate only until checked against independent exact rows and the full domain.",
        "limits": {"wall_seconds": 300, "rss_bytes": 4294967296, "workers": 1},
        "claim_boundary": "finite exact-row rank witness for one declared mixed-cubic feature family on two N41 pair domains; CPU times are exploratory and no N131 relation or complete IC timing follows",
    }
    with OUTPUT.open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": protocol["status"],
                      "feature_count": protocol["feature_count"],
                      "screen_sha256": protocol["screen_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
