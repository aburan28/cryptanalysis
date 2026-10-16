#!/usr/bin/env python3
"""Derive the new primary panel P and check the old held-out panel, before any timing.

* `inputs/primary_targets.json`: COUNT new public points from B's public
  hash-to-curve law (the beat `koblitz.compact_orbit.n83_single_target`,
  domain `kic-n83-single-target-public-point-v1`) through the pinned harness
  `single_target_panel.public_point` in `snapshots/r770`, with the new role
  `ROLE` and seeds 0..COUNT-1. No earlier run has used this role, so no
  earlier run has seen these points and none of them motivated either
  change. No scalar is known for any of them. COUNT is the size chosen by
  `power_check.py` (`analysis/power.json`).
* `inputs/old_heldout_targets.json`: the 384-point held-out panel of
  `claude/n83-scan-order` (role `scanorder-heldout`, copied from
  `experiments/koblitz-n83-scanorder-20261015/inputs/heldout_targets.json`
  @ af41562e7). It is regenerated here from the same law and must match byte
  for byte. It is a secondary panel only.

Every primary point must be in the prime-order subgroup, distinct, and
different from Q0, B's 16 fresh points and the 384 old held-out points.
`--check` regenerates both files and compares them with the committed ones.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
PRIMARY = HERE / "inputs" / "primary_targets.json"
OLD_HELDOUT = HERE / "inputs" / "old_heldout_targets.json"
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
BEAT = "koblitz.compact_orbit.n83_single_target"
ROLE = "combined-primary-v1"
COUNT = 576
OLD_ROLE, OLD_COUNT = "scanorder-heldout", 384


def harness():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)

    beat = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                      .read_text())["beats"][BEAT]
    return panel, beat, panel.cached_curve(dict(beat["curve_fixture"]))


def panel_record(panel, beat, curve, role, count, extra=None):
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
    record = {"schema": 1, "beat_id": BEAT, "domain": domain, "role": role,
              "input_law": panel.input_law(beat).replace("<role>", role),
              "points": points, "scalar_known_to_anyone": False}
    record.update(extra or {})
    return record


def derive():
    panel, beat, curve = harness()
    old = panel_record(panel, beat, curve, OLD_ROLE, OLD_COUNT)
    power = json.loads((HERE / "analysis" / "power.json").read_text())
    if power["chosen_panel_size"] != COUNT:
        raise ValueError("COUNT differs from power_check.py's chosen panel size")
    primary = panel_record(panel, beat, curve, ROLE, COUNT,
                           {"sized_by": "power_check.py (analysis/power.json chosen_panel_size)"})
    used = json.loads(B_TARGETS.read_text())
    earlier = ({tuple(used["q0"]["point"])} | {tuple(e["point"]) for e in used["panel_b"]["points"]} |
               {tuple(e["point"]) for e in old["points"]})
    if any(tuple(e["point"]) in earlier for e in primary["points"]):
        raise ValueError("a primary point equals Q0, a fresh point or an old held-out point")
    return primary, old


def text(record):
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    primary, old = derive()
    if OLD_HELDOUT.read_text() != text(old):
        raise SystemExit("inputs/old_heldout_targets.json differs from the regenerated scanorder-heldout panel")
    if args.check:
        if PRIMARY.read_text() != text(primary):
            raise SystemExit("inputs/primary_targets.json differs from the regenerated points")
        print("targets_verified=" + str(PRIMARY))
        return
    PRIMARY.write_text(text(primary))
    print(str(PRIMARY))


if __name__ == "__main__":
    main()
