#!/usr/bin/env python3
"""Replay constant-folded N83 width-16 relations in independent Sage."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
sys.path.insert(0, str(PAIR))
from verify_n83_quotient_receipt_sage import raw_to_coords  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "sage_relation_replay.json"
    assert not output.exists(), "independent replay already frozen"
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
    images = bridge["onb_to_poly_basis_images"]
    gamma = [field(poly([(int(value) >> i) & 1 for i in range(83)]))
             for value in images]
    affine_seeds = {}
    for dimension in (16,):
        seeds = {gamma[81]}
        for basis in gamma[:dimension]:
            seeds |= {value + basis for value in seeds}
        assert len(seeds) == 1 << dimension
        affine_seeds[dimension] = seeds

    def belongs_to_rotated_seed(x, dimension):
        for _ in range(83):
            if x in affine_seeds[dimension]:
                return True
            x *= x
        return False

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

    def check_normalization(relation, dimension):
        power = relation["normalizing_frobenius_power"]
        assert 0 <= power < 83
        originals = [point(pair) for pair in relation["raw_leaf_points"]]
        normalized = [point(pair) for pair in relation[
            "normalized_raw_leaf_points"]]
        assert len(originals) == len(normalized) == 5
        for original, transformed in zip(originals, normalized):
            assert curve(original[0] ** (1 << power),
                         original[1] ** (1 << power)) == transformed
        assert normalized[0][0] in affine_seeds[dimension]
        for transformed, relative_power in zip(
                normalized, protocol["fixed_relative_frobenius_powers"]):
            inverse = (83 - relative_power) % 83
            assert transformed[0] ** (1 << inverse) in affine_seeds[dimension]
        original_public = point(relation["public_target"])
        normalized_public = point(relation["normalized_public_target"])
        assert curve(original_public[0] ** (1 << power),
                     original_public[1] ** (1 << power)) == normalized_public

    public = point(protocol["workload"]["public_point_onb_raw"])
    order = protocol["workload"]["subgroup_order"]
    assert order * public == curve(0)
    rows = []
    for dimension in protocol["run_order"]:
        result_path = HERE / f"width{dimension}_ordinary.json"
        result = json.loads(result_path.read_text())
        relation = result["verified_relation"]
        if relation is None:
            rows.append({"dimension": dimension, "status": "no_relation_to_replay",
                         "result_sha256": sha(result_path)})
            continue
        assert result["status"] == "verified_relation"
        check_normalization(relation, dimension)
        raw = [point(pair) for pair in relation["raw_leaf_points"]]
        projected = [point(pair) for pair in relation["projected_points"]]
        assert len(raw) == len(projected) == 5
        assert all(belongs_to_rotated_seed(original[0], dimension)
                   for original in raw)
        for original, signed, image in zip(raw, relation["signs"], projected):
            assert signed in (-1, 1)
            assert 4 * (original if signed == 1 else -original) == image
            assert order * image == curve(0)
        assert sum(projected, curve(0)) == public
        assert relation["public_target"] == [str(v) for v in protocol[
            "workload"]["public_point_onb_raw"]]
        rows.append({"dimension": dimension, "status": "PASS",
                     "result_sha256": sha(result_path),
                     "projected_point_count": len(projected)})
    for dimension in (16,):
        control_path = HERE / "locked_control.json"
        control = json.loads(control_path.read_text())
        assert control["dimension"] == dimension
        assert control["status"] == "PASS"
        relation = control["replay"]
        assert relation["status"] == "verified_five_point_relation"
        check_normalization(relation, dimension)
        raw = [point(pair) for pair in relation["raw_leaf_points"]]
        projected = [point(pair) for pair in relation["projected_points"]]
        control_public = point(control["public_point_onb_raw"])
        assert len(raw) == len(projected) == 5
        assert all(belongs_to_rotated_seed(original[0], dimension)
                   for original in raw)
        for original, sign, image in zip(raw, relation["signs"], projected):
            assert sign in (-1, 1)
            assert 4 * (original if sign == 1 else -original) == image
            assert order * image == curve(0)
        assert sum(projected, curve(0)) == control_public
        assert relation["public_target"] == control["public_point_onb_raw"]
        rows.append({"kind": f"locked_normalized_control_{dimension}",
                     "status": "PASS", "result_sha256": sha(control_path),
                     "projected_point_count": len(projected)})
    record = {"kind": "n83_geometric_m5_independent_sage_relation_replay",
              "status": "PASS", "curve_id": protocol["curve_id"],
              "workload_id": protocol["workload_id"],
              "protocol_sha256": sha(protocol_path),
              "runtime_info_sha256": sha(runtime_path),
              "bridge_sha256": sha(BRIDGE),
              "verifier_source_sha256": sha(Path(__file__)),
              "rows": rows}
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": rows}))


if __name__ == "__main__":
    main()
