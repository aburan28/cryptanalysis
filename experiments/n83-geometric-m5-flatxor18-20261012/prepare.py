#!/usr/bin/env python3
"""Freeze the equal-conflict N83 flattened-XOR circuit pilot."""

import json
from pathlib import Path

from flat_karatsuba import HERE, PARENT, runner


ROOT = runner.ROOT


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width18_ordinary.json"
    parent_control_path = PARENT / "karatsuba_control.json"
    parent_replay_path = PARENT / "sage_relation_replay.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    screen_path = HERE / "shape_screen.json"
    screen = json.loads(screen_path.read_text())
    assert screen["selfcheck"]["status"] == "PASS"
    assert screen["karatsuba"]["and_gates"] == screen[
        "reference"]["and_gates"] == 12174
    control_path = HERE / "karatsuba_control.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    assert control["replay"]["status"] == "verified_five_point_relation"
    sources = {**parent["source_sha256"]}
    for path in [HERE / name for name in
                 ("flat_karatsuba.py", "control.py", "pilot.py", "prepare.py")]:
        assert path.is_file()
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_flattened_xor_equal_conflict_pilot_protocol",
        "proposal_id": "Q2026101257",
        "comparison_variable": (
            "flatten recursive Karatsuba output XOR combinations before "
            "materializing field product coordinates; same base, target, "
            "AND gates and pairwise Frobenius selectors"),
        "method_comparison_parent": "Q2026101254 width-18 materialized-XOR Karatsuba",
        "solver": {**parent["solver"], "max_conflicts": 300000},
        "limits": {"wall_seconds_per_arm": 60,
                   "sampled_solver_rss_stop_bytes": 4294967296},
        "run_order": ["pairwise", "flattened", "flattened", "pairwise"],
        "timing_tier": "exploratory_local_unisolated",
        "source_sha256": sources,
        "shape_screen_sha256": runner.sha(screen_path),
        "control_receipt_sha256": runner.sha(control_path),
        "parent_protocol_sha256": runner.sha(parent_path),
        "parent_result_sha256": runner.sha(parent_result_path),
        "parent_control_sha256": runner.sha(parent_control_path),
        "parent_sage_replay_sha256": runner.sha(parent_replay_path),
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "run_order": protocol["run_order"],
                      "max_conflicts": protocol["solver"]["max_conflicts"]}),
          flush=True)


if __name__ == "__main__":
    main()
