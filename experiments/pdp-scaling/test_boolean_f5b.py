import random
import unittest

from boolean_f5b import BooleanF5B


class BooleanF5BTests(unittest.TestCase):
    def test_implicit_field_pairs_are_required_for_singleton_basis(self):
        engine = BooleanF5B(2)
        polynomial = engine.from_terms([0, 3])  # xy + 1
        self.assertFalse(engine.is_groebner([polynomial]))
        self.assertFalse(engine.is_groebner(
            [polynomial], engine.reduction_table([polynomial])))
        basis = engine.basis([polynomial])
        self.assertEqual([sorted(engine.terms(p)) for p in basis],
                         [[0, 1], [0, 2]])
        self.assertTrue(engine.is_groebner(basis))

    def test_indexed_syzygy_divisibility(self):
        engine = BooleanF5B(5)
        engine.index_syzygy((0b00101, 3))
        self.assertTrue(engine.redundant_indexed((0b10101, 3), 0))
        self.assertFalse(engine.redundant_indexed((0b10001, 3), 0))

    def test_packed_grevlex_order_matches_sympy(self):
        from sympy.polys.orderings import grevlex

        nvars = 6
        engine = BooleanF5B(nvars)
        masks = list(range(1 << nvars))
        expected = sorted(masks, key=lambda mask: grevlex(tuple(
            (mask >> i) & 1 for i in range(nvars))))
        self.assertEqual(sorted(masks, key=engine.order_key), expected)

    def test_random_bases_preserve_all_boolean_roots(self):
        rng = random.Random(8301)
        for nvars in range(2, 7):
            for _ in range(24):
                engine = BooleanF5B(nvars, timeout=5)
                generators = []
                for _ in range(nvars + 1):
                    terms = {rng.randrange(1 << nvars)
                             for _ in range(rng.randrange(1, 9))}
                    generators.append(engine.from_terms(terms))
                basis = engine.basis(generators)
                self.assertTrue(engine.same_roots(generators, basis))
                self.assertTrue(engine.is_groebner(basis))


if __name__ == "__main__":
    unittest.main()
