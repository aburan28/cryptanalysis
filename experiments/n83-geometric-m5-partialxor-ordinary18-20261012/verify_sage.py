#!/usr/bin/env python3
"""Independently replay partial-XOR control and ordinary relation."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FLAT = ROOT / "experiments/n83-geometric-m5-partialxor18-20261012"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from verify_n83_quotient_receipt_sage import raw_to_coords  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "sage_relation_replay.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["curve_id"] == protocol["curve_id"]
    binary = GF(2)
    poly = PolynomialRing(binary, "t")
    t = poly.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    gamma = [field(poly([(int(raw) >> bit) & 1 for bit in range(83)]))
             for raw in bridge["onb_to_poly_basis_images"]]
    seeds = {gamma[81]}
    for basis in gamma[:18]:
        seeds |= {value + basis for value in seeds}
    assert len(seeds) == 1 << 18

    def point(raw_pair):
        def element(raw):
            coords = raw_to_coords(int(raw))
            value = field(0)
            while coords:
                low = coords & -coords
                value += gamma[low.bit_length() - 1]
                coords ^= low
            return value
        return curve(element(raw_pair[0]), element(raw_pair[1]))

    def rotated_seed(x):
        for _ in range(83):
            if x in seeds:
                return True
            x *= x
        return False

    def replay(relation, public, raw_public):
        assert relation["status"] == "verified_five_point_relation"
        power = relation["normalizing_frobenius_power"]
        assert 0 <= power < 83
        original = [point(pair) for pair in relation["raw_leaf_points"]]
        normalized = [point(pair) for pair in relation[
            "normalized_raw_leaf_points"]]
        projected = [point(pair) for pair in relation["projected_points"]]
        assert len(original) == len(normalized) == len(projected) == 5
        for source, image in zip(original, normalized):
            assert curve(source[0] ** (1 << power),
                         source[1] ** (1 << power)) == image
            assert rotated_seed(source[0])
        assert normalized[0][0] in seeds
        order = protocol["workload"]["subgroup_order"]
        for source, sign, image in zip(original, relation["signs"], projected):
            assert sign in (-1, 1)
            assert 4 * (source if sign == 1 else -source) == image
            assert order * image == curve(0)
        assert sum(projected, curve(0)) == public
        assert relation["public_target"] == [str(value) for value in raw_public]

    control_path = FLAT / "karatsuba_control.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    control_public = point(control["replay"]["public_target"])
    replay(control["replay"], control_public,
           control["replay"]["public_target"])
    result_path = HERE / "width18_ordinary.json"
    result = json.loads(result_path.read_text())
    public = point(protocol["workload"]["public_point_onb_raw"])
    assert protocol["workload"]["subgroup_order"] * public == curve(0)
    rows = [{"kind": "locked_control", "status": "PASS",
             "result_sha256": sha(control_path)}]
    if result["verified_relation"] is not None:
        assert result["status"] == "verified_relation"
        assert result["verified_relation"]["choice"] == 0
        replay(result["verified_relation"], public,
               protocol["workload"]["public_point_onb_raw"])
        rows.append({"kind": "ordinary_public_target", "status": "PASS",
                     "result_sha256": sha(result_path)})
    else:
        rows.append({"kind": "ordinary_public_target",
                     "status": "no_relation_to_replay",
                     "result_sha256": sha(result_path)})
    record = {"status": "PASS", "kind": "n83_karatsuba_independent_sage_replay",
              "curve_id": protocol["curve_id"],
              "workload_id": protocol["workload_id"],
              "protocol_sha256": sha(protocol_path),
              "runtime_info_sha256": sha(runtime_path),
              "bridge_sha256": sha(BRIDGE),
              "verifier_source_sha256": sha(Path(__file__)),
              "rows": rows}
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": rows}), flush=True)


if __name__ == "__main__":
    main()
