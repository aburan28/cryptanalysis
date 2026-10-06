"""Exact checker compatibility, fresh-proof ownership and failure-prefix controls."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import importlib.util
import os
import unittest
from adapter import HERE, Checker, native, producer

spec = importlib.util.spec_from_file_location('constant_reference65', HERE.parent/'round65/independent_checker.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
BACKENDS = ('cpu', 'metal_simd') if os.environ.get('INDEPENDENT_TEST_METAL') == '1' else ('cpu',)
MODES = ('original', 'prepared', 'folded')


def logical(value):
    if isinstance(value, dict):
        return {k: logical(v) for k, v in value.items()
                if k != 'constant_identity_stats' and not isinstance(v, float)}
    return value


class ConstantCheckerTests(unittest.TestCase):
    def fixture(self, equations=3):
        anf = producer.Packed(5, equations, [(4, 1), (24, 1 << (equations-1)), (0, 1 << (equations-1))])
        with producer.Producer(2, 3, equations) as p:
            answer = p.produce(anf)
        return anf, answer['roots'], answer['basis'], answer['proof_bytes']

    def test_widths_builds_symmetry_and_preparation(self):
        for eq in (1, 31, 32, 33, 63, 64, 65, 127, 128):
            args = self.fixture(eq)
            for symmetry in (False, True):
                for backend in BACKENDS:
                    with reference.Checker(2, 3, eq, symmetry=symmetry, transform_backend=backend) as old:
                        expected = old.certify(*args)
                        for flags in ({}, {'sanitizer': True}, {'constant_audit_test': True}):
                            for mode in MODES:
                                with Checker(2, 3, eq, symmetry=symmetry, transform_backend=backend,
                                             constant_identity=mode, **flags) as c:
                                    for prepare in (False, True):
                                        if prepare:
                                            with c.prepare(args[0]) as token:
                                                actual = c.certify_prepared(token, *args)
                                        else: actual = c.certify(*args)
                                        self.assertTrue(actual['verified'])
                                        for name in ('stats','partial_stats','symmetry_check_stats',
                                                     'identity_check_stats','partial_reservation_stats','partial_locality_stats'):
                                            self.assertEqual(logical(actual[name]), logical(expected[name]))
                                        stats = actual['constant_identity_stats']
                                        self.assertEqual(stats['requested'], MODES.index(mode))
                                        self.assertEqual(stats['used'], int(mode != 'original'))
                                        words = 4*((eq+63)//64) if mode != 'original' else 0
                                        self.assertEqual(stats['prepared_words'], words)
                                        self.assertEqual(stats['workspace_bytes'], words*(4 if eq <= 32 else 8))
                                        self.assertEqual(stats['features'], 7)
                                        self.assertEqual(stats['avoided_parities'], actual['symmetry_check_stats']['avoided_constant_parities'])
                                        self.assertEqual(stats['audit_features'], 7 if flags.get('constant_audit_test') and mode!='original' else 0)

    def test_changed_witnesses_preserve_first_failure_and_accounting(self):
        anf = producer.Packed(5, 3, [(0, 1), (4, 2), (8, 4)])
        for symmetry in (False, True):
            for mode in MODES:
                with Checker(2, 3, 3, symmetry=symmetry, constant_identity=mode, constant_audit_test=True) as c, reference.Checker(2, 3, 3, symmetry=symmetry) as old:
                    for witness, features in ((1,7),(3,2),(5,3),(1,7),(0,7)):
                        words = (producer.U64*4)(1,1,1,witness)
                        args = anf, [], [[0]], bytes(words)
                        actual, expected = c.certify(*args), old.certify(*args)
                        self.assertEqual(logical(actual), logical(expected))
                        self.assertEqual(actual['constant_identity_stats']['features'], features)
                        self.assertEqual(actual['constant_identity_stats']['avoided_parities'], actual['symmetry_check_stats']['avoided_constant_parities'])

    def test_bad_witnesses_and_budget_prefixes(self):
        anf, roots, basis, raw = self.fixture()
        words = list((producer.U64*(len(raw)//8)).from_buffer_copy(raw))
        words[5] ^= 4
        cases = [(roots[:-1], basis, raw), (roots, [], raw),
                 (roots, basis, bytes((producer.U64*len(words))(*words))),
                 (roots, basis, raw[:-8]), ([*roots, roots[-1]], basis, raw)]
        for mode in MODES:
            for flags in ({}, {'sanitizer':True}, {'partial_budget_test':True}, {'budget_test':True}, {'symmetry_late_budget_test':True}):
                with Checker(2,3,3,constant_identity=mode,**flags) as c, reference.Checker(2,3,3,**flags) as old:
                    for tail in cases:
                        try: expected=old.certify(anf,*tail)
                        except ValueError:
                            with self.assertRaises(ValueError): c.certify(anf,*tail)
                        else:
                            actual=c.certify(anf,*tail)
                            self.assertFalse(actual['verified'])
                            self.assertEqual(logical(actual),logical(expected))

    def test_valid_alternative_witness(self):
        anf, roots, basis, raw = self.fixture()
        words=list((producer.U64*(len(raw)//8)).from_buffer_copy(raw)); words[5]^=2
        for mode in MODES:
            with Checker(2,3,3,constant_identity=mode) as c:
                self.assertTrue(c.certify(anf,roots,basis,bytes((producer.U64*len(words))(*words)))['verified'])

    def test_configuration_and_fresh_input_invalidate_generation(self):
        args=self.fixture(); changed=producer.Packed(5,3,[(4,1),(24,4),(0,5)])
        with Checker(2,3,3) as c:
            for mode in MODES:
                token=c.prepare(args[0]); c.configure_constant_identity(mode)
                with self.assertRaises(ValueError): c.certify_prepared(token,*args)
                token=c.prepare(args[0])
                with self.assertRaises(ValueError): c.certify_prepared(token,changed,*args[1:])
                self.assertTrue(c.certify(*args)['verified'])
            for mode in (True, 1, None, 'invalid'):
                with self.assertRaises(ValueError): c.configure_constant_identity(mode)
        with self.assertRaises(RuntimeError): c.configure_constant_identity('original')

    def test_cross_thread_preparation_and_owner(self):
        args=self.fixture()
        for mode in MODES:
            with Checker(2,3,3,constant_identity=mode) as c, Checker(2,3,3) as other, ThreadPoolExecutor(max_workers=1) as pool:
                token=pool.submit(c.prepare,args[0]).result()
                with self.assertRaises(ValueError): other.certify_prepared(token,*args)
                actual=c.certify_prepared(token,*args)
                self.assertTrue(actual['verified']); self.assertEqual(actual['constant_identity_stats']['requested'],MODES.index(mode))
                with self.assertRaises(ValueError): c.certify_prepared(token,*args)

    def test_early_failure_does_not_reuse_previous_stats(self):
        args=self.fixture()
        with Checker(2,3,3,constant_identity='prepared') as c:
            self.assertTrue(c.certify(*args)['verified'])
            token=c.prepare(args[0])
            failed=c.certify_prepared(token,args[0],[*args[1],args[1][-1]],*args[2:])
            self.assertFalse(failed['verified']); self.assertEqual(failed['constant_identity_stats']['used'],0)
            self.assertEqual(failed['constant_identity_stats']['prepared_words'],0)
            self.assertEqual(failed['preparation_stats']['discarded'],1)

    def test_allocation_failure_leaves_original_available(self):
        args=self.fixture()
        with self.assertRaises(RuntimeError): Checker(2,3,3,constant_identity='prepared',constant_workspace_test=True)
        with Checker(2,3,3,constant_workspace_test=True) as c:
            with self.assertRaises(RuntimeError): c.configure_constant_identity('prepared')
            self.assertEqual(c.constant_identity,'original')
            actual=c.certify(*args); self.assertTrue(actual['verified'])
            self.assertEqual(actual['constant_identity_stats']['workspace_bytes'],0)

    def test_capability_and_invalid_native_mode(self):
        suffix='.dylib' if native.sys.platform=='darwin' else '.so'
        lib=ct.CDLL(str(HERE/'build'/('checker-unavailable'+suffix)))
        lib.check_create.argtypes=[ct.c_uint32]*3; lib.check_create.restype=ct.c_void_p
        lib.check_destroy.argtypes=[ct.c_void_p]
        for name in ('check_constant_configure','check_device_transform_configure'):
            fn=getattr(lib,name); fn.argtypes=[ct.c_void_p,ct.c_uint32]; fn.restype=ct.c_int
        handle=lib.check_create(2,3,3)
        self.assertTrue(handle)
        try:
            self.assertEqual(lib.check_device_transform_configure(handle,2),-2)
            self.assertEqual(lib.check_constant_configure(handle,1),0)
            self.assertEqual(lib.check_constant_configure(handle,3),-1)
            self.assertEqual(lib.check_constant_configure(handle,0),0)
        finally: lib.check_destroy(handle)


if __name__=='__main__': unittest.main()
