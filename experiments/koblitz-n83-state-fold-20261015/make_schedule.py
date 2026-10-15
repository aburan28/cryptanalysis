#!/usr/bin/env python3
"""Write the frozen run order (`schedule.json`) from `protocol.json`.

Segments, in the protocol's `design.segment_order`:

* `C<i>` (i = 1..points): cold point s<i-1> (`inputs/cold_targets.json`):
  one fresh process for each IC cold arm (cB, cF, cFaa, cX, cBL, cFL, cBF,
  cFF, cFI) and one tuned-rho process (rT, seed 850000 + point seed),
  shuffled with `random.Random(2026101600 + i)`;
* `K<b>` (b = 1, 2): one rank-stage process each of kB and kN on the block's
  unit with the block's rank seed, shuffled with `random.Random(2026101700 + b)`.

`--check` regenerates and requires byte identity with the committed file.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = HERE / "inputs" / "cold_targets.json"


def build(protocol):
    design = protocol["design"]
    if hashlib.sha256(TARGETS.read_bytes()).hexdigest() != protocol["sources"]["local_sha256"]["cold_targets"]:
        raise ValueError("cold_targets.json differs from the protocol's digest")
    points = {"s%03d" % e["seed"]: e for e in json.loads(TARGETS.read_text())["points"]}
    if len(points) != design["cold_points"]:
        raise ValueError("cold panel size differs from the protocol")
    blocks = {b["id"]: b for b in design["rank_blocks"]}
    segments = []
    for segment_id in design["segment_order"]:
        panel, index = segment_id[0], int(segment_id[1:])
        if panel == "C":
            entry = points["s%03d" % (index - 1)]
            runs = []
            for arm in design["cold_arms"]:
                seed = design["rho_seed_base"] + entry["seed"] if arm == "rT" else 7
                runs.append({"arm": arm, "point_id": "s%03d" % entry["seed"], "point": entry["point"], "seed": seed})
            random.Random(2026101600 + index).shuffle(runs)
        elif panel == "K":
            block = blocks[segment_id]
            entry = points[block["unit"]]
            runs = [{"arm": arm, "point_id": block["unit"], "point": entry["point"], "seed": block["rank_seed"]}
                    for arm in ("kB", "kN")]
            random.Random(2026101700 + index).shuffle(runs)
        else:
            raise ValueError("unknown segment " + segment_id)
        segments.append({"id": segment_id, "panel": panel, "block": index, "runs": runs})
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
