#!/usr/bin/env python3
"""Exact symmetric quotient and conditional product-space checks."""

import hashlib
import json
import random
import time
from pathlib import Path

from sage.all import GF, PolynomialRing


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010"
TERMS_PATH = PARENT / "resultant_terms.json"
INPUTS_PATH = PARENT / "inputs.json"
PROTOCOL_PATH = HERE / "protocol.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xor_terms(a, b):
    return a.symmetric_difference(b)


def symmetric_terms(terms):
    # S_k = p^k+q^k, P=p+q, T=pq, in characteristic two.
    power_sums = [set(), {(1, 0)}]
    for _ in range(2, 9):
        power_sums.append(xor_terms({(i + 1, j) for i, j in power_sums[-1]},
                                    {(i, j + 1) for i, j in power_sums[-2]}))
    output = set()
    visited = set()
    for s, p, q, z in sorted(terms):
        if (s, p, q, z) in visited:
            continue
        assert (s, q, p, z) in terms
        if p == q:
            orbit = {(s, 0, p, z)}
        else:
            orbit = {(s, i, j + min(p, q), z)
                     for i, j in power_sums[abs(p - q)]}
        output ^= orbit
        visited.add((s, p, q, z))
        visited.add((s, q, p, z))
    assert visited == terms
    return output


def field(n, exponents):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    return GF(2**n, name="t", modulus=sum(t**e for e in exponents))


def decode(F, value):
    t = F.gen()
    total = F.zero()
    index = 0
    while value:
        if value & 1:
            total += t**index
        value >>= 1
        index += 1
    return total


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def evaluate(terms, s, a, b, z):
    total = s.parent().zero()
    for i, j, k, ell in terms:
        total += s**i * a**j * b**k * z**ell
    return total


def subspace_basis(F, d, s):
    t = F.gen()
    values = [F.zero()]
    for i in range(1, d + 1):
        v = t**(2*i) + s*t**i
        if v == 0:
            continue
        values += [x + v for x in values]
    assert len(set(values)) == 2**(d-1)
    return values


def main():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert protocol["source_sha256"] == {
        "run.py": sha256(Path(__file__)),
        "resultant_terms.json": sha256(TERMS_PATH),
        "inputs.json": sha256(INPUTS_PATH),
    }
    original = {tuple(x) for x in json.loads(TERMS_PATH.read_text())["terms_s_p_q_z"]}
    quotient = symmetric_terms(original)
    R = PolynomialRing(GF(2), names=("s", "p", "q", "z"))
    ss, pp, qq, zz = R.gens()
    h = sum((ss**i*pp**j*qq**k*zz**ell for i, j, k, ell in original), R.zero())
    lifted = sum((ss**i*(pp+qq)**j*(pp*qq)**k*zz**ell
                  for i, j, k, ell in quotient), R.zero())
    assert h == lifted
    inputs = json.loads(INPUTS_PATH.read_text())["panels"]
    report = {
        "status": "PASS_EXACT_SYMMETRIC_QUOTIENT",
        "source_sha256": protocol["source_sha256"],
        "original_terms": len(original),
        "quotient_terms": len(quotient),
        "quotient_degrees_s_P_T_z": [max(v[i] for v in quotient) for i in range(4)],
        "exact_polynomial_identity": True,
        "panels": {},
    }
    for n in (41, 131):
        started = time.monotonic()
        panel = inputs[str(n)]
        F = field(n, panel["field_modulus_exponents"])
        s = decode(F, panel["source_sum_field"])
        values = subspace_basis(F, panel["source_dimension"], s)
        value_set = set(values)
        p0, q0 = [decode(F, v) for v in panel["pair_products"]]
        P0, T0 = p0 + q0, p0*q0
        assert p0 in value_set and q0 in value_set
        rng = random.Random(20261010 + n)
        selected_P = [F.zero(), P0]
        selected_P += [values[rng.randrange(len(values))] for _ in range(4)]
        image_results = []
        for P in selected_P:
            image = {p*p + P*p for p in values}
            expected = len(values) if P == 0 else len(values)//2
            assert len(image) == expected
            image_results.append({"P": encode(P), "image_size": len(image)})
        assert T0 in {p*p + P0*p for p in values}
        random_equalities = 128 if n == 131 else 256
        for _ in range(random_equalities):
            p, q = rng.choice(values), rng.choice(values)
            z = decode(F, rng.getrandbits(n))
            assert evaluate(original, s, p, q, z) == evaluate(quotient, s, p+q, p*q, z)
        controls = {}
        for key in ("positive_z", "trace_zero_control_z"):
            z = decode(F, panel[key])
            if n == 41:
                old_hits = [(encode(p), encode(q))
                            for p in values for q in values
                            if evaluate(original, s, p, q, z) == 0]
                new_hits = {(encode(p+q), encode(p*q))
                            for p in values for q in values
                            if evaluate(quotient, s, p+q, p*q, z) == 0}
                assert new_hits == {(p^q, encode(decode(F,p)*decode(F,q)))
                                    for p, q in old_hits}
                controls[key] = {"ordered_algebraic_hits": len(old_hits),
                                 "quotient_algebraic_hits": len(new_hits),
                                 "quotient_hit_keys": sorted([list(x) for x in new_hits])}
            else:
                controls[key] = {"constructed_pair_vanishes":
                                 evaluate(quotient, s, P0, T0, z) == 0}
        report["panels"][str(n)] = {
            "field_degree": n, "source_dimension": panel["source_dimension"],
            "product_space_size": len(values),
            "selected_conditional_images": image_results,
            "constructed_quotient_key": [encode(P0), encode(T0)],
            "random_identity_checks": random_equalities,
            "controls": controls,
            "exploratory_wall_seconds": time.monotonic()-started,
        }
    (HERE / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": report["status"],
                      "terms": [report["original_terms"], report["quotient_terms"]],
                      "n41_controls": report["panels"]["41"]["controls"],
                      "n131_seconds": report["panels"]["131"]["exploratory_wall_seconds"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
