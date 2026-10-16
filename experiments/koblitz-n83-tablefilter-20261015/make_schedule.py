#!/usr/bin/env python3
"""Write the frozen run order (`schedule.json`) from `protocol.json`.

Segments, in the order `design.segment_order` of the protocol:

* `P<s>` (s = 1..6): primary slice s (64 points, seeds 64(s-1) .. 64s-1 of
  `inputs/primary_targets.json`): one process for each of the six primary
  IC arms (`pP`, `pT`, `pTaa`, `pX`, `pK`, `pT29`) and one tuned-rho process
  per point (`rT`, seed 860000 + point seed), all 70 runs shuffled with
  `random.Random(2026104100 + s)`;
* `O<b>` (b = 1): Q0 and B's 16 fresh points in one 17-target process for
  each of `oP`, `oT`, shuffled with `random.Random(2026104300 + b)`.

`--check` regenerates the schedule and requires byte identity with the
committed file. `claude/n83-probe-pipeline`'s `make_schedule.py` with new
arms and seeds.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIMARY = HERE / "inputs" / "primary_targets.json"


def build(protocol):
    design = protocol["design"]
    pins = protocol["sources"]["local_sha256"]
    if hashlib.sha256(PRIMARY.read_bytes()).hexdigest() != pins["primary_targets"]:
        raise ValueError("primary_targets.json differs from the protocol's digest")
    primary = json.loads(PRIMARY.read_text())["points"]
    size = design["slice"]
    if len(primary) != design["primary_points"] or design["primary_points"] != size * design["primary_segments"]:
        raise ValueError("primary panel size differs from the protocol")
    segments = []
    for segment_id in design["segment_order"]:
        panel, index = segment_id[0], int(segment_id[1:])
        if panel == "P":
            lo, hi = (index - 1) * size, index * size
            runs = [{"arm": arm, "point_id": "P%d" % index, "point": None, "seed": 0, "slice": "%d:%d" % (lo, hi)}
                    for arm in design["primary_ic_arms"]]
            for entry in primary[lo:hi]:
                runs.append({"arm": "rT", "point_id": "p%03d" % entry["seed"], "point": entry["point"],
                             "seed": design["rho_seed_base"] + entry["seed"]})
            random.Random(2026104100 + index).shuffle(runs)
        elif panel == "O":
            runs = [{"arm": arm, "point_id": "O%d" % index, "point": None, "seed": 0, "slice": "0:17"}
                    for arm in design["old17_arms"]]
            random.Random(2026104300 + index).shuffle(runs)
        else:
            raise ValueError("unknown segment " + segment_id)
        segments.append({"id": segment_id, "panel": panel, "block": index, "runs": runs})
    counts = {p: sum(1 for s in segments if s["panel"] == p) for p in "PO"}
    if (counts["P"], counts["O"]) != (design["primary_segments"], design["old17_blocks"]):
        raise ValueError("segment counts differ from the protocol")
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
