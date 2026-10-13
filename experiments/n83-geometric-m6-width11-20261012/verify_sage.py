#!/usr/bin/env python3
"""Independently replay N83 six-leaf control and ordinary target result."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from verify_n83_quotient_receipt_sage import raw_to_coords  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "independent_sage_replay.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["curve_id"] == protocol["curve_id"]
    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    gamma = [field(ring([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    inverse = bridge["poly_to_onb_basis_images"]
    assert len(gamma) == len(inverse) == 83
    seeds = {gamma[81]}
    for basis in gamma[:11]:
        seeds |= {value + basis for value in seeds}
    assert len(seeds) == 1 << 11

    def element(raw):
        coords = raw_to_coords(int(raw))
        value = field(0)
        while coords:
            low = coords & -coords
            value += gamma[low.bit_length() - 1]
            coords ^= low
        return value

    def point(raw_pair):
        return curve(element(raw_pair[0]), element(raw_pair[1]))

    def to_onb(value):
        bits = sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))
        coords = 0
        while bits:
            low = bits & -bits
            coords ^= inverse[low.bit_length() - 1]
            bits ^= low
        return coords

    row = protocol["base_rows"][0]
    cache_path = ROOT / row["canonical_x_cache_file"]
    assert sha(cache_path) == row["canonical_x_cache_sha256"]
    cache = cache_path.read_bytes()
    assert len(cache) == 11 * row["K"]
    base_x = {int.from_bytes(cache[i:i + 11], "little")
              for i in range(0, len(cache), 11)}
    assert len(base_x) == row["K"] == 1096

    def canonical_x(P):
        x = P[0]
        return min(to_onb(x ** (2 ** power)) for power in range(83))

    def check_projected(points, public):
        order = protocol["workload"]["subgroup_order"]
        projected = [4 * P for P in points]
        assert all(P != curve(0) and order * P == curve(0)
                   for P in projected)
        assert all(canonical_x(P) in base_x for P in projected)
        assert sum(projected, curve(0)) == public
        return projected

    control_path = HERE / "six_point_control.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    leaves = [point(raw) for raw in control["leaf_points_raw"]]
    assert len(leaves) == 6
    assert all(P[0] in seeds for P in leaves)
    assert [to_onb(P[0]) for P in leaves] == control["leaf_x_onb"]
    u0 = leaves[0] + leaves[1]
    u1 = leaves[2] + leaves[3]
    u2 = leaves[4] + leaves[5]
    u3 = u0 + u1
    assert [point(raw) for raw in control["intermediate_points_raw"]] == [
        u0, u1, u2, u3]
    raw_target = point(control["raw_target"])
    public_control = point(control["public_target"])
    assert u3 + u2 == raw_target
    assert 4 * raw_target == public_control
    check_projected(leaves, public_control)

    result_path = HERE / "width11_m6_ordinary.json"
    result = json.loads(result_path.read_text())
    public = point(protocol["workload"]["public_point_onb_raw"])
    assert protocol["workload"]["subgroup_order"] * public == curve(0)
    rows = [{"kind": "planted_six_point_control", "status": "PASS",
             "result_sha256": sha(control_path)}]
    if result["verified_relation"] is not None:
        relation = result["verified_relation"]
        assert result["status"] == "verified_relation"
        assert relation["status"] == "verified_six_point_relation"
        original = [point(raw) for raw in relation["raw_leaf_points"]]
        assert len(original) == 6
        signed = [P if sign == 1 else -P for P, sign in
                  zip(original, relation["signs"])]
        target = point(relation["raw_target"])
        assert sum(signed, curve(0)) == target
        assert 4 * target == public
        projected = check_projected(signed, public)
        assert projected == [point(raw) for raw in relation["projected_points"]]
        assert [canonical_x(P) for P in projected] == relation["column_keys"]
        rows.append({"kind": "ordinary_public_target", "status": "PASS",
                     "result_sha256": sha(result_path)})
    else:
        rows.append({"kind": "ordinary_public_target",
                     "status": "no_relation_to_replay",
                     "result_sha256": sha(result_path)})
    report = {
        "status": "PASS", "kind": "n83_six_leaf_independent_sage_replay",
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "bridge_sha256": sha(BRIDGE),
        "verifier_source_sha256": sha(Path(__file__)),
        "rows": rows,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": rows}), flush=True)


if __name__ == "__main__":
    main()
