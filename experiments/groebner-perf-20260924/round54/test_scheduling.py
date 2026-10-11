"""Exact scheduled output and deterministic failure/drain controls."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import sys
import threading
import unittest
from unittest.mock import patch

from adapter import Checker, HERE, load, producer, scheduling

prior = load('schedule53_prior52', HERE.parent/'round52/adapter.py')
accounting = load('schedule53_accounting', HERE.parent/'round52/locality_accounting.py')
sys.path.insert(0, str(HERE))


def sample(equations=3):
    return producer.Packed(5, equations, [(4, 1), (24, 1 << (equations-1)),
                                         (0, 1 << (equations-1))])


class SchedulingTests(unittest.TestCase):
    def test_serial_prepared_overlap_exact_output_and_reuse(self):
        for equations in (3, 32, 33, 65, 128):
            anf = sample(equations)
            with producer.Basis(2, 3, equations) as basis, prior.producer.Basis(2, 3, equations) as old:
                expected = old.compute(anf)
                for mode in ('serial', 'prepared', 'overlap', 'overlap', 'serial'):
                    basis.configure_preparation(mode)
                    actual = basis.compute(anf)
                    self.assertEqual(actual['status'], 'gb')
                    for field in ('basis_terms', 'basis_sha256', 'proof_bytes', 'proof_sha256'):
                        self.assertEqual(actual[field], expected[field], field)
                    accounting.compare_certificates(actual['basis_certificate'], expected['basis_certificate'])
                    receipt = actual['preparation_schedule']
                    self.assertTrue(receipt['drained'])
                    self.assertEqual(receipt['worker_count'], 2 if mode == 'overlap' else 1)
                    if mode != 'serial':
                        self.assertEqual(actual['basis_certificate']['preparation_stats']['used'], 1)
                        self.assertEqual(receipt['preparation_code'], 0)
                        self.assertGreaterEqual(receipt['prepare_end_ns'], receipt['prepare_start_ns'])
                        self.assertGreaterEqual(receipt['schedule_wall_ns'], receipt['snapshot_ns'])
                        self.assertEqual(receipt['input_snapshot_bytes'], ct.sizeof(anf.masks)+ct.sizeof(anf.coefficients))

    def test_owned_snapshot_survives_original_mutation(self):
        for width in (32, 64):
            for equations in (32, 65):
                anf = sample(equations)
                anf.masks = ((ct.c_uint32 if width == 32 else ct.c_uint64)*len(anf.masks))(*anf.masks)
                with Checker(2, 3, equations) as checker:
                    owned = scheduling.snapshot(checker, anf)
                expected = bytes(owned.masks), bytes(owned.coefficients)
                anf.masks[0] ^= 1
                anf.coefficients[0] ^= 1
                self.assertEqual((bytes(owned.masks), bytes(owned.coefficients)), expected)
                self.assertIs(type(owned.masks), type(anf.masks))

    def test_producer_failures_drain_worker_and_close_waits(self):
        # Events make the worker stay live until both the producer failure and
        # close request have happened. No sleeps or timing speed claims.
        for error in (producer.Inconclusive('budget control'), RuntimeError('producer control')):
            basis = producer.Basis(2, 3, 3)
            basis.configure_preparation('overlap')
            checker = basis.checker
            entered, release, failed, closing = (threading.Event() for _ in range(4))
            prepare = checker.prepare

            def held_prepare(anf):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('test worker release timed out')
                return prepare(anf)

            def fail_producer(*args, **kwargs):
                self.assertTrue(entered.wait(10))
                failed.set()
                raise error

            def close():
                closing.set()
                basis.close()

            try:
                with patch.object(checker, 'prepare', held_prepare), patch.object(basis.producer, 'produce', fail_producer), ThreadPoolExecutor(2) as pool:
                    run = pool.submit(basis.compute, sample())
                    try:
                        self.assertTrue(failed.wait(10))
                        closed = pool.submit(close)
                        self.assertTrue(closing.wait(10))
                        self.assertFalse(run.done())
                        self.assertFalse(closed.done())
                    finally:
                        release.set()
                    if isinstance(error, producer.Inconclusive):
                        answer = run.result(10)
                        self.assertEqual(answer['status'], 'inconclusive')
                        receipt = answer['preparation_schedule']
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'producer control') as raised:
                            run.result(10)
                        receipt = raised.exception.preparation_schedule
                    closed.result(10)
                    self.assertTrue(receipt['drained'])
                    self.assertEqual(receipt['preparation_code'], 0)
                    self.assertIs(basis.checker, checker)
                    self.assertIsNone(basis._preparation_executor)
            finally:
                release.set()
                basis.close()

    def test_preparation_errors_propagate_and_next_query_recovers(self):
        for mode in ('prepared', 'overlap'):
            with producer.Basis(2, 3, 3) as basis:
                basis.configure_preparation(mode)
                checker = basis.checker
                with patch.object(checker, 'prepare', side_effect=RuntimeError('prepare control')):
                    with self.assertRaisesRegex(RuntimeError, 'prepare control') as raised:
                        basis.compute(sample())
                receipt = raised.exception.preparation_schedule
                self.assertTrue(receipt['drained'])
                self.assertIn('prepare control', receipt['preparation_error'])
                self.assertIs(basis.checker, checker)
                self.assertTrue(basis.compute(sample())['complete'])

    def test_failed_preparation_keeps_serial_fallback_and_receipt(self):
        for mode in ('prepared', 'overlap'):
            with producer.Basis(2, 3, 3) as basis:
                basis.configure_preparation(mode)
                checker = basis.checker
                prepare = checker.prepare

                def soft_failure(anf):
                    prepared = prepare(anf)
                    prepared.code = 5
                    return prepared

                with patch.object(checker, 'prepare', soft_failure):
                    answer = basis.compute(sample())
                self.assertTrue(answer['complete'])
                self.assertEqual(answer['basis_certificate']['preparation_stats']['used'], 0)
                self.assertEqual(answer['preparation_schedule']['preparation_code'], 5)
                self.assertEqual(answer['preparation_schedule']['preparation']['ready'], 1)

    def test_independent_workers_and_configuration_lifecycle(self):
        def run(equations):
            with producer.Basis(2, 3, equations) as basis:
                basis.configure_preparation('overlap')
                return basis.compute(sample(equations))

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, (3, 65)))
        for equations, result in zip((3, 65), results):
            self.assertTrue(result['complete'])
            self.assertEqual(result['basis_certificate']['preparation_stats']['bound_words'], 3*(1+(equations+63)//64))
        basis = producer.Basis(2, 3, 3)
        for mode in (None, True, '', 'gpu'):
            with self.assertRaises(ValueError):
                basis.configure_preparation(mode)
        basis.configure_preparation('overlap')
        basis.close()
        basis.close()
        with self.assertRaises(RuntimeError):
            basis.configure_preparation('serial')
        with self.assertRaises(RuntimeError):
            basis.compute(sample())


if __name__ == '__main__':
    unittest.main()
