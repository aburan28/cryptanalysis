#!/usr/bin/env python3
"""Freeze independent replay inputs for both bucket operators."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
ROW = BASE / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "audit_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "audit.py").read_text())
    generic = json.loads((HERE / "result.json").read_text())
    norm = json.loads((HERE / "norm_result.json").read_text())
    assert generic["status"] == norm["status"] == "COMPLETE_BUCKET_DIAGNOSTIC"
    protocol = json.loads((HERE / "protocol.json").read_text())
    data = {"status": "FROZEN", "cases": protocol["cases"],
            "public_target_q": protocol["public_target_q"], "residual": protocol["residual"],
            "sha256": {"source": sha(HERE / "audit.py"), "geometry": sha(GEOMETRY),
                       "row": sha(ROW), "generic": sha(HERE / "result.json"),
                       "norm": sha(HERE / "norm_result.json"),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
