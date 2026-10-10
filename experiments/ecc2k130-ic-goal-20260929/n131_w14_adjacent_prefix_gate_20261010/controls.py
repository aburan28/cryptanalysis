#!/usr/bin/env python3
"""Frozen uniform-output panel for projected adjacent W14 pair filtering."""
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "controls_protocol.json").read_text())
    dependencies = {"controls": HERE / "controls.py", "run": HERE / "run.py",
                    "first_protocol": HERE / "protocol.json",
                    "first_result": HERE / "result.json"}
    assert protocol["status"] == "FROZEN_BEFORE_RUN"
    assert protocol["sha256"] == {name: sha(path) for name, path in dependencies.items()}
    assert not (HERE / "controls_result.json").exists()
    started = time.monotonic_ns()
    adjacent = run.load_adjacent()
    run.candidate_oracle = adjacent.oracle
    candidate = adjacent.oracle.PairOracle(adjacent.oracle.load_support(run.SUPPORT))
    joint = adjacent.build_joint(candidate)
    rng = random.Random(protocol["seed"])
    values = [rng.getrandbits(131) for _ in range(protocol["control_count"])]
    widths = protocol["free_low_bits"]
    masks = {width: run.invariant_mask(candidate.field, width,
                                       joint["product_basis"]) for width in widths}
    rows = []
    for width in widths:
        for index, z in enumerate(values):
            row = run.gate(candidate, joint, z, width, masks[width])
            rows.append({"width": width, "index": index,
                         "status": row["status"], "rank": row["rank"],
                         "nullity": row["nullity"]})
    measured = time.monotonic_ns() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    result = {"status": "COMPLETE_UNIFORM_PREFIX_PANEL", "candidate_id": None,
              "protocol_sha256": sha(HERE / "controls_protocol.json"),
              "source_sha256": protocol["sha256"], "control_count": len(values),
              "control_digest": hashlib.sha256(b"".join(v.to_bytes(17, "little")
                                                    for v in values)).hexdigest(),
              "free_low_bits": widths,
              "invariant_masks": {str(k): v for k, v in masks.items()},
              "rows": rows, "wall_ns": measured, "peak_rss_bytes": peak}
    if measured > protocol["wall_cap_seconds"] * 1_000_000_000:
        result["status"] = "CENSORED_TIME"
    if peak > protocol["rss_cap_bytes"]:
        result["status"] = "CENSORED_MEMORY"
    (HERE / "controls_result.json").write_text(json.dumps(result, sort_keys=True,
                                                           indent=2) + "\n")
    print(json.dumps({"status": result["status"], "wall_ns": measured,
                      "peak_rss_bytes": peak, "control_count": len(values),
                      "counts": {str(w): sum(row["status"] == "SPAN_REJECT"
                                             for row in rows if row["width"] == w)
                                 for w in widths}}))


if __name__ == "__main__":
    main()
