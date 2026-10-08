"""Focused correctness checks for the stage-probe algebra."""

import unittest

from boolean_core import ANFField, echelon, evaluate, replay_trace, sparse_macaulay


class BooleanCoreTest(unittest.TestCase):
    def test_s3_numeric_identity_on_small_field(self):
        # x^5+x^2+1 is irreducible.  Compare the descended ANF with arithmetic
        # in the original field for every two-bit leaf assignment.
        f = ANFField(5, (1 << 5) | (1 << 2) | 1)

        def mul(a, b):
            answer = 0
            while b:
                if b & 1:
                    answer ^= a
                a <<= 1
                if a & (1 << 5):
                    a ^= f.modulus
                b >>= 1
            return answer

        left = f.linear([0, 1], [1, 2])
        right = f.linear([2, 3], [3, 5])
        target = f.constant(7)
        equations = f.s3(left, right, target)
        for assignment in range(16):
            x = (1 if assignment & 1 else 0) ^ (2 if assignment & 2 else 0)
            y = (3 if assignment & 4 else 0) ^ (5 if assignment & 8 else 0)
            e2 = mul(x, y) ^ mul(x, 7) ^ mul(y, 7)
            expected = mul(e2, e2) ^ mul(mul(x, y), 7) ^ 1
            observed = sum(evaluate(eq, assignment) << i for i, eq in enumerate(equations))
            self.assertEqual(observed, expected)

    def test_sparse_macaulay_linear_map_and_transpose(self):
        equations = [{1, 2, 0}, {3, 0}]
        matrix = sparse_macaulay(equations, 2, 2)
        self.assertTrue(matrix.rows)
        for x in range(1 << len(matrix.columns)):
            for y in range(1 << len(matrix.rows)):
                left = (matrix.matvec(x) & y).bit_count() & 1
                right = (x & matrix.transposed_matvec(y)).bit_count() & 1
                self.assertEqual(left, right)

    def test_trace_replay_rejects_changed_pivot(self):
        rows = (0b110, 0b101, 0b011)
        reduced, trace = echelon(rows)
        self.assertEqual(replay_trace(rows, trace), reduced)
        self.assertIsNone(replay_trace((0, 0, 0), trace))


if __name__ == "__main__":
    unittest.main()
