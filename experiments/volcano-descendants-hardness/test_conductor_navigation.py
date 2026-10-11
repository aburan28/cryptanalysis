import json
from pathlib import Path
import unittest

from conductor_navigation import annotate_summary, inventory, prime64


class NavigationTests(unittest.TestCase):
    def toy(self, **overrides):
        # Ordinary class over F_101: 6^2 - 4*101 = -23*4^2.
        data = dict(characteristic=101, q=101, trace=6, field_discriminant=-23,
                    frobenius_conductor=4, factors={2: 2}, allowed_primes=[],
                    source_conductor=1, source_evidence='toy fixture')
        data.update(overrides)
        return inventory(**data)

    def test_repeated_prime_levels(self):
        rows = self.toy()['strata']
        self.assertEqual([r['order_conductor'] for r in rows], ['1', '2', '4'])
        self.assertEqual(rows[-1]['local_levels'], {'2': 2})
        self.assertEqual(rows[-1]['barriers'][0]['vertical_steps_required'], 2)

    def test_allowed_degree_only_removes_conductor_obstruction(self):
        rows = self.toy(allowed_primes=[2])['strata']
        self.assertTrue(all(r['source_separation'] == 'no_conductor_obstruction' for r in rows))
        self.assertTrue(all(r['map_status'] == 'unknown' for r in rows))
        self.assertTrue(all(r['measured_advantage'] is None for r in rows))

    def test_unknown_source_is_not_surface(self):
        rows = self.toy(source_conductor=None, source_evidence=None)['strata']
        self.assertTrue(all(r['source_separation'] == 'unknown' and r['barriers'] is None for r in rows))

    def test_source_at_floor(self):
        rows = self.toy(source_conductor=4)['strata']
        self.assertEqual(rows[0]['barriers'][0]['source_level'], 2)
        self.assertEqual(rows[-1]['source_separation'], 'no_conductor_obstruction')

    def test_invalid_inputs(self):
        cases = [dict(trace=0), dict(q=102), dict(field_discriminant=-92),
                 dict(factors={2: 1}), dict(factors={4: 1}), dict(source_conductor=3),
                 dict(source_evidence=None), dict(allowed_primes=[101]),
                 dict(allowed_primes=[4]), dict(max_strata=2)]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.toy(**case)

    def test_unit_conductor(self):
        # 3^2 - 4*7 = -19, ordinary maximal Frobenius order.
        rows = self.toy(characteristic=7, q=7, trace=3, field_discriminant=-19,
                        frobenius_conductor=1, factors={})['strata']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['local_levels'], {})

    def test_prime_checker_rejects_pseudoprimes(self):
        for n in [0, 1, 341, 561, 3215031751, 3825123056546413051, 2**64+13]:
            self.assertFalse(prime64(n), n)
        self.assertTrue(prime64(146505763881528721))

    def test_existing_summary_adapter_preserves_measurements(self):
        path = Path(__file__).with_name('results.json')
        before = json.loads(path.read_text())
        after = annotate_summary(before, [263])
        self.assertEqual(before['descendants'], after['descendants'])
        self.assertEqual(before['sweep_263'], after['sweep_263'])
        self.assertNotIn('conductor_navigation', before)
        rows = after['conductor_navigation']['strata']
        self.assertEqual([r['source_separation'] for r in rows],
                         ['no_conductor_obstruction']*2 + ['separated_by_excluded_prime']*2)
        self.assertEqual(rows[2]['barriers'][0]['prime'], '146505763881528721')
        self.assertEqual(rows[2]['barriers'][0]['degree_bits'], 58)


if __name__ == '__main__':
    unittest.main()
