#!/usr/bin/env python3
"""Freeze the two archived N41 seed-bucket compatibility controls."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    source = HERE / "run.py"
    ast.parse(source.read_text())
    geometry = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
    predecessor = BASE / "n131_w14_s3_prefix_rank_20261010/result.json"
    runtime = HERE / "sage_runtime_info.json"
    g = json.loads(geometry.read_text())["n41"]
    p = json.loads(predecessor.read_text())["n41"]
    assert p["positive_residual"] == [332635421840, 2054854538524]
    assert g["public_target_q"] == [1458168294740, 1672312028033]
    protocol = {
        "status": "FROZEN", "proposal_id": "Q20261010043600", "candidate_id": None,
        "curve_id": g["curve_id"], "target_count": 1,
        "method": "resultant in the second pair-output coordinate followed by GCD with the first exact seed-bucket image polynomial",
        "cases": {"positive": [16, 5], "negative": [1, 1]},
        "expected_x_hits": {"positive": 1, "negative": 0},
        "public_target_q": g["public_target_q"], "residual": p["positive_residual"],
        "limits": {"workers": 1, "combined_rss_bytes": 4294967296,
                   "wall_seconds": 120},
        "wall_cap_seconds": 120, "rss_cap_bytes": 4294967296,
        "sha256": {"run": sha(source), "geometry": sha(geometry),
                   "predecessor": sha(predecessor), "runtime": sha(runtime)},
    }
    with output.open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
