#!/usr/bin/env python3
"""Freeze the length-21 XOR materialization pilot."""

import json

from partial import HERE, flat


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = flat.HERE / "protocol.json"
    parent = json.loads(parent_path.read_text())
    control = json.loads((HERE / "karatsuba_control.json").read_text())
    screen = json.loads((HERE / "shape_screen.json").read_text())
    assert parent["proposal_id"] == "Q2026101257"
    assert control["status"] == "PASS"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert screen["proposal_id"] == "Q2026101259"
    assert screen["selfcheck"]["status"] == "PASS"
    sources = dict(parent["source_sha256"])
    for name in ("partial.py", "screen.py", "control.py", "prepare.py",
                 "pilot.py"):
        path = HERE / name
        sources[str(path.relative_to(flat.runner.ROOT))] = flat.runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_partial_xor_equal_conflict_pilot_protocol",
        "proposal_id": "Q2026101259",
        "comparison_variable": "materialize Karatsuba output XORs at recursion length 21",
        "solver": {**parent["solver"], "max_conflicts": 1000000},
        "limits": {"wall_seconds_per_arm": 180,
                   "sampled_solver_rss_stop_bytes": 4294967296},
        "run_order": ["pairwise", "partial21", "partial21", "pairwise"],
        "timing_tier": "exploratory_local_unisolated",
        "source_sha256": sources,
        "screen_sha256": flat.runner.sha(HERE / "shape_screen.json"),
        "control_sha256": flat.runner.sha(HERE / "karatsuba_control.json"),
        "parent_protocol_sha256": flat.runner.sha(parent_path),
        "parent_full_ordinary_sha256": flat.runner.sha(
            flat.PARENT / "width18_ordinary.json"),
    }
    flat.runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "run_order": protocol["run_order"]}), flush=True)


if __name__ == "__main__":
    main()
