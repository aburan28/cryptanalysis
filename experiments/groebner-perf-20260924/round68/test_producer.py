"""Exact producer compatibility, failure accounting, fresh queries and owner serialization."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import gzip
import json
import os
import unittest

from adapter import HERE, Checker, ProjectionQuery, base, producer
from public_replay import Point

METAL = os.environ.get('PRODUCER_TEST_METAL') == '1'
BACKENDS = ('cpu', 'metal') if METAL else ('cpu',)
MODES = ('cpu', 'metal', 'metal_tiled')
REFERENCE = base.producer


def logical(record):
    return {key: value for key, value in record.items() if type(value) in (int, bool)}


class SharedProducerTests(unittest.TestCase):
    def test_query_factories_keep_the_unchanged_reference(self):
        item = json.loads(gzip.decompress((HERE.parent / 'round40/fixtures/inputs.json.gz').read_bytes()))[0]
        shape = tuple(item[key] for key in ('n', 'mod', 'b', 'm', 'ell'))
        with ProjectionQuery(*shape) as new, base.ProjectionQuery(*shape) as old:
            self.assertEqual(new.basis.producer.path.parent.parent.name, 'round68')
            self.assertEqual(old.basis.producer.path.parent.parent.name, 'round51')
            self.assertEqual(new.checker.path.parent.parent.name, 'round66')
            self.assertEqual(old.checker.path.parent.parent.name, 'round66')
            actual, expected = new.solve(Point(**item['target'])), old.solve(Point(**item['target']))
            self.assertTrue(actual['verified'] and expected['verified'])
            self.assertEqual(actual['proof_sha256'], expected['proof_sha256'])
            self.assertIn('producer_transform_stats', actual)
            self.assertNotIn('producer_transform_stats', expected)

    def fixture(self, equations=3, last=0):
        return producer.Packed(5, equations, [(4, 1), (24, 1 << (equations - 1)),
                                              (0, (1 << (equations - 1)) ^ last)])

    def compare(self, actual, expected):
        for name in ('roots', 'basis', 'proof_bytes', 'proof_sha256', 'proof_byteorder'):
            self.assertEqual(actual[name], expected[name], name)
        for name in ('stats', 'gpu_projection_stats', 'partial_stats', 'projection_stats',
                     'normalization_stats', 'multiplier_stats', 'deferred_stats', 'symmetry_stats'):
            self.assertEqual(logical(actual[name]), logical(expected[name]), name)

    def accounting(self, answer, mode, backend, equations=3):
        stats = answer['producer_transform_stats']
        requested = MODES.index(mode)
        self.assertEqual(stats['requested_mode'], requested)
        self.assertEqual(stats['executed_mode'], requested)
        self.assertEqual(stats['additional_table_bytes'], 0)
        bytes_ = 4 * 7 * 4
        used = backend == 'metal' and equations <= 32
        self.assertEqual(stats['projection_uploaded_bytes'], bytes_ if used and not requested else 0)
        self.assertEqual(stats['projection_reused_bytes'], bytes_ if requested else 0)
        self.assertEqual(stats['kernel']['input_bytes'], bytes_ if requested else 0)
        self.assertEqual(stats['kernel']['output_bytes'], bytes_ if requested else 0)
        self.assertEqual(stats['kernel']['completed_dispatches'], (2 if mode == 'metal' else 1) if requested else 0)

    def test_widths_builds_and_unchanged_independent_checker(self):
        for equations in (1, 31, 32, 33, 63, 64, 65, 127, 128):
            anf = self.fixture(equations)
            for backend in BACKENDS:
                modes = MODES if backend == 'metal' and equations <= 32 else ('cpu',)
                with REFERENCE.Producer(2, 3, equations, backend=backend) as old:
                    expected = old.produce(anf)
                for sanitizer in (False, True):
                    with producer.Producer(2, 3, equations, backend=backend, sanitizer=sanitizer) as p, Checker(2, 3, equations, constant_identity='prepared') as checker:
                        for mode in modes:
                            p.configure_producer_transform(mode)
                            actual = p.produce(anf, checker=checker)
                            self.compare(actual, expected)
                            self.assertTrue(actual['certificate']['verified'])
                            self.accounting(actual, mode, backend, equations)
                        if modes == ('cpu',):
                            with self.assertRaisesRegex(RuntimeError, 'compatible Metal producer'):
                                p.configure_producer_transform('metal_tiled')
                            self.assertEqual(p.producer_transform, 'cpu')
                            self.compare(p.produce(anf), expected)

    def test_fresh_inputs_symmetry_projection_and_partial_modes(self):
        for backend in BACKENDS:
            with producer.Producer(2, 3, 3, backend=backend) as p, REFERENCE.Producer(2, 3, 3, backend=backend) as old, Checker(2, 3, 3, constant_identity='prepared') as checker:
                for partial in (False, True):
                    p.configure_partial(partial); old.configure_partial(partial)
                    for projection in (False, True):
                        p.configure_gpu_projection(projection); old.configure_gpu_projection(projection)
                        for mode in MODES if backend == 'metal' else ('cpu',):
                            p.configure_producer_transform(mode)
                            for last in (0, 1, 2, 0):
                                anf = self.fixture(last=last)
                                actual = p.produce(anf, checker=checker)
                                self.compare(actual, old.produce(anf))
                                self.assertTrue(actual['certificate']['verified'])
                                self.accounting(actual, mode, backend)
                                bad = actual['proof_bytes'][:-8]
                                with self.assertRaises(ValueError):
                                    checker.certify(anf, actual['roots'], actual['basis'], bad)

    def test_early_failure_resets_metadata_then_recovers(self):
        for backend in BACKENDS:
            with producer.Producer(2, 3, 3, backend=backend) as p:
                for mode in MODES if backend == 'metal' else ('cpu',):
                    p.configure_producer_transform(mode)
                    anf = self.fixture()
                    expected = p.produce(anf)
                    masks, width, coefficients = p.views(anf)
                    original = coefficients[0]
                    coefficients[0] |= 1 << 3
                    stats = producer.Stats()
                    result = p.lib.branch_solve(p._handle, masks, width, coefficients, len(masks), ct.byref(stats))
                    self.assertFalse(result)
                    self.assertEqual(p.lib.branch_error_code(), 6)
                    failed = p.lib.branch_last_producer_transform_stats().contents.record()
                    self.assertEqual(failed['requested_mode'], MODES.index(mode))
                    self.assertEqual(failed['executed_mode'], 0)
                    self.assertEqual(failed['kernel']['completed_dispatches'], 0)
                    self.assertEqual(failed['projection_reused_bytes'], 0)
                    coefficients[0] = original
                    self.compare(p.produce(anf), expected)

    def test_budget_failures_keep_executed_gpu_work(self):
        for backend in BACKENDS:
            for sanitizer in (False, True):
                # Explicit enumeration budget build; sanitizer is exercised by
                # separate successful/failing shape controls in the other groups.
                if sanitizer: continue
                with producer.Producer(2, 3, 3, backend=backend, enumeration_budget_test=True) as p:
                    reference = None
                    for mode in MODES if backend == 'metal' else ('cpu',):
                        p.configure_producer_transform(mode)
                        with self.assertRaises(producer.Inconclusive) as caught:
                            p.produce(self.fixture())
                        failure = caught.exception
                        current = {name: logical(getattr(failure, name)) for name in
                                   ('metrics', 'gpu_projection_stats', 'partial_stats', 'projection_stats',
                                    'normalization_stats', 'multiplier_stats', 'deferred_stats', 'symmetry_stats')}
                        if reference is None: reference = current
                        else: self.assertEqual(current, reference)
                        self.accounting({'producer_transform_stats': failure.producer_transform_stats}, mode, backend)
                        # A successful contradiction after the budget failure must
                        # use entirely fresh coefficients and a new generation.
                        success = p.produce(producer.Packed(5, 3, [(0, 1)]))
                        self.assertEqual(success['roots'], [])
                        self.assertEqual(success['basis'], [[0]])

    def test_existing_budget_controls_preserve_cpu_results(self):
        for flag in ('budget_test', 'multiplier_budget_test', 'copy_budget_test',
                     'reconstruction_budget_test', 'partial_commit_budget_test'):
            with producer.Producer(2, 3, 3, **{flag: True}) as p, REFERENCE.Producer(2, 3, 3, **{flag: True}) as old:
                for anf in (self.fixture(), producer.Packed(5, 3, [(0, 1)])):
                    try: expected = old.produce(anf)
                    except producer.Inconclusive as previous:
                        with self.assertRaises(producer.Inconclusive) as current: p.produce(anf)
                        self.assertEqual(logical(current.exception.metrics), logical(previous.metrics))
                    else: self.compare(p.produce(anf), expected)

    def test_owner_serialization_configuration_and_close(self):
        for backend in BACKENDS:
            inputs = [self.fixture(last=last) for last in (0, 1, 2, 0)]
            with REFERENCE.Producer(2, 3, 3, backend=backend) as old:
                expected = [old.produce(anf) for anf in inputs]
            with producer.Producer(2, 3, 3, backend=backend) as p:
                modes = MODES if backend == 'metal' else ('cpu',)
                for bad in (True, 1, None, 'invalid'):
                    with self.assertRaises(ValueError): p.configure_producer_transform(bad)
                self.assertEqual(p.lib.branch_producer_transform_configure(None, 0), -1)
                self.assertEqual(p.lib.branch_producer_transform_configure(p._handle, 99), -1)
                def call(index):
                    p.configure_producer_transform(modes[index % len(modes)])
                    return p.produce(inputs[index % len(inputs)])
                with ThreadPoolExecutor(max_workers=4) as pool:
                    answers = list(pool.map(call, range(16)))
                for index, answer in enumerate(answers): self.compare(answer, expected[index % len(inputs)])
                if backend == 'metal':
                    self.assertEqual(len({answer['producer_transform_stats']['generation'] for answer in answers}), 16)
            with self.assertRaises(RuntimeError): p.produce(inputs[0])
            with self.assertRaises(RuntimeError): p.configure_producer_transform('cpu')


if __name__ == '__main__': unittest.main()
