#!/usr/bin/env python3
"""Freeze a bounded fixed-preimage portfolio for one N83 public target."""

import json
from pathlib import Path

from portfolio import HERE, ROOT, SOURCE, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = SOURCE / "protocol.json"
    parent_result_path = SOURCE / "width18_ordinary.json"
    parent_replay_path = SOURCE / "sage_relation_replay.json"
    parent_control_path = SOURCE / "karatsuba_control.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    assert json.loads(parent_result_path.read_text())["status"] == "bounded_unknown"
    assert json.loads(parent_replay_path.read_text())["status"] == "PASS"
    assert json.loads(parent_control_path.read_text())["status"] == "PASS"
    choices = [1, 2, 3, 4, 5, 7, 11, 19, 37, 73, 147, 267]
    assert len(choices) == len(set(choices)) == 12
    assert all(0 <= choice < 332 for choice in choices)
    sources = {**parent["source_sha256"]}
    sources[str((HERE / "portfolio.py").relative_to(ROOT))] = runner.sha(
        HERE / "portfolio.py")
    sources[str(Path(__file__).relative_to(ROOT))] = runner.sha(Path(__file__))
    protocol = {
        **parent,
        "kind": "n83_width18_fixed_raw_target_choice_portfolio_protocol",
        "proposal_id": "Q2026101255",
        "comparison_variable": (
            "try twelve frozen cofactor-preimage and Frobenius target slices "
            "on the same width-18 base, public point and Karatsuba circuit"),
        "method_comparison_parent": "Q2026101254 choice-zero width-18 Karatsuba stage",
        "target_choices": choices,
        "target_preimage_policy": (
            "fixed 12-choice sequence from the 332 raw-preimage/Frobenius "
            "coset; each choice is a separate constant-target XCNF"),
        "limits": {
            "total_wall_seconds": 600,
            "per_choice_wall_seconds": 50,
            "sampled_solver_rss_stop_bytes": 4294967296,
            "max_models_per_choice": 1,
        },
        "source_sha256": sources,
        "parent_protocol_sha256": runner.sha(parent_path),
        "parent_result_sha256": runner.sha(parent_result_path),
        "parent_sage_replay_sha256": runner.sha(parent_replay_path),
        "parent_control_sha256": runner.sha(parent_control_path),
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "choices": choices, "B": protocol["base_rows"][0]["B"]}),
          flush=True)


if __name__ == "__main__":
    main()
