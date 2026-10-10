#!/usr/bin/env sage -python
"""Generate exact signed pair phi outputs under the frozen d13 law."""

import hashlib
import importlib.util
import json
import random
import resource
import sys
import time
from pathlib import Path

import freeze

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "n131_d13_batch_pair_outputs_20261009/pilot.py"


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def load_pilot():
    spec = importlib.util.spec_from_file_location("frozen_pair_pilot", PILOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    sample_path = HERE / "sample.bin"
    result_path = HERE / "sample_result.json"
    if sample_path.exists() or result_path.exists():
        raise FileExistsError("preserve first exact d13 pair sample")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {
            name: freeze.sha(path) for name, path in freeze.paths().items()}:
        raise ValueError("source or checked Sage runtime changed")
    started = time.monotonic_ns()
    pilot = load_pilot()
    (_, onb, raw_curve, sage_curve, valid, sage_points, raw_points,
     to_pb, sage_int) = pilot.setup()
    setup_ns = time.monotonic_ns() - started
    rng = random.Random(protocol["sample_seed"])
    records = bytearray()
    saved = []
    one = onb.one()
    for left in range(protocol["left_count"]):
        partners = sorted(rng.sample(range(left + 1, len(valid)),
                                     protocol["partners_per_left"]))
        for right in partners:
            p = raw_points[left]
            q = raw_points[right]
            for branch, output in enumerate((raw_curve.add(p, q),
                                             raw_curve.add(p, raw_curve.neg(q)))):
                if output is None or output[0] == one:
                    raise ValueError("sampled pair has an exceptional output")
                phi = onb.toCoords(onb.inv(onb.add(output[0], one)))
                records.extend(valid[left].to_bytes(2, "little"))
                records.extend(valid[right].to_bytes(2, "little"))
                records.append(branch)
                records.extend(phi.to_bytes(17, "little"))
                if len(saved) < 64:
                    saved.append({"left_index": left, "right_index": right,
                                  "branch": branch, "x_pb": to_pb(output[0]),
                                  "phi_onb": phi})
        if (time.monotonic_ns() - started >
                protocol["sample_wall_cap_seconds"] * 1_000_000_000 or
                rss_bytes() > protocol["rss_cap_bytes"]):
            failure = {"status": "CENSORED_CAP", "completed_left": left + 1,
                       "elapsed_ns": time.monotonic_ns() - started,
                       "peak_rss_bytes": rss_bytes(),
                       "protocol_sha256": freeze.sha(HERE / "protocol.json")}
            (HERE / "sample_failure.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n")
            raise RuntimeError("frozen sample resource cap")
    if len(records) != protocol["sample_rows"] * protocol["record_bytes"]:
        raise ValueError("frozen sample row count changed")
    sample_path.write_bytes(records)
    result = {"status": "EXACT_PAIR_OUTPUT_SAMPLE", "curve_id": protocol["curve_id"],
              "proposal_id": protocol["proposal_id"], "candidate_id": None,
              "rows": protocol["sample_rows"], "distinct_phi_masks": len({
                  int.from_bytes(records[i+5:i+22], "little")
                  for i in range(0, len(records), 22)}),
              "sample_sha256": freeze.sha(sample_path),
              "first_64": saved, "setup_ns": setup_ns,
              "generation_ns": time.monotonic_ns() - started - setup_ns,
              "total_ns": time.monotonic_ns() - started,
              "peak_rss_bytes": rss_bytes(),
              "protocol_sha256": freeze.sha(HERE / "protocol.json")}
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rows": result["rows"],
                      "distinct_phi_masks": result["distinct_phi_masks"],
                      "total_s": result["total_ns"] / 1e9}))


if __name__ == "__main__":
    main()
