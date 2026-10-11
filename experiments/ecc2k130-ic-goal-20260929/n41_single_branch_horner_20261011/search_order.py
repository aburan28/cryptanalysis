"""Exhaustively count shared sparse-Horner operations for all five axes."""

import hashlib
import itertools
import json
from pathlib import Path

from circuit import NORM
from run import HERE, save


def count_order(order, A, B):
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
    return multiplications, squares, len(coefficients)


def main():
    norm = json.loads(NORM.read_text())
    A, B = (frozenset(map(tuple, norm[key])) for key in ("A_terms", "B_terms"))
    rows = []
    for order in itertools.permutations(range(5)):
        muls, squares, nodes = count_order(order, A, B)
        rows.append({"order": list(order), "field_multiplications": muls,
                     "field_squares": squares, "shared_coefficient_nodes": nodes})
    rows.sort(key=lambda row: (row["field_multiplications"], row["field_squares"],
                               row["order"]))
    assert len(rows) == 120
    assert rows[0]["order"] == [1, 2, 0, 4, 3]
    assert rows[0]["field_multiplications"] == 54
    record = {"status": "EXHAUSTIVE_FIVE_AXIS_ORDER_SEARCH",
              "variable_names": ["a", "S", "Z", "P", "Q"],
              "count": len(rows), "rows": rows,
              "source_sha256": {
                  "norm_result.json": hashlib.sha256(NORM.read_bytes()).hexdigest(),
                  "search_order.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    save(HERE / "order_search.json", record)
    print(json.dumps({"status": record["status"], "best": rows[0],
                      "count": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
