#!/usr/bin/env python3
"""Exact width-11 one-coordinate affine-shift census on the N83 curve."""

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
CODEGEN = ROOT / "ecc2k130/codegen"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_ratio(top, bottom):
    with localcontext() as ctx:
        ctx.prec = 50
        return str(Decimal(top) / Decimal(bottom))


def scan(label, offset, onb, curve, orbit):
    keys = set()
    valid = invalid = identities = duplicates = 0
    started = time.perf_counter_ns()
    for seed in range(1 << 11):
        x = offset ^ seed
        if x == 0:
            invalid += 1
            continue
        point = curve.pointFromX(onb.fromCoords(x))
        if point is None:
            invalid += 1
            continue
        valid += 1
        projected = curve.mul(point, 4)
        if projected is None:
            identities += 1
            continue
        key, _, _ = orbit.canonical(projected)
        if key in keys:
            duplicates += 1
        keys.add(key)
    assert valid + invalid == 2048
    assert valid - identities - duplicates == len(keys)
    return ({"shift_coordinate": label, "offset_onb_coordinates": offset,
             "valid_lifts": valid, "invalid_or_zero_lifts": invalid,
             "identity_projections": identities,
             "duplicate_orbit_seeds": duplicates,
             "folded_columns_K": len(keys),
             "actual_usable_points_B_before_folding": 166 * len(keys),
             "scan_wall_ns_exploratory": time.perf_counter_ns() - started}, keys)


def main():
    output = HERE / "census.json"
    key_path = HERE / "best_keys.bin"
    assert not output.exists() and not key_path.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert protocol["dimension"] == 11
    assert protocol["offset_coordinates"] == [None] + list(range(11, 83))
    assert sha(Path(__file__)) == protocol["source_sha256"][str(Path(__file__).relative_to(ROOT))]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest
    prior = ROOT / protocol["frontier_file"]
    assert sha(prior) == protocol["frontier_sha256"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    order = protocol["subgroup_order"]
    assert curves.isPrimeBig(order)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    rows = []
    best_row = None
    best_keys = None
    for label in protocol["offset_coordinates"]:
        offset = 0 if label is None else 1 << label
        row, keys = scan(label, offset, onb, curve, orbit)
        rows.append(row)
        if best_row is None or row["folded_columns_K"] > best_row["folded_columns_K"]:
            best_row, best_keys = row, keys
        print(json.dumps({"shift_coordinate": label,
                          "K": row["folded_columns_K"],
                          "valid": row["valid_lifts"]}), flush=True)
    previous = next(row for row in rows if row["shift_coordinate"] == 81)
    expected = next(row for row in json.loads(prior.read_text())["rows"]
                    if row["dimension"] == 11 and
                    row["offset_onb_coordinates"] == 1 << 81)
    assert previous["folded_columns_K"] == expected["folded_columns_K"]
    assert previous["valid_lifts"] == expected["valid_lifts"]
    assert previous["duplicate_orbit_seeds"] == expected["duplicate_orbit_seeds"]
    key_path.write_bytes(b"".join(k.to_bytes(21, "little") for k in sorted(best_keys)))
    B = best_row["actual_usable_points_B_before_folding"]
    record = {
        "kind": "n83_width11_one_coordinate_shift_census_v1",
        "status": "complete_geometry_stage",
        "curve_id": protocol["curve_id"],
        "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "rows": rows,
        "coordinates_0_through_10": "identical to the unshifted width-11 subspace",
        "best_shift_coordinate": best_row["shift_coordinate"],
        "best_K": best_row["folded_columns_K"],
        "best_B": B,
        "best_six_subset_uniform_target_first_moment": exact_ratio(math.comb(B, 6), order),
        "best_key_file": key_path.name,
        "best_key_sha256": sha(key_path),
        "baseline_shift_coordinate": 81,
        "baseline_K": previous["folded_columns_K"],
        "baseline_B": previous["actual_usable_points_B_before_folding"],
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "ordinary_query_relation_yield": None,
        "novel_rank_per_query": None,
        "one_target_online_ms": None,
    }
    output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
