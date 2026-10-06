"""Count integrity tests for the actual audit helper, without Modal or a GPU."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from benchreport import benchResult, summarizeSamples


class PackedAuditCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'packed_audit.py'
        helper = next(node for node in ast.parse(path.read_text()).body
                      if isinstance(node, ast.FunctionDef) and node.name == 'checkScalarCounts')
        modePath = path.with_name('modal_app.py')
        modeHelper = next(node for node in ast.parse(modePath.read_text()).body
                          if isinstance(node, ast.FunctionDef) and node.name == 'checkPackedReduction')
        modeNamespace = dict(re=re, PACKED_DIRECT_REDUCE='0', PACKED_GENERATED_PRODUCT='0',
                             PACKED_STATE_TILE='0', PACKED_CLMAD='0', PACKED_CLMAD_SQUARE='0', PACKED_KARAT3='0', PACKED_WEIGHTED_PREFIX='0',
                             PACKED_COMPACT_STATE='0', PACKED_SHARED_SIGMA='0',
                             PACKED_TOP_CLMAD='0')
        exec(compile(ast.Module(body=[modeHelper], type_ignores=[]), str(modePath), 'exec'), modeNamespace)
        namespace = dict(re=re, client=SimpleNamespace(benchResult=benchResult,
                         checkPackedReduction=modeNamespace['checkPackedReduction']))
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(path), 'exec'), namespace)
        cls.check = staticmethod(namespace['checkScalarCounts'])

    def raw(self, workers=192512, weight=0, batch=32):
        walks = workers * batch
        expected = walks * 1024 * 32
        return (f'backend cuda-packed131: {workers} threads x {batch} slots x 1 lanes = {walks} walks, '
                f'dp weight {weight}, 1024 steps per launch\n'
                'packed direct reduction: 0\n'
                'packed generated product: 0\n'
                'packed native carryless multiply: 0\n'
                'packed native carryless square: 0\n'
                'packed three-limb Karatsuba: 0\n'
                'packed weighted prefix: 0\n'
                'packed compact state: 0\n'
                'packed shared sigma: 0\n'
                'packed top clmad: 0\n'
                'packed state tile: 0\n'
                f'1.0 s 6000.000 M it/s {expected // 2} iterations 0 dp 0 stored 0 dropped\n'
                f'2.0 s 6000.000 M it/s {expected} iterations 0 dp 0 stored 0 dropped\n'
                'finished: 6000.000 M it/s, 0 distinguished points (0 verified against the reference, 0 dropped)\n')

    def sample(self, raw):
        return benchResult(['fixture'], 0, raw)

    def test_explicit_and_automatic_workers(self):
        for requested in (0, 192512):
            sample = self.sample(self.raw())
            self.assertTrue(self.check(sample, requested, 0))
            self.assertEqual(sample['actualWorkers'], 192512)
            self.assertEqual(sample['expectedIterations'], 201863462912)
            self.assertEqual(sample['reportedIterations'], 201863462912)

    def test_top_clmad_identity_is_required_and_exact(self):
        # A rate is only comparable to the build it was requested from.  The
        # top-word clmad knob changes the arithmetic a product executes, so a
        # sample whose printed identity is missing, doubled or different from
        # the requested build must not rank -- exactly the rule every other
        # packed knob is held to.
        raw = self.raw()
        self.assertTrue(self.check(self.sample(raw), 0, 0))
        marker = 'packed top clmad: 0\n'
        self.assertIn(marker, raw)
        for bad in (raw.replace(marker, ''), raw.replace(marker, marker * 2),
                    raw.replace(marker, 'packed top clmad: 1\n'),
                    raw.replace(marker, 'packed top clmad: true\n')):
            sample = self.sample(bad)
            self.assertFalse(self.check(sample, 0, 0))
            self.assertFalse(sample['valid'])
            self.assertIn('top clmad', sample.get('error', ''))

    def test_invalid_work_cannot_keep_a_positive_summary(self):
        raw = self.raw()
        first, rest = raw.split('\n', 1)
        variants = {
            'inflated': raw.replace('201863462912 iterations', '403726925824 iterations'),
            'partial': raw.replace('201863462912 iterations', '151397597184 iterations'),
            'ignored workers': self.raw(workers=96256),
            'missing identity': rest,
            'duplicate identity': first + '\n' + raw,
            'wrong batch': raw.replace('32 slots', '16 slots'),
            'wrong steps': raw.replace('1024 steps', '512 steps'),
            'wrong cutoff': self.raw(weight=34),
            'missing reducer': raw.replace('packed direct reduction: 0\n', ''),
            'wrong reducer': raw.replace('packed direct reduction: 0', 'packed direct reduction: 1'),
            'duplicate reducer': raw + 'packed direct reduction: 0\n',
            'missing generated product': raw.replace('packed generated product: 0\n', ''),
            'wrong generated product': raw.replace('packed generated product: 0', 'packed generated product: 1'),
            'duplicate generated product': raw + 'packed generated product: 0\n',
            'missing native square mode': raw.replace('packed native carryless square: 0\n', ''),
            'wrong native square mode': raw.replace('packed native carryless square: 0', 'packed native carryless square: 1'),
            'duplicate native square mode': raw + 'packed native carryless square: 0\n',
            'missing native carryless mode': raw.replace('packed native carryless multiply: 0\n', ''),
            'wrong native carryless mode': raw.replace('packed native carryless multiply: 0', 'packed native carryless multiply: 1'),
            'duplicate native carryless mode': raw + 'packed native carryless multiply: 0\n',
            'missing weighted prefix': raw.replace('packed weighted prefix: 0\n', ''),
            'wrong weighted prefix': raw.replace('packed weighted prefix: 0', 'packed weighted prefix: 2'),
            'duplicate weighted prefix': raw + 'packed weighted prefix: 0\n',
            'missing tile': raw.replace('packed state tile: 0\n', ''),
            'wrong tile': raw.replace('packed state tile: 0', 'packed state tile: 256'),
            'duplicate malformed tile': raw + 'packed state tile: 1\n',
            'drops': raw.replace('0 dropped', '1 dropped'),
            'nonfinite': raw.replace('finished: 6000.000', 'finished: nan'),
        }
        for label, text in variants.items():
            with self.subTest(label=label):
                sample = self.sample(text)
                self.assertFalse(self.check(sample, 192512, 0))
                self.assertEqual(sample['rate'], 0)
                summary = summarizeSamples([self.sample(raw), sample])
                self.assertFalse(summary['valid'])
                self.assertEqual(summary['rate'], 0)

    def test_collection_uses_its_actual_mode_and_count(self):
        sample = self.sample(self.raw(weight=34))
        self.assertTrue(self.check(sample, 192512, 34))
        self.assertEqual(sample['reportedIterations'], 201863462912)
        self.assertFalse(self.check(self.sample(self.raw()), 192512, 34))

    def test_batch_and_workers_preserve_the_same_scalar_population(self):
        for batch, workers in ((8, 770048), (16, 385024), (32, 192512)):
            for weight in (0, 34):
                with self.subTest(batch=batch, weight=weight):
                    sample = self.sample(self.raw(workers, weight, batch))
                    self.assertTrue(self.check(sample, workers, weight, batch))
                    self.assertEqual(sample['requestedBatch'], batch)
                    self.assertEqual(sample['actualBatch'], batch)
                    self.assertEqual(sample['scalarWalks'], 6160384)
                    self.assertEqual(sample['reportedIterations'], 201863462912)

    def test_same_count_does_not_hide_wrong_geometry(self):
        for batch, workers in ((8, 770048), (16, 385024)):
            # This completed B32 fixture has the same total scalar work, but
            # must not satisfy a request for a different batch or population.
            sample = self.sample(self.raw())
            self.assertFalse(self.check(sample, workers, 0, batch))
            self.assertEqual(sample['rate'], 0)
            sample = self.sample(self.raw(workers, 0, batch))
            self.assertFalse(self.check(sample, 192512, 0, batch))
            self.assertEqual(sample['rate'], 0)


if __name__ == '__main__':
    unittest.main()

