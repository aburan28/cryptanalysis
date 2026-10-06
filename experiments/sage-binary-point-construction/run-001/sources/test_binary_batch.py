"""Exact tests; execute with sage -python -m unittest discover."""
import unittest

from sage.all import EllipticCurve, GF, set_random_seed
from load_candidate import add_pairs, candidate


class BinaryBatchTests(unittest.TestCase):
    def setUp(self):
        set_random_seed(20260923)

    def test_exhaustive_small_fields(self):
        for degree in (2, 3, 4):
            F = GF(2**degree, 'z')
            for a, b in ((F(0), F(1)), (F(1), F(1)), (F.gen(), F.gen())):
                E = EllipticCurve(F, [1, a, 0, 0, b])
                points = list(E)
                pairs = [(P, Q) for P in points for Q in points]
                self.assertEqual(add_pairs(E, iter(pairs)), [P + Q for P, Q in pairs])

    def test_large_fields_and_exceptional_cases(self):
        set_random_seed(20260923)
        for degree in (19, 31, 67, 131):
            F = GF(2**degree, 'z')
            for a, b in ((F(0), F(1)), (F(1), F(1)), (F.gen(), F.gen())):
                E = EllipticCurve(F, [1, a, 0, 0, b])
                points = [E.random_point() for _ in range(32)]
                O = E(0)
                T = E(0, b.sqrt())
                pairs = list(zip(points, points[1:] + points[:1]))
                pairs += [(P, P) for P in points]
                pairs += [(P, -P) for P in points]
                pairs += [(O, P) for P in points] + [(P, O) for P in points]
                pairs += [(T, T), (O, O), (T, points[0])]
                self.assertEqual(add_pairs(E, pairs), [P + Q for P, Q in pairs])
                self.assertEqual(add_pairs(E, []), [])
                self.assertEqual(add_pairs(E, pairs[:1]), [sum(pairs[0])])

    def test_reject_unsupported_inputs(self):
        E = EllipticCurve(GF(17), [1, 1])
        with self.assertRaises(ValueError):
            add_pairs(E, [])
        F = GF(2**3, 'z')
        E = EllipticCurve(F, [1, 1, 0, 0, 1])
        other = EllipticCurve(F, [1, 0, 0, 0, 1])
        with self.assertRaises(ValueError):
            add_pairs(E, [(E(0), other(0))])
        with self.assertRaises(ValueError):
            add_pairs(E, [(0, E(0))])
        unsupported = EllipticCurve(F, [0, 0, 1, 0, 1])
        with self.assertRaises(ValueError):
            add_pairs(unsupported, [])

    def test_batch_inversion(self):
        F = GF(2**8, 'z')
        values = list(F)[1:]
        self.assertEqual(candidate._invert_nonzero(values), [~x for x in values])
        self.assertEqual(candidate._invert_nonzero([]), [])
        self.assertEqual(candidate._invert_nonzero([F.gen()]), [~F.gen()])

    def test_cartesian_exhaustive_and_block_boundaries(self):
        for degree in (2, 3, 4):
            F = GF(2**degree, 'z')
            for a, b in ((F(0), F(1)), (F(1), F(1)), (F.gen(), F.gen())):
                E = EllipticCurve(F, [1, a, 0, 0, b])
                points = list(E)
                expected = [P + Q for P in points for Q in points]
                for size in (1, 3, 17, 1024):
                    actual = candidate.add_cartesian(E, iter(points), iter(points), size)
                    self.assertEqual(actual, expected)
                    for P in actual:
                        self.assertIs(P.curve(), E)
                        self.assertIs(P.parent(), E(0).parent())
                        self.assertEqual(type(P), type(E(0)))
                self.assertEqual(candidate.add_cartesian(E, [], points), [])
                self.assertEqual(candidate.add_cartesian(E, points, []), [])
                self.assertEqual(candidate.add_cartesian(E, points[:1]*3, points[:2]*2),
                                 [P+Q for P in points[:1]*3 for Q in points[:2]*2])

    def test_cartesian_large_and_input_validation(self):
        set_random_seed(20260924)
        for degree in (19, 31, 67, 131):
            F = GF(2**degree, 'z')
            E = EllipticCurve(F, [1, F.gen(), 0, 0, F.gen()])
            points = [E.random_point() for _ in range(16)] + [E(0), E(0, F.gen().sqrt())]
            self.assertEqual(candidate.add_cartesian(E, points, points, 31),
                             [P+Q for P in points for Q in points])
            with self.assertRaises(ValueError):
                candidate.add_cartesian(E, [E(0)], [0])
            for size in (0, -1):
                with self.assertRaises(ValueError):
                    candidate.add_cartesian(E, [], [], size)
            with self.assertRaises(TypeError):
                candidate.add_cartesian(E, [], [], 1.5)

    def test_output_point_interoperability(self):
        import pickle
        F = GF(2**19, 'z')
        E = EllipticCurve(F, [1, 1, 0, 0, 1])
        P, Q = E.random_point(), E.random_point()
        R = add_pairs(E, [(P, Q)])[0]
        self.assertEqual(hash(R), hash(P+Q))
        self.assertEqual(pickle.loads(pickle.dumps(R)), P+Q)
        self.assertEqual(3*R - Q, 3*P + 2*Q)
        self.assertEqual(E(list(R)), R)

    def test_frobenius_exhaustive_powers(self):
        for degree in (1, 2, 3, 4, 5):
            F = GF(2**degree, 'z')
            for a in (0, 1):
                E = EllipticCurve(F, [1,a,0,0,1])
                points = list(E)
                for k in (-degree-1, -1, 0, 1, 2, degree, degree+1):
                    phi = E.frobenius_isogeny(k % degree)
                    expected = [phi(P) for P in points]
                    actual = candidate.frobenius_points(E, iter(points), k)
                    self.assertEqual(actual, expected)
                    self.assertEqual(candidate.frobenius_points(E, actual, -k), points)

    def test_frobenius_large_homomorphism_and_validation(self):
        for degree in (19,31,67,131):
            F = GF(2**degree, 'z')
            for a in (0,1):
                E = EllipticCurve(F, [1,a,0,0,1])
                P, Q = E.random_point(), E.random_point()
                points = [P,Q,P+Q,-P,E(0),E(0,1)]
                for k in (1,7,-1):
                    actual = candidate.frobenius_points(E, points, k)
                    phi = E.frobenius_isogeny(k % degree)
                    self.assertEqual(actual, [phi(R) for R in points])
                    self.assertEqual(actual[0]+actual[1], actual[2])
                    self.assertEqual(-actual[0], actual[3])
                self.assertEqual(candidate.frobenius_points(E, []), [])
                with self.assertRaises(ValueError):
                    candidate.frobenius_points(E, [0])
                with self.assertRaises(TypeError):
                    candidate.frobenius_points(E, [], 0.5)
            for a,b in ((F.gen(),F(1)), (F(1),F.gen())):
                E = EllipticCurve(F,[1,a,0,0,b])
                with self.assertRaises(ValueError):
                    candidate.frobenius_points(E, [])


if __name__ == '__main__':
    unittest.main()
