"""Universal quartic factorization after two Artin-Schreier substitutions."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "symbolic_protocol.json").read_text())
    for label, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, label
    terms = json.loads(SOURCE.read_text())["terms"]
    ring = PolynomialRing(GF(2), names=("a", "v", "u", "P", "Q"))
    a, v, u, P, Q = ring.gens()
    b = a + v*v + v
    z = u*u + u
    start = time.monotonic()
    H = sum(a**ea * b**eb * P**ep * Q**eq * z**ez
            for ea, eb, ep, eq, ez in terms)
    built = time.monotonic()
    factorization = H.factor()
    factored = time.monotonic()
    assert factorization.unit() == 1
    factors = [f for f, multiplicity in factorization for _ in range(multiplicity)]
    assert len(factors) == 2
    assert all((f.degree(P), f.degree(Q)) == (4, 4) for f in factors)
    assert factors[0] * factors[1] == H
    result = {
        "status": "PASS_UNIVERSAL_ARTIN_SCHREIER_QUARTIC_FACTORIZATION",
        "protocol_sha256": sha(HERE / "symbolic_protocol.json"),
        "substitution": {"b": "a+v^2+v", "z": "u^2+u"},
        "variable_order": ["a", "v", "u", "P", "Q"],
        "original_resultant_term_count": len(terms),
        "substituted_resultant_term_count": len(H.dict()),
        "factors": [
            {"bidegree_PQ": [4, 4], "total_degree": int(f.total_degree()),
             "term_count": len(f.dict()),
             "terms": sorted([list(map(int, exponents)) for exponents in f.dict()])}
            for f in factors],
        "build_seconds_exploratory": built - start,
        "factor_seconds_exploratory": factored - built,
    }
    with (HERE / "symbolic_result.json").open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print({"status": result["status"], "substituted_terms": len(H.dict()),
           "factor_terms": [len(f.dict()) for f in factors],
           "factor_bidegrees": [(int(f.degree(P)), int(f.degree(Q))) for f in factors]}, flush=True)


if __name__ == "__main__":
    main()
