"""Recompute public raw lifts in the reciprocal coordinate used by H."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTANT = ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"
CONTROLS = ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "control_result.json"
N41_Q = ROOT / "n41_seed_partition_indexless_20261010" / "replay_result.json"
N131_PREIMAGES = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" / "target_preimages.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_and_curve(n):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    return field, curve, decode, encode, point


def factor_case(n, public, archived, control, terms):
    field, curve, decode, encode, point = field_and_curve(n)
    order = 549756390943 if n == 41 else 680564733841876926932320129493409985129
    q = point(public)
    assert order * q == curve(0)
    torsion = [curve(0), curve(field(0), field(1)),
               curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(torsion)) == 4 and all(4 * item == curve(0) for item in torsion)
    base_preimage = pow(4, -1, order) * q
    if n == 41:
        lifts = [base_preimage + offset for offset in torsion]
    else:
        lifts = [point(row["point"]) for row in archived["preimages"]]
        assert set(lifts) == {base_preimage + offset for offset in torsion}
    ring = PolynomialRing(field, names=("P", "Q"))
    P, Q = ring.gens()
    a, b = map(decode, control["rotated_seed_coordinates"])
    records = []
    for index, raw in enumerate(lifts):
        assert 4 * raw == q and raw != curve(0) and raw[0] not in (0, 1)
        z_h = 1 / raw[0]
        z_transformed = 1 / (raw[0] + 1)
        if n == 131:
            assert encode(z_transformed) == archived["preimages"][index]["reciprocal_x_z"]
        started = time.monotonic()
        polynomial = sum(a**ea * b**eb * P**ep * Q**eq * z_h**ez
                         for ea, eb, ep, eq, ez in terms)
        factorization = polynomial.factor()
        degrees = [[int(factor.degree(P)), int(factor.degree(Q)),
                    int(exponent), len(factor.dict())]
                   for factor, exponent in factorization]
        rebuilt = ring(factorization.unit())
        for factor, exponent in factorization:
            rebuilt *= factor**exponent
        assert rebuilt == polynomial
        records.append({"index": index, "point": [encode(raw[0]), encode(raw[1])],
                        "z_h_reciprocal_x": encode(z_h),
                        "z_transformed_reciprocal_x_plus_one": encode(z_transformed),
                        "trace_z_h": int(z_h.trace()),
                        "factor_degrees_and_terms": degrees,
                        "factor_seconds_exploratory": time.monotonic() - started})
        print(n, index, encode(z_h), degrees, flush=True)
    assert all(row["point"] != list(public) for row in records)
    return {"public_target": list(public), "subgroup_order": order,
            "base_raw_preimage": [encode(base_preimage[0]), encode(base_preimage[1])],
            "preimages": records}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    for label, (path, digest) in protocol["source_sha256"].items():
        assert sha(Path(path)) == digest, label
    terms = json.loads(RESULTANT.read_text())["terms"]
    controls = json.loads(CONTROLS.read_text())
    public41 = json.loads(N41_Q.read_text())["public_target"]
    archived131 = json.loads(N131_PREIMAGES.read_text())
    result = {"status": "PASS_CORRECTED_RECIPROCAL_X_PUBLIC_LIFTS",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "n41": factor_case(41, public41, None, controls["n41"], terms),
              "n131": factor_case(131, archived131["public_target"], archived131,
                                  controls["n131"], terms)}
    with (HERE / "result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
