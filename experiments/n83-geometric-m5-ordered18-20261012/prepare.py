#!/usr/bin/env python3
"""Freeze the ordered-leaf arm against the Q54 N83 base and public point."""

import json
from pathlib import Path

from ordered import HERE, PARENT, runner


def main():
    output = HERE / "protocol.json"
    assert not output.exists(), "refusing to replace a frozen protocol"
    parent_path = PARENT / "protocol.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101254"
    assert parent["workload_id"] == "df4396f4d8fc"
    assert parent["base_rows"][0]["dimension"] == 18
    control_path = HERE / "ordered_control.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    assert control["ordered_source_sha256"] == runner.sha(HERE / "ordered.py")
    assert control["control_source_sha256"] == runner.sha(HERE / "control.py")
    sources = dict(parent["source_sha256"])
    for path in (HERE / "ordered.py", HERE / "control.py",
                 HERE / "ordinary.py", Path(__file__)):
        sources[str(path.relative_to(runner.ROOT))] = runner.sha(path)
    protocol = {
        **parent,
        "kind": "n83_width18_karatsuba_ordered_four_free_leaves_v1",
        "proposal_id": "Q2026101264",
        "candidate_id": None,
        "comparison_variable": "unsigned raw-x order on four interchangeable free leaves",
        "method_comparison_parent": "Q2026101254 width-18 Karatsuba",
        "parent_protocol_sha256": runner.sha(parent_path),
        "parent_result_sha256": runner.sha(PARENT / "width18_ordinary.json"),
        "control_sha256": runner.sha(control_path),
        "leaf_domain": "first leaf normalized to affine seed; four free leaves sorted by unsigned raw x coordinate",
        "source_sha256": sources,
    }
    runner.save(output, protocol)
    print(json.dumps({"status": "frozen", "proposal_id": protocol["proposal_id"],
                      "workload_id": protocol["workload_id"],
                      "B": protocol["base_rows"][0]["B"],
                      "K": protocol["base_rows"][0]["K"]}), flush=True)


if __name__ == "__main__":
    main()
