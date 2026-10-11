#!/usr/bin/env sage -python
"""Check the exact descendant codomain lacks coordinate Frobenius self-action."""

import argparse
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    config = json.loads((HERE / "CONFIG.json").read_text())
    route = json.loads(ROUTE.read_text())
    assert sha(ROUTE) == config["route_manifest_sha256"]
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["descendant_curve_id"]
    assert route["endomorphism"]["source_order_conductor"] == 1
    assert route["endomorphism"]["target_order_conductor"] == 263
    assert route["endomorphism"]["source_volcano_level"] == 0
    assert route["endomorphism"]["target_volcano_level"] == 1
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    k = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(word):
        word = int(word)
        return k(sum(t**i for i in range(word.bit_length()) if word & (1 << i)))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    nodes = route["curve_nodes"]
    source = EllipticCurve(k, [decode(v) for v in nodes["source"][
        "coefficients_a1_a2_a3_a4_a6"]])
    target = EllipticCurve(k, [decode(v) for v in nodes["target"][
        "coefficients_a1_a2_a3_a4_a6"]])
    assert [encode(a) for a in source.ainvs()] == nodes["source"][
        "coefficients_a1_a2_a3_a4_a6"]
    assert [encode(a) for a in target.ainvs()] == nodes["target"][
        "coefficients_a1_a2_a3_a4_a6"]
    source_j = source.j_invariant()
    target_j = target.j_invariant()
    target_a6 = target.ainvs()[4]
    assert source_j == k.one() and source_j**2 == source_j
    assert target_a6 not in (k.zero(), k.one())
    assert target_j == 1/target_a6 and target_j**2 != target_j
    conjugate = EllipticCurve(k, [value**2 for value in target.ainvs()])
    assert conjugate.j_invariant() == target_j**2
    assert not target.is_isomorphic(conjugate)
    G = source([decode(v) for v in nodes["source"]["generator_G"]])
    H = target([decode(v) for v in nodes["target"]["generator_G"]])
    squared_source = source([G[0]**2, G[1]**2])
    squared_target = conjugate([H[0]**2, H[1]**2])
    r = nodes["source"]["subgroup_order"]
    assert r*G == source(0) and r*H == target(0)
    assert r*squared_source == source(0)
    assert r*squared_target == conjugate(0)
    receipt = {
        "schema": "ecc2k130-equal-w24-descendant-frobenius-sage-v1",
        "status": "PASS_DESCENDANT_J_NOT_BINARY_AND_CONJUGATE_DISTINCT",
        "candidate_id": None,
        "source_curve_id": config["source_curve_id"],
        "descendant_curve_id": config["descendant_curve_id"],
        "source_j": encode(source_j),
        "descendant_j": encode(target_j),
        "descendant_j_squared": encode(target_j**2),
        "descendant_conjugate_isomorphic": False,
        "source_generator_coordinate_square_on_source": True,
        "descendant_generator_coordinate_square_on_conjugate": True,
        "descendant_generator_coordinate_square_on_original": bool(
            target.is_on_curve(H[0]**2, H[1]**2)),
        "source_order_conductor": 1,
        "descendant_order_conductor": 263,
        "source_volcano_level_263": 0,
        "descendant_volcano_level_263": 1,
        "route_manifest_sha256": sha(ROUTE),
        "config_sha256": sha(HERE / "CONFIG.json"),
        "sage_runtime_info_sha256": sha(HERE / "runtime-info.json"),
        "verifier_sha256": sha(Path(__file__)),
        "sage_version": sage_version,
        "induced_subgroup_action_cost": None,
        "natural_pdp_yield": None,
        "actual_relation_matrix_columns": None,
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "source_j": receipt["source_j"],
                      "descendant_j": receipt["descendant_j"],
                      "descendant_j_squared": receipt["descendant_j_squared"]}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
