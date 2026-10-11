"""Index/encoding checks for the large materialized pair table."""
import pathlib
import random
import struct
import unittest

import generate_large_pairs as large


class LargePairTests(unittest.TestCase):
    def testTriangularIndexBoundaries(self):
        directions = 2 * 131 * 256
        for v in range(directions):
            for u in (0, v // 2, v):
                index = large.pairIndex(u, v)
                self.assertEqual(large.pairIndices(index), (u, v))
                self.assertEqual(index, large.pairIndex(v, u))
        self.assertEqual(large.pairIndex(directions - 1, directions - 1) + 1, 2249360128)
        self.assertGreater(large.pairIndex(directions - 1, directions - 1), 2**31 - 1)
        self.assertEqual(562348416 * 36, 20244542976)
        self.assertEqual(2249360128 * 36, 80976964608)

    def testEncodingAndExceptionalPoint(self):
        self.assertIsNone(large.decode(struct.pack('<9I', *([0] * 8), 0x80000000)))
        self.assertEqual(large.decode(struct.pack('<9I', 1, 2, 3, 4, 5, 6, 7, 8, 63)),
                         (1 | (2 << 32) | (3 << 64) | (4 << 96) | (7 << 128),
                          5 | (6 << 32) | (7 << 64) | (8 << 96) | (7 << 128)))
        for raw in (b'', b'\0' * 35, struct.pack('<9I', *([0] * 8), 64),
                    struct.pack('<9I', 1, *([0] * 7), 0x80000000)):
            with self.assertRaises(ValueError):
                large.decode(raw)

    def testPilotDiskSample(self):
        root = pathlib.Path(__file__).resolve().parent / 'pair8-generator-check-20260921'
        if not (root / 'pairs.bin').exists():
            self.skipTest('local materialization is not present')
        directions = (root / 'directions.bin').read_bytes()
        points = [large.decode(directions[i:i + 36]) for i in range(0, len(directions), 36)]
        curve = large.CurvePb(large.Pb(131, large.POLY))
        rng = random.Random(60922)
        with (root / 'pairs.bin').open('rb') as output:
            for _ in range(32):
                u, v = rng.randrange(len(points)), rng.randrange(len(points))
                output.seek(36 * large.pairIndex(u, v))
                self.assertEqual(large.decode(output.read(36)), curve.add(points[u], points[v]))


if __name__ == '__main__':
    unittest.main()
