#!/usr/bin/env sage -python
"""Derive the universal same-seed reciprocal four-atom output resultant."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ring = PolynomialRing(GF(2), names=("s", "p", "q", "z", "c", "d"))
    s, p, q, z, c, d = ring.gens()
    left = (1 + p**2) * c**2 + p * c + s**2
    right = (1 + q**2) * d**2 + q * d + s**2
    upper = (1 + c**2 * d**2) * z**2 + c * d * z + (c + d)**2
    first = right.resultant(upper, d)
    final = left.resultant(first, c)
    assert final.degree(z) == 8 and final.degree(p) == final.degree(q) == 8
    assert final.degree(s) == 16 and len(final.monomials()) == 150
    assert final(p=q, q=p) == final
    terms = []
    for exponents, coefficient in final.dict().items():
        es, ep, eq, ez, ec, ed = map(int, exponents)
        assert int(coefficient) == 1 and ec == ed == 0
        terms.append([es, ep, eq, ez])
    terms.sort()
    result = {
        "status": "PASS_UNIVERSAL_SAME_SEED_FOUR_ATOM_RESULTANT",
        "characteristic": 2,
        "curve_model": "y^2+xy=x^3+1",
        "diagonal_atom_reciprocal_coordinate": "w",
        "pair_equation": "(1+p^2)c^2+p*c+s^2=0",
        "upper_equation": "(1+c^2*d^2)z^2+c*d*z+(c+d)^2=0",
        "resultant_order": ["d", "c"],
        "degrees": {"s": 16, "p": 8, "q": 8, "z": 8},
        "term_count": len(terms),
        "terms_s_p_q_z": terms,
        "source_sha256": {"script": sha(Path(__file__))},
    }
    with (HERE / "resultant_terms.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "term_count": len(terms), "degrees": result["degrees"]}))


if __name__ == "__main__":
    main()
