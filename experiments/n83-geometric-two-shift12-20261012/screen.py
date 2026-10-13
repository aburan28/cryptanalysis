#!/usr/bin/env python3
"""Exact lift screen and full replay of competitive width-12 N83 offsets."""

import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
CODEGEN = ROOT / "ecc2k130/codegen"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path[:0] = [str(CODEGEN), str(PAIR)]

import curves  # noqa: E402
import field as onb_field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_inverses(values, one):
    prefix = [one]
    for value in values:
        assert value != 0
        prefix.append(prefix[-1] * value)
    inverse = prefix[-1]**-1
    result = [None] * len(values)
    for index in range(len(values) - 1, -1, -1):
        result[index] = inverse * prefix[index]
        inverse *= values[index]
    assert inverse == one
    return result


def exact_keys(offset, onb, curve, orbit):
    keys = set()
    valid = identities = duplicates = 0
    for seed in range(4096):
        point = curve.pointFromX(onb.fromCoords(offset ^ seed))
        if point is None:
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
    return {"valid_lifts": valid, "identity_projections": identities,
            "duplicate_orbit_seeds": duplicates, "K": len(keys),
            "B": 166 * len(keys)}, keys


def main():
    output = HERE / "screen.json"
    key_path = HERE / "best_keys.bin"
    progress = HERE / "screen.progress.jsonl"
    assert not output.exists() and not key_path.exists() and not progress.exists(), \
        "refusing to overwrite evidence"
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert protocol["dimension"] == 12
    assert protocol["external_bit_indices"] == list(range(12, 83))
    assert protocol["selection_rule"] == "screen all two-bit offsets; fully replay descending valid lifts while valid lifts exceed current best K"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(BRIDGE) == protocol["bridge_sha256"]
    previous = ROOT / protocol["prior_protocol_file"]
    assert sha(previous) == protocol["prior_protocol_sha256"]
    prior = json.loads(previous.read_text())
    prior_row = next(row for row in prior["base_rows"] if row["dimension"] == 12)
    assert prior_row["K"] == protocol["baseline_K"] == 2130
    prior_keys = ROOT / protocol["prior_key_file"]
    assert sha(prior_keys) == protocol["prior_key_sha256"]
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"

    bridge = json.loads(BRIDGE.read_text())
    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    poly = GF(2**83, name="z", modulus=modulus)
    gamma = [poly(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    assert len(gamma) == 83
    base = [poly(0)]
    for element in gamma[:12]:
        base += [value + element for value in base]
    assert len(set(base)) == 4096
    one = poly(1)
    pairs = list(itertools.combinations(protocol["external_bit_indices"], 2))
    assert len(pairs) == 2485
    rows = []
    started = time.perf_counter_ns()
    with progress.open("w") as stream:
        for i, j in pairs:
            offset = gamma[i] + gamma[j]
            xs = [offset + seed for seed in base]
            assert all(x != 0 for x in xs)
            inverse = batch_inverses(xs, one)
            valid = sum(int((x + inv).trace()) == 0 for x, inv in zip(xs, inverse))
            row = {"shift_coordinates": [i, j], "valid_lifts": valid}
            rows.append(row)
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            if len(rows) % 64 == 0:
                stream.flush()
                print(json.dumps({"completed": len(rows),
                                  "max_valid": max(r["valid_lifts"] for r in rows)}),
                      flush=True)
    screen_wall_ns = time.perf_counter_ns() - started

    onb = onb_field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    competitive = []
    best_K = protocol["baseline_K"]
    best_B = 166 * best_K
    best_pair = [82]
    best_geometry = None
    best_key_bytes = prior_keys.read_bytes()
    for row in sorted(rows, key=lambda row: (-row["valid_lifts"], row["shift_coordinates"])):
        if row["valid_lifts"] <= best_K:
            break
        i, j = row["shift_coordinates"]
        result, keys = exact_keys((1 << i) ^ (1 << j), onb, curve, orbit)
        assert result["valid_lifts"] == row["valid_lifts"]
        competitive.append({**row, **result})
        if result["K"] > best_K:
            best_K, best_B, best_pair = result["K"], result["B"], [i, j]
            best_geometry = result
            best_key_bytes = b"".join(k.to_bytes(21, "little")
                                      for k in sorted(keys))
    key_path.write_bytes(best_key_bytes)
    report = {
        "kind": "n83_width12_two_coordinate_shift_screen_v1",
        "status": "complete_geometry_screen",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime),
        "rows": rows,
        "competitive_full_scans": competitive,
        "baseline_K": protocol["baseline_K"],
        "best_shift_coordinates": best_pair,
        "best_full_scan": best_geometry,
        "best_K": best_K,
        "best_B": best_B,
        "best_key_file": key_path.name,
        "best_key_sha256": sha(key_path),
        "screen_wall_ns_exploratory": screen_wall_ns,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "ordinary_query_relation_yield": None,
        "novel_rank_per_query": None,
        "one_target_online_ms": None,
    }
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "best_K": best_K,
                      "best_shift_coordinates": best_pair,
                      "competitive_scans": len(competitive)}), flush=True)


if __name__ == "__main__":
    main()
