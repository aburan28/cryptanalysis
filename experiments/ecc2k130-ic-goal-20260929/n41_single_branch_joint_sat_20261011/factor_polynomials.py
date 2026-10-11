"""Factor the universal A/B coefficients of the single-branch quartic."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_quartic_joint_public_20261010" / "norm_result.json"


def main():
    source = json.loads(SOURCE.read_text())
    ring = PolynomialRing(GF(2), names=("a", "s", "z", "p", "q"))
    variables = ring.gens()
    polys = {}
    rows = {}
    for label in ("A", "B"):
        poly = sum((ring.monomial(*term) for term in source[label + "_terms"]), ring.zero())
        polys[label] = poly
        factors = poly.factor()
        rebuilt = ring(factors.unit())
        summary = []
        for factor, multiplicity in factors:
            rebuilt *= factor ** multiplicity
            summary.append({"multiplicity": int(multiplicity),
                            "terms": sorted([[*map(int, exponents), int(value)]
                                             for exponents, value in factor.dict().items()]),
                            "term_count": len(factor.dict()),
                            "degree": int(factor.total_degree())})
        assert rebuilt == poly
        rows[label] = {"term_count": len(poly.dict()), "factors": summary,
                       "total_degree": int(poly.total_degree())}
    gcd = polys["A"].gcd(polys["B"])
    result = {"status": "PASS_EXACT_COEFFICIENT_FACTORIZATION",
              "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "variables": list(map(str, variables)),
              "polynomials": rows, "gcd_terms": len(gcd.dict()),
              "gcd_total_degree": int(gcd.total_degree())}
    (HERE / "factor_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "factor_counts": {k: [f["term_count"] for f in v["factors"]]
                                        for k, v in rows.items()},
                      "gcd_terms": result["gcd_terms"]}, sort_keys=True))


if __name__ == "__main__":
    main()
