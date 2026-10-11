"""Exact GF(2) shear search for the single-branch quartic compiler."""

import hashlib
import itertools
import json
from pathlib import Path

from circuit import NORM
from run import HERE, save


def shear(terms, source, added):
    out = set()
    for term in terms:
        exponent = term[source]
        for degree in range(exponent + 1):
            if degree & exponent != degree:
                continue
            result = list(term)
            result[source] = degree
            result[added] += exponent - degree
            result = tuple(result)
            if result in out:
                out.remove(result)
            else:
                out.add(result)
    return frozenset(out)


def count(order, A, B):
    multiplications = squares = 0
    powers = {(axis, 1) for axis in range(5)}
    coefficients = {}

    def power(axis, exponent):
        nonlocal multiplications, squares
        if (axis, exponent) not in powers:
            power(axis, exponent // 2)
            squares += 1
            multiplications += exponent & 1
            powers.add((axis, exponent))

    def coefficient(terms, depth):
        nonlocal multiplications
        key = (terms, depth)
        if key in coefficients:
            return coefficients[key]
        if depth == 5:
            assert terms == frozenset({(0, 0, 0, 0, 0)})
            is_one = True
        else:
            axis = order[depth]
            groups = {}
            for term in terms:
                exponent = term[axis]
                reduced = term[:axis] + (0,) + term[axis + 1:]
                groups.setdefault(exponent, set()).add(reduced)
            exponents = sorted(groups, reverse=True)
            current = exponents[0]
            is_one = coefficient(frozenset(groups[current]), depth + 1)
            for exponent in exponents[1:]:
                power(axis, current - exponent)
                multiplications += not is_one
                coefficient(frozenset(groups[exponent]), depth + 1)
                is_one = False
                current = exponent
            if current:
                power(axis, current)
                multiplications += not is_one
                is_one = False
        coefficients[key] = is_one
        return is_one

    coefficient(A, 0)
    coefficient(B, 0)
    return multiplications, squares


def main():
    norm = json.loads(NORM.read_text())
    original = {name: frozenset(map(tuple, norm[f"{name}_terms"])) for name in ("A", "B")}
    orders = list(itertools.permutations(range(5)))
    baseline = min((count(order, *original.values()), order) for order in orders)
    rows = []
    for source in range(5):
        for added in range(5):
            if source == added:
                continue
            A = shear(original["A"], source, added)
            B = shear(original["B"], source, added)
            assert shear(A, source, added) == original["A"]
            assert shear(B, source, added) == original["B"]
            (multiplications, squares), order = min(
                (count(candidate, A, B), candidate) for candidate in orders)
            rows.append({"source_axis": source, "added_axis": added,
                         "order": list(order), "field_multiplications": multiplications,
                         "field_squares": squares,
                         "term_counts": {"A": len(A), "B": len(B)}})
    rows.sort(key=lambda row: (row["field_multiplications"], row["field_squares"],
                               row["source_axis"], row["added_axis"]))
    assert len(rows) == 20 and rows[0]["source_axis"] == 1
    assert rows[0]["added_axis"] == 2 and rows[0]["order"] == [1, 4, 0, 2, 3]
    assert rows[0]["field_multiplications"] == 46
    record = {"status": "EXACT_SINGLE_SHEAR_AND_HORNER_ORDER_SEARCH",
              "variables": ["a", "S", "Z", "P", "Q"],
              "baseline": {"field_multiplications": baseline[0][0],
                           "field_squares": baseline[0][1], "order": list(baseline[1])},
              "rows": rows,
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (NORM, Path(__file__))}}
    save(HERE / "transform_search.json", record)
    print(json.dumps({"status": record["status"], "best": rows[0]}, sort_keys=True))


if __name__ == "__main__":
    main()
