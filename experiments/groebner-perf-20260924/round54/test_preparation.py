"""Exact input binding, one-shot lifetime and proof-dependent fallback semantics."""
import ctypes as ct
import sys
import unittest

from adapter import Checker, HERE, load, producer

prior = load('prepared53_test_prior52', HERE.parent/'round52/adapter.py')
accounting = load('prepared53_test_accounting52', HERE.parent/'round52/locality_accounting.py')
sys.path.insert(0, str(HERE))


class PreparationTests(unittest.TestCase):
    def test_prepared_matches_serial_on_all_modes_and_word_boundaries(self):
        for equations in (31, 32, 33, 64, 65, 128):
            terms = [(4, 1), (24, 1 << (equations-1)), (0, 1 << (equations-1))]
            anf = producer.Packed(5, equations, terms)
            with producer.Producer(2, 3, equations) as p:
                answer = p.produce(anf)
            args = anf, answer['roots'], answer['basis'], answer['proof_bytes']
            for flags in ({}, {'sanitizer': True}, {'transform_audit_test': True}, {'locality_audit_test': True}):
                with Checker(2, 3, equations, **flags) as c, prior.Checker(2, 3, equations, **flags) as old:
                    for symmetry in (False, True):
                        c.configure_symmetry(symmetry); old.configure_symmetry(symmetry)
                        for transform in ('full', 'axes', 'tile8', 'tile16', 'tile32', 'hoisted'):
                            c.configure_transform(transform); old.configure_transform(transform)
                            for mode in ('strided', 'local'):
                                c.configure_partial_coefficients(mode); old.configure_partial_coefficients(mode)
                                expected = old.certify(*args)
                                accounting.compare_certificates(c.certify(*args), expected)
                                with c.prepare(anf) as prepared:
                                    self.assertEqual(prepared.code, 0)
                                    result = c.certify_prepared(prepared, *args)
                                accounting.compare_certificates(result, expected)
                                self.assertEqual(result['preparation_stats']['used'], 1)
                                self.assertEqual(result['preparation_stats']['recomputed'], 0)
                                self.assertEqual(result['preparation_stats']['bound_words'], len(terms)*(1+(equations+63)//64))

    def test_stale_changed_input_configuration_and_owner_are_rejected(self):
        a = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        b = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 3)])
        with producer.Producer(2, 3, 3) as p:
            answer = p.produce(a)
        tail = answer['roots'], answer['basis'], answer['proof_bytes']
        with Checker(2, 3, 3) as c, Checker(2, 3, 3) as other:
            prepared = c.prepare(a)
            with self.assertRaises(ValueError):
                c.certify_prepared(prepared, b, *tail)
            with self.assertRaises(ValueError):
                c.certify_prepared(prepared, a, *tail)
            prepared = c.prepare(a)
            with self.assertRaises(ValueError):
                other.certify_prepared(prepared, a, *tail)
            self.assertTrue(c.certify_prepared(prepared, a, *tail)['verified'])
            old, new = c.prepare(a), c.prepare(a)
            # Discarding an older generation must not discard the newer one.
            old.close()
            self.assertTrue(c.certify_prepared(new, a, *tail)['verified'])
            for configure in (lambda: c.configure_transform('full'), lambda: c.configure_identity('dense'),
                              lambda: c.configure_symmetry(True), lambda: c.configure_partial_coefficients('local')):
                with c.prepare(a) as prepared:
                    configure()
                    with self.assertRaises(ValueError):
                        c.certify_prepared(prepared, a, *tail)
                self.assertTrue(c.certify(a, *tail)['verified'])
            prepared = c.prepare(a)
            self.assertTrue(c.certify(a, *tail)['verified'])
            with self.assertRaises(ValueError):
                c.certify_prepared(prepared, a, *tail)
        with self.assertRaises(RuntimeError):
            c.prepare(a)

    def test_proof_budget_fallback_rebuilds_and_keeps_old_counters(self):
        # Input symmetry is cheap, but the proof-offset initialization exceeds
        # the soft budget. A speculative tile transform must be rebuilt in full.
        anf = producer.Packed(11, 3, [(0, 1)])
        with producer.Producer(8, 3, 3) as p:
            answer = p.produce(anf)
        args = anf, answer['roots'], answer['basis'], answer['proof_bytes']
        for transform in ('tile8', 'tile16', 'tile32', 'hoisted'):
            with Checker(8, 3, 3, transform=transform, symmetry_late_budget_test=True) as c, prior.Checker(8, 3, 3, transform=transform, symmetry_late_budget_test=True) as old:
                expected = old.certify(*args)
                with c.prepare(anf) as prepared:
                    result = c.certify_prepared(prepared, *args)
                self.assertTrue(result['verified'])
                self.assertEqual(result['preparation_stats']['recomputed'], 1)
                accounting.compare_certificates(result, expected)

    def test_charged_failures_and_native_invalid_tokens(self):
        anf = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with producer.Producer(2, 3, 3) as p:
            answer = p.produce(anf)
        args = anf, answer['roots'], answer['basis'], answer['proof_bytes']
        for flag in ('budget_test', 'partial_budget_test', 'symmetry_budget_test', 'symmetry_workspace_test', 'symmetry_late_budget_test'):
            with Checker(2, 3, 3, **{flag: True}) as c, prior.Checker(2, 3, 3, **{flag: True}) as old:
                with c.prepare(anf) as prepared:
                    result = c.certify_prepared(prepared, *args)
                accounting.compare_certificates(result, old.certify(*args))
                with c.prepare(anf) as prepared:
                    prepared.token = 0
                    with self.assertRaises(ValueError):
                        c.certify_prepared(prepared, *args)
                with c.prepare(anf) as prepared:
                    prepared.token += 1
                    with self.assertRaises(ValueError):
                        c.certify_prepared(prepared, *args)

    def test_prepared_malformed_and_incomplete_proofs_match_prior(self):
        anf = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with producer.Producer(2, 3, 3) as p:
            answer = p.produce(anf)
        raw = answer['proof_bytes']
        words = list((producer.U64*(len(raw)//8)).from_buffer_copy(raw))
        cases = [(answer['roots'][:-1], answer['basis'], raw),
                 (answer['roots'], [], raw),
                 ([*answer['roots'], answer['roots'][-1]], answer['basis'], raw),
                 (answer['roots'], [[], *answer['basis']], raw)]
        for kind in ('unknown-tag', 'padding', 'duplicate', 'reorder', 'overlap',
                     'extent', 'nonlinear', 'wrong-kind', 'zero', 'missing-one', 'missing-all'):
            bad = words[:]
            if kind == 'unknown-tag': bad[4] |= 1 << 62
            elif kind == 'padding': bad[5] |= 8
            elif kind == 'duplicate': bad[9] = bad[4]
            elif kind == 'reorder': bad[4:9], bad[9:14] = bad[9:14], bad[4:9]
            elif kind == 'overlap': bad[0] = 1
            elif kind == 'extent': bad.pop()
            elif kind == 'nonlinear': bad[5] = 2
            elif kind == 'wrong-kind': bad[4] &= ~(1 << 63)
            elif kind == 'zero':
                for offset in range(4, len(bad), 5):
                    bad[offset+1:offset+5] = [0]*4
            elif kind == 'missing-one': del bad[4:9]
            else: bad = bad[:4]
            cases.append((answer['roots'], answer['basis'], bytes((producer.U64*len(bad))(*bad))))
        for sanitizer in (False, True):
            with Checker(2, 3, 3, sanitizer=sanitizer) as c, prior.Checker(2, 3, 3, sanitizer=sanitizer) as old:
                for symmetry in (False, True):
                    c.configure_symmetry(symmetry); old.configure_symmetry(symmetry)
                    for transform in ('full', 'tile16'):
                        c.configure_transform(transform); old.configure_transform(transform)
                        for tail in cases:
                            with c.prepare(anf) as prepared:
                                try:
                                    expected = old.certify(anf, *tail)
                                except ValueError:
                                    with self.assertRaises(ValueError):
                                        c.certify_prepared(prepared, anf, *tail)
                                else:
                                    result = c.certify_prepared(prepared, anf, *tail)
                                    accounting.compare_certificates(result, expected)
                            with c.prepare(anf) as prepared:
                                self.assertTrue(c.certify_prepared(prepared, anf, answer['roots'], answer['basis'], raw)['verified'])

    def test_preparation_soft_failure_and_exact_representation_binding(self):
        anf = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with producer.Producer(2, 3, 3) as p:
            answer = p.produce(anf)
        tail = answer['roots'], answer['basis'], answer['proof_bytes']
        cubic = producer.Packed(5, 3, [(28, 1)])
        with Checker(2, 3, 3) as c:
            with c.prepare(cubic) as prepared:
                self.assertEqual(prepared.code, 7)
                self.assertEqual(prepared.token, 0)
                self.assertEqual(prepared.stats['attempted'], 1)
                self.assertEqual(prepared.stats['ready'], 0)
                self.assertGreaterEqual(prepared.stats['seconds'], 0)
            same_other_width = producer.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
            same_other_width.masks = (ct.c_uint32*3)(4, 24, 0)
            same_other_order = producer.Packed(5, 3, [(0, 2), (24, 2), (4, 1)])
            changed_mask = producer.Packed(5, 3, [(5, 1), (24, 2), (0, 2)])
            for changed in (same_other_width, same_other_order, changed_mask):
                with c.prepare(anf) as prepared:
                    with self.assertRaises(ValueError):
                        c.certify_prepared(prepared, changed, *tail)


if __name__ == '__main__':
    unittest.main()
