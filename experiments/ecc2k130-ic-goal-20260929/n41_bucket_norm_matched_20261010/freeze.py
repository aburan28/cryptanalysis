#!/usr/bin/env python3
"""Freeze source-matched N41 seed-bucket norm comparison inputs."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n41_seed_bucket_resultant_20261010"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "compare.py").read_text())
    old = json.loads((PREVIOUS / "protocol.json").read_text())
    audit = json.loads((PREVIOUS / "audit.json").read_text())
    assert audit["status"] == "PASS"
    data = {"status": "FROZEN", "proposal_id": "Q20261010045500",
            "candidate_id": None, "target_count": 1,
            "curve_id": old["curve_id"], "public_target_q": old["public_target_q"],
            "residual": old["residual"], "cases": old["cases"],
            "case_order": ["negative", "positive"],
            "method_order": ["split_root", "bsgs", "bsgs", "split_root"],
            "method_boundary": "target-dependent norm, GCD, and root extraction after both exact bucket polynomials are ready",
            "wall_cap_seconds": 120, "rss_cap_bytes": 4294967296,
            "sha256": {"source": sha(HERE / "compare.py"),
                       "helper": sha(PREVIOUS / "run.py"),
                       "bsgs": sha(PREVIOUS / "norm_bsgs.py"),
                       "geometry": sha(GEOMETRY),
                       "prior_audit": sha(PREVIOUS / "audit.json"),
                       "prior_result": sha(PREVIOUS / "result.json"),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
