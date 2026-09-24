"""Point initialization invariants, plus the accepted arithmetic regression suite."""
import copy
import pickle
from pathlib import Path
import sys
import unittest

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_batch
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_native import BinaryBatchTests, NativeTests, generate


class ConstructionTests(unittest.TestCase):
    def fixture(self, degree=19):
        set_random_seed(2026092451+degree)
        field = GF(2**degree, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, field.gen(), 0, 0, field.gen()])
        points, _ = generate(curve, 8, 451+degree)
        return field, curve, points

    def test_fresh_state_and_interoperability(self):
        for degree in (5, 19, 67, 131):
            field, curve, points = self.fixture(degree)
            pairs = [(P,Q) for P in points for Q in points if P+Q]
            actual = binary_batch.add_pairs(curve, pairs)
            for result, (P,Q) in zip(actual, pairs):
                expected = P+Q
                fresh = curve._point(curve, list(expected), check=False)
                self.assertEqual(result.__dict__, fresh.__dict__)
                self.assertIs(type(result), type(fresh))
                self.assertIs(result.parent(), fresh.parent())
                self.assertIs(result.curve(), curve)
                self.assertTrue(result._normalized)
                self.assertIsInstance(result._coords, tuple)
                self.assertEqual(result[2], field.one())
                self.assertEqual(hash(result), hash(expected))
                self.assertIs(result.codomain(), curve)
                self.assertIs(result.domain(), fresh.domain())
                self.assertEqual(result.category(), fresh.category())
                self.assertEqual(result.xy(), expected.xy())
                self.assertEqual(tuple(result), tuple(expected))
                self.assertEqual(repr(result), repr(expected))
                self.assertEqual(curve(list(result)), expected)
                result.normalize_coordinates()
                self.assertEqual(result, expected)
                for reconstructed in (pickle.loads(pickle.dumps(result)),
                                      copy.copy(result), copy.deepcopy(result)):
                    self.assertEqual(reconstructed, expected)
                    self.assertIs(reconstructed.parent(), result.parent())
                    self.assertIs(type(reconstructed), type(result))
                    self.assertIsNot(reconstructed.__dict__, result.__dict__)
                self.assertEqual(result+P, expected+P)
                self.assertEqual(result-Q, P)
                self.assertEqual(-result, -expected)
            # Scalar multiplication exercises the normal point implementation.
            self.assertEqual(7*actual[0], 7*(pairs[0][0]+pairs[0][1]))

    def test_no_copied_caches_or_shared_output_state(self):
        _, curve, points = self.fixture(5)
        P = next(P for P in points if 2*P)
        P.order()
        P._batch_test_marker = 'input only'
        P.domain()
        P.codomain()
        actual = binary_batch.add_pairs(curve, [(P,P)]*4)
        for result in actual:
            self.assertEqual(set(result.__dict__), {'_coords','_codomain','_normalized'})
            self.assertEqual(result, 2*P)
        self.assertEqual(len({id(P) for P in actual}), 4)
        self.assertEqual(len({id(P.__dict__) for P in actual}), 4)
        actual[0]._batch_test_marker = 'output only'
        self.assertFalse(hasattr(actual[1], '_batch_test_marker'))

    def test_custom_point_constructor_is_preserved(self):
        _, curve, points = self.fixture()
        pairs = [(P,P) for P in points if 2*P]
        expected = [P+Q for P,Q in pairs]
        calls = {'allocate':0, 'initialize':0}

        class CustomPoint(EllipticCurvePoint_finite_field):
            def __new__(cls, *args, **kwargs):
                calls['allocate'] += 1
                return super().__new__(cls)

            def __init__(self, *args, **kwargs):
                calls['initialize'] += 1
                super().__init__(*args, **kwargs)
                self.custom_marker = 'constructed'

        original = curve._point
        try:
            curve._point = CustomPoint
            actual = binary_batch.add_pairs(curve, pairs)
            self.assertEqual(actual, expected)
            self.assertEqual(calls, {'allocate':len(pairs), 'initialize':len(pairs)})
            for point in actual:
                self.assertIs(type(point), CustomPoint)
                self.assertEqual(point.custom_marker, 'constructed')
                self.assertIs(point.parent(), curve.point_homset())
        finally:
            curve._point = original

    def test_unnormalized_inputs_and_normalization(self):
        field, curve, points = self.fixture()
        scale = field.gen()
        unnormalized = []
        for P in points:
            Q = copy.copy(P)
            Q._coords = tuple(c*scale for c in P)
            Q._normalized = False
            unnormalized.append(Q)
        actual = binary_batch.add_cartesian(curve, unnormalized, unnormalized, 3)
        expected = [P+Q for P in points for Q in points]
        self.assertEqual(actual, expected)
        for point in actual:
            self.assertTrue(point._normalized)
            self.assertEqual(curve(list(point)), point)

    def test_exceptional_results_keep_identity(self):
        field, curve, points = self.fixture()
        P = points[0]
        O = curve(0)
        T = curve(0, curve.a6().sqrt())
        actual = binary_batch.add_pairs(curve, [(O,P),(P,O),(O,O),(P,-P),(T,T)])
        self.assertIs(actual[0], P)
        self.assertIs(actual[1], P)
        self.assertIs(actual[2], O)
        self.assertEqual(actual[3:], [O,O])
        for point in actual:
            self.assertIs(point.curve(), curve)
            self.assertIs(type(point), type(P))
        self.assertEqual(binary_batch.add_pairs(curve, []), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
