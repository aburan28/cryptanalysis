"""Exact Boolean ANF of the rotated four-atom resultant on N41 product spaces."""

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
MODULUS = (1 << 41) | (1 << 3) | 1
MASK = (1 << 41) - 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a & (1 << 41):
            a ^= MODULUS
    return out


def square(a):
    return mul(a, a)


def rotate(a, count):
    for _ in range(count):
        a = square(a)
    return a


def powers(a):
    result = [1]
    for _ in range(8):
        result.append(mul(result[-1], a))
    return result


def product_basis(seed):
    products = set()
    for w in range(0, 1 << 7, 2):
        products.add(square(w) ^ mul(seed, w))
    assert len(products) == 32
    basis = []
    span = {0}
    for product in sorted(products):
        if product not in span:
            basis.append(product)
            span.update({x ^ product for x in tuple(span)})
    assert len(basis) == 5 and span == products
    ordered = [0] * 32
    for mask in range(1, 32):
        low = mask & -mask
        ordered[mask] = ordered[mask ^ low] ^ basis[low.bit_length() - 1]
    assert set(ordered) == products
    return basis, ordered


def evaluate(terms, ap, bp, pp, qp, zp):
    value = 0
    for ea, eb, ep, eq, ez in terms:
        term = mul(ap[ea], bp[eb])
        term = mul(term, pp[ep])
        term = mul(term, qp[eq])
        value ^= mul(term, zp[ez])
    return value


def run():
    protocol = json.loads((HERE / "protocol.json").read_text())
    for label, (path, expected) in protocol["source_sha256"].items():
        assert digest(Path(path)) == expected, label
    control = json.loads((PARENT / "control_result.json").read_text())["n41"]
    terms = json.loads((PARENT / "resultant.json").read_text())["terms"]
    seed = control["seed_mask"] << 1
    basis, products = product_basis(seed)
    r0, r1 = control["pair_rotations"]
    a, b = rotate(seed, r0), rotate(seed, r1)
    assert [a, b] == control["rotated_seed_coordinates"]
    rotated_p = [rotate(x, r0) for x in products]
    rotated_q = [rotate(x, r1) for x in products]
    ap, bp = powers(a), powers(b)
    pp = [powers(x) for x in rotated_p]
    qp = [powers(x) for x in rotated_q]
    start = time.monotonic()
    cases = {}
    for label, z in (("positive", control["four_atom_reciprocal_output"]),
                     ("field_control", control["independent_field_control_z"])):
        zp = powers(z)
        values = [evaluate(terms, ap, bp, pp[i & 31], qp[i >> 5], zp)
                  for i in range(1024)]
        zero_indices = [i for i, v in enumerate(values) if v == 0]
        coefficients = values[:]
        for bit in range(10):
            for mask in range(1024):
                if mask & (1 << bit):
                    coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
        counts = Counter(mask.bit_count() for mask, value in enumerate(coefficients)
                         if value)
        encoded = b"".join(v.to_bytes(6, "little") for v in coefficients)
        cases[label] = {
            "z": z,
            "zero_count": len(zero_indices),
            "zero_indices": zero_indices,
            "zero_products": [[rotated_p[i & 31], rotated_q[i >> 5]]
                              for i in zero_indices],
            "boolean_degree": max(counts),
            "nonzero_coefficient_count": sum(counts.values()),
            "nonzero_coefficients_by_degree": dict(sorted(counts.items())),
            "coefficient_vector_sha256": hashlib.sha256(encoded).hexdigest(),
        }
    assert cases["positive"]["zero_products"] == control["positive_algebraic_product_hits"]
    assert cases["field_control"]["zero_products"] == control["control_algebraic_product_hits"]
    result = {
        "status": "PASS_EXACT_N41_ROTATED_RESULTANT_BOOLEAN_ANF",
        "protocol_sha256": digest(HERE / "protocol.json"),
        "field_degree": 41,
        "source_dimension": 6,
        "seed_mask": control["seed_mask"],
        "pair_rotations": [r0, r1],
        "product_basis": basis,
        "product_states_per_pair": 32,
        "terms": len(terms),
        "cases": cases,
        "elapsed_seconds_exploratory": time.monotonic() - start,
    }
    (HERE / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    run()
