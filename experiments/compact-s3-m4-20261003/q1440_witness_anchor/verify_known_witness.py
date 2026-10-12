#!/usr/bin/env python3
"""Replay Q1439's verified control models in all unpinned Q1440 formulas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PARENT))
import experiment as q1440  # noqa: E402
from q1439_fixed_leaf import experiment as q1439  # noqa: E402
from run_probe import parse_model, sha  # noqa: E402


def main():
    protocol = q1440.check_protocol()
    rows = []
    for n in (53, 83):
        prepared = q1440.inputs(n)
        source = PARENT / "q1439_fixed_leaf/runs" / f"n{n}_control/solver.stdout.txt"
        model = parse_model(source.read_text())
        assert model is not None
        for cell in q1440.CELLS:
            key = f"n{n}_{cell}"
            formula, leaves, mid, selector = q1440.build(prepared, cell)
            assert q1440.stats(formula) == protocol["cells"][key]["formula_stats"]
            q1439.check_formula_model(formula, model)
            checked = q1439.check_relation(prepared, formula, leaves, mid,
                                           selector, model)
            assert checked["status"] == "verified_four_point_relation"
            assert checked["raw_leaf_x"] == prepared["fixture"]["fixture"][
                "raw_leaf_x"]
            rows.append({"key": key, "source_control_model_sha256": sha(source),
                         "verified_relation_status": checked["status"],
                         "raw_leaf_x": checked["raw_leaf_x"],
                         "source_control_target_choice": checked["target_choice"]})
    result = {"kind": "q1440_known_witness_satisfiability_replay",
              "status": "passed", "proposal_id": "Q1440",
              "candidate_id": None, "isogeny": "none",
              "rows": rows, "protocol_sha256": sha(q1440.PROTOCOL),
              "source_sha256": sha(Path(__file__)),
              "scope": "Q1439 verified control model satisfies each Q1440 leaf-free XCNF and independently replays as a four-point relation; it does not measure ordinary query yield"}
    path = HERE / "known_witness_verification.json"
    assert not path.exists(), "refuse to overwrite witness replay"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
