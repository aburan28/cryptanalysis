#!/usr/bin/env python3
"""Freeze ordinary N83 width-18 search with flattened Karatsuba XORs."""

import json
from pathlib import Path

from ordinary import HERE, ROOT, FLAT, runner


PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width18_ordinary.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    flat_protocol_path = FLAT / "protocol.json"
    flat_result_path = FLAT / "pilot_result.json"
    flat_control_path = FLAT / "karatsuba_control.json"
    flat_replay_path = FLAT / "sage_relation_replay.json"
    assert json.loads(flat_protocol_path.read_text())["proposal_id"] == (
        "Q2026101257")
    assert json.loads(flat_result_path.read_text())["status"] == "bounded_unknown"
    assert json.loads(flat_control_path.read_text())["status"] == "PASS"
    assert json.loads(flat_replay_path.read_text())["status"] == "PASS"
    sources = {**parent["source_sha256"]}
    for path in (FLAT / "flat_karatsuba.py", HERE / "ordinary.py",
                 Path(__file__)):
        assert path.is_file()
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_shifted_width18_flattened_xor_karatsuba_five_summand_protocol",
        "proposal_id": "Q2026101258",
        "comparison_variable": (
            "flatten recursive Karatsuba output XOR combinations before "
            "field-coordinate materialization on the same complete width-18 "
            "base and public target"),
        "method_comparison_parent": "Q2026101254 width-18 materialized-XOR Karatsuba",
        "field_multiplier": {**parent["field_multiplier"],
                             "xor_output_policy": "flatten recursive coefficient combinations into each field-product output row"},
        "source_sha256": sources,
        "parent_karatsuba_protocol_sha256": runner.sha(parent_path),
        "parent_karatsuba_result_sha256": runner.sha(parent_result_path),
        "flat_pilot_protocol_sha256": runner.sha(flat_protocol_path),
        "flat_pilot_result_sha256": runner.sha(flat_result_path),
        "flat_control_sha256": runner.sha(flat_control_path),
        "flat_sage_replay_sha256": runner.sha(flat_replay_path),
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": protocol["base_rows"][0]["B"],
                      "K": protocol["base_rows"][0]["K"]}), flush=True)


if __name__ == "__main__":
    main()
