"""Differential field arithmetic, carry-bound counterexample and witness checks."""
from dataclasses import replace
from copy import deepcopy
import gzip
import json
from pathlib import Path
import random
import unittest
from packed_field import GF2n, SquareField, PackedField, PackedBits, PreparedReplay, HERE
from gf2n import modulus, Curve
from curve_replay import PublicReplay, PublicQuery, NativeReplay, Point


def carryless(a, b):
    result = 0
    while b:
        low = b & -b
        result ^= a << (low.bit_length() - 1)
        b ^= low
    return result


class FieldTests(unittest.TestCase):
    def test_exhaustive_small_fields(self):
        for n in range(1, 6):
            mod = 3 if n == 1 else modulus(n)
            reference = GF2n(n, mod)
            for F in (SquareField(n, mod), PackedField(n, mod)):
                for a in range(1 << n):
                    self.assertEqual(F.sqr(a), reference.sqr(a))
                    for b in range(1 << n):
                        self.assertEqual(F.mul(a, b), reference.mul(a, b))
                        self.assertEqual(F.sqr(a ^ b), F.sqr(a) ^ F.sqr(b))

    def test_byte_and_power_of_two_boundaries(self):
        rng = random.Random(202610036401)
        for n in (7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129):
            reference = GF2n(n, modulus(n))
            for F in (SquareField(n, reference.mod), PackedField(n, reference.mod)):
                for i in range(n):
                    self.assertEqual(F.sqr(1 << i), reference.sqr(1 << i))
                    if isinstance(F, PackedField):
                        for j in range(n):
                            self.assertEqual(F.mul(1 << i, 1 << j), reference.mul(1 << i, 1 << j))
                for a in (0, 1, 1 << (n - 1), (1 << n) - 1):
                    self.assertEqual(F.sqr(a), reference.sqr(a))
                    self.assertEqual(F.mul(a, a), reference.mul(a, a))
                for _ in range(32):
                    a, b, c = (rng.getrandbits(n) for _ in range(3))
                    self.assertEqual(F.mul(a, b), reference.mul(a, b))
                    self.assertEqual(F.mul(a, b ^ c), F.mul(a, b) ^ F.mul(a, c))
                    self.assertEqual(F.sqr(a), reference.sqr(a))
                self.assertEqual(F.inv(2), reference.inv(2))
                self.assertEqual(F.mul(2, F.inv(2)), 1)

    def test_exact_packing_and_parity(self):
        rng = random.Random(202610036402)
        for n in (1, 2, 3, 7, 8, 9, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255):
            bits = PackedBits(n)
            for i in range(n):
                self.assertEqual(bits.pack(1 << i), 1 << (8 * i))
            values = [0, 1, (1 << n) - 1, 1 << (n - 1), *(rng.getrandbits(n) for _ in range(10))]
            for a in values:
                self.assertEqual(bits.pack(a), sum(((a >> i) & 1) << (8 * i) for i in range(n)))
                for b in values:
                    self.assertEqual(bits.product(a, b), carryless(a, b))

    def test_carry_bound_is_necessary(self):
        # At 256 coefficients, the middle convolution coefficient equals 256:
        # its carry corrupts the next base-256 coefficient's parity.
        n = 256
        packed = sum(1 << (8 * i) for i in range(n))
        product = packed * packed
        wrong = sum(((product >> (8 * i)) & 1) << i for i in range(2 * n - 1))
        self.assertNotEqual(wrong, carryless((1 << n) - 1, (1 << n) - 1))
        with self.assertRaises(ValueError): PackedBits(n)
        with self.assertRaises(ValueError): PackedField(n, (1 << n) | 1)

    def test_invalid_shapes_and_elements(self):
        for n, mod in ((0, 1), (256, 1), (5, -37), (5, 33), (True, 3)):
            with self.assertRaises(ValueError): PackedField(n, mod)
        F = PackedField(5, modulus(5))
        for value in (-1, 32, True, 1.0):
            with self.assertRaises(ValueError): F.mul(value, 1)
            with self.assertRaises(ValueError): F.mul(1, value)
            with self.assertRaises(ValueError): F.sqr(value)
            with self.assertRaises(ValueError): F._bits.product(value, 1)

    def test_tables_are_target_independent_and_immutable(self):
        a, b = PackedField(31, modulus(31)), PackedField(31, modulus(31))
        self.assertEqual(a.__dict__, b.__dict__ | {'_bits': a._bits})
        self.assertTrue(all(isinstance(row, tuple) for row in (*a._squares, *a._reductions)))
        before = deepcopy(a.__dict__)
        for value in (0, 1, 7, (1 << 31) - 1):
            a.mul(value, value ^ 1); a.sqr(value)
        self.assertEqual(a.__dict__, before | {'_bits': a._bits})


class WitnessTests(unittest.TestCase):
    def test_frozen_witnesses_and_tampering(self):
        # This reads archived certificates only; the online query path still
        # creates fresh witnesses. The producer's native library is not used.
        data = json.loads(gzip.decompress((HERE.parent / 'round63/results/preflight.json.gz').read_bytes()))
        cases = {c['name']: c for c in data['inputs']}
        targets = json.loads((HERE.parent / 'round63/public_targets.json').read_text())
        reference = PublicReplay(31, 2147483657, 1)
        for mode in ('squares', 'packed'):
            checker = PreparedReplay(31, 2147483657, 1, mode)
            count = 0
            for row in data['rows']:
                case = cases[row['name']]; result = row['measurement']['result']
                if row['arm'] != 'native' or row['sanitizer'] or case['boundary'] != 'pdp' or not result['verified']:
                    continue
                anf = {}
                for i, equation in enumerate(case['equations']):
                    for mask in equation: anf[mask] = anf.get(mask, 0) ^ (1 << i)
                query = PublicQuery(case['n'], case['mod'], case['b'], case['m'], case['ell'],
                                    Point(*targets[row['name']]['target']), anf)
                assignment, witness = result['assignment'], result['curve_witness']
                self.assertTrue(checker.verify(query, assignment, witness))
                self.assertFalse(checker.verify(replace(query, anf={0: 1}), assignment, witness))
                for name in ('points', 'steps', 'slopes'):
                    for i in range(query.m):
                        bad = deepcopy(witness)
                        if name == 'slopes': bad[name][i] ^= 1
                        else: bad[name][i][1] ^= 1
                        self.assertFalse(reference.verify(query, assignment, bad))
                        self.assertFalse(checker.verify(query, assignment, bad))
                count += 1
            self.assertEqual(count, 5)

    def test_fresh_native_witnesses_and_no_producer_calls_in_check(self):
        rng = random.Random(202610036403)
        for n in (3, 5, 9, 31, 63):
            reference = PublicReplay(n, modulus(n), 1)
            for mode in ('squares', 'packed'):
                checker = PreparedReplay(n, reference.F.mod, 1, mode)
                natives = [NativeReplay(checker, sanitizer) for sanitizer in (False, True)]
                try:
                    for _ in range(10):
                        ell = min(n, 21)
                        points = [reference.E.random_factor_base_point(ell, rng) for _ in range(3)]
                        target = reference.E.sum(points)
                        if target.inf: continue
                        assignment = sum(p.x << (i * ell) for i, p in enumerate(points))
                        query = PublicQuery(n, reference.F.mod, 1, 3, ell, target, {})
                        expected = reference.find(query, assignment)
                        self.assertEqual(expected['status'], 'match')
                        for native in natives: self.assertEqual(native.find(query, assignment), expected)
                        self.assertTrue(checker.verify(query, assignment, expected['witness']))
                    def forbidden(*args): raise RuntimeError('producer operation in checker')
                    checker.F.inv = forbidden; checker.E.lift_x = forbidden; checker.E.add = forbidden
                    self.assertTrue(checker.verify(query, assignment, expected['witness']))
                finally:
                    for native in natives: native.close()


if __name__ == '__main__': unittest.main()
