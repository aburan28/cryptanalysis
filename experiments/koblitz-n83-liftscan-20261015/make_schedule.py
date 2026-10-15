#!/usr/bin/env python3
"""Write the frozen run order (`schedule.json`) from `protocol.json`.

Segments, in order:

1. `X`: the exactness runs before any timing: the stage `verifycanon` arm
   (every one of the 12,000,064 words the frozen E-1 stage canonicalizes),
   then the online `verify` arm on Q0 and on each of the 16 fresh points
   (every partner-root word each one-target scan probes).
2. `S1..S16`: stage blocks; each holds the four stage arms once, in the order
   `random.Random(2026101500 + block).shuffle` gives.
3. `Q1, F1, Q2, F2, ..., Q8, F8`: a Q block holds the five IC arms and the
   tuned rho (seed 202610060 + block) on Q0, shuffled with
   `random.Random(2026101600 + block)`; an F segment holds two fresh points,
   each with the two IC arms and the tuned rho (seed 830000 + w), shuffled
   with `random.Random(2026101700 + w)`.

`--check` regenerates the schedule and requires byte identity with the
committed file.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"


def build(protocol):
    design = protocol["design"]
    if hashlib.sha256(B_TARGETS.read_bytes()).hexdigest() != protocol["online"]["targets_file_sha256"]:
        raise ValueError("B's targets.json differs from the protocol's digest")
    targets = json.loads(B_TARGETS.read_text())
    q0 = protocol["online"]["q0"]
    if targets["q0"]["point"] != q0:
        raise ValueError("B's Q0 differs from the protocol's")
    fresh = targets["panel_b"]["points"][:design["fresh_points"]]
    if [entry["seed"] for entry in fresh] != list(range(design["fresh_points"])):
        raise ValueError("fresh points are not seeds 0..15")
    segments = []
    exact = [{"arm": "sV", "point_id": "e1", "point": None, "seed": 0}]
    exact.append({"arm": "qV", "point_id": "q0", "point": q0, "seed": 0})
    exact += [{"arm": "qV", "point_id": "w%02d" % e["seed"], "point": e["point"], "seed": 0} for e in fresh]
    segments.append({"id": "X", "panel": "X", "runs": exact})
    for block in range(1, design["stage_blocks"] + 1):
        runs = [{"arm": arm, "point_id": "e1", "point": None, "seed": 0} for arm in design["stage_arms"]]
        random.Random(2026101500 + block).shuffle(runs)
        segments.append({"id": "S%d" % block, "panel": "S", "block": block, "runs": runs})
    per_segment = design["fresh_points"] // design["q0_blocks"]
    for block in range(1, design["q0_blocks"] + 1):
        runs = [{"arm": arm, "point_id": "q0", "point": q0, "seed": 0} for arm in design["q0_ic_arms"]]
        runs.append({"arm": "rT", "point_id": "q0", "point": q0, "seed": 202610060 + block})
        random.Random(2026101600 + block).shuffle(runs)
        segments.append({"id": "Q%d" % block, "panel": "Q", "block": block, "runs": runs})
        f_runs = []
        for entry in fresh[(block - 1) * per_segment: block * per_segment]:
            w = entry["seed"]
            point_runs = [{"arm": arm, "point_id": "w%02d" % w, "point": entry["point"], "seed": 0}
                          for arm in design["fresh_ic_arms"]]
            point_runs.append({"arm": "rT", "point_id": "w%02d" % w, "point": entry["point"], "seed": 830000 + w})
            random.Random(2026101700 + w).shuffle(point_runs)
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
    path = HERE / "schedule.json"
    if args.check:
        if path.read_text() != text:
            raise SystemExit("schedule.json differs from the schedule the protocol defines")
        print("schedule_verified=" + str(path))
        return
    path.write_text(text)
    print(str(path))


if __name__ == "__main__":
    main()
