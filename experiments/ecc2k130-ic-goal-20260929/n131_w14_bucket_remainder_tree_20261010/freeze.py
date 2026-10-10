#!/usr/bin/env python3
"""Freeze exact N131 W14 root-evaluation replacement inputs."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n131_w14_seed_bucket_norm_20261010"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "run.py").read_text())
    prior = json.loads((PREVIOUS / "query_result.json").read_text())
    roots = json.loads((PREVIOUS / "roots.json").read_text())
    assert prior["status"] == "COMPLETE_N131_PROPOSED_OUTPUT_PANEL"
    assert roots["status"] == "COMPLETE_EXACT_ROOTS"
    assert roots["distinct_raw_pair_x_per_rotation"] == 4124
    data = {"status": "FROZEN", "proposal_id": "Q20261010051800",
            "candidate_id": None, "target_count": 0,
            "curve_id": prior["curve_id"], "seed_sum": 2,
            "case_order": ["trace_zero_control", "positive", "positive",
                           "trace_zero_control"],
            "method": "balanced S3 factor product, reusable left subproduct tree, exact remainder-tree evaluation at every left root",
            "wall_cap_seconds": 600, "rss_cap_bytes": 4294967296,
            "sha256": {"source": sha(HERE / "run.py"),
                       "prior_source": sha(PREVIOUS / "query.py"),
                       "roots": sha(PREVIOUS / "roots.json"),
                       "prior_result": sha(PREVIOUS / "query_result.json"),
                       "control": sha(CONTROL),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
