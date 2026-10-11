"""Prove the nondegenerate two-link elimination identity over characteristic two."""

import hashlib
import json
import random
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
sys.path.insert(0, str(BASE))
import fixed_pair_circuit as pair  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def constant(value):
    return frozenset({(0, 0, 0, 0, 0)}) if value & 1 else frozenset()


def variable(index):
    powers = [0]*5
    powers[index] = 1
    return frozenset({tuple(powers)})


def add(*terms):
    result = set()
    for term in terms:
        result.symmetric_difference_update(term)
    return frozenset(result)


def multiply(a, b):
    result = set()
    for left in a:
        for right in b:
            term = tuple(x+y for x, y in zip(left, right))
            if term in result:
                result.remove(term)
            else:
                result.add(term)
    return frozenset(result)


def square(a):
    return frozenset(tuple(2*x for x in term) for term in a)


def main():
    protocol_path = HERE / "identity_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "pair": BASE / "fixed_pair_circuit.py",
             "circuit": HERE / "resultant_circuit.py",
             "circuit_result": HERE / "circuit_result.json",
             "prior_resultant": HERE.parent / "s3_two_link_resultant_circuit.py"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name

    one = constant(1)
    h, k, c, z, middle = (variable(index) for index in range(5))
    delta = add(h, k)
    s = add(multiply(k, c), multiply(h, z))
    e = add(c, z, s)
    f = add(multiply(add(one, h), square(middle)),
            multiply(h, middle), c)
    g = add(multiply(add(one, k), square(middle)),
            multiply(k, middle), z)
    linear_combination = add(multiply(add(one, k), f),
                             multiply(add(one, h), g))
    assert linear_combination == add(multiply(delta, middle), e)
    resultant = add(square(e), multiply(delta, s))
    substituted_f = add(multiply(add(one, h), square(e)),
                        multiply(h, multiply(e, delta)),
                        multiply(c, square(delta)))
    substituted_g = add(multiply(add(one, k), square(e)),
                        multiply(k, multiply(e, delta)),
                        multiply(z, square(delta)))
    assert substituted_f == multiply(add(one, h), resultant)
    assert substituted_g == multiply(add(one, k), resultant)

    rng = random.Random(protocol["field_test_seed"])
    for _ in range(protocol["field_test_count"]):
        a, b, m = (rng.getrandbits(131) for _ in range(3))
        mul, sq = pair.gf_mul, pair.gf_square
        ab = mul(a, b)
        triple = mul(ab, m)
        old = sq(triple ^ a ^ b ^ m) ^ mul(
            triple, ab ^ mul(m, a ^ b) ^ a ^ b ^ m ^ 1)
        coef = mul(sq(a) ^ a, sq(b) ^ b)
        quadratic = mul(1 ^ coef, sq(m)) ^ mul(coef, m) ^ sq(a ^ b)
        assert old == quadratic

    result = {"status": "PASS_NONDEGENERATE_TWO_LINK_IDENTITY",
              "characteristic_two_polynomial_equalities": 3,
              "field_s3_quadratic_tests": protocol["field_test_count"],
              "field_test_seed": protocol["field_test_seed"],
              "resultant_monomials": len(resultant),
              "nondegeneracy_required": "h+k != 0",
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "identity_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "polynomial_equalities": 3,
                      "field_tests": protocol["field_test_count"]}))


if __name__ == "__main__":
    main()
