#!/usr/bin/env python3
"""Freeze equal-conflict pairwise versus sequential selector pilot."""

import json
from pathlib import Path

from selector_amo import HERE, PARENT, ROOT, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width18_ordinary.json"
    parent_control_path = PARENT / "karatsuba_control.json"
    parent_replay_path = PARENT / "sage_relation_replay.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    assert json.loads(parent_control_path.read_text())["status"] == "PASS"
    assert json.loads(parent_replay_path.read_text())["status"] == "PASS"
    screen_path = HERE / "shape_screen.json"
    screen = json.loads(screen_path.read_text())
    assert screen["status"] == "PASS"
    assert screen["selector_selfcheck"]["status"] == "PASS"
    assert screen["amo_shape"]["and_gates"] == screen[
        "pairwise_shape"]["and_gates"] == 12174
    sources = {**parent["source_sha256"]}
    for path in [HERE / name for name in
                 ("selector_amo.py", "control.py", "pilot.py", "prepare.py")]:
        assert path.is_file()
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_sequential_selector_equal_conflict_pilot_protocol",
        "proposal_id": "Q2026101256",
        "comparison_variable": (
            "replace pairwise one-hot Frobenius selector clauses by exact "
            "sequential at-most-one clauses on the same base and public target"),
        "method_comparison_parent": "Q2026101254 width-18 Karatsuba choice-zero formula",
        "selector_encoding": "Sinz sequential at-most-one plus one at-least-one clause per 83-way leaf selector",
        "solver": {**parent["solver"], "max_conflicts": 300000},
        "limits": {"wall_seconds_per_arm": 60,
                   "sampled_solver_rss_stop_bytes": 4294967296},
        "run_order": ["pairwise", "sequential", "sequential", "pairwise"],
        "timing_tier": "exploratory_local_unisolated",
        "source_sha256": sources,
        "shape_screen_sha256": runner.sha(screen_path),
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
