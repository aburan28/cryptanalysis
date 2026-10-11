"""Exact successful, malformed and every-prefix work-budget accounting."""
import sys
import unittest

from adapter import HERE, Checker, load, producer
from reservation_accounting import reservation_accounting

prior = load('reservation54_test_prior53', HERE.parent/'round53/adapter.py')
accounting = load('reservation54_accounting', HERE.parent/'round53/locality_accounting.py')
sys.path.insert(0, str(HERE))


def compare(actual, expected):
    accounting.compare_certificates(actual, expected)
    assert actual['partial_locality_stats'] == expected['partial_locality_stats']



def fixture(y=3, equations=3, quadratic=6):
    linear = next(j for j in range(y) if not quadratic >> j & 1)
    anf = producer.Packed(2+y, equations, [(1 << (2+linear), 1),
                                         (quadratic << 2, 1 << (equations-1)),
                                         (0, 1 << (equations-1))])
    with producer.Producer(2, y, equations) as p:
        answer = p.produce(anf)
    words = list((producer.U64*(len(answer['proof_bytes'])//8)).from_buffer_copy(answer['proof_bytes']))
    limbs = (equations+63)//64
    assert words[4*limbs] >> 63 == 1
    words[4*limbs+1:4*limbs+1+limbs] = [0]*limbs
    words[4*limbs+1+(equations-1)//64] = 1 << ((equations-1)%64)
    malformed = bytes((producer.U64*len(words))(*words))
    return anf, answer, malformed


class ReservationTests(unittest.TestCase):
    def test_every_small_budget_matches_direct_at_all_row_boundaries(self):
        seen = {'reserved': 0, 'fallback': 0, 'exception': 0, 'verified': 0, 'limited': 0}
        for equations in (3, 65, 128):
            for quadratic in (3, 5, 6):
                anf, answer, malformed = fixture(equations=equations, quadratic=quadratic)
                with Checker(2, 3, equations, reservation_budget_test=True, symmetry=False) as new, \
                        Checker(2, 3, equations, reservation_budget_test=True, symmetry=False, partial_reservation='direct') as direct:
                    for budget in range(513):
                        for checker in (new, direct):
                            checker.configure_partial_budget_test(budget)
                        for raw in (answer['proof_bytes'], malformed):
                            args = anf, answer['roots'], answer['basis'], raw
                            actual, expected = new.certify(*args), direct.certify(*args)
                            compare(actual, expected)
                            reservation_accounting(actual, True)
                            reservation_accounting(expected, False)
                            self.assertLessEqual(actual['partial_stats']['work'], budget)
                            s = actual['partial_reservation_stats']
                            seen['reserved'] += s['reserved_rows']
                            seen['fallback'] += s['budget_fallbacks']
                            seen['exception'] += s['exception_flushes']
                            seen['verified'] += actual['verified']
                            seen['limited'] += actual['code'] == 5
        self.assertTrue(all(seen.values()), seen)

    def test_word_boundaries_audits_and_prior_failure_counters(self):
        for equations in (31, 32, 33, 63, 64, 65, 127, 128):
            anf, answer, malformed = fixture(equations=equations)
            for flags in ({}, {'sanitizer': True}, {'locality_audit_test': True}, {'partial_budget_test': True}):
                with Checker(2, 3, equations, **flags) as new, prior.Checker(2, 3, equations, **flags) as old:
                    for symmetry in (False, True):
                        new.configure_symmetry(symmetry); old.configure_symmetry(symmetry)
                        for transform in ('full', 'tile16'):
                            new.configure_transform(transform); old.configure_transform(transform)
                            for locality in ('local', 'strided'):
                                new.configure_partial_coefficients(locality); old.configure_partial_coefficients(locality)
                                for mode in ('direct', 'reserved'):
                                    new.configure_partial_reservation(mode)
                                    for raw in (answer['proof_bytes'], malformed):
                                        args = anf, answer['roots'], answer['basis'], raw
                                        expected = old.certify(*args)
                                        actual = new.certify(*args)
                                        compare(actual, expected)
                                        reservation_accounting(actual, mode == 'reserved')
                                        with new.prepare(anf) as prepared:
                                            actual = new.certify_prepared(prepared, *args)
                                        compare(actual, expected)
                                        reservation_accounting(actual, mode == 'reserved')

    def test_maximum_row_and_zero_witnesses(self):
        # Keep the root set bounded while covering the maximum 112-word row.
        y, equations = 10, 128
        terms = [(1 << (2+j), 1 << j) for j in range(7)]
        terms += [(3 << (2+8), 1 << 127), (0, 1 << 127)]
        anf = producer.Packed(12, equations, terms)
        with producer.Producer(2, y, equations) as p:
            answer = p.produce(anf)
        with Checker(2, y, equations, locality_audit_test=True, symmetry=False) as new, \
                prior.Checker(2, y, equations, locality_audit_test=True, symmetry=False) as old:
            args = anf, answer['roots'], answer['basis'], answer['proof_bytes']
            actual, expected = new.certify(*args), old.certify(*args)
            compare(actual, expected)
            reservation_accounting(actual, True)
            self.assertEqual(actual['partial_reservation_stats']['max_row_words'], 112)
            words = list((producer.U64*(len(answer['proof_bytes'])//8)).from_buffer_copy(answer['proof_bytes']))
            for offset in range(8, len(words), 23):
                words[offset+1:offset+23] = [0]*22
            raw = bytes((producer.U64*len(words))(*words))
            actual, expected = new.certify(anf, answer['roots'], answer['basis'], raw), old.certify(anf, answer['roots'], answer['basis'], raw)
            compare(actual, expected)
            self.assertEqual(actual['partial_reservation_stats']['reservation_attempts'], 0)

    def test_runtime_budget_is_test_only_and_configuration_invalidates_preparation(self):
        anf, answer, _ = fixture()
        tail = answer['roots'], answer['basis'], answer['proof_bytes']
        with Checker(2, 3, 3) as ordinary:
            with self.assertRaises(ValueError):
                ordinary.configure_partial_budget_test(8)
        with Checker(2, 3, 3, reservation_budget_test=True) as c:
            for invalid in (None, True, 0, 'unknown'):
                with self.assertRaises(ValueError):
                    c.configure_partial_reservation(invalid)
            for invalid in (None, True, -1, 67108865, 1.0):
                with self.assertRaises(ValueError):
                    c.configure_partial_budget_test(invalid)
            for configure in (lambda: c.configure_partial_reservation('direct'),
                              lambda: c.configure_partial_budget_test(67108864)):
                with c.prepare(anf) as prepared:
                    configure()
                    with self.assertRaises(ValueError):
                        c.certify_prepared(prepared, anf, *tail)
                self.assertTrue(c.certify(anf, *tail)['verified'])
        with self.assertRaises(RuntimeError):
            c.configure_partial_reservation('reserved')
        with self.assertRaises(RuntimeError):
            c.configure_partial_budget_test(8)


if __name__ == '__main__':
    unittest.main()
