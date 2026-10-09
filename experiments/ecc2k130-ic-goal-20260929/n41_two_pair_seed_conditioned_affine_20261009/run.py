#!/usr/bin/env python3
"""Exact affine x rank for every N41 suffix seed-sum pair."""

import hashlib
import importlib.util
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
CENSUS = GOAL / "n41_two_free_pair_occupancy_20261009"
SIGN = GOAL / "n41_two_pair_sign_orbit_x_support_20261009"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    protocol = json.loads((HERE / "protocol.json").read_text())
    files = {
        "geometry": CENSUS / "geometry_snapshot.json",
        "arithmetic": CENSUS / "arithmetic_snapshot.py",
        "census_result": CENSUS / "result.json",
        "census_sage_audit": CENSUS / "audit.json",
        "sign_source": SIGN / "run.py",
        "sign_protocol": SIGN / "protocol.json",
        "sign_result": SIGN / "result.json",
        "sign_sage_audit": SIGN / "audit.json",
        "producer": HERE / "run.py",
        "auditor": HERE / "audit.py",
    }
    if {key: sha(path) for key, path in files.items()} != protocol["source_sha256"]:
        raise ValueError("frozen source or input hash differs")
    sign_result = json.loads(files["sign_result"].read_text())
    sign_audit = json.loads(files["sign_sage_audit"].read_text())
    if (sign_result["status"] != "PASS_EXACT_SIGN_ORBITS_AND_X_FIBERS" or
            sign_audit["status"] != "PASS_INDEPENDENT_SAGE_SIGN_AND_X_FIBER_AUDIT" or
            sign_result["free_sign_orbits"] != protocol["expected_sign_orbits"]):
        raise ValueError("prior sign-orbit gate differs")
    spec = importlib.util.spec_from_file_location("frozen_sign_source", files["sign_source"])
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen sign source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, n41, _, curve = module.load_inputs()
    if n41["curve_id"] != protocol["curve_id"] or n41["public_target_q"] != protocol["public_target_q"]:
        raise ValueError("frozen N41 instance differs")
    return protocol, n41, curve, module.build_domain


def add_pivot(pivots, row):
    while row:
        bit = row.bit_length() - 1
        if bit not in pivots:
            pivots[bit] = row
            return True
        row ^= pivots[bit]
    return False


def kernel(pivots, n=41):
    free = sorted(set(range(n)) - set(pivots))
    basis = []
    for bit in free:
        v = 1 << bit
        for p in sorted(pivots):
            if ((pivots[p] & v).bit_count() & 1):
                v |= 1 << p
        if any((row & v).bit_count() & 1 for row in pivots.values()):
            raise ValueError("bad affine kernel")
        basis.append(v)
    return basis


def main():
    if (HERE / "result.json").exists() or (HERE / "started.json").exists():
        raise FileExistsError("preserve first frozen rank execution")
    protocol, n41, curve, build_domain = inputs()
    with (HERE / "started.json").open("x") as out:
        json.dump({"status": "RUNNING", "protocol_sha256": sha(HERE / "protocol.json"),
                   "started_epoch": time.time()}, out, indent=2, sort_keys=True)
        out.write("\n")
    start = time.monotonic_ns()
    status, error = "PRODUCER_FAILURE", None
    bins = {}
    orbit_count = 0
    try:
        domains = []
        negations = []
        for rotation in protocol["suffix_pair_rotations"]:
            pairs, neg = build_domain(curve, n41["point_rows_by_unique_rotation"][str(rotation)])
            domains.append(pairs)
            negations.append(neg)
        for i, left in enumerate(domains[0]):
            for j, right in enumerate(domains[1]):
                if left[1] & right[1]:
                    continue
                if i * 1956 + j >= negations[0][i] * 1956 + negations[1][j]:
                    continue
                orbit_count += 1
                key = "%d,%d" % (left[2], right[2])
                cell = bins.setdefault(key, {"orbits": 0, "pivots": {}, "witnesses": []})
                cell["orbits"] += 1
                if len(cell["pivots"]) == protocol["full_affine_rank"]:
                    continue
                total = curve.add(left[0], right[0])
                if total is None or total[0] & 1:
                    raise ValueError("unexpected identity or non-trace-zero subgroup x")
                row = 1 | ((total[0] >> 1) << 1)
                if add_pivot(cell["pivots"], row):
                    cell["witnesses"].append([i, j, total[0]])
            if i % 16 == 0:
                if time.monotonic_ns() - start > protocol["producer_wall_cap_seconds"] * 10**9:
                    raise TimeoutError("frozen producer wall cap")
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if sys.platform != "darwin":
                    peak *= 1024
                if peak > protocol["rss_cap_bytes"]:
                    raise MemoryError("frozen producer RSS cap")
        if orbit_count != protocol["expected_sign_orbits"] or len(bins) != protocol["expected_seed_sum_pair_bins"]:
            raise ValueError("sign-orbit or seed-sum partition differs")
        status = "COMPLETE_ALL_SEED_BINS"
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, TimeoutError):
            status = "CENSORED_TIME"
        elif isinstance(exc, MemoryError):
            status = "CENSORED_MEMORY"
    output = {}
    for key, cell in sorted(bins.items(), key=lambda item: tuple(map(int, item[0].split(",")))):
        output[key] = {"orbits": cell["orbits"], "rank": len(cell["pivots"]),
                       "witnesses": cell["witnesses"],
                       "affine_equations": kernel(cell["pivots"]) if status == "COMPLETE_ALL_SEED_BINS" else []}
    ranks = [cell["rank"] for cell in output.values()]
    elapsed = time.monotonic_ns() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    if status == "COMPLETE_ALL_SEED_BINS" and (elapsed > protocol["producer_wall_cap_seconds"] * 10**9 or peak > protocol["rss_cap_bytes"]):
        status = "CENSORED_RESOURCE_AFTER_SCAN"
    receipt = {
        "status": status, "error": error, "curve_id": protocol["curve_id"],
        "candidate_id": None, "run_id": None,
        "sign_orbits_scanned": orbit_count, "seed_sum_pair_bins": len(output),
        "min_affine_rank": min(ranks) if ranks else None,
        "max_affine_rank": max(ranks) if ranks else None,
        "deficient_bins": sum(rank < protocol["full_affine_rank"] for rank in ranks),
        "bin_records": output, "producer_wall_ns": elapsed,
        "peak_rss_bytes": peak, "protocol_sha256": sha(HERE / "protocol.json"),
    }
    with (HERE / "result.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "seed_sum_pair_bins", "min_affine_rank",
                       "max_affine_rank", "deficient_bins", "producer_wall_ns")}, sort_keys=True))
    if status != "COMPLETE_ALL_SEED_BINS":
        raise RuntimeError(status)


if __name__ == "__main__":
    main()
