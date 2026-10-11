"""Factor the P/Q coefficient polynomials in the universal quartic."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_quartic_joint_public_20261010" / "norm_result.json"


def main():
    source = json.loads(SOURCE.read_text())
    ring = PolynomialRing(GF(2), names=("a", "s", "z"))
    a, s, z = ring.gens()
    variables = (a, s, z)
    rows = {}
    for label in ("A", "B"):
        groups = {}
        for ea, es, ez, ep, eq in source[label + "_terms"]:
            groups.setdefault((ep, eq), ring.zero())
            groups[ep, eq] += a**ea * s**es * z**ez
        record = []
        for key, polynomial in sorted(groups.items()):
            factors = polynomial.factor()
            assert ring(factors.prod()) == polynomial
            record.append({"P_Q_exponents": list(key),
                           "coefficient_terms": len(polynomial.dict()),
                           "factors": [{"multiplicity": int(multiplicity),
                                        "terms": sorted([[*map(int, exp), int(value)]
                                                         for exp, value in factor.dict().items()]),
                                        "term_count": len(factor.dict())}
                                       for factor, multiplicity in factors]})
        rows[label] = record
    output = {"status": "PASS_EXACT_PQ_COEFFICIENT_FACTORIZATION",
              "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "records": rows}
    (HERE / "coefficient_result.json").write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": output["status"],
                      "coefficient_counts": {k: len(v) for k, v in rows.items()},
                      "factor_shapes": {k: [tuple(f["term_count"] for f in v["factors"])
                                           for v in rows[k]] for k in rows}}, sort_keys=True))


if __name__ == "__main__":
    main()
