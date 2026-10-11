"""Factor the fixed-seed resultant at raw torsion shifts of public points."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n131_w15_rotated_fouratom_inverse_20261010"
TARGET = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" / "target_preimages.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_field(n, terms, controls, inputs):
    q = PolynomialRing(GF(2), "t")
    t = q.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="T", modulus=modulus)
    T = field.gen()

    def decode(value):
        return sum(T**i for i in range(n) if (value >> i) & 1)

    def trace(value):
        output = field.zero()
        for _ in range(n):
            output += value
            value *= value
        assert output == 0 or output == 1
        return 0 if output == 0 else 1

    a, b = map(decode, controls["rotated_seed_coordinates"])
    ring = PolynomialRing(field, names=("P", "Q"))
    P, Q = ring.gens()
    records = []
    for label, number in inputs:
        z = decode(number)
        start = time.monotonic()
        polynomial = sum(a**ea * b**eb * P**ep * Q**eq * z**ez
                         for ea, eb, ep, eq, ez in terms)
        factorization = polynomial.factor()
        rebuilt = ring(factorization.unit())
        degrees = []
        for factor, exponent in factorization:
            rebuilt *= factor**exponent
            degrees.append([int(factor.degree(P)), int(factor.degree(Q)), int(exponent),
                            len(factor.dict())])
        assert rebuilt == polynomial
        records.append({"label": label, "z": number,
                        "trace_z_plus_inverse": trace(z + 1/z),
                        "trace_z": trace(z),
                        "factor_degrees_and_terms": degrees,
                        "factor_seconds_exploratory": time.monotonic() - start})
        print(n, label, degrees, flush=True)
    return records


def main():
    protocol = json.loads((HERE / "torsion_protocol.json").read_text())
    for name, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    terms = json.loads((SOURCE / "resultant.json").read_text())["terms"]
    controls = json.loads((SOURCE / "control_result.json").read_text())
    preimages = json.loads(TARGET.read_text())["preimages"]
    p41 = controls["n41"]["four_atom_reciprocal_output"]
    p131 = controls["n131"]["four_atom_reciprocal_output"]
    n41_inputs = [("known_block", p41), ("known_block_plus_t2", p41 ^ 1),
                  ("field_control", 3), ("public_subgroup", 1674099877300),
                  ("public_subgroup_plus_t2", 1674099877301)]
    n131_inputs = [("known_block", p131), ("known_block_plus_t2", p131 ^ 1),
                   ("field_control", 3)]
    n131_inputs += [("public_raw_lift_" + str(entry["index"]),
                     entry["reciprocal_x_z"]) for entry in preimages]
    result = {
        "status": "PASS_TORSION_SHIFT_RESULTANT_FACTORIZATION_SCREEN",
        "protocol_sha256": sha(HERE / "torsion_protocol.json"),
        "n41": test_field(41, terms, controls["n41"], n41_inputs),
        "n131": test_field(131, terms, controls["n131"], n131_inputs),
    }
    with (HERE / "torsion_result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
