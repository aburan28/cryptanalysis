"""The frozen panels of the n=83 root-table filter experiment, as (unit id, point) lists.

Shared by `arm.py` and `verify_receipt.py`. Units: `p000`.. (primary,
`inputs/primary_targets.json`) and `q0`, `w00`..`w15` (`old17`: Q0 then B's
16 fresh points, from B's `inputs/targets.json`). `claude/n83-probe-pipeline`'s
`panels.py`, unchanged in substance.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"


def panel_points(name):
    """[(unit id, [x, y])] of a panel, in its frozen order."""
    if name == "primary":
        entries = json.loads((HERE / "inputs" / "primary_targets.json").read_text())["points"]
        return [("p%03d" % e["seed"], [int(v) for v in e["point"]]) for e in entries]
    if name == "old17":
        targets = json.loads(B_TARGETS.read_text())
        fresh = targets["panel_b"]["points"][:16]
        return ([("q0", [int(v) for v in targets["q0"]["point"]])] +
                [("w%02d" % e["seed"], [int(v) for v in e["point"]]) for e in fresh])
    raise ValueError("unknown panel " + name)
