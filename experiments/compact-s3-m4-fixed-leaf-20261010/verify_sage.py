#!/usr/bin/env python3
"""Independent exact Sage replay of the two Q1423 locked relations."""

import hashlib
import json
from pathlib import Path
import sys

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import field  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xor_images(mask, images):
    value = 0
    while mask:
        bit = mask & -mask
        value ^= images[bit.bit_length() - 1]
        mask ^= bit
    return value


def replay(n):
    receipt_path = HERE / f"n{n}_locked.json"
    receipt = json.loads(receipt_path.read_text())
    relation = receipt["verified_relation"]
    assert receipt["solver"]["status"] == "SAT"
    assert receipt["formula_model_checked"] and relation is not None
    bridge_path = OLD / f"field_bridges/n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    assert bridge["status"] == "PASS"
    assert bridge["curve_id"] == receipt["curve_id"]
    f2 = GF(2)
    ring = PolynomialRing(f2, "z")
    z = ring.gen()
    modulus = z ** n + sum(z ** bit for bit in bridge[
        "target_implementation_basis"]["low_terms"])
    assert str(modulus) == bridge["target_implementation_basis"]["defining_modulus"]
    assert modulus.is_irreducible()
    extension = GF(2 ** n, f"q1423_{n}", modulus=modulus)
    ec = EllipticCurve(extension, [1, 0, 0, 0, 1])
    onb = field.Onb(n)
    images = bridge["onb_to_poly_basis_images"]

    def element(word):
        bits = xor_images(onb.toCoords(int(word)), images)
        return sum(extension.gen() ** bit for bit in range(n)
                   if bits >> bit & 1)

    def point(pair):
        return ec(element(pair[0]), element(pair[1]))

    order = int(bridge["subgroup_order"])
    public = point(receipt["public_target"])
    remainder = point(receipt["remainder"])
    fixed = point(receipt["fixed_point"])
    leaves = [point(pair) for pair in relation["leaf_points"]]
    assert all(order * value == ec(0)
               for value in [public, remainder, fixed, *leaves])
    assert sum(leaves, ec(0)) == remainder
    assert remainder + fixed == public
    assert len(leaves) == 3
    selected_modes = []
    for mode in ("control_unpinned", "pool1", "pool64"):
        other_path = HERE / f"n{n}_{mode}.json"
        other = json.loads(other_path.read_text())
        q = point(other["public_target"])
        p3 = point(other["fixed_point"])
        t = point(other["remainder"])
        assert all(order * value == ec(0) for value in (q, p3, t))
        assert t + p3 == q
        selected_modes.append({"mode": mode, "receipt_sha256": sha(other_path),
                               "status": "PASS_TARGET_SUBTRACTION_AND_SUBGROUP"})
    return {"curve_id": receipt["curve_id"], "field_degree": n,
            "subgroup_order": str(order), "leaf_count": 3,
            "receipt_sha256": sha(receipt_path), "bridge_sha256": sha(bridge_path),
            "selected_modes": selected_modes,
            "status": "PASS_EXACT_POINT_SUM_AND_SUBGROUP"}


def main():
    runtime_path = HERE / "sage_runtime.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    result = {"schema": "q1423-sage-verification-v1", "status": "PASS",
              "cases": [replay(53), replay(83)],
              "runtime_sha256": sha(runtime_path), "verifier_sha256": sha(__file__)}
    (HERE / "verification_sage.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
