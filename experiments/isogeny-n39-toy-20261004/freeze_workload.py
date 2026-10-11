#!/usr/bin/env python3
"""Freeze the exact paired N39 stage-panel targets as a canonical workload."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = json.loads((HERE / "receipt-r1.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert receipt["status"] == "verified_stage_control"
    assert len(receipt["held_out_rows"]) == protocol["target_count"]
    record = {
        "schema_version": 1,
        "field": receipt["field"],
        "source_curve": {key: receipt["source_curve"][key] for key in
                         ("ainvs", "subgroup_order", "cofactor", "generator")},
        "descendant_curve": {key: receipt["descendant_curve"][key] for key in
                             ("ainvs", "generator")},
        "target_input_law": receipt["workload"]["input_law"],
        "target_generation_seed": protocol["target_seed"],
        "target_count": protocol["target_count"],
        "source_targets": [row["source_target"] for row in receipt["held_out_rows"]],
        "descendant_targets": [row["descendant_target"] for row in receipt["held_out_rows"]],
        "timing_policy": "warm_pair_index; target generation excluded; descendant target map charged separately",
        "fixed_wall_limit_seconds": protocol["fixed_wall_limit_seconds"],
    }
    workload_id = hashlib.sha256(canonical(record)).hexdigest()[:12]
    output = {"workload_id": workload_id, "workload_record": record}
    path = HERE / "workload.json"
    expected = json.dumps(output, indent=2) + "\n"
    if args.check:
        assert path.read_text() == expected
    else:
        if path.exists():
            parser.error(f"workload already exists: {path}")
        path.write_text(expected)
    print(json.dumps({"workload_id": workload_id,
                      "target_count": record["target_count"],
                      "verified": True}, indent=2))


if __name__ == "__main__":
    main()
