#!/usr/bin/env python3
"""Freeze the Sage inverse join, inputs, and prior independent audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (HERE / "sage_query_protocol.json").exists()
    assert not (HERE / "sage_query_result.json").exists()
    source = json.loads((HERE / "result.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert source["status"] == "COMPLETE"
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_W15_S3_JOIN_AUDIT"
    assert audit["sha256"]["producer_result"] == sha(HERE / "result.json")
    roots = json.loads((BASE / "pair_roots.json").read_text())
    assert roots["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    from sage_query import sources
    protocol = {"status": "FROZEN_W15_S3_SAGE_QUERY",
                "curve_id": source["curve_id"], "candidate_id": None,
                "target_count": 1,
                "cases": [row["name"] for row in source["cases"]],
                "input_law": "constructed first-four-atom sum and both trace-zero raw lifts of the published point",
                "timing_boundary": "from supplied reciprocal target coordinate to complete left-domain S3 inverse scan and right-set lookup; setup and independent replay separate",
                "per_query_cap_seconds": 120,
                "rss_cap_bytes": 4*1024**3, "workers": 1,
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    with (HERE / "sage_query_protocol.json").open("x") as out:
        json.dump(protocol, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps({"status": protocol["status"], "cases": protocol["cases"]}))


if __name__ == "__main__":
    main()
