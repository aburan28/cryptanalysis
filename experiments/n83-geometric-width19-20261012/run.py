#!/usr/bin/env python3
"""Enumerate exact shifted N83 geometric width 19."""

import hashlib
import json
import math
import resource
import sys
import time
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEGEN = ROOT / "ecc2k130" / "codegen"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimal_ratio(numerator, denominator):
    with localcontext() as context:
        context.prec = 50
        return str(Decimal(numerator) / Decimal(denominator))


def scan(dimension, offset, onb, curve, orbit, order):
    keys = set()
    valid = invalid = projected_identity = duplicates = 0
    started = time.perf_counter_ns()
    for coordinates in range(1 << dimension):
        raw = coordinates ^ offset
        if raw == 0:
            invalid += 1
            continue
        point = curve.pointFromX(onb.fromCoords(raw))
        if point is None:
            invalid += 1
            continue
        valid += 1
        projected = curve.mul(point, 4)
        if projected is None:
            projected_identity += 1
            continue
        key, _, _ = orbit.canonical(projected)
        if key in keys:
            duplicates += 1
        keys.add(key)
    assert valid + invalid == 1 << dimension
    assert valid - projected_identity - duplicates == len(keys)
    ordered = sorted(keys)
    K = len(keys)
    B = 166 * K
    states = 83 * K * K
    filename = f"d{dimension}_{'linear' if offset == 0 else 'gamma82'}_keys.bin"
    key_path = HERE / filename
    assert not key_path.exists(), "refusing to overwrite a frozen key set"
    key_path.write_bytes(b"".join(key.to_bytes(21, "little") for key in ordered))
    return {
        "dimension": dimension,
        "offset_onb_coordinates": offset,
        "seed_x_count": 1 << dimension,
        "valid_lifts": valid,
        "invalid_or_zero_lifts": invalid,
        "identity_projections": projected_identity,
        "duplicate_orbit_seeds": duplicates,
        "folded_columns_K": K,
        "actual_usable_points_B_before_folding": B,
        "four_subset_first_moment": decimal_ratio(math.comb(B, 4), order),
        "five_subset_first_moment": decimal_ratio(math.comb(B, 5), order),
        "full_pair_root_states": states,
        "compact16_root_payload_bytes": 32 * states,
        "cached_xy_payload_bytes": 64 * states,
        "root_plus_cached_xy_payload_bytes": 96 * states,
        "canonical_key_file": filename,
        "canonical_key_sha256": sha(key_path),
        "scan_wall_ns": time.perf_counter_ns() - started,
    }


def main():
    protocol_path = HERE / "protocol.json"
    runtime_path = HERE / "sage_runtime_info.json"
    output = HERE / "frontier.json"
    assert not output.exists(), "refusing to overwrite a frozen frontier"
    protocol = json.loads(protocol_path.read_text())
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert protocol["dimensions"] == [19]
    assert protocol["offsets"] == [1 << 81]
    order = protocol["subgroup_order"]
    assert curves.isPrimeBig(order)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    rows = []
    for dimension in protocol["dimensions"]:
        for offset in protocol["offsets"]:
            row = scan(dimension, offset, onb, curve, orbit, order)
            rows.append(row)
            print(json.dumps({"dimension": dimension, "offset": offset,
                              "K": row["folded_columns_K"],
                              "root_plus_cached_bytes": row[
                                  "root_plus_cached_xy_payload_bytes"]}), flush=True)
    record = {
        "kind": "n83_exact_shifted_geometric_width19_base",
        "status": "complete_geometry_stage",
        "curve_id": protocol["curve_id"],
        "candidate_id": None,
        "memory_cap_bytes": protocol["memory_cap_bytes"],
        "rows": rows,
        "source_sha256": {"runner": sha(Path(__file__)),
                          "protocol": sha(protocol_path),
                          "sage_runtime_info": sha(runtime_path),
                          "field": sha(CODEGEN / "field.py"),
                          "curves": sha(CODEGEN / "curves.py"),
                          "orbit_key": sha(PAIR / "orbit_key.py")},
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "ordinary_query_relation_yield": None,
        "novel_rank_per_query": None,
        "one_target_online_ms": None,
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
