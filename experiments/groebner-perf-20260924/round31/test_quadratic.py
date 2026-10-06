"""Exact root/basis controls, including high-nullity fallback and failed reuse."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import random
import unittest

from quadratic import Producer, Packed, Inconclusive, Unsupported, SparseChecker, U32, U64
from sparse_checker import PackedANF


def packed(n, equations, items):
    items = list(items)
    masks = (U32*len(items))(*(m for m, _ in items))
    limbs = (equations+63)//64
    coefficients = (U64*(len(items)*limbs))(*(
        (c>>(64*j))&((1<<64)-1) for _, c in items for j in range(limbs)))
    return PackedANF(n, equations, masks, coefficients, len(items))


def roots(n, items):
    answer = []
    for point in range(1<<n):
        value = 0
        for monomial, coefficient in items:
            if point & monomial == monomial:
                value ^= coefficient
        if not value:
            answer.append(point)
    return answer


class ExactTests(unittest.TestCase):
    def check(self, x, y, equations, items, *, sanitizer=False):
        p = packed(x+y, equations, items)
        expected = roots(x+y, items)
        with Producer(x, y, equations, sanitizer=sanitizer) as producer:
            answer = producer.produce(p)
        self.assertEqual(answer['roots'], expected)
        with SparseChecker(x+y, equations, sanitizer=sanitizer) as checker:
            proof = checker.certify(p, answer['basis'])
            self.assertTrue(proof['verified'], proof)
            self.assertEqual(proof['solutions'], expected)
        return answer

    def test_exhaustive_single_equations(self):
        # All 256 Boolean functions on one fixed and two residual variables.
        for bits in range(256):
            items = [(m, 1) for m in range(8) if bits>>m&1]
            self.check(1, 2, 1, items)

    def test_random_wide_equations_and_duplicate_parity(self):
        rng = random.Random(2026092931)
        for sanitizer in (False, True):
            for x, y in ((1, 1), (2, 3), (3, 3), (3, 4)):
                for equations in (1, 31, 64, 65, 128):
                    items = [(m, rng.getrandbits(equations)) for m in range(1<<(x+y))
                             if (m>>x).bit_count()<=2 and rng.randrange(3)==0]
                    items += [(0, 1), (0, 1), (1, 0)]
                    self.check(x, y, equations, items, sanitizer=sanitizer)

    def test_lifted_false_roots_are_removed(self):
        # z0=z1=0, z0*z1=1 is linearly consistent in the lift, impossible in z.
        answer = self.check(1, 2, 3, [(2, 1), (4, 2), (6, 4), (0, 4)])
        self.assertEqual(answer['roots'], [])
        self.assertGreater(answer['stats']['lifted_candidates'], 0)

    def test_high_nullity_original_variable_fallback(self):
        answer = self.check(2, 4, 1, [(3, 1), (4|8, 1)])
        self.assertGreater(answer['stats']['fallback_branches'], 0)
        self.assertGreater(answer['stats']['fallback_assignments'], 0)

    def test_many_roots_do_not_return_partial_basis(self):
        for sanitizer in (False, True):
            with Producer(4, 5, 1, sanitizer=sanitizer) as producer:
                with self.assertRaises(Inconclusive):
                    producer.produce(packed(9, 1, []))
                # Numeric workspace must be reset after a failed call.
                answer = producer.produce(packed(9, 1, [(0, 1)]))
                self.assertEqual(answer['roots'], [])

    def test_budget_failure_and_reuse(self):
        with Producer(3, 3, 1, budget_test=True) as producer:
            with self.assertRaises(Inconclusive):
                producer.produce(packed(6, 1, []))
            self.assertEqual(producer.produce(packed(6, 1, [(0, 1)]))['roots'], [])

    def test_unsupported_and_invalid(self):
        with Producer(2, 3, 3) as producer:
            with self.assertRaises(Unsupported):
                producer.produce(packed(5, 3, [(4|8|16, 1)]))
            for p in (packed(5, 3, [(32, 1)]), packed(5, 3, [(0, 8)])):
                with self.assertRaises(ValueError):
                    producer.produce(p)
        with self.assertRaises(ValueError):
            Producer(20, 10, 1)
        with self.assertRaises(ValueError):
            Producer(2, 11, 1)

    def test_wide_masks_and_last_equation_limb(self):
        items = [(1, 1<<127), (2, 1), (0, 1)]
        expected = roots(5, items)
        with Producer(2, 3, 128) as producer:
            self.assertEqual(producer.produce(Packed(5, 128, items))['roots'], expected)

    def test_concurrent_workspace_and_close(self):
        inputs = [packed(5, 2, [(1, 1), (0, i&1), (2, 2)]) for i in range(16)]
        expected = [roots(5, [(1, 1), (0, i&1), (2, 2)]) for i in range(16)]
        with Producer(2, 3, 2) as producer:
            with ThreadPoolExecutor(max_workers=4) as pool:
                answers = list(pool.map(producer.produce, inputs))
            self.assertEqual([a['roots'] for a in answers], expected)
        with self.assertRaises(RuntimeError):
            producer.produce(inputs[0])


if __name__ == '__main__':
    unittest.main()
