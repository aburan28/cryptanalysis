#!/usr/bin/env python3
"""Independent integer GF(2^n) replay of the affine-plane resultant GCDs."""

import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Field:
    def __init__(self, n):
        self.n = n
        self.modulus = (1 << n) | (0x9 if n == 41 else 0x2007)

    def reduce(self, value):
        while value.bit_length() > self.n:
            value ^= self.modulus << (value.bit_length() - self.n - 1)
        return value

    def mul(self, a, b):
        result = 0
        while a:
            if a & 1:
                result ^= b
            a >>= 1
            b <<= 1
        return self.reduce(result)

    def inv(self, value):
        assert value != 0
        u, v, a, b = value, self.modulus, 1, 0
        while u != 1:
            assert u != 0
            gap = u.bit_length() - v.bit_length()
            if gap < 0:
                u, v = v, u
                a, b = b, a
                gap = -gap
            u ^= v << gap
            a ^= b << gap
        result = self.reduce(a)
        assert self.mul(value, result) == 1
        return result


def trim(poly):
    while poly and poly[-1] == 0:
        poly.pop()
    return poly


def poly_mod(a, b, field):
    a = a[:]
    trim(a)
    b = trim(b[:])
    assert b
    inverse = field.inv(b[-1])
    while len(a) >= len(b):
        factor = field.mul(a[-1], inverse)
        shift = len(a) - len(b)
        for j, value in enumerate(b):
            a[shift + j] ^= field.mul(factor, value)
        trim(a)
    return a


def poly_gcd(a, b, field):
    a, b = trim(a[:]), trim(b[:])
    while b:
        a, b = b, poly_mod(a, b, field)
    if not a:
        return []
    inverse = field.inv(a[-1])
    return [field.mul(value, inverse) for value in a]


def square_mod(a, modulus, field):
    if not a:
        return []
    square = [0] * (2 * len(a) - 1)
    for j, value in enumerate(a):
        square[2*j] = field.mul(value, value)
    return poly_mod(square, modulus, field)


def linearized_coefficients(field, s, dimension):
    coefficients = [1]
    for i in range(1, dimension + 1):
        w = 1 << i
        vector = field.mul(w, w) ^ field.mul(s, w)
        power, image = vector, 0
        for coefficient in coefficients:
            image ^= field.mul(coefficient, power)
            power = field.mul(power, power)
        if image == 0:
            assert vector == 0 and i == 1
            continue
        updated = [0] * (len(coefficients) + 1)
        for j, coefficient in enumerate(coefficients):
            updated[j] ^= field.mul(image, coefficient)
            updated[j + 1] ^= field.mul(coefficient, coefficient)
        coefficients = updated
    assert len(coefficients) == dimension
    return coefficients


def polynomial_evaluate(coefficients, value, field):
    answer = 0
    for coefficient in reversed(coefficients):
        answer = field.mul(answer, value) ^ coefficient
    return answer


def specialized_h(field, s, c, z, universal_terms):
    delta = field.mul(c, c) ^ field.mul(s, c)
    powers = {}
    for name, value, limit in (("s", s, 16), ("d", delta, 8), ("z", z, 8)):
        entries = [1]
        for _ in range(limit):
            entries.append(field.mul(entries[-1], value))
        powers[name] = entries
    h = [0] * 17
    for es, ep, eq, ez in universal_terms:
        base = field.mul(powers["s"][es], powers["z"][ez])
        for selected in range(eq + 1):
            if selected & eq != selected:
                continue
            coefficient = field.mul(base, powers["d"][eq-selected])
            h[ep + selected] ^= coefficient
    return trim(h)


def intersection_gcd(field, h, coefficients):
    if len(h) <= 1:
        return [1]
    power = [0, 1]
    accumulated = []
    for coefficient in coefficients:
        if len(accumulated) < len(power):
            accumulated += [0] * (len(power) - len(accumulated))
        for j, value in enumerate(power):
            accumulated[j] ^= field.mul(coefficient, value)
        power = square_mod(power, h, field)
    return poly_gcd(h, trim(accumulated), field)


def symbolic_specialization(universal_terms):
    q = {(0, 0, 1, 0), (0, 2, 0, 0), (1, 1, 0, 0)}
    def multiply(left, right):
        result = set()
        for a in left:
            for b in right:
                key = tuple(x + y for x, y in zip(a, b))
                if key in result:
                    result.remove(key)
                else:
                    result.add(key)
        return result
    powers = [{(0, 0, 0, 0)}]
    for _ in range(8):
        powers.append(multiply(powers[-1], q))
    result = set()
    for es, ep, eq, ez in universal_terms:
        for ds, dc, dp, dz in powers[eq]:
            term = (es + ds, dc, ep + dp, ez + dz)
            if term in result:
                result.remove(term)
            else:
                result.add(term)
    return result


def main():
    start = time.perf_counter_ns()
    specialized = json.loads((HERE / "resultant.json").read_text())
    universal = json.loads((PARENT / "resultant_terms.json").read_text())
    controls = json.loads((PARENT / "inputs.json").read_text())["panels"]
    result = json.loads((HERE / "oracle_result_v3.json").read_text())
    prior_audit = json.loads((PARENT / "sage_audit.json").read_text())
    assert prior_audit["status"] == "PASS_INDEPENDENT_SAGE_FOUR_ATOM_NATIVE_ORACLE"
    assert symbolic_specialization(universal["terms_s_p_q_z"]) == {
        tuple(row) for row in specialized["terms_s_c_p_z"]}
    reports = []
    for row in result["rows"]:
        n, dimension = row["field_degree"], row["source_dimension"]
        field = Field(n)
        panel = controls[str(n)]
        seed_mask = panel["masks"][0] ^ panel["masks"][1]
        offset_mask = panel["masks"][0] ^ panel["masks"][2]
        s = sum(((seed_mask >> i) & 1) << (i + 1) for i in range(dimension))
        c = sum(((offset_mask >> i) & 1) << (i + 1) for i in range(dimension))
        delta = field.mul(c, c) ^ field.mul(s, c)
        assert (s, c, delta) == (row["seed_sum_field"], row["offset_field"], row["delta_field"])
        assert panel["pair_products"][0] ^ delta == panel["pair_products"][1]
        coefficients = linearized_coefficients(field, s, dimension)
        h = specialized_h(field, s, c, row["output_z"], universal["terms_s_p_q_z"])
        common = intersection_gcd(field, h, coefficients)
        degree = len(common) - 1
        assert degree == row["gcd_degree"] and len(h) - 1 == row["h_degree"]
        assert len(row["roots_p"]) == degree
        assert all(polynomial_evaluate(common, p, field) == 0 for p in row["roots_p"])
        if row["case"] == "positive":
            assert set(row["roots_p"]) == set(panel["pair_products"])
        else:
            assert degree == 0 and not row["roots_p"]
        if n == 41:
            products = set()
            for mask in range(1 << dimension):
                w = sum(((mask >> i) & 1) << (i + 1) for i in range(dimension))
                products.add(field.mul(w, w) ^ field.mul(s, w))
            assert len(products) == 1 << (dimension - 1)
            assert {p for p in products if polynomial_evaluate(h, p, field) == 0} == set(row["roots_p"])
        reports.append({"field_degree": n, "source_dimension": dimension,
                        "case": row["case"], "h_degree": len(h) - 1,
                        "gcd_degree": degree, "roots_p": row["roots_p"]})
    audit = {"status": "PASS_INDEPENDENT_INTEGER_FIELD_AFFINE_PLANE_GCD",
             "rows": reports, "wall_ns": time.perf_counter_ns() - start,
             "source_sha256": {"script": digest(__file__),
                               "specialization": digest(HERE / "resultant.json"),
                               "universal_resultant": digest(PARENT / "resultant_terms.json"),
                               "oracle_result": digest(HERE / "oracle_result_v3.json"),
                               "prior_group_audit": digest(PARENT / "sage_audit.json")}}
    with (HERE / "independent_audit.json").open("x") as out:
        json.dump(audit, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": audit["status"], "rows": len(reports),
                      "wall_ns": audit["wall_ns"]}))


if __name__ == "__main__":
    main()
