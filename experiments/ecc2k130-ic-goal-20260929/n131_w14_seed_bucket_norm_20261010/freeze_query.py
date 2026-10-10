#!/usr/bin/env python3
"""Freeze the exact N131 fixed-seed proposed-output norm panel."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
NATIVE = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "query_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "query.py").read_text())
    roots = json.loads((HERE / "roots.json").read_text())
    assert roots["status"] == "COMPLETE_EXACT_ROOTS"
    assert roots["allowed_source_pairs"] == 2062
    assert roots["distinct_raw_pair_x_per_rotation"] == 4124
    control = json.loads(CONTROL.read_text())["panels"]["131"]
    assert control["curve_id"] == roots["curve_id"]
    data = {"status": "FROZEN", "proposal_id": "Q20261010045900",
            "candidate_id": None, "target_count": 0,
            "curve_id": control["curve_id"], "seed_sum": 2,
            "case_order": ["trace_zero_control", "positive"],
            "method": "balanced product of exact right-bucket S3 factors, reduction modulo exact left-bucket polynomial, GCD and roots",
            "wall_cap_seconds": 600, "rss_cap_bytes": 4294967296,
            "sha256": {"source": sha(HERE / "query.py"),
                       "roots": sha(HERE / "roots.json"),
                       "control": sha(CONTROL), "native": sha(NATIVE),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
