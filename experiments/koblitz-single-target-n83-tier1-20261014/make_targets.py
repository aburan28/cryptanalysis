#!/usr/bin/env python3
"""Derive the panel's public points with the n=61 harness's own target law.

Panel A and C use the frozen point Q0 of the 2026-10-06 experiment. Panel B
uses the first W public hash-to-curve points of the crypto beat
`koblitz.compact_orbit.n83_single_target` (domain
`kic-n83-single-target-public-point-v1`, role `eval`, seeds 0..W-1), made by
`single_target_panel.public_point` in the pinned snapshot. No scalar is known
for any Panel B point. `--check` regenerates and compares with the committed
`inputs/targets.json` instead of writing it.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "crypto_source_snapshot"
OUTPUT = HERE / "inputs" / "targets.json"


def derive():
    protocol = json.loads((HERE / "tier1_protocol.json").read_text())
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402  (pinned harness)

    beats = json.loads((SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")
                       .read_text())["beats"]
    beat = beats[protocol["harness"]["beat_id"]]
    curve = panel.cached_curve(dict(beat["curve_fixture"]))
    q0 = json.loads((SNAPSHOT / protocol["inputs"]["frozen_target"]).read_text().splitlines()[0])
    q0 = [int(v) for v in q0]
    q0_point = curve.decode(q0)
    if q0_point is None or curve.mul(q0_point, curve.r) is not None:
        raise ValueError("frozen Q0 is not in the prime-order subgroup")
    domain = beat["target_law"]["domain"]
    count = int(protocol["panels"]["B"]["targets"])
    eval_points = [{"seed": seed, "point": [str(v) for v in panel.public_point(curve, domain, "eval", seed)]}
                   for seed in range(count)]
    if any(entry["point"] == [str(v) for v in q0] for entry in eval_points):
        raise ValueError("a Panel B point equals Q0")
    if len({tuple(entry["point"]) for entry in eval_points}) != count:
        raise ValueError("Panel B points repeat")
    return {
        "schema": 1,
        "beat_id": protocol["harness"]["beat_id"],
        "q0": {"source": protocol["inputs"]["frozen_target"], "point": [str(v) for v in q0],
               "scalar_known_to_arms": False},
        "panel_b": {"domain": domain, "role": "eval", "input_law": panel.input_law(beat),
                    "points": eval_points, "scalar_known_to_anyone": False},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = derive()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("inputs/targets.json differs from the regenerated public points")
        print("targets_verified=" + str(OUTPUT))
        return
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(text)
    print(str(OUTPUT))


if __name__ == "__main__":
    main()
