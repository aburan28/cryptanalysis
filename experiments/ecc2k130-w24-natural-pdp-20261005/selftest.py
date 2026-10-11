#!/usr/bin/env python3
"""Check XCNF gate semantics against independent small-field truth cases."""

import json
import subprocess
import tempfile
from pathlib import Path

from xor_circuit import Circuit


CMS = "/opt/homebrew/bin/cryptominisat5"


def small_mul(left, right, n, low_terms):
    # Direct polynomial product and long reduction, independent of Karatsuba.
    product = 0
    for i in range(n):
        for j in range(n):
            product ^= (((left >> i) & 1) & ((right >> j) & 1)) << (i+j)
    modulus = (1 << n) | sum(1 << bit for bit in low_terms)
    while product.bit_length() > n:
        product ^= modulus << (product.bit_length()-n-1)
    return product


def status(circuit):
    with tempfile.TemporaryDirectory(prefix="w24-circuit-test-") as temporary:
        path = Path(temporary) / "test.xcnf"
        circuit.write(path)
        result = subprocess.run([CMS, "--threads=1", "--verb=0", str(path)],
                                capture_output=True, text=True, timeout=10)
        statements = [line[2:].strip() for line in result.stdout.splitlines()
                      if line.startswith("s ")]
        assert len(statements) == 1, result.stdout[-1000:]
        return statements[0]


def multiplication_case(left, right, expected, n, low_terms):
    circuit = Circuit(n, low_terms)
    a = [circuit.variable() for _ in range(n)]
    b = [circuit.variable() for _ in range(n)]
    for bit, wire in enumerate(a):
        circuit.pin(wire, (left >> bit) & 1)
    for bit, wire in enumerate(b):
        circuit.pin(wire, (right >> bit) & 1)
    circuit.require_zero(circuit.add(circuit.mul(a, b),
                                     circuit.constant(expected)))
    return status(circuit)


def boundary_case(value, bound):
    circuit = Circuit(5, (2, 0))
    row = [circuit.variable() for _ in range(5)]
    circuit.forbid_above(row, bound)
    for bit, wire in enumerate(row):
        circuit.pin(wire, (value >> bit) & 1)
    return status(circuit)


def main():
    products = ((3, 5, 5, (2, 0)), (17, 29, 5, (2, 0)),
                (31, 31, 5, (2, 0)), (0, 19, 5, (2, 0)),
                (1, 27, 5, (2, 0)), (511, 511, 9, (4, 0)),
                (341, 495, 9, (4, 0)))
    for left, right, n, low_terms in products:
        correct = small_mul(left, right, n, low_terms)
        assert multiplication_case(left, right, correct, n, low_terms) == "SATISFIABLE"
        assert multiplication_case(left, right, correct ^ 1,
                                   n, low_terms) == "UNSATISFIABLE"
    for value in (0, 1, 18, 19, 20, 21, 31):
        assert boundary_case(value, 19) == (
            "SATISFIABLE" if value <= 19 else "UNSATISFIABLE")
    print(json.dumps({"status": "PASS", "product_cases": len(products),
                      "comparison_cases": 7}, sort_keys=True))


if __name__ == "__main__":
    main()
