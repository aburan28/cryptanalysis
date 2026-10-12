import unittest

from p256_isogeny_search.constants import P256, TOY_CURVE
from p256_isogeny_search.ec import ShortWeierstrassCurve


class CurveArithmeticTests(unittest.TestCase):
    def check_curve(self, parameters):
        curve = ShortWeierstrassCurve(parameters.p, parameters.a, parameters.b)
        generator = curve.from_affine((parameters.gx, parameters.gy))
        self.assertTrue(curve.is_on_curve(curve.to_affine(generator)))
        self.assertTrue(curve.scalar_mul(parameters.n, generator).is_infinity)
        doubled = curve.double(generator)
        self.assertTrue(curve.equal(doubled, curve.add(generator, generator)))
        self.assertTrue(
            curve.add(generator, curve.negate(generator)).is_infinity
        )

    def test_p256(self):
        self.check_curve(P256)

    def test_toy_curve(self):
        self.check_curve(TOY_CURVE)

    def test_batch_normalization_preserves_points(self):
        curve = ShortWeierstrassCurve(P256.p, P256.a, P256.b)
        generator = curve.from_affine((P256.gx, P256.gy))
        points = [
            curve.scalar_mul(scalar, generator) for scalar in (0, 1, 2, 17, 12345)
        ]
        normalized = curve.batch_normalize(points)
        self.assertTrue(all(curve.equal(a, b) for a, b in zip(points, normalized)))
        self.assertTrue(all(point.is_infinity or point.z == 1 for point in normalized))


if __name__ == "__main__":
    unittest.main()
