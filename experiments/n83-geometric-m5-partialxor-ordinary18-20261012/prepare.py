#!/usr/bin/env python3
"""Freeze full ordinary N83 width-18 partial XOR search."""

import json
from pathlib import Path

from ordinary import HERE, ROOT, PART, runner


PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width18_ordinary.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    pilot_protocol_path = PART / "protocol.json"
    pilot_result_path = PART / "pilot_result.json"
    control_path = PART / "karatsuba_control.json"
    replay_path = PART / "sage_relation_replay.json"
    assert json.loads(pilot_protocol_path.read_text())["proposal_id"] == (
        "Q2026101259")
    assert json.loads(pilot_result_path.read_text())["status"] == "bounded_unknown"
    assert json.loads(control_path.read_text())["status"] == "PASS"
    assert json.loads(replay_path.read_text())["status"] == "PASS"
    sources = {**parent["source_sha256"]}
    for path in (PART / "partial.py", PART.parent /
                 "n83-geometric-m5-flatxor18-20261012/flat_karatsuba.py",
                 HERE / "ordinary.py", Path(__file__)):
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_shifted_width18_partial21_xor_five_summand_protocol",
        "proposal_id": "Q2026101260",
        "comparison_variable": (
            "materialize recursive Karatsuba output XORs at length 21 "
            "on the same complete width-18 base and public target"),
        "method_comparison_parent": "Q2026101254 width-18 materialized-XOR Karatsuba",
        "field_multiplier": {**parent["field_multiplier"],
                             "xor_output_policy": "materialize Karatsuba recursion outputs at length 21"},
        "source_sha256": sources,
        "parent_karatsuba_protocol_sha256": runner.sha(parent_path),
        "parent_karatsuba_result_sha256": runner.sha(parent_result_path),
        "partial_pilot_protocol_sha256": runner.sha(pilot_protocol_path),
        "partial_pilot_result_sha256": runner.sha(pilot_result_path),
        "partial_control_sha256": runner.sha(control_path),
        "partial_sage_replay_sha256": runner.sha(replay_path),
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": protocol["base_rows"][0]["B"],
                      "K": protocol["base_rows"][0]["K"]}), flush=True)


if __name__ == "__main__":
    main()
