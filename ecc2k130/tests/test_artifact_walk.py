import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'metal'))
sys.path.insert(0, str(ROOT / 'research' / 'step_table'))
import artifact_reference as reference
import run_walk
import pack


def encode(point):
    if point is None:
        return struct.pack('<9I', *((0,) * 8 + (0x80000000,)))
    x, y = point
    words = [(x >> (32 * i)) & 0xffffffff for i in range(4)]
    words += [(y >> (32 * i)) & 0xffffffff for i in range(4)]
    words += [(x >> 128) | ((y >> 128) << 3)]
    return struct.pack('<9I', *words)


class ArtifactReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        record = json.loads((ROOT / 'research/step_table/table32-20260921.json').read_text())
        positive, _ = pack.pack(record, 8)
        directions = bytearray()
        for offset in range(0, len(positive), 36):
            point = reference.decode(positive[offset:offset + 36])
            directions.extend(encode(point))
            directions.extend(encode(cls.negate(point)))
        cls.walk = reference.Reference(bytes(directions), 8)

    @staticmethod
    def negate(point):
        return None if point is None else (point[0], point[0] ^ point[1])

    def testSelectorConstantsAndDirections(self):
        for value in (0, 1, 3, (1 << 131) - 1, 0x123456789abcdef):
            self.assertEqual(reference.table.popcount(value), bin(value).count('1'))
        self.assertEqual(len(self.walk.constants()), 13708)
        self.assertEqual(len(self.walk.points), 2 * 131 * 8)
        for direction in range(0, len(self.walk.points), 71):
            self.assertEqual(self.walk.points[direction ^ 1], self.negate(self.walk.points[direction]))

    def testReplayIsDeterministicAndCoefficientFree(self):
        state1, reports1 = self.walk.replay(3, 17, 20260921, 96, -1)
        state2, reports2 = self.walk.replay(3, 17, 20260921, 96, -1)
        self.assertEqual((state1, reports1), (state2, reports2))
        values = reference.STATE.unpack(state1)
        self.assertEqual(values[16], 95)  # one seed addition, then 95 walk updates
        self.assertEqual(values[17], 1)
        self.assertEqual(values[20], 0)
        self.assertEqual(reports1, [])

    def testRelaxedDistinguishedPointsReseedAndReport(self):
        state, reports = self.walk.replay(0, 8, 1234, 48, 64)
        values = reference.STATE.unpack(state)
        self.assertGreater(values[17], 1)
        self.assertEqual(values[20], len(reports))
        for raw in reports:
            report = reference.REPORT.unpack(raw)
            self.assertEqual(report[2], 0)
            self.assertEqual(report[-1], 0)

    def testExceptionalSeedExhaustionIsTerminal(self):
        state = self.walk.initial(reference.MASK - 3)
        state['mode'] = 1
        self.walk.cycle(state, 0, 8, 130)
        # First cycle seeds; the next reports and cannot allocate seed+lanes.
        self.walk.cycle(state, 0, 8, 130)
        self.assertEqual(state['mode'], 3)

    def testThroughputAccounting(self):
        report = {'gpuSeconds': 2.0, 'dispatchWallSeconds': 4.0,
                  'walkUpdates': 1_000, 'groupOperations': 1_200,
                  'iterationsPerSecond': 500.0, 'millionIterationsPerSecond': 0.0005,
                  'chargedGroupOperationsPerSecond': 600.0, 'wallIterationsPerSecond': 250.0}
        run_walk.validateRates(report)
        report['iterationsPerSecond'] = 501.0
        with self.assertRaisesRegex(ValueError, 'accounting mismatch'):
            run_walk.validateRates(report)


if __name__ == '__main__':
    unittest.main()
