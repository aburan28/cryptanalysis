"""Fresh coefficient copies, direct-table audit, word boundaries and charged exits."""
import ctypes as ct
import sys
import unittest

from adapter import HERE, Checker, load, producer
from locality_accounting import locality_accounting, compare_certificates

prior = load('local52_test_prior51', HERE.parent/'round51/adapter.py')
sys.path.insert(0, str(HERE))


class LocalityTests(unittest.TestCase):
    def test_fresh_valid_invalid_valid_and_every_cached_coefficient(self):
        for y, equations in [(3, e) for e in (31, 32, 33, 64, 65, 128)] + [(y, e) for y in (7, 10) for e in (32, 128)]:
            rank = max(1, y-3)
            high = 1 << (equations-1)
            terms = [(1 << (2+j), 1 << j) for j in range(rank)]
            terms += [(((1 << (y-2)) | (1 << (y-1))) << 2, high), (0, high)]
            changed = [*terms, (1, 1)]
            a, b = (producer.Packed(y+2, equations, t) for t in (terms, changed))
            with producer.Producer(2, y, equations) as p:
                answers = [p.produce(v) for v in (a, b)]
            for flags in ({}, {'sanitizer': True}, {'locality_audit_test': True}):
                old_flags = {'sanitizer': bool(flags)}
                with Checker(2, y, equations, **flags) as c, prior.Checker(2, y, equations, **old_flags) as old:
                    for symmetry in (False, True):
                        c.configure_symmetry(symmetry); old.configure_symmetry(symmetry)
                        for transform in ('full', 'axes', 'tile8', 'tile16', 'tile32', 'hoisted'):
                            c.configure_transform(transform); old.configure_transform(transform)
                            for identity in ('dense', 'factored_local'):
                                c.configure_identity(identity); old.configure_identity(identity)
                                for mode in ('strided', 'local'):
                                    c.configure_partial_coefficients(mode)
                                    for packed, answer, valid in ((a, answers[0], True), (b, answers[0], False), (b, answers[1], True), (a, answers[0], True)):
                                        args = packed, answer['roots'], answer['basis'], answer['proof_bytes']
                                        result, baseline = c.certify(*args), old.certify(*args)
                                        self.assertEqual(result['verified'], valid)
                                        compare_certificates(result, baseline)
                                        locality_accounting(result, y, equations, mode, audit='locality_audit_test' in flags)

    def test_budget_boundaries_and_zero_witnesses(self):
        packed = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with producer.Producer(2, 3, 3) as p:
            answer = p.produce(packed)
        for flag in ('budget_test', 'partial_budget_test', 'symmetry_budget_test', 'symmetry_workspace_test', 'symmetry_late_budget_test'):
            with Checker(2, 3, 3, **{flag: True}) as c, prior.Checker(2, 3, 3, **{flag: True}) as old:
                for mode in ('strided', 'local'):
                    c.configure_partial_coefficients(mode)
                    args = packed, answer['roots'], answer['basis'], answer['proof_bytes']
                    result, baseline = c.certify(*args), old.certify(*args)
                    compare_certificates(result, baseline)
                    locality_accounting(result, 3, 3, mode)
        words = list((producer.U64*(len(answer['proof_bytes'])//8)).from_buffer_copy(answer['proof_bytes']))
        for offset in range(4, len(words), 5):
            words[offset+1:offset+5] = [0]*4
        proof = bytes((producer.U64*len(words))(*words))
        with Checker(2, 3, 3, locality_audit_test=True, symmetry=False) as c:
            result = c.certify(packed, answer['roots'], answer['basis'], proof)
            self.assertTrue(result['verified'])
            self.assertGreater(result['partial_stats']['records'], 0)
            self.assertEqual(result['partial_locality_stats']['copy_words'], 0)
            locality_accounting(result, 3, 3, 'local', audit=True)

    def test_configuration_lifecycle(self):
        with Checker(2, 3, 3) as c:
            for bad in (True, False, 0, 1, None, 'cached'):
                with self.assertRaises(ValueError):
                    c.configure_partial_coefficients(bad)
            self.assertEqual(c.lib.check_partial_locality_configure(None, 0), -1)
            self.assertEqual(c.lib.check_partial_locality_configure(c._handle, 2), -1)
            for mode in ('strided', 'local', 'strided', 'local'):
                c.configure_partial_coefficients(mode)
        with self.assertRaises(RuntimeError):
            c.configure_partial_coefficients('local')


if __name__ == '__main__':
    unittest.main()
