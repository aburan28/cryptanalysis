"""Algebraic tests for the experimental table, separate from GPU validation."""

import hashlib
import json
import pathlib
import random
import unittest

import table

HERE = pathlib.Path(__file__).resolve().parent


class SelectorTests(unittest.TestCase):
    def testExhaustiveSmallFieldEquivariance(self):
        f, select = table.Onb(5), table.Selector(5)
        for x in range(1, 31):
            for y in range(32):
                tag = select.tag(x, y, 8)
                for k in range(5):
                    xx = f.toCoords(f.frob(f.fromCoords(x), k))
                    yy = f.toCoords(f.frob(f.fromCoords(y), k))
                    self.assertEqual(select.tag(xx, yy, 8), (tag[0], (tag[1] + k) % 5, tag[2]))
                    self.assertEqual(select.tag(xx, yy ^ xx, 8), (tag[0], (tag[1] + k) % 5, tag[2] ^ 1))

    def testPhaseExceptions(self):
        select = table.Selector(131)
        for x in (0, (1 << 131) - 1):
            with self.assertRaises(ValueError):
                select.orient(x, 0)

    def testCycleRule(self):
        t = (2, 19, 0)
        inv = (2, 19, 1)
        self.assertEqual(table.resolve(t, [inv], 8), (3, 19, 0))
        self.assertEqual(table.resolve(t, [(1, 20, 1), inv, (1, 20, 0)], 8), (3, 19, 0))
        self.assertEqual(table.resolve(t, [], 8), t)
        self.assertEqual(table.resolve((7, 0, 0), [(7, 0, 1)], 8), (0, 0, 0))
        # The rule must transform together with history under automorphisms.
        history = [(1, 20, 1), inv, (1, 20, 0)]
        for phase in range(131):
            for sign in (0, 1):
                def transform(tag):
                    return tag[0], (tag[1] + phase) % 131, tag[2] ^ sign
                self.assertEqual(table.resolve(transform(t), list(map(transform, history)), 8),
                                 transform(table.resolve(t, history, 8)))

    def testCoefficients(self):
        for branch in range(32):
            a = table.coefficient(20260921, branch, 0, 0, 2095853)
            self.assertTrue(0 < a < 2095853)
            self.assertEqual(a, table.coefficient(20260921, branch, 0, 0, 2095853))
            self.assertNotEqual(a, table.coefficient(20260921, branch, 1, 0, 2095853))


class MaterializedTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((HERE / 'table32-20260921.json').read_text())
        cls.f = table.Onb(131)
        cls.curve = table.Curve(cls.f)
        cls.selector = table.Selector(131)

    def point(self, row):
        return tuple(self.f.fromCoords(int(row[c], 16)) for c in ('x', 'y'))

    def testTableDigestAndCoordinates(self):
        record = self.record
        core = {k: v for k, v in record.items() if k not in (
            'identitySha256', 'setupGroupOps', 'auditGroupOps', 'buildSeconds',
            'packedCoordinatesBytes', 'cudaNineWordCoordinatesBytes', 'gpuMeasured')}
        self.assertEqual(hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         record['identitySha256'])
        self.assertEqual(len(record['rows']), 32)
        self.assertEqual(len(record['conjugates']), 32 * 131)
        seen = set()
        for row in record['rows']:
            p = self.point(row)
            self.assertTrue(self.curve.onCurve(p))
            key = self.selector.orient(int(row['x'], 16), int(row['y'], 16))[3]
            self.assertNotIn(key, seen)
            seen.add(key)
            for k in range(131):
                expected = self.curve.frob(p, k)
                encoded = record['conjugates'][32 * k + row['branch']]
                actual = tuple(self.f.fromCoords(int(v, 16)) for v in encoded)
                self.assertEqual(actual, expected)

    def testActual131BitStepAndCoefficients(self):
        record, c, f = self.record, self.curve, self.f
        base = tuple(f.fromCoords(int(v, 16)) for v in record['generator'])
        target = tuple(f.fromCoords(int(v, 16)) for v in record['target'])
        self.assertEqual(target, c.mul(base, table.KNOWN))
        ell, eigen = int(record['ell']), int(record['eigenvalue'])
        a, b = 1357, 1
        p = c.add(c.mul(base, a), target)
        history = []
        for _ in range(4):
            tag = self.selector.tag(f.toCoords(p[0]), f.toCoords(p[1]), 32)
            h, k, eps = table.resolve(tag, history, 32)
            entry = record['rows'][h]
            delta = c.frob(self.point(entry), k)
            factor = pow(eigen, k, ell) * (-1 if eps else 1)
            if eps:
                delta = c.neg(delta)
            p = c.add(p, delta)
            a = (a + factor * int(entry['a'])) % ell
            b = (b + factor * int(entry['b'])) % ell
            self.assertEqual(p, c.mul(base, (a + table.KNOWN * b) % ell))
            self.assertTrue(c.onCurve(p))
            history = (history + [(h, k, eps)])[-3:]

    def testRandom131BitSelectorCovariance(self):
        rng = random.Random(7091)
        for _ in range(64):
            x, y = rng.getrandbits(131), rng.getrandbits(131)
            tag = self.selector.tag(x, y, 32)
            for k in (0, 1, 19, 65, 130):
                xx = self.f.toCoords(self.f.frob(self.f.fromCoords(x), k))
                yy = self.f.toCoords(self.f.frob(self.f.fromCoords(y), k))
                self.assertEqual(self.selector.tag(xx, yy, 32), (tag[0], (tag[1] + k) % 131, tag[2]))
                self.assertEqual(self.selector.tag(xx, yy ^ xx, 32), (tag[0], (tag[1] + k) % 131, tag[2] ^ 1))


if __name__ == '__main__':
    unittest.main()
