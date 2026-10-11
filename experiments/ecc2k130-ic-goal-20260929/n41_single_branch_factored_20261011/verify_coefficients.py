"""Reconstruct the factored P,Q coefficients as exact GF(2) polynomials."""

import hashlib
import json
from pathlib import Path

from circuit import COEFFICIENTS, NORM
from run import HERE, save


def multiply(left, right):
    out = set()
    for a in left:
        for b in right:
            term = tuple(x + y for x, y in zip(a, b))
            if term in out:
                out.remove(term)
            else:
                out.add(term)
    return out


def main():
    norm = json.loads(NORM.read_text())
    records = json.loads(COEFFICIENTS.read_text())["records"]
    counts = {}
    for name in ("A", "B"):
        out = set()
        for entry in records[name]:
            coefficient = {(0, 0, 0)}
            for factor in entry["factors"]:
                terms = {tuple(row[:3]) for row in factor["terms"]}
                assert len(terms) == factor["term_count"]
                assert all(row[3] == 1 for row in factor["terms"])
                for _ in range(factor["multiplicity"]):
                    coefficient = multiply(coefficient, terms)
            P, Q = entry["P_Q_exponents"]
            for a, S, Z in coefficient:
                term = (a, S, Z, P, Q)
                if term in out:
                    out.remove(term)
                else:
                    out.add(term)
        assert out == {tuple(row) for row in norm[f"{name}_terms"]}
        counts[name] = len(out)
    record = {"status": "PASS_EXACT_FACTORED_COEFFICIENT_RECONSTRUCTION",
              "term_counts": counts,
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (NORM, COEFFICIENTS, Path(__file__))}}
    save(HERE / "coefficient_audit.json", record)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
