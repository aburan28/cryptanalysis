#!/usr/bin/env python3
"""Write the frozen run order (`schedule.json`) from `protocol.json`.

Segments Q1, F(0-3), Q2, F(4-7), ... as the protocol's `design.order` says.
A Q block holds every rho arm x seed and every IC arm once, in the order
`random.Random(2026101400 + block).shuffle` gives; an F segment holds four
fresh points, each with four rho arms x two seeds and one cached IC run, in
the order `random.Random(2026101500 + w).shuffle` gives. `--check` regenerates
the schedule and requires byte identity with the committed file.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"


def build(protocol):
    q_panel = protocol["panels"]["Q"]
    f_panel = protocol["panels"]["F"]
    if hashlib.sha256(B_TARGETS.read_bytes()).hexdigest() != protocol["sources"]["reused_from_B"]["targets_file_sha256"]:
        raise ValueError("B's targets.json differs from the protocol's digest")
    targets = json.loads(B_TARGETS.read_text())
    q0 = protocol["inputs"]["q0"]
    if targets["q0"]["point"] != q0:
        raise ValueError("B's Q0 differs from the protocol's")
    fresh = targets["panel_b"]["points"][:f_panel["points"]]
    seeds = q_panel["rho_seeds"]["SA"] + q_panel["rho_seeds"]["SB"]
    segments = []
    blocks = q_panel["blocks"]
    per_segment = f_panel["points"] // blocks
    for block in range(1, blocks + 1):
        runs = [{"arm": arm, "point_id": "q0", "point": q0, "seed": seed}
                for arm in q_panel["rho_arms"] for seed in seeds]
        runs += [{"arm": arm, "point_id": "q0", "point": q0, "seed": 0,
                  "rank_seed": 20 + block if arm.endswith("f") else 7}
                 for arm in q_panel["ic_arms"]]
        random.Random(2026101400 + block).shuffle(runs)
        segments.append({"id": "Q%d" % block, "panel": "Q", "block": block, "runs": runs})
        f_runs = []
        for entry in fresh[(block - 1) * per_segment: block * per_segment]:
            w = entry["seed"]
            point_runs = [{"arm": arm, "point_id": "w%02d" % w, "point": entry["point"], "seed": seed}
                          for arm in f_panel["rho_arms"] for seed in (830000 + w, 202610061 + w)]
            point_runs += [{"arm": "iB770c", "point_id": "w%02d" % w, "point": entry["point"],
                            "seed": 0, "rank_seed": 7}]
            random.Random(2026101500 + w).shuffle(point_runs)
            f_runs += point_runs
        segments.append({"id": "F%d" % block, "panel": "F", "block": block, "runs": f_runs})
    serial = 0
    for segment in segments:
        for run in segment["runs"]:
            serial += 1
            run["serial"] = serial
    return {"schema": 1, "protocol_kind": protocol["kind"], "segments": segments, "runs": serial}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    text = json.dumps(build(protocol), indent=1, sort_keys=True) + "\n"
    path = HERE / protocol["design"]["schedule_file"]
    if args.check:
        if path.read_text() != text:
            raise SystemExit("schedule.json differs from the schedule the protocol defines")
        print("schedule_verified=" + str(path))
        return
    path.write_text(text)
    print(str(path))


if __name__ == "__main__":
    main()
