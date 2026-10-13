#!/usr/bin/env python3
"""Exact high-coordinate translate screen of the N83 rectangle plane."""

import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/n83-geometric-rectangle14-20261012"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
sys.path[:0] = [str(ROOT / "ecc2k130/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]
from curves import Curve  # noqa: E402
from field import Onb  # noqa: E402
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


def affine_raw_values(offset, basis):
    values = [offset]
    for vector in basis:
        values += [x ^ vector for x in values]
    assert len(values) == len(set(values)) == 16384
    return values


def full_orbit_scan(values, onb, curve, orbit):
    keys = set()
    valid = identities = duplicates = 0
    for raw in values:
        point = curve.pointFromX(onb.fromCoords(raw))
        if point is None:
            continue
        valid += 1
        projected = curve.mul(point, 4)
        if projected is None:
            identities += 1
            continue
        key, _, _ = orbit.canonical(projected)
        duplicates += key in keys
        keys.add(key)
    return {"valid_lifts": valid, "identity_projections": identities,
            "duplicate_orbit_seeds": duplicates, "K": len(keys),
            "B": 166 * len(keys)}, keys


def main():
    output = HERE / "screen.json"
    key_file = HERE / "best_keys.bin"
    assert not output.exists() and not key_file.exists(), "refusing to overwrite evidence"
    protocol = json.loads((HERE / "protocol.json").read_text())
    manifest = json.loads((BASE / "basis_manifest.json").read_text())
    prior = json.loads((BASE / "rectangle.json").read_text())
    assert protocol["basis_manifest_sha256"] == sha(BASE / "basis_manifest.json")
    assert protocol["prior_result_sha256"] == sha(BASE / "rectangle.json")
    assert protocol["bridge_sha256"] == sha(BRIDGE)
    assert protocol["field_source_sha256"] == sha(ROOT / "ecc2k130/codegen/field.py")
    assert protocol["curve_source_sha256"] == sha(ROOT / "ecc2k130/codegen/curves.py")
    assert protocol["orbit_source_sha256"] == sha(ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py")
    assert manifest["effective_columns_K"] == prior["folded_columns_K"] == 8532
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    offset = manifest["affine_offset_onb_coordinates"]
    basis = manifest["basis_onb_coordinates"]
    raw_base = affine_raw_values(offset, basis)
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**83, name="a", modulus=t**83+t**7+t**4+t**2+1)
    bridge = json.loads(BRIDGE.read_text())
    gamma = [field(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    one = field(1)
    base = [field(0)]
    for vector in basis:
        converted = field(0)
        while vector:
            low = vector & -vector
            converted += gamma[low.bit_length()-1]
            vector ^= low
        base += [x + converted for x in base]
    assert len(base) == 16384
    poly_offset = field(0)
    value = offset
    while value:
        low = value & -value
        poly_offset += gamma[low.bit_length()-1]
        value ^= low
    assert len(set(base)) == 16384
    started = time.perf_counter_ns()
    rows = []
    for bit in range(12, 83):
        xs = [poly_offset + gamma[bit] + x for x in base]
        inverses = batch_inverses(xs, one)
        valid = sum(int((x + inv).trace()) == 0 for x, inv in zip(xs, inverses))
        rows.append({"translation_bit": bit, "valid_lifts": valid})
        if len(rows) % 8 == 0:
            print(json.dumps({"screened": len(rows),
                              "max_lifts": max(row["valid_lifts"] for row in rows)}), flush=True)
    onb = Onb(83)
    curve = Curve(onb)
    orbit = OrbitKey(onb)
    best_K = 8532
    best_bit = None
    best_geometry = None
    best_keys = None
    full_scans = []
    for row in sorted(rows, key=lambda row: (-row["valid_lifts"], row["translation_bit"])):
        if row["valid_lifts"] <= best_K:
            break
        bit = row["translation_bit"]
        geometry, keys = full_orbit_scan([x ^ (1 << bit) for x in raw_base],
                                         onb, curve, orbit)
        assert geometry["valid_lifts"] == row["valid_lifts"]
        full_scans.append({"translation_bit": bit, **geometry})
        if geometry["K"] > best_K:
            best_K, best_bit, best_geometry, best_keys = geometry["K"], bit, geometry, keys
    if best_keys is None:
        key_file.write_bytes((BASE / "rectangle_keys.bin").read_bytes())
    else:
        key_file.write_bytes(b"".join(k.to_bytes(21, "little") for k in sorted(best_keys)))
    result = {
        "kind": "n83_rectangle14_high_bit_translate_screen_v1",
        "status": "complete_geometry_screen",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(HERE / "protocol.json"),
        "producer_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "rows": rows,
        "full_scans": full_scans,
        "baseline_K": prior["folded_columns_K"],
        "best_K": best_K,
        "best_B": 166 * best_K,
        "best_translation_bit": best_bit,
        "best_geometry": best_geometry,
        "key_file": key_file.name,
        "key_sha256": sha(key_file),
        "wall_ns_exploratory": time.perf_counter_ns()-started,
        "ordinary_query_relation_yield": None,
        "one_target_online_ms": None,
    }
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"best_K": best_K, "best_bit": best_bit,
                      "max_valid": max(row["valid_lifts"] for row in rows),
                      "full_scans": len(full_scans)}), flush=True)


if __name__ == "__main__":
    main()
