"""Independent transform certificate, lifetime, width and capability controls."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import os
import unittest

from adapter import Checker, base, native, producer

BACKENDS = ('cpu', 'metal', 'metal_simd') if os.environ.get('INDEPENDENT_TEST_METAL') == '1' else ('cpu',)


def discrete(record):
    """Compare all legacy logical counters; phase seconds are diagnostics."""
    if isinstance(record, dict):
        return {k: discrete(v) for k, v in record.items()
                if k not in ('backend', 'device_transform_stats') and not isinstance(v, float)}
    return record


class TransformTests(unittest.TestCase):
    def fixture(self, equations=3):
        anf = producer.Packed(5, equations, [(4, 1), (24, 1 << (equations-1)), (0, 1 << (equations-1))])
        with producer.Producer(2, 3, equations) as p:
            answer = p.produce(anf)
        return anf, answer['roots'], answer['basis'], answer['proof_bytes']

    def test_widths_sanitizers_and_prepared_generations(self):
        for eq in (1, 31, 32, 33, 63, 64, 65, 127, 128):
            args = self.fixture(eq)
            for flags in ({}, {'sanitizer': True}, {'transform_audit_test': True}):
                for backend in BACKENDS:
                    with Checker(2, 3, eq, transform_backend=backend, **flags) as c, base.Checker(2, 3, eq) as old:
                        expected = old.certify(*args)
                        for prepare in (False, True):
                            if prepare:
                                with c.prepare(args[0]) as token:
                                    result = c.certify_prepared(token, *args)
                                self.assertEqual(result['preparation_stats']['used'], 1)
                                self.assertEqual(result['preparation_stats']['recomputed'], 0)
                            else:
                                result = c.certify(*args)
                            self.assertTrue(result['verified'])
                            for name in ('stats', 'partial_stats', 'identity_check_stats',
                                         'partial_reservation_stats', 'partial_locality_stats', 'symmetry_check_stats'):
                                self.assertEqual(discrete(result[name]), discrete(expected[name]))
                            device = result['device_transform_stats']
                            self.assertEqual(device['executed'], int(backend != 'cpu'))
                            self.assertEqual(device['dispatches'], 0 if backend == 'cpu' else 2 if backend == 'metal' else 1)
                            if backend != 'cpu':
                                self.assertIn('registry=', device['device_name'])
                                self.assertEqual(device['input_bytes'], 7 * ((eq+63)//64) * 4 * (4 if eq <= 32 else 8))
                                if flags.get('transform_audit_test'):
                                    self.assertEqual(result['transform_check_stats']['audit_words'], device['input_bytes']//(4 if eq <= 32 else 8))

    def test_cross_thread_prepare_retains_device_metadata(self):
        args = self.fixture()
        for backend in BACKENDS:
            with Checker(2, 3, 3, transform_backend=backend) as c, ThreadPoolExecutor(max_workers=1) as pool:
                token = pool.submit(c.prepare, args[0]).result()
                result = c.certify_prepared(token, *args)
                self.assertTrue(result['verified'])
                self.assertEqual(result['device_transform_stats']['executed'], int(backend != 'cpu'))
                self.assertEqual(result['preparation_stats']['used'], 1)
                with self.assertRaises(ValueError): c.certify_prepared(token, *args)

    def test_failed_proof_retains_already_executed_preparation(self):
        args = self.fixture()
        for backend in BACKENDS:
            with Checker(2, 3, 3, transform_backend=backend) as c:
                token = c.prepare(args[0])
                result = c.certify_prepared(token, args[0], [*args[1], args[1][-1]], *args[2:])
                self.assertFalse(result['verified'])
                self.assertEqual(result['device_transform_stats']['executed'], int(backend != 'cpu'))
                self.assertEqual(result['preparation_stats']['discarded'], 1)

    def test_configuration_and_changed_input_invalidate_preparation(self):
        args = self.fixture()
        changed = producer.Packed(5, 3, [(4, 1), (24, 4), (0, 5)])
        for backend in BACKENDS:
            with Checker(2, 3, 3, transform_backend=backend) as c:
                token = c.prepare(args[0])
                with self.assertRaises(ValueError): c.certify_prepared(token, changed, *args[1:])
                token = c.prepare(args[0])
                c.configure_transform_backend('cpu')
                with self.assertRaises(ValueError): c.certify_prepared(token, *args)
                c.configure_transform('axes')
                with self.assertRaises(ValueError): c.configure_transform_backend('metal')
                c.configure_transform('full')
                c.configure_transform_backend(backend)
                if backend != 'cpu':
                    with self.assertRaises(RuntimeError): c.configure_transform('tile16')
                self.assertTrue(c.certify(*args)['verified'])
                for invalid in (True, None, 1, 'cuda'):
                    with self.assertRaises(ValueError): c.configure_transform_backend(invalid)
            with self.assertRaises(RuntimeError): c.configure_transform_backend('cpu')

    def test_bad_witnesses_preserve_rejection_and_charged_prefix(self):
        anf, roots, basis, raw = self.fixture()
        words = list((producer.U64 * (len(raw)//8)).from_buffer_copy(raw))
        altered = words[:]
        altered[5] ^= 4
        cases = [(roots[:-1], basis, raw), (roots, [], raw),
                 (roots, basis, bytes((producer.U64 * len(altered))(*altered))),
                 (roots, basis, raw[:-8]), ([*roots, roots[-1]], basis, raw)]
        for backend in BACKENDS:
            for flags in ({}, {'sanitizer': True}, {'partial_budget_test': True}, {'budget_test': True}):
                with Checker(2, 3, 3, transform_backend=backend, **flags) as c, base.Checker(2, 3, 3, **flags) as old:
                    for tail in cases:
                        try: expected = old.certify(anf, *tail)
                        except ValueError:
                            with self.assertRaises(ValueError): c.certify(anf, *tail)
                        else:
                            actual = c.certify(anf, *tail)
                            self.assertFalse(actual['verified'])
                            self.assertEqual(discrete(actual), discrete(expected))

    def test_valid_alternative_witness_is_still_accepted(self):
        # Equation bit 1 is zero in this fixture. Adding it to a multiplier
        # changes the encoding but not the certified identity.
        anf, roots, basis, raw = self.fixture()
        words = list((producer.U64 * (len(raw)//8)).from_buffer_copy(raw))
        words[5] ^= 2
        alternative = bytes((producer.U64 * len(words))(*words))
        for backend in BACKENDS:
            with Checker(2, 3, 3, transform_backend=backend) as c:
                self.assertTrue(c.certify(anf, roots, basis, alternative)['verified'])

    def test_portable_library_reports_explicit_unavailable(self):
        suffix = '.dylib' if native.sys.platform == 'darwin' else '.so'
        lib = ct.CDLL(str(native.HERE/'build'/('checker-unavailable'+suffix)))
        lib.check_create.argtypes = [ct.c_uint32]*3
        lib.check_create.restype = ct.c_void_p
        lib.check_destroy.argtypes = [ct.c_void_p]
        lib.check_device_transform_configure.argtypes = [ct.c_void_p, ct.c_uint32]
        lib.check_device_transform_configure.restype = ct.c_int
        handle = lib.check_create(2, 3, 3)
        self.assertTrue(handle)
        try:
            self.assertEqual(lib.check_device_transform_configure(handle, 1), -2)
            self.assertEqual(lib.check_device_transform_configure(handle, 0), 0)
            self.assertEqual(lib.check_device_transform_configure(handle, 3), -1)
        finally: lib.check_destroy(handle)


if __name__ == '__main__':
    unittest.main()
