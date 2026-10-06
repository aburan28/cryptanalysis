"""The default and sparse CPU paths work without a Metal library or device."""
import unittest
from unittest.mock import patch

from compare_query import GPUQuery, Curve, GF2n
from mapped_query import GPUChecker
from descend import make_instance


class PortableTests(unittest.TestCase):
    def test_cpu_default_and_sparse_match_original_equations(self):
        original = make_instance(11, 3, 2, seed=101)
        curve = Curve(GF2n(11, original.mod), original.b)
        target = curve.sum(original.points)
        expected = None
        with patch('compare_query.MappedQuery', side_effect=AssertionError('CPU must not create Metal work')):
            for arm in ('cpu', 'sparse-cpu'):
                with GPUQuery(11, original.mod, original.b, 3, 2, arm=arm) as query:
                    result = query.solve(target)
                self.assertTrue(result['verified'])
                self.assertIsNone(result['gpu_device'])
                self.assertEqual(original.evaluate(result['assignment']), 0)
                if expected is None:
                    expected = result['basis_sha256']
                self.assertEqual(result['basis_sha256'], expected)

    def test_explicit_unavailable_backend_is_reported(self):
        with patch('mapped_query.sys.platform', 'linux'):
            with self.assertRaisesRegex(RuntimeError, 'Metal requires macOS'):
                GPUChecker(2, 2)


if __name__ == '__main__':
    unittest.main()
