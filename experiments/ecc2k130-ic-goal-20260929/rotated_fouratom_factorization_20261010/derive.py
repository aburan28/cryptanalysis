"""Factor exact rotated four-atom resultants after fixing seed and output."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))


def run(case):
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    n = 41 if case.startswith("n41") else 131
    q = PolynomialRing(GF(2), "t")
    t = q.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="T", modulus=modulus)
    T = field.gen()

    def decode(value):
        return sum(T**i for i in range(n) if (value >> i) & 1)

    data = json.loads((SOURCE / "control_result.json").read_text())["n41" if n == 41 else "n131"]
    a, b = map(decode, data["rotated_seed_coordinates"])
    if case.endswith("positive"):
        z = decode(data["four_atom_reciprocal_output"])
    elif case.endswith("control"):
        z = decode(data["independent_field_control_z"])
    elif case == "n41_public_target":
        z = 1 / decode(1458168294740)
    else:
        raise ValueError(case)
    ring = PolynomialRing(field, names=("P", "Q"))
    P, Q = ring.gens()
    terms = json.loads((SOURCE / "resultant.json").read_text())["terms"]
    start = time.monotonic()
    polynomial = sum(a**ea * b**eb * P**ep * Q**eq * z**ez
                     for ea, eb, ep, eq, ez in terms)
    built = time.monotonic()
    factorization = polynomial.factor()
    factored = time.monotonic()
    factors = [factor for factor, exponent in factorization for _ in range(exponent)]
    assert factors
    factors[0] *= factorization.unit()
    rebuilt = ring.one()
    for factor in factors:
        rebuilt *= factor
    assert rebuilt == polynomial
    result = {
        "status": "PASS_EXACT_SPECIALIZED_RESULTANT_FACTOR",
        "case": case,
        "field_degree": n,
        "a": encode(a), "b": encode(b), "z": encode(z),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "polynomial_terms": len(polynomial.dict()),
        "polynomial_bidegree": [int(polynomial.degree(P)), int(polynomial.degree(Q))],
        "factors": [
            {"bidegree": [int(f.degree(P)), int(f.degree(Q))],
             "term_count": len(f.dict()),
             "terms": sorted([[int(exponents[0]), int(exponents[1]), encode(value)]
                              for exponents, value in f.dict().items()])}
            for f in factors],
        "build_seconds_exploratory": built - start,
        "factor_seconds_exploratory": factored - built,
    }
    path = HERE / f"{case}.json"
    with path.open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({key: value for key, value in result.items() if key != "factors"}, sort_keys=True), flush=True)
    print("factor summaries", [(f["bidegree"], f["term_count"]) for f in result["factors"]], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("n41_positive", "n41_control", "n41_public_target",
                                         "n131_positive", "n131_control"))
    run(parser.parse_args().case)
