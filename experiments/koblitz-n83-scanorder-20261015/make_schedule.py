#!/usr/bin/env python3
"""Write the frozen run order (`schedule.json`) from `protocol.json`.

Segments, in order Q1, F1, Q2, F2, H1, Q3, F3, H2, ..., Q7, F7, H6, Q8, F8:

* `Q<b>` (b = 1..8): the four IC arms on Q0 (`qB`, `qP`, `qBaa`, `qH`) and
  the tuned rho (seed 202610060 + b), shuffled with
  `random.Random(2026101800 + b)`;
* `F<b>`: two of B's fresh points (w = 2b-2, 2b-1), each with the four IC
  arms (`fB`, `fP`, `fBaa`, `fH`) and the tuned rho (seed 830000 + w, B's
  rule), each point's five runs shuffled with `random.Random(2026101900 + w)`;
* `H<h>` (h = 1..6): held-out slice h (64 points, seeds 64(h-1) .. 64h-1 of
  `inputs/heldout_targets.json`), one `hB` and one `hP` process, shuffled
  with `random.Random(2026102000 + h)`.

`--check` regenerates the schedule and requires byte identity with the
committed file. Adapted from `../koblitz-n83-liftscan-20261015/make_schedule.py`.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
B_TARGETS = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"
HELDOUT = HERE / "inputs" / "heldout_targets.json"


def build(protocol):
    design = protocol["design"]
    if hashlib.sha256(B_TARGETS.read_bytes()).hexdigest() != protocol["online"]["targets_file_sha256"]:
        raise ValueError("B's targets.json differs from the protocol's digest")
    if hashlib.sha256(HELDOUT.read_bytes()).hexdigest() != protocol["sources"]["local_sha256"]["heldout_targets"]:
        raise ValueError("heldout_targets.json differs from the protocol's digest")
    targets = json.loads(B_TARGETS.read_text())
    q0 = protocol["online"]["q0"]
    if targets["q0"]["point"] != q0:
        raise ValueError("B's Q0 differs from the protocol's")
    fresh = targets["panel_b"]["points"][:design["fresh_points"]]
    if [entry["seed"] for entry in fresh] != list(range(design["fresh_points"])):
        raise ValueError("fresh points are not seeds 0..15")
    heldout = json.loads(HELDOUT.read_text())["points"]
    size = design["heldout_slice"]
    if len(heldout) != design["heldout_points"] or len(heldout) != size * design["heldout_segments"]:
        raise ValueError("held-out panel size differs from the protocol")
    per_segment = design["fresh_points"] // design["q0_blocks"]
    segments = []
    h_after = set(design["heldout_after_f_blocks"])
    h_next = 1
    for block in range(1, design["q0_blocks"] + 1):
        runs = [{"arm": arm, "point_id": "q0", "point": q0, "seed": 0} for arm in design["q0_ic_arms"]]
        runs.append({"arm": "rT", "point_id": "q0", "point": q0, "seed": 202610060 + block})
        random.Random(2026101800 + block).shuffle(runs)
        segments.append({"id": "Q%d" % block, "panel": "Q", "block": block, "runs": runs})
        f_runs = []
        for entry in fresh[(block - 1) * per_segment: block * per_segment]:
            w = entry["seed"]
            point_runs = [{"arm": arm, "point_id": "w%02d" % w, "point": entry["point"], "seed": 0}
                          for arm in design["fresh_ic_arms"]]
            point_runs.append({"arm": "rT", "point_id": "w%02d" % w, "point": entry["point"], "seed": 830000 + w})
            random.Random(2026101900 + w).shuffle(point_runs)
            f_runs += point_runs
        segments.append({"id": "F%d" % block, "panel": "F", "block": block, "runs": f_runs})
        if block in h_after:
            lo, hi = (h_next - 1) * size, h_next * size
            h_runs = [{"arm": arm, "point_id": "h%d" % h_next, "point": None, "seed": 0,
                       "slice": "%d:%d" % (lo, hi)} for arm in design["heldout_arms"]]
            random.Random(2026102000 + h_next).shuffle(h_runs)
            segments.append({"id": "H%d" % h_next, "panel": "H", "block": h_next, "runs": h_runs})
            h_next += 1
    if h_next - 1 != design["heldout_segments"]:
        raise ValueError("held-out segments differ from the protocol")
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
