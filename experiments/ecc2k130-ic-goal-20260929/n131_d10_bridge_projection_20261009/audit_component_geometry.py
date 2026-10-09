#!/usr/bin/env python3
"""Recount native-XOR component rows and columns after both exact transforms."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BRIDGE = GOAL / "n131_d10_xor_bridge_20261009/bridge_cnf"
SOURCE = BRIDGE / "bridge_cnf.xcnf"
PROJECTED = HERE / "budget1/projected.xcnf"
PROJECTION = HERE / "budget1/result.json"
PIVOT_AUDIT = HERE / "budget1/independent_elimination_audit.json"
COMPONENT_AUDITOR = (GOAL / "n131_d10_xor_bridge_20261009/"
                     "audit_bridge_cnf.py")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = HERE / "independent_component_geometry.json"
    if output.exists():
        raise FileExistsError(output)
    projection = json.loads(PROJECTION.read_text())
    pivot = json.loads(PIVOT_AUDIT.read_text())
    bridge = json.loads((BRIDGE / "independent_audit.json").read_text())
    if (projection["status"] != "PASS" or pivot["status"] != "PASS" or
            bridge["status"] != "PASS_EQUIVALENT_AND_COMPONENT_FIT" or
            sha(SOURCE) != projection["source_sha256"]["input_xcnf"] or
            sha(PROJECTED) != projection["source_sha256"]["projected_xcnf"]):
        raise ValueError("exact transform certificate or input differs")
    spec = importlib.util.spec_from_file_location("component_auditor",
                                                  COMPONENT_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = module.xor_components(SOURCE)
    after = module.xor_components(PROJECTED)
    if (before["xor_rows"] != projection["original_xor_rows"] or
            after["xor_rows"] != projection["projected_xor_rows"] or
            before["component_count"] != after["component_count"] or
            after["max_rows"] > 10000 or after["max_columns"] > 15000):
        raise ValueError("component geometry or frozen matrix cap differs")
    result = {
        "kind": "n131_d10_bridge_then_fill_projection_xor_component_audit",
        "status": "PASS_COMPONENT_FIT",
        "before": before,
        "after": after,
        "source_sha256": {
            "bridge_xcnf": sha(SOURCE),
            "projected_xcnf": sha(PROJECTED),
            "projection_receipt": sha(PROJECTION),
            "pivot_audit": sha(PIVOT_AUDIT),
            "component_auditor": sha(COMPONENT_AUDITOR),
            "script": sha(Path(__file__)),
        },
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "before_rows": before["max_rows"],
                      "after_rows": after["max_rows"],
                      "after_columns": after["max_columns"]}))


if __name__ == "__main__":
    main()
