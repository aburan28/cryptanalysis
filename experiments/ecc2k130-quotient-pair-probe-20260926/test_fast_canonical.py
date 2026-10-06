"""Exact equivalence controls for the x-first quotient canonicalization."""

import unittest

import curves
import field
from fast_canonical import canonical_x_first
from perf_probe import base_prefix
from quotient_pair_probe import canonical, make_base


class CanonicalXFirstTest(unittest.TestCase):
    def check_points(self, curve, base, degree):
        points = [None]
        points.extend(base[:8])
        points.extend(curve.add(base[i], base[-i - 1]) for i in range(8))
        points.extend(curve.frob(point) for point in base[:4])
        points.extend(curve.neg(point) for point in base[:4])
        for point in points:
            with self.subTest(degree=degree, point=point):
                self.assertEqual(canonical_x_first(curve, point, degree),
                                 canonical(curve, point, degree))

    def test_polynomial_basis_toy_curves(self):
        for degree, weight in ((13, 1), (19, 2), (23, 2)):
            _, curve, _, base, _ = make_base(degree, weight)
            self.check_points(curve, base, degree)

    def test_optimal_normal_basis_stage_curves(self):
        for degree, cofactor in ((53, 428), (83, 4)):
            order = curves.curveOrder(degree) // cofactor
            _, curve, base, _, _ = base_prefix(degree, cofactor, order, 2)
            self.check_points(curve, base, degree)

    def test_degree_131_curve_lifts(self):
        onb = field.Onb(131)
        curve = curves.Curve(onb)
        points = []
        for j in range(1, 20):
            point = curve.pointFromX(onb.fromCoords(1 | (1 << j)))
            if point is not None:
                points.extend((point, curve.neg(point), curve.frob(point)))
            if len(points) >= 9:
                break
        self.assertEqual(len(points), 9)
        for point in points:
            with self.subTest(point=point):
                self.assertEqual(canonical_x_first(curve, point, 131),
                                 canonical(curve, point, 131))


if __name__ == "__main__":
    unittest.main()
