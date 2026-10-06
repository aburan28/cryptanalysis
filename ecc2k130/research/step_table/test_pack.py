import copy
import json
import pathlib
import struct
import unittest

import pack


class PackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((pathlib.Path(__file__).resolve().parent / 'table32-20260921.json').read_text())

    def testPrefixPackingAndExactMaterialization(self):
        root = pathlib.Path(__file__).resolve().parent / 'packed-20260921'
        for branches in (8, 16, 32):
            data, meta = pack.pack(self.record, branches)
            self.assertEqual(len(data), 131 * branches * 36)
            self.assertEqual(data, (root / ('table%d.bin' % branches)).read_bytes())
            self.assertEqual(meta, json.loads((root / ('table%d.json' % branches)).read_text()))
            # Every packed top word contains only the six specified bits.
            for offset in range(0, len(data), 36):
                self.assertLess(struct.unpack_from('<I', data, offset + 32)[0], 64)

    def testTamperingAndInvalidPrefixFail(self):
        changed = copy.deepcopy(self.record)
        changed['conjugates'][0][0] = '0x1'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            pack.pack(changed, 8)
        for branches in (0, 7, 64):
            with self.assertRaisesRegex(ValueError, 'prefix size'):
                pack.pack(self.record, branches)

    def testCoordinatesCannotBeTruncated(self):
        with self.assertRaises(ValueError):
            pack.linear(1 << 131, [0] * 131)
        with self.assertRaises(ValueError):
            pack.linear(-1, [0] * 131)


if __name__ == '__main__':
    unittest.main()
