#!/usr/bin/env python3
"""Derive the new held-out cold panel before any timing.

`inputs/cold_targets.json`: COUNT public points from B's public hash-to-curve
law (beat `koblitz.compact_orbit.n83_single_target`, domain
`kic-n83-single-target-public-point-v1`) through the pinned harness
`single_target_panel.public_point` in `snapshots/r770`, with the new role
`ROLE` and seeds 0..COUNT-1. No scalar is known for any of them.

COUNT = max(16, power_check.py's chosen size): the power check picks 8 for the
primary; 16 leaves room for the secondary per-point online ratios.

Every point must be in the prime-order subgroup, distinct, and different
from every earlier n=83 panel this law produced: Q0 and B's whole panel B
(`../koblitz-single-target-n83-tier1-20261014/inputs/targets.json`), the 384
scan-order held-out points (role `scanorder-heldout`) and the 576 combined
primary points (role `combined-primary-v1`, branch `claude/n83-combined`),
both regenerated here from the same law. `--check` regenerates and compares.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
OUT = HERE / "inputs" / "cold_targets.json"
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
BEAT = "koblitz.compact_orbit.n83_single_target"
ROLE = "statefold-cold-v1"
EARLIER_ROLES = (("scanorder-heldout", 384), ("combined-primary-v1", 576))


def harness():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)

    beat = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                      .read_text())["beats"][BEAT]
    return panel, beat, panel.cached_curve(dict(beat["curve_fixture"]))


def count():
    power = json.loads((HERE / "analysis" / "power.json").read_text())
    return max(16, power["chosen_panel_size"])


def derive():
    panel, beat, curve = harness()
    domain = beat["target_law"]["domain"]
    earlier = set()
    used = json.loads(B_TARGETS.read_text())
    earlier.add(tuple(used["q0"]["point"]))
    earlier |= {tuple(e["point"]) for e in used["panel_b"]["points"]}
    for role, size in EARLIER_ROLES:
        earlier |= {tuple(str(v) for v in panel.public_point(curve, domain, role, seed)) for seed in range(size)}
    points = []
    for seed in range(count()):
        x, y = panel.public_point(curve, domain, ROLE, seed)
        q = curve.decode([x, y])
        if q is None or curve.mul(q, curve.r) is not None:
            raise ValueError("point %d is not in the prime-order subgroup" % seed)
        if (str(x), str(y)) in earlier:
            raise ValueError("point %d repeats an earlier panel" % seed)
        points.append({"seed": seed, "point": [str(x), str(y)]})
    if len({tuple(e["point"]) for e in points}) != len(points):
        raise ValueError("points repeat")
    return {"schema": 1, "beat_id": BEAT, "domain": domain, "role": ROLE,
            "input_law": panel.input_law(beat).replace("<role>", ROLE), "points": points,
            "scalar_known_to_anyone": False,
            "disjoint_from": ["q0", "panel_b (all points)"] + ["%s seeds 0..%d" % (r, n - 1) for r, n in EARLIER_ROLES],
            "earlier_points_checked": len(earlier),
            "sized_by": "max(16, power_check.py chosen_panel_size)"}


def text(record):
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    record = derive()
    if args.check:
        if OUT.read_text() != text(record):
            raise SystemExit("inputs/cold_targets.json differs from the regenerated points")
        print("targets_verified=" + str(OUT))
        return
    OUT.write_text(text(record))
    print(str(OUT))


if __name__ == "__main__":
    main()
