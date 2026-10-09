#!/usr/bin/env python3
"""Exact N41 suffix x-orbits grouped by two still-free seed sums."""

import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    if sha(Path(__file__)) != protocol["source_sha256"]["produce.py"]:
        raise ValueError("producer source changed after freeze")
    for key, location in protocol["inputs"].items():
        if sha(Path(location)) != protocol["input_sha256"][key]:
            raise ValueError(f"frozen input changed: {key}")
    if (HERE / "x_orbits.bin").exists() or (HERE / "production.json").exists():
        raise FileExistsError("preserve first x-orbit production")
    sign_path = Path(protocol["inputs"]["sign_source"])
    spec = importlib.util.spec_from_file_location("frozen_sign_source", sign_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import frozen sign-orbit domain source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, geometry, _, curve = module.load_inputs()
    if (geometry["curve_id"] != protocol["curve_id"] or
            geometry["public_target_q"] != protocol["public_target_q"]):
        raise ValueError("frozen curve or target changed")
    domains = []
    negations = []
    for rotation in protocol["suffix_pair_rotations"]:
        domain, negatives = module.build_domain(
            curve, geometry["point_rows_by_unique_rotation"][str(rotation)])
        domains.append(domain)
        negations.append(negatives)
    source_sign = json.loads(Path(protocol["inputs"]["sign_result"]).read_text())
    if (source_sign["status"] != "PASS_EXACT_SIGN_ORBITS_AND_X_FIBERS" or
            source_sign["free_sign_orbits"] != protocol["expected_orbits"]):
        raise ValueError("prior sign-orbit certificate changed")
    start = time.monotonic_ns()
    status = "RUNNING"
    error = None
    records = bytearray()
    bins = [0] * (63 * 63)
    counts = {"pair_combinations_examined": 0, "column_rejects": 0,
              "inverse_orbit_rejects": 0, "accepted_orbits": 0}
    try:
        for i, left in enumerate(domains[0]):
            for j, right in enumerate(domains[1]):
                counts["pair_combinations_examined"] += 1
                if left[1] & right[1]:
                    counts["column_rejects"] += 1
                    continue
                if i * 1956 + j >= negations[0][i] * 1956 + negations[1][j]:
                    counts["inverse_orbit_rejects"] += 1
                    continue
                point = curve.add(left[0], right[0])
                if point is None or point[0] & 1:
                    raise ValueError("valid orbit has identity or odd-trace x")
                s, t = left[2], right[2]
                if not 1 <= s <= 63 or not 1 <= t <= 63:
                    raise ValueError("seed-sum range changed")
                records.extend(bytes((s, t)) + point[0].to_bytes(6, "little") +
                               i.to_bytes(2, "little") + j.to_bytes(2, "little"))
                counts["accepted_orbits"] += 1
                bins[(s - 1) * 63 + (t - 1)] += 1
            if i % 16 == 0:
                elapsed = (time.monotonic_ns() - start) / 1e9
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if sys.platform != "darwin":
                    peak *= 1024
                if elapsed >= protocol["limits"]["producer_wall_seconds"]:
                    raise TimeoutError("producer wall cap")
                if peak >= protocol["limits"]["rss_bytes"]:
                    raise MemoryError("producer RSS cap")
        if (counts["accepted_orbits"] != protocol["expected_orbits"] or
                min(bins) != protocol["expected_bin_min"] or
                max(bins) != protocol["expected_bin_max"]):
            raise ValueError("sign-orbit or seed-bin counts differ")
        status = "EXACT_X_ORBITS_WRITTEN"
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        status = "TIME_CAP" if isinstance(exc, TimeoutError) else (
            "MEMORY_CAP" if isinstance(exc, MemoryError) else "PRODUCER_FAILURE")
    if status == "EXACT_X_ORBITS_WRITTEN":
        (HERE / "x_orbits.bin").write_bytes(records)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    receipt = {"status": status, "error": error, "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "curve_id": protocol["curve_id"],
               "counts": counts, "bin_count": len(bins),
               "bin_min": min(bins), "bin_max": max(bins),
               "x_orbits_sha256": sha(HERE / "x_orbits.bin") if status == "EXACT_X_ORBITS_WRITTEN" else None,
               "source_sha256": sha(Path(__file__)),
               "protocol_sha256": sha(protocol_path),
               "wall_ns": time.monotonic_ns() - start,
               "peak_rss_bytes": peak}
    (HERE / "production.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "orbits": counts["accepted_orbits"],
                      "wall_s": receipt["wall_ns"] / 1e9}))
    if status != "EXACT_X_ORBITS_WRITTEN":
        raise RuntimeError(status)


if __name__ == "__main__":
    main()
