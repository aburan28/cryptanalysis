#!/usr/bin/env python3
"""Frozen N131 W14 diagonal-atom pair inverse panel."""

import collections
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from pair_inverse import DiagonalPairInverse, SUPPORT, prior

HERE = Path(__file__).resolve().parent
PRIOR_ORACLE = Path(prior.__file__)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)),
                       ("pair_inverse", HERE / "pair_inverse.py"),
                       ("inputs", HERE / "inputs.json"),
                       ("support", SUPPORT), ("prior_oracle", PRIOR_ORACLE)):
        if sha(path) != protocol["sha256"][name]:
            raise ValueError("frozen digest mismatch: " + name)
    inputs = json.loads((HERE / "inputs.json").read_text())
    if inputs["curve_id"] != protocol["curve_id"]:
        raise ValueError("curve identity changed")
    setup_started = time.monotonic_ns()
    inverse = DiagonalPairInverse()
    setup_ns = time.monotonic_ns()-setup_started
    started = time.monotonic_ns()
    rows = []
    for case in inputs["cases"]:
        if (time.monotonic_ns()-started >
                protocol["panel_wall_cap_seconds"]*10**9):
            rows.append({"kind": case["kind"], "z": case["z"],
                         "status": "NOT_RUN_CAP", "rank": None,
                         "pairs": [], "query_ns": 0})
            continue
        begin = time.monotonic_ns()
        pairs, detail = inverse.joint(case["z"])
        elapsed_ns = time.monotonic_ns()-begin
        expected = tuple(sorted((case["a"], case["b"]))) if \
            case["kind"] == "positive" else None
        if expected is not None and expected not in pairs:
            raise AssertionError("positive diagonal pair not recovered")
        row = {"kind": case["kind"], "z": case["z"],
               "status": detail["status"], "rank": detail["rank"],
               "seed_sum": detail["seed_sum"], "pairs": pairs,
               "query_ns": elapsed_ns}
        if expected is not None:
            row["expected_pair"] = expected
        rows.append(row)
        if rss_bytes() > protocol["rss_cap_bytes"]:
            raise MemoryError("frozen panel RSS cap reached")
    wall_ns = time.monotonic_ns()-started
    counts = {kind: dict(collections.Counter(row["status"] for row in rows
                 if row["kind"] == kind)) for kind in ("positive", "trace_zero_uniform")}
    result = {"status": "COMPLETE_DIAGNOSTIC" if all(
        row["status"] != "NOT_RUN_CAP" for row in rows) else "CENSORED_DIAGNOSTIC",
              "candidate_id": None, "proposal_id": protocol["proposal_id"],
              "target_count": 0, "curve_id": protocol["curve_id"],
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path),
              "inputs_sha256": sha(HERE / "inputs.json"),
              "setup_ns": setup_ns, "panel_wall_ns": wall_ns,
              "rows": rows, "status_counts": counts,
              "peak_rss_bytes": rss_bytes()}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "counts": counts, "wall_s": round(wall_ns/1e9, 3)}))


if __name__ == "__main__":
    main()
