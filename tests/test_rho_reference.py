"""tools/rho_reference.py: one rho reference, two named batch variants.

    python3 -m unittest tests/test_rho_reference.py -v
"""

import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rho_reference", ROOT / "tools" / "rho_reference.py")
rho = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rho)


class RhoReferenceTest(unittest.TestCase):
    def test_scalar_mul_ops_is_ceil_three_halves_bits(self):
        # Rust: (3 * bits).div_ceil(2); Python: (3 * bits + 1) // 2 -- the same integer for every bits.
        for bits in range(0, 300):
            r = (1 << bits) - 1 if bits else 0
            self.assertEqual(r.bit_length(), bits)
            self.assertEqual(rho.scalar_mul_ops(r), -(-3 * bits // 2))
            self.assertEqual(rho.scalar_mul_ops(r), math.ceil(Fraction3(bits)))

    def test_floor_and_single_target(self):
        r, n = 130873, 19
        self.assertEqual(rho.single_target_group_operations(r), math.sqrt(math.pi * r / 2))
        self.assertEqual(rho.floor_group_operations(r, 2 * n), math.sqrt(math.pi * r / (4 * n)))
        self.assertAlmostEqual(rho.single_target_group_operations(r) / math.sqrt(r), 1.2533141373155003)

    def test_variants(self):
        r = 1000003
        s = rho.scalar_mul_ops(r)
        for t in (1, 2, 9):
            for a in (1, 6):
                g = rho.batch_group_operations(r, t, a, "generous")
                w = rho.batch_group_operations(r, t, a, "with_setup")
                self.assertAlmostEqual(w - g, t * (2 * s + 1) + 32 * s, places=6)
        self.assertEqual(rho.batch_group_operations(r, 1, 6, "generous"), math.sqrt(math.pi * (r / 6) / 2))
        # sum_{k<T} C(2k,k)/4^k
        self.assertAlmostEqual(rho.kuhn_struik_series(4), 1 + 1 / 2 + 3 / 8 + 5 / 16)
        with self.assertRaises(ValueError):
            rho.batch_group_operations(r, 1, 1, "folded")

    def test_references_block(self):
        ref = rho.references(1000003, 4, 6, 7)
        for v in rho.VARIANTS:
            block = ref["variants"][v]
            self.assertEqual(block["independent_batch_operations"], 4 * block["single_target_operations"])
            self.assertEqual(block["single_target_operations"] % 7, 0)
        self.assertLess(ref["variants"]["generous"]["folded_batch_operations"],
                        ref["variants"]["with_setup"]["folded_batch_operations"])


def Fraction3(bits):
    from fractions import Fraction

    return Fraction(3 * bits, 2)


if __name__ == "__main__":
    unittest.main()
