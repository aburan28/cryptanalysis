#!/usr/bin/env python3
"""Derive the new held-out cold panel before any timing.

`inputs/cold_targets.json`: COUNT public points from B's public hash-to-curve
law (beat `koblitz.compact_orbit.n83_single_target`, domain
`kic-n83-single-target-public-point-v1`) through the pinned harness
`single_target_panel.public_point` in `snapshots/r770`, with the new role
`ROLE` and seeds 0..COUNT-1. No earlier run has used this role, and no
scalar is known for any of the points.

Every point must be in the prime-order subgroup, distinct, and different
from every earlier n=83 panel of this law on main (2026-10-16): Q0 and B's
fresh points (role `eval`, `../koblitz-single-target-n83-tier1-20261014/
inputs/targets.json`), the 384 scan-order held-out points
(`scanorder-heldout`), the 576 combined primary points
(`combined-primary-v1`), the 384 probe-pipeline primary points
(`probepipe-primary-v1`), the 16 state-fold cold points
(`statefold-cold-v1`), the 384 table-filter primary points
(`tablefilter-primary-v1`) and the 20 stacked cold points
(`stacked-cold-v1`, run 38862448935), all regenerated here from the same law.

COUNT = 20 (the power check sizes the rank blocks, not the cold panel: the
cold arms of baseline and candidate run the same code, so the points only
carry the cold term of the end-to-end cost; 20 keep its interval narrow).
This is `koblitz-n83-stacked-20261016`'s `make_targets.py` with the new role,
a fixed count and the stacked panel added to the exclusion list.
`--check` regenerates and compares.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
PRIMARY = HERE / "inputs" / "cold_targets.json"
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
BEAT = "koblitz.compact_orbit.n83_single_target"
ROLE = "rankcut-cold-v1"
COUNT = 20
EARLIER_ROLES = (("scanorder-heldout", 384), ("combined-primary-v1", 576), ("probepipe-primary-v1", 384),
                 ("statefold-cold-v1", 16), ("tablefilter-primary-v1", 384), ("stacked-cold-v1", 20))


def harness():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)

    beat = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                      .read_text())["beats"][BEAT]
    return panel, beat, panel.cached_curve(dict(beat["curve_fixture"]))


def points_of(panel, beat, curve, role, count):
    domain = beat["target_law"]["domain"]
    points = []
    for seed in range(count):
        x, y = panel.public_point(curve, domain, role, seed)
        q = curve.decode([x, y])
        if q is None or curve.mul(q, curve.r) is not None:
            raise ValueError("%s point %d is not in the prime-order subgroup" % (role, seed))
        points.append({"seed": seed, "point": [str(x), str(y)]})
    if len({tuple(e["point"]) for e in points}) != count:
        raise ValueError("%s points repeat" % role)
    return points


def derive():
    panel, beat, curve = harness()
    primary = points_of(panel, beat, curve, ROLE, COUNT)
    used = json.loads(B_TARGETS.read_text())
    earlier = {tuple(used["q0"]["point"])} | {tuple(e["point"]) for e in used["panel_b"]["points"]}
    for role, count in EARLIER_ROLES:
        earlier |= {tuple(e["point"]) for e in points_of(panel, beat, curve, role, count)}
    if any(tuple(e["point"]) in earlier for e in primary):
        raise ValueError("a primary point equals a point of an earlier n=83 panel")
    return {"schema": 1, "beat_id": BEAT, "domain": beat["target_law"]["domain"], "role": ROLE,
            "input_law": panel.input_law(beat).replace("<role>", ROLE), "points": primary,
            "scalar_known_to_anyone": False,
            "disjoint_from": ["q0", "eval (B's panel_b, %d points)" % len(used["panel_b"]["points"])] +
                             ["%s (%d points)" % rc for rc in EARLIER_ROLES],
            "sized_by": "fixed 20 (power_check.py sizes the rank blocks)"}


def text(record):
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    record = derive()
    if args.check:
        if PRIMARY.read_text() != text(record):
            raise SystemExit("inputs/cold_targets.json differs from the regenerated points")
        print("targets_verified=" + str(PRIMARY))
        return
    PRIMARY.write_text(text(record))
    print(str(PRIMARY))


if __name__ == "__main__":
    main()
