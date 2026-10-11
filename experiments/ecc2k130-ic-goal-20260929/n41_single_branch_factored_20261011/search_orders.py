"""Enumerate all coefficient and product Horner orders for the factored DAG."""

import hashlib
import itertools
import json
from pathlib import Path

from circuit import COEFFICIENTS, NORM, compile_quartic
from run import HERE, KaratsubaCircuit, save


def main():
    norm = json.loads(NORM.read_text())
    rows = []
    for coefficient_order in itertools.permutations(range(3)):
        for product_order in itertools.permutations(range(2)):
            circuit = KaratsubaCircuit(41, [0, 3])
            inputs = [[circuit.variable() for _ in range(41)] for _ in range(5)]
            _, _, multiplications, squares = compile_quartic(
                circuit, inputs, norm, coefficient_order, product_order)
            rows.append({"coefficient_order": list(coefficient_order),
                         "product_order": list(product_order),
                         "field_multiplications": multiplications,
                         "field_squares": squares,
                         "and_gates": circuit.and_count,
                         "variables": circuit.next_var - 1})
    rows.sort(key=lambda row: (row["field_multiplications"], row["and_gates"],
                               row["field_squares"], row["coefficient_order"],
                               row["product_order"]))
    assert len(rows) == 12 and rows[0]["field_multiplications"] == 57
    record = {"status": "EXHAUSTIVE_FACTORED_ORDER_SEARCH",
              "coefficient_variables": ["a", "S", "Z"],
              "product_variables": ["P", "Q"],
              "rows": rows,
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (Path(__file__), HERE / "circuit.py",
                                             COEFFICIENTS, NORM)}}
    save(HERE / "factor_order_result.json", record)
    print(json.dumps({"status": record["status"], "best": rows[0]}, sort_keys=True))


if __name__ == "__main__":
    main()
