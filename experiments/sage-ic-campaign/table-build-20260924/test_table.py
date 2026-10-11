"""Bitwise table contract across field widths, powers, and moduli."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np
from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('old_binary_hardware',
                                               HERE / 'baseline-pr75/binary_hardware.py')
incumbent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(incumbent)
NATIVE = binary_hardware._library()._name


class TableTests(unittest.TestCase):
    def compare(self, field, power):
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        with incumbent.FrobeniusPlan(curve, power, backend='cpu',
                                     native_library=NATIVE) as old:
            with binary_hardware.FrobeniusPlan(curve, power, backend='cpu',
                                               native_library=NATIVE) as new:
                np.testing.assert_array_equal(new._table, old._table)
                self.assertEqual(new._table.dtype, np.uint32)
                self.assertTrue(new._table.flags.c_contiguous)
                self.assertFalse(new._table.flags.writeable)

    def test_all_word_boundaries(self):
        for degree in (1, 2, 5, 8, 19, 31, 32, 33, 63, 64, 65,
                       67, 127, 128, 129, 131, 163, 255, 256):
            field = GF(2**degree, 'z')
            for power in (0, 1, 7, 65, -1):
                self.compare(field, power)

    def test_alternate_irreducible_moduli(self):
        for degree in (19, 131):
            standard = GF(2**degree, 'z')
            alternate = standard.modulus().reverse()
            self.assertTrue(alternate.is_irreducible())
            field = GF(2**degree, 'w', modulus=alternate)
            for power in (1, 7, 65):
                self.compare(field, power)


if __name__ == '__main__':
    unittest.main(verbosity=2)
