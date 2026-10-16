#!/usr/bin/env python3
"""Derive the new primary panel of the root-table filter experiment, before any timing.

`inputs/primary_targets.json`: COUNT new public points from B's public
hash-to-curve law (the beat `koblitz.compact_orbit.n83_single_target`, domain
`kic-n83-single-target-public-point-v1`) through the pinned harness
`single_target_panel.public_point` in `snapshots/r770`, with the new role
`ROLE` and seeds 0..COUNT-1. No earlier run has used this role, so no earlier
run has seen these points and none of them motivated the change. No scalar is
known for any of them. COUNT is the size chosen by `power_check.py`
(`analysis/power.json`).

Every point must be in the prime-order subgroup, distinct, and different from
every point of every earlier n=83 panel drawn from the same law, on main and
on the open branches (2026-10-15): Q0 and B's fresh points (role `eval`,
`koblitz-single-target-n83-tier1-20261014`, all of `panel_b`), the 384
scan-order held-out points (role `scanorder-heldout`, main), the 576
combined primary points (role `combined-primary-v1`, `claude/n83-combined`),
the 384 probe-pipeline primary points (role `probepipe-primary-v1`,
`claude/n83-probe-pipeline`) and the 16 state-fold cold points (role
`statefold-cold-v1`, `claude/n83-state-fold`); the earlier roles are
regenerated here. (The section 23 panel of `koblitz-s23-tuned-rho-20261015`
has no n=83 curve; `ic-probe-latency-20261015`, the reconcile and lift_scan
experiments used Q0 and B's points.) `--check` regenerates the file and
compares it with the committed one. `claude/n83-probe-pipeline`'s
`make_targets.py` with the new role and the longer exclusion list.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
PRIMARY = HERE / "inputs" / "primary_targets.json"
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
BEAT = "koblitz.compact_orbit.n83_single_target"
ROLE = "tablefilter-primary-v1"
COUNT = 384
EARLIER_ROLES = (("scanorder-heldout", 384), ("combined-primary-v1", 576), ("probepipe-primary-v1", 384),
                 ("statefold-cold-v1", 16))


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
    power = json.loads((HERE / "analysis" / "power.json").read_text())
    if power["chosen_panel_size"] != COUNT:
        raise ValueError("COUNT differs from power_check.py's chosen panel size")
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
            "sized_by": "power_check.py (analysis/power.json chosen_panel_size)"}


def text(record):
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    record = derive()
    if args.check:
        if PRIMARY.read_text() != text(record):
            raise SystemExit("inputs/primary_targets.json differs from the regenerated points")
        print("targets_verified=" + str(PRIMARY))
        return
    PRIMARY.write_text(text(record))
    print(str(PRIMARY))


if __name__ == "__main__":
    main()
