"""Exhaustive Boolean projection check for the N9 exact-weight constraint."""

import unittest

import pycryptosat

from circuit import Circuit
from fc_hamming import require_exact_weight as require_fc_weight
from unary_hamming import require_exact_weight as require_unary_weight


class FCHammingTest(unittest.TestCase):
    def check_all_nine_bit_masks(self, weight_constraint):
        circuit = Circuit(9, [0, 4])
        bits = [circuit.variable() for _ in range(9)]
        weight_constraint(circuit, bits, 2)
        solver = pycryptosat.Solver(threads=1)
        for clause in circuit.clauses:
            solver.add_clause([int(v) for v in clause.split()[:-1]])
        for row in circuit.xors:
            terms = [int(v) for v in row.split()[1:-1]]
            rhs = bool(1 ^ (sum(v < 0 for v in terms) & 1))
            solver.add_xor_clause([abs(v) for v in terms], rhs)
        for mask in range(1 << 9):
            assumptions = [var if mask >> i & 1 else -var
                           for i, var in enumerate(bits)]
            sat, _ = solver.solve(assumptions=assumptions)
            self.assertEqual(sat, mask.bit_count() == 2, mask)

    def test_fc_all_nine_bit_masks(self):
        self.check_all_nine_bit_masks(require_fc_weight)

    def test_unary_all_nine_bit_masks(self):
        self.check_all_nine_bit_masks(require_unary_weight)


if __name__ == "__main__":
    unittest.main()
