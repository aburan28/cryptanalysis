#!/usr/bin/env sage -python
"""Exact same-seed four-atom output screen using a degree-eight resultant."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def field_setup(n):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="t", modulus=modulus)

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    return field, decode, encode


def independent_product_basis(field, encode, dimension, seed_sum):
    basis_w = [field.gen()**i for i in range(1, dimension + 1)]
    pivots = {}
    output = []
    for w in basis_w:
        candidate = w**2 + seed_sum * w
        reduced = encode(candidate)
        while reduced:
            index = reduced.bit_length() - 1
            if index not in pivots:
                pivots[index] = reduced
                output.append(candidate)
                break
            reduced ^= pivots[index]
    assert len(output) == dimension - 1
    return output


def subspace_coefficients(field, basis):
    # S_V(X)=product_(v in V)(X+v)=sum_i c_i X^(2^i).
    coefficients = [field.one()]
    for vector in basis:
        value = sum((c * vector**(2**i) for i, c in enumerate(coefficients)),
                    field.zero())
        assert value != 0
        following = [field.zero()] * (len(coefficients) + 1)
        for i, coefficient in enumerate(coefficients):
            following[i] += value * coefficient
            following[i + 1] += coefficient**2
        coefficients = following
    return coefficients


def resultant_coefficients(field, s, z, terms):
    powers_s = [s**i for i in range(17)]
    powers_z = [z**i for i in range(9)]
    rows = [[field.zero() for _ in range(9)] for _ in range(9)]
    for es, ep, eq, ez in terms:
        rows[eq][ep] += powers_s[es] * powers_z[ez]
    return rows


def evaluate_h(field, ring, rows, p):
    coefficients = []
    for row in rows:
        value = field.zero()
        for coefficient in reversed(row):
            value = value * p + coefficient
        coefficients.append(value)
    return ring(coefficients)


def low_degree_subspace_gcd(ring, h, coefficients):
    if h.is_zero():
        return None
    if h.degree() == 0:
        return ring.one()
    power = ring.gen() % h
    remainder = ring.zero()
    for coefficient in coefficients:
        remainder += coefficient * power
        power = (power * power) % h
    return h.gcd(remainder)


def run(n, case):
    protocol = json.loads((HERE / "protocol.json").read_text())
    sources = {"script": Path(__file__), "terms": HERE / "resultant_terms.json",
               "inputs": HERE / "inputs.json", "runtime": HERE / "sage_runtime_info.json"}
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources.items()}
    assert protocol["status"] == "FROZEN_BEFORE_FOUR_ATOM_ORACLE_PANEL"
    inputs = json.loads((HERE / "inputs.json").read_text())
    panel = inputs["panels"][str(n)]
    field, decode, encode = field_setup(n)
    s = decode(panel["source_sum_field"])
    z = decode(panel["positive_z"] if case == "positive" else panel["trace_zero_control_z"])
    assert int(z.trace()) == 0
    terms = json.loads((HERE / "resultant_terms.json").read_text())["terms_s_p_q_z"]
    setup_start = time.monotonic_ns()
    basis = independent_product_basis(field, encode, panel["source_dimension"], s)
    coeffs = subspace_coefficients(field, basis)
    values = [field.zero()]
    for vector in basis:
        values.extend([value + vector for value in list(values)])
    assert len(values) == (1 << (panel["source_dimension"] - 1))
    assert len({encode(value) for value in values}) == len(values)
    rows = resultant_coefficients(field, s, z, terms)
    ring = PolynomialRing(field, "q")
    setup_ns = time.monotonic_ns() - setup_start
    start = time.monotonic_ns()
    hits = []
    processed = 0
    status = "COMPLETE_ALGEBRAIC_SCAN"
    for p in values:
        if processed % 32 == 0:
            if time.monotonic_ns() - start >= protocol["cap_seconds_per_case"] * 10**9:
                status = "CENSORED_TIME"
                break
            if rss_bytes() > protocol["rss_cap_bytes"]:
                status = "OOM"
                break
        h = evaluate_h(field, ring, rows, p)
        common = low_degree_subspace_gcd(ring, h, coeffs)
        if common is None:
            hits.append({"p": encode(p), "status": "DEGENERATE_RESULTANT"})
        elif common.degree() > 0:
            hits.append({"p": encode(p), "gcd_degree": int(common.degree()),
                         "q_roots": [encode(root) for root, _ in common.roots()]})
        processed += 1
    query_ns = time.monotonic_ns() - start
    expected = set(panel["pair_products"])
    found_products = {hit["p"] for hit in hits}
    if status == "COMPLETE_ALGEBRAIC_SCAN" and case == "positive":
        assert expected <= found_products
        assert all(any(q in expected for q in hit.get("q_roots", []))
                   for hit in hits if hit["p"] in expected)
    result = {"status": status, "field_degree": n, "case": case,
              "candidate_id": None, "target_count": 0,
              "seed_sum_mask": panel["source_mask_sum"], "seed_sum_field": encode(s),
              "output_z": encode(z), "product_space_dimension": len(basis),
              "subspace_polynomial_terms": len(coeffs),
              "resultant_degree_q_bound": 8,
              "total_product_states": len(values), "processed_product_states": processed,
              "algebraic_hits": hits, "expected_positive_products": sorted(expected)
                  if case == "positive" else None,
              "setup_ns": setup_ns, "query_ns": query_ns,
              "peak_rss_bytes": rss_bytes(),
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "inputs": sha(HERE / "inputs.json"),
                                "terms": sha(HERE / "resultant_terms.json"),
                                "script": sha(Path(__file__))}}
    path = HERE / f"result_n{n}_{case}.json"
    with path.open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "field_degree": n, "case": case,
                      "processed": processed, "hits": len(hits),
                      "query_seconds": query_ns / 1e9,
                      "peak_rss_bytes": result["peak_rss_bytes"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int, choices=(41, 131))
    parser.add_argument("case", choices=("positive", "trace_zero_control"))
    args = parser.parse_args()
    run(args.n, args.case)
