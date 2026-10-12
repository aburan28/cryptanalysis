"""Focused controls for the generated exponent circuit and planted target."""

import unittest

import arithmetic as a
import run as gate
from witness import EvaluatingCircuit, bits


class OrbitM5Tests(unittest.TestCase):
    def test_barrel_and_in_formula_exponent_range(self):
        codes = (1, (1 << 7) | (1 << 65), (1 << 130) | (1 << 4) | 1)
        for code in codes:
            for exponent in (0, 1, 2, 7, 31, 65, 127, 128, 129, 130, 131, 255):
                circuit = EvaluatingCircuit(bits(code, a.N) + bits(exponent, 8),
                                            1 << 30)
                row = [circuit.variable() for _ in range(a.N)]
                exponent_row = [circuit.variable() for _ in range(8)]
                circuit.forbid_above(exponent_row, 130)
                output = gate.barrel_wires(circuit, row, exponent_row)
                rotated = sum(int(circuit.value(wire)) << bit
                              for bit, wire in enumerate(output))
                expected = sum(((code >> bit) & 1) << ((bit + exponent) % a.N)
                               for bit in range(a.N))
                self.assertEqual(rotated, expected)
                allowed = all(any((circuit.value(abs(literal)) if literal > 0
                                   else not circuit.value(abs(literal)))
                                  for literal in map(int, clause.split()[:-1]))
                              for clause in circuit.clauses)
                self.assertEqual(allowed, exponent <= 130)

    def test_planted_group_input(self):
        config, seed, normal, workload = gate.load_inputs()
        basis = a.source_basis()
        columns, output = gate.normal_seed_columns(basis, normal)
        self.assertEqual((len(columns), len(output)), (24, 131))
        q, fibers, controls, index = gate.planted_input(seed, config, basis)
        self.assertEqual(len(controls), 5)
        self.assertEqual(len(fibers), 4)
        self.assertIsNotNone(q)
        self.assertIsNone(a.scalar_mul(a.R, q))
        self.assertEqual(controls[0]["mask"], 5213401)
        self.assertEqual(workload["workload_id"], "eee7f6ee5f6b")
        self.assertEqual(a.group_sum(tuple(row["raw_point"]) for row in controls),
                         fibers[index])


if __name__ == "__main__":
    unittest.main()
