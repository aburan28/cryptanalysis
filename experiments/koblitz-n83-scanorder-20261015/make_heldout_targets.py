#!/usr/bin/env python3
"""Derive the held-out public points (secondary panel H), before any timing.

The points use B's public hash-to-curve law (the crypto beat
`koblitz.compact_orbit.n83_single_target`, domain
`kic-n83-single-target-public-point-v1`) through the pinned harness
`single_target_panel.public_point` in `snapshots/r770`, with role
`scanorder-heldout` and seeds 0..47. That role is new, so no earlier run has
seen these points, and none of them motivated the hypothesis (the 16 fresh
points and Q0 did). No scalar is known for any of them. `--check`
regenerates and compares with the committed `inputs/heldout_targets.json`.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
OUTPUT = HERE / "inputs" / "heldout_targets.json"
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
ROLE = "scanorder-heldout"
COUNT = 384
BEAT = "koblitz.compact_orbit.n83_single_target"


def derive():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)

    beat = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                      .read_text())["beats"][BEAT]
    curve = panel.cached_curve(dict(beat["curve_fixture"]))
    domain = beat["target_law"]["domain"]
    points = []
    for seed in range(COUNT):
        x, y = panel.public_point(curve, domain, ROLE, seed)
        q = curve.decode([x, y])
        if q is None or curve.mul(q, curve.r) is not None:
            raise ValueError("held-out point %d is not in the prime-order subgroup" % seed)
        points.append({"seed": seed, "point": [str(x), str(y)]})
    used = json.loads(B_TARGETS.read_text())
    earlier = {tuple(used["q0"]["point"])} | {tuple(e["point"]) for e in used["panel_b"]["points"]}
    if any(tuple(e["point"]) in earlier for e in points):
        raise ValueError("a held-out point equals Q0 or a fresh point")
    if len({tuple(e["point"]) for e in points}) != COUNT:
        raise ValueError("held-out points repeat")
    return {"schema": 1, "beat_id": BEAT, "domain": domain, "role": ROLE,
            "input_law": panel.input_law(beat).replace("<role>", ROLE),
            "points": points, "scalar_known_to_anyone": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(derive(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("inputs/heldout_targets.json differs from the regenerated points")
        print("heldout_verified=" + str(OUTPUT))
        return
    OUTPUT.write_text(text)
    print(str(OUTPUT))


if __name__ == "__main__":
    main()
