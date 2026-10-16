"""tools/bitops.py reproduces every bitop/v1 reference vector exactly.

    python3 -m unittest tests/test_bitops.py -v
"""

import hashlib
import importlib.util
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bitops", ROOT / "tools" / "bitops.py")
bitops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bitops)

VECTORS = ROOT / "docs" / "units" / "bitop-v1.vectors.json"
# sha256 of crypto:docs/units/bitop-v1.vectors.json as copied (docs/units/README.md).
# The copy must stay byte-identical to the source; a changed vector is bitop/v2.
SOURCE_SHA256 = "36a78bd8baf445307e2198ac49a79394138b4e7ae9d7cb7028cf1536e35132d8"


class VectorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(VECTORS.read_text())

    def test_copy_equals_the_source(self):
        self.assertEqual(hashlib.sha256(VECTORS.read_bytes()).hexdigest(), SOURCE_SHA256)
        self.assertEqual(self.doc["schema"], "bitop.vectors/v1")
        self.assertEqual(self.doc["unit"], bitops.UNIT)

    def test_every_row_reproduces_exactly(self):
        rows = self.doc["vectors"]
        self.assertEqual(len(rows), 264)
        for row in rows:
            with self.subTest(**{"field": str(row["field"]), "r_bits": row["r_bits"], "prim": row["prim"]}):
                self.assertEqual(str(bitops.gates(row["prim"], row["field"], row["r_bits"])), row["gates"])

    def test_the_generated_set_is_the_committed_set(self):
        # Same rows in the same order: no primitive priced here that the reference leaves unpriced.
        self.assertEqual(bitops.vectors(), self.doc["vectors"])


class ConventionTest(unittest.TestCase):
    def test_small_widths_by_hand(self):
        self.assertEqual(bitops.int_mul(8), 64 + 7 * 40)
        self.assertEqual(bitops.f2_mul(3), 9 + 4 + 8)
        # I + 2M + S + 9A over F_{2^3}.
        self.assertEqual(bitops.gates("group_add", bitops.binary_field(3), 3), 90 + 42 + 8 + 27)

    def test_unpriced_primitives_raise(self):
        with self.assertRaises(bitops.NoPrice):
            bitops.gates("as_solve", bitops.prime_field(32), 32)
        with self.assertRaises(bitops.NoPrice):
            bitops.gates("legendre", bitops.binary_field(41), 39)
        with self.assertRaises(KeyError):
            bitops.gates("ec_add", bitops.binary_field(41), 39)

    def test_log2_and_work(self):
        self.assertEqual(bitops.log2(1 << 100), 100.0)
        self.assertLess(abs(bitops.log2(3) - math.log2(3)), 1e-15)
        self.assertLess(abs(bitops.log2((1 << 128) - 1) - 128.0), 1e-12)
        f = bitops.binary_field(13)
        w = bitops.work({"group_add": 3, "word_op": 2, "field_mul": 0}, f, 12)
        self.assertEqual(w["primitives"], {"group_add": 3, "word_op": 2})
        self.assertEqual(w["bitops"], 3 * bitops.gates("group_add", f, 12) + 128)
        self.assertEqual(w["unit"], "bitop/v1")


if __name__ == "__main__":
    unittest.main()
