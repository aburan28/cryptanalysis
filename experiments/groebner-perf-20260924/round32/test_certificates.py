"""Exhaustive arithmetic and forged-proof controls for complete branch coverage."""
from concurrent.futures import ThreadPoolExecutor
import os
import random
import sys
import unittest

from certified import Producer, Checker, Packed, Inconclusive, Unsupported, U64
from quadratic_reference import verify_basis


def roots(n, items):
    return [a for a in range(1 << n) if not evaluate(items, a)]


def evaluate(items, a):
    value = 0
    for m, c in items:
        if a&m == m:
            value ^= c
    return value


def proof_words(proof):
    return [int.from_bytes(proof[i:i+8], sys.byteorder) for i in range(0, len(proof), 8)]


def verify_contradictions(x, y, equations, items, proof):
    words, limbs = proof_words(proof), (equations+63)//64
    assert len(words) == (1 << x)*limbs
    marked = 0
    for a in range(1 << x):
        u = sum(words[a*limbs+i] << (64*i) for i in range(limbs))
        assert u < 1 << equations
        if not u:
            continue
        marked += 1
        polynomial = set()
        for mask, c in items:
            left, right = mask&((1 << x)-1), mask>>x
            if left&a == left and (c&u).bit_count()%2:
                polynomial.symmetric_difference_update((right,))
        assert polynomial == {0}, (a, u, polynomial)
    return marked


class CertificateTests(unittest.TestCase):
    def check(self, x, y, equations, items, *, backend='cpu', sanitizer=False):
        anf = Packed(x+y, equations, items)
        with Producer(x, y, equations, backend=backend, sanitizer=sanitizer) as producer, \
             Checker(x, y, equations, sanitizer=sanitizer) as checker:
            answer = producer.produce(anf, checker=checker)
        expected = roots(x+y, items)
        self.assertEqual(answer['roots'], expected)
        self.assertTrue(answer['certificate']['verified'], answer['certificate'])
        self.assertTrue(verify_basis(x+y, items, expected, answer['basis'], len(expected)))
        self.assertEqual(verify_contradictions(x, y, equations, items, answer['proof_bytes']),
                         answer['certificate']['stats']['contradictions'])
        self.assertEqual(answer['certificate']['stats']['contradictions'], (1 << x)-answer['stats']['consistent'])
        self.assertEqual(answer['certificate']['stats']['branches'], 1 << x)
        self.assertEqual(answer['certificate']['stats']['assignments'],
                         answer['certificate']['stats']['enumerated_branches']*(1 << y))
        return answer

    def test_every_three_variable_boolean_function(self):
        for bits in range(256):
            items = [(m, 1) for m in range(8) if bits>>m&1]
            self.check(1, 2, 1, items)

    def test_seeded_equation_widths_duplicates_and_ubsan(self):
        rng = random.Random(2026092932)
        for sanitizer in (False, True):
            for x, y in ((1, 1), (2, 3), (4, 3), (1, 7)):
                for equations in (1, 31, 32, 33, 64, 65, 128):
                    items = [(m, rng.getrandbits(equations)) for m in range(1 << (x+y))
                             if (m>>x).bit_count() <= 2 and rng.randrange(3) == 0]
                    items += [(0, 1), (0, 1), (1, 0)]
                    self.check(x, y, equations, items, sanitizer=sanitizer)

    def test_spurious_lift_roots_and_high_nullity_fallback(self):
        a = self.check(1, 2, 3, [(2, 1), (4, 2), (6, 4), (0, 4)])
        self.assertEqual(a['roots'], [])
        self.assertEqual(a['certificate']['stats']['contradictions'], 0)
        self.assertEqual(a['certificate']['stats']['assignments'], 8)
        a = self.check(2, 4, 1, [(3, 1), (4|8, 1)])
        self.assertGreater(a['stats']['fallback_branches'], 0)

    def test_forged_contradictions_and_incomplete_roots(self):
        items = [(1 << i, 1 << i) for i in range(5)]
        p = Packed(5, 5, items)
        with Producer(2, 3, 5) as producer, Checker(2, 3, 5) as checker:
            a = producer.produce(p)
            words = proof_words(a['proof_bytes'])
            words[0] = 1  # Actual root branch cannot derive the constant 1.
            bad = checker.certify(p, a['roots'], a['basis'], (U64*len(words))(*words))
            self.assertEqual(bad['code'], 9)
            self.assertEqual(checker.certify(p, [], a['basis'], a['proof_bytes'])['code'], 3)
            self.assertEqual(checker.certify(p, [0, 0], a['basis'], a['proof_bytes'])['code'], 2)
            self.assertEqual(checker.certify(p, [1], a['basis'], a['proof_bytes'])['code'], 2)
            for basis in ([[0]], [], [[1, 0]]):
                self.assertFalse(checker.certify(p, a['roots'], basis, a['proof_bytes'])['verified'])
            with self.assertRaises(ValueError):
                checker.certify(p, a['roots'], a['basis'], a['proof_bytes'][:-8])
            with self.assertRaises(ValueError):
                checker.certify(p, a['roots'], a['basis'], a['proof_bytes']+b'\0'*8)
            # Omitting a witness is safe only because the whole branch is checked.
            empty = (U64*4)()
            valid = checker.certify(p, a['roots'], a['basis'], empty)
            self.assertTrue(valid['verified'])
            self.assertEqual(valid['stats']['assignments'], 32)

    def test_budget_root_limits_and_successful_reuse(self):
        p = Packed(9, 1, [(0, 1)])
        with Producer(4, 5, 1) as producer, Checker(4, 5, 1, budget_test=True) as checker:
            a = producer.produce(p)
            self.assertTrue(checker.certify(p, [], a['basis'], a['proof_bytes'])['verified'])
            self.assertEqual(checker.certify(p, [], a['basis'], (U64*16)())['code'], 5)
            self.assertTrue(checker.certify(p, [], a['basis'], a['proof_bytes'])['verified'])
            with self.assertRaises(Inconclusive):
                producer.produce(Packed(9, 1, []))
            self.assertEqual(producer.produce(p)['roots'], [])
        with Checker(4, 5, 1) as checker:
            self.assertEqual(checker.certify(Packed(9, 1, []), [], [], (U64*16)())['code'], 5)
        with Producer(3, 3, 1, budget_test=True) as producer:
            with self.assertRaises(Inconclusive):
                producer.produce(Packed(6, 1, []))
            self.assertEqual(producer.produce(Packed(6, 1, [(0, 1)]))['roots'], [])

    def test_invalid_wide_witness_and_unsupported_degree(self):
        with Producer(2, 3, 65) as producer, Checker(2, 3, 65) as checker:
            p = Packed(5, 65, [(0, 1 << 64)])
            a = producer.produce(p, checker=checker)
            self.assertTrue(a['certificate']['verified'])
            words = proof_words(a['proof_bytes'])
            words[1] |= 2
            with self.assertRaises(ValueError):
                checker.certify(p, [], [[0]], (U64*len(words))(*words))
            high = Packed(5, 65, [(4|8|16, 1)])
            with self.assertRaises(Unsupported):
                producer.produce(high)
            self.assertEqual(checker.certify(high, [], [[0]], (U64*8)())['code'], 7)
        with self.assertRaises(ValueError):
            Producer(20, 10, 31)
        with self.assertRaises(ValueError):
            Checker(20, 10, 31)

    def test_nonlinear_complete_certificates_beyond_twenty_variables(self):
        for x, y in ((14, 7), (14, 10), (16, 10)):
            n = x+y
            fixed = 0x1234 & ((1 << x)-1)
            items = [(1 << i, 1 << i) for i in range(x)] + [(0, fixed)]
            # y0*y1=1, yj=y0. This has exactly the all-one residual root.
            items += [((1 << x)|(1 << (x+1)), 1 << x), (0, 1 << x)]
            items += [(1 << (x+j), 1 << (x+j)) for j in range(1, y)]
            items += [(1 << x, sum(1 << (x+j) for j in range(1, y)))]
            expected = [fixed | (((1 << y)-1) << x)]
            p = Packed(n, n, items)
            with Producer(x, y, n) as producer, Checker(x, y, n) as checker:
                a = producer.produce(p, checker=checker)
                self.assertEqual(a['roots'], expected)
                self.assertTrue(a['certificate']['verified'], a['certificate'])
                self.assertTrue(verify_basis(n, items, expected, a['basis'], 1))
                self.assertEqual(a['certificate']['stats']['enumerated_branches'], 1)
                self.assertEqual(a['certificate']['stats']['assignments'], 1 << y)
                self.assertEqual(checker.certify(p, [], a['basis'], a['proof_bytes'])['code'], 3)

    def test_concurrent_calls_and_closed_handles(self):
        inputs = [Packed(5, 2, [(1, 1), (0, i&1), (2, 2)]) for i in range(16)]
        with Producer(2, 3, 2) as producer, Checker(2, 3, 2) as checker:
            with ThreadPoolExecutor(max_workers=4) as pool:
                result = list(pool.map(lambda p: producer.produce(p, checker=checker), inputs))
            self.assertTrue(all(a['certificate']['verified'] for a in result))
        with self.assertRaises(RuntimeError):
            producer.produce(inputs[0])
        with self.assertRaises(RuntimeError):
            checker.evaluate(inputs[0], 0)


@unittest.skipUnless(os.environ.get('QUADRATIC_TEST_METAL') == '1', 'Metal not requested')
class MetalCertificateTests(CertificateTests):
    # Inherited tests also cover the portable checker and fallback libraries;
    # every small arithmetic comparison actually executes the GPU when supported.
    def check(self, x, y, equations, items, *, backend='cpu', sanitizer=False):
        if sanitizer:
            return super().check(x, y, equations, items, sanitizer=True)
        a = super().check(x, y, equations, items, backend='metal')
        self.assertEqual(a['stats']['gpu_used'], int(equations <= 32 and y*(y+1)//2 <= 31))
        return a


if __name__ == '__main__':
    unittest.main()
