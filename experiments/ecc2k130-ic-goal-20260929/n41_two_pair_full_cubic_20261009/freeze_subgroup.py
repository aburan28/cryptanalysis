#!/usr/bin/env python3
"""Freeze a coordinate-rank control on uniformly sampled N41 subgroup points."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "subgroup_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first subgroup-rank protocol")
    prior = json.loads((HERE / "rank.json").read_text())
    if prior["coordinate_rank"] != 3198 or prior["coordinate_feature_count"] != 3322:
        raise ValueError("two-pair coordinate rank changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_random_subgroup_coordinate_quadratic_rank",
        "proposal_id": "Q20261009231000", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "point_count": 6000, "random_seed": 20261009231005,
        "input_law": "independent uniform nonzero scalars modulo 549756390943 applied to the frozen public subgroup point",
        "coordinate_features": "constant, x bits 1..40, y bits 0..40, and every pairwise product in lexicographic order",
        "milestones": [1000, 2000, 3000, 4000, 5000, 6000],
        "limits": {"workers": 1, "wall_seconds": 120, "rss_bytes": 4294967296},
        "decision_rule": "Compare the rank of 3322 coordinate-only quadratic features on fresh subgroup points with rank 3198 from two-pair sums; matching rank is evidence that the observed 124 coordinate identities are subgroup-wide.",
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "rank.json", "produce.py")},
        "source_sha256": digest(HERE / "subgroup_coordinate_rank.py"),
        "claim_boundary": "rank-control evidence on a random subgroup sample, not a symbolic proof on every point",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
