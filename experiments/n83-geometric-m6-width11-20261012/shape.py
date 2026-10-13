#!/usr/bin/env python3
"""Screen the six-leaf width-11 circuit against the frozen public target."""

import json
from pathlib import Path

from m6 import HERE, PARENT, build, runner, selfcheck


def main():
    output = HERE / "shape.json"
    assert not output.exists()
    parent_path = PARENT / "width18_ordinary.json"
    parent = json.loads(parent_path.read_text())
    assert parent["workload_id"] == "df4396f4d8fc"
    assert parent["formula_target_choice"] == 0
    onb = runner.field.Onb(83)
    arithmetic = selfcheck(onb)
    formula, leaves, intermediate, _ = build(onb, parent["formula_target_x"])
    assert len(leaves) == 6 and len(intermediate) == 4
    receipt = {
        "status": "PASS", "kind": "n83_shifted_width11_six_leaf_shape",
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "target_x_onb": parent["formula_target_x"],
        "target_choice": 0, "formula_shape": runner.stats(formula),
        "karatsuba_selfcheck": arithmetic,
        "m6_source_sha256": runner.sha(HERE / "m6.py"),
        "screen_source_sha256": runner.sha(Path(__file__)),
        "parent_result_sha256": runner.sha(parent_path),
    }
    runner.save(output, receipt)
    print(json.dumps({"status": "PASS", "formula_shape": receipt["formula_shape"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
