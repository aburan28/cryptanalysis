#!/usr/bin/env python3
"""Freeze the baby-step/giant-step bucket norm control."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "bsgs_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "norm_bsgs.py").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    horner = json.loads((HERE / "norm_result.json").read_text())
    assert horner["status"] == "COMPLETE_BUCKET_DIAGNOSTIC"
    data = {"status": "FROZEN", "proposal_id": protocol["proposal_id"],
            "candidate_id": None, "target_count": 1,
            "method": "baby-step/giant-step polynomial evaluation in the quadratic S3 quotient",
            "cases": protocol["cases"], "residual": protocol["residual"],
            "public_target_q": protocol["public_target_q"],
            "wall_cap_seconds": 120, "rss_cap_bytes": 4294967296,
            "sha256": {"source": sha(HERE / "norm_bsgs.py"),
                       "helper": sha(HERE / "run.py"), "geometry": sha(GEOMETRY),
                       "generic": sha(HERE / "result.json"),
                       "horner": sha(HERE / "norm_result.json"),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
