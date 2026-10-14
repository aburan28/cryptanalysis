#!/usr/bin/env python3
"""Freeze full ordinary N83 width-18 Gaussian-matrix comparison."""

import json
from pathlib import Path

from ordinary import HERE, ROOT, PARENT, runner


PILOT = ROOT / "experiments/n83-geometric-m5-gauss18-20261012"


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width18_ordinary.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    pilot_protocol_path = PILOT / "protocol.json"
    pilot_result_path = PILOT / "pilot_result.json"
    control_path = PILOT / "karatsuba_control.json"
    replay_path = PILOT / "sage_relation_replay.json"
    assert json.loads(pilot_protocol_path.read_text())["proposal_id"] == (
        "Q2026101262")
    assert json.loads(pilot_result_path.read_text())["status"] == "bounded_unknown"
    assert json.loads(control_path.read_text())["status"] == "PASS"
    assert json.loads(replay_path.read_text())["status"] == "PASS"
    wrapper = PILOT / "gauss_one.sh"
    pilot = json.loads(pilot_protocol_path.read_text())
    assert runner.sha(wrapper) == pilot["solvers"]["gauss"]["sha256"]
    sources = {**parent["source_sha256"]}
    for path in (wrapper, HERE / "ordinary.py", Path(__file__)):
        sources[str(path.relative_to(ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_gaussian_one_matrix_five_summand_protocol",
        "proposal_id": "Q2026101263",
        "comparison_variable": (
            "admit the smallest CryptoMiniSat Gaussian XOR component, "
            "retaining the exact width-18 base, formula, public point and cap"),
        "method_comparison_parent": "Q2026101254 default CryptoMiniSat",
        "solver": {**parent["solver"], "path": str(wrapper),
                   "sha256": runner.sha(wrapper),
                   "underlying_binary_path": parent["solver"]["path"],
                   "underlying_binary_sha256": parent["solver"]["sha256"],
                   "options": pilot["solvers"]["gauss"]["options"]},
        "source_sha256": sources,
        "parent_karatsuba_protocol_sha256": runner.sha(parent_path),
        "parent_karatsuba_result_sha256": runner.sha(parent_result_path),
        "gauss_pilot_protocol_sha256": runner.sha(pilot_protocol_path),
        "gauss_pilot_result_sha256": runner.sha(pilot_result_path),
        "gauss_control_sha256": runner.sha(control_path),
        "gauss_sage_replay_sha256": runner.sha(replay_path),
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": protocol["base_rows"][0]["B"],
                      "K": protocol["base_rows"][0]["K"]}), flush=True)


if __name__ == "__main__":
    main()
