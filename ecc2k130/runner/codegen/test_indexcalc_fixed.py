import copy
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import curves
import field
import indexcalc_fixed as fixed


ROOT = Path(__file__).resolve().parents[2]


def fixture(m=5, seed=101, summands=3, targets=2):
    onb = fixed.engine.AuditField(m, fixed.engine.Ledger())
    curve = curves.Curve(onb)
    prime = curves.curveOrder(m) // 4
    rng = random.Random(seed)
    generator = curve.randomPointOfOrder(prime, 4, rng)
    def encoded(point):
        return {axis: hex(onb.toCoords(value)) for axis, value in zip(('x', 'y'), point)}
    expected = {}
    points = []
    for i in range(targets):
        name = 'target-' + str(i)
        scalar = rng.randrange(1, prime)
        expected[name] = scalar
        points.append(dict(id=name, **encoded(curve.mul(generator, scalar))))
    document = {'schema_version': 1, 'curve': {'family': 'koblitz-a0', 'degree': m,
        'basis': 'type-ii-onb', 'subgroup_order': str(prime), 'cofactor': 4},
        'generator': encoded(generator), 'factor_base': {'kind': 'hamming-weight', 'weight': 4 if m == 5 else 2},
        'summands': summands, 'targets': points}
    return document, expected


def transcript(campaign):
    return list(campaign.db.execute('SELECT stream,number,witness,coefficients,a,b FROM relations ORDER BY stream,number'))


class FixedTests(unittest.TestCase):
    def test_complete_cold_resume_and_add_target(self):
        document, expected = fixture(9)
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory) as campaign:
                report = campaign.run(attempts=256, pairBudget=10000, seconds=2)
                self.assertEqual(report['status'], 'complete')
                for name, scalar in expected.items():
                    self.assertEqual(int(report['targets'][name]['scalar']), scalar)
                original = transcript(campaign)
            with fixed.Campaign(document, directory) as campaign:
                with patch.object(campaign, 'decompose', side_effect=AssertionError('replayed a completed target')):
                    report = campaign.run(attempts=256, pairBudget=0)
                self.assertEqual(report['status'], 'complete')
                self.assertEqual(report['reuse'].get('pair_candidates_built', 0), 0)
                self.assertEqual(report['reuse'].get('new_attempts', 0), 0)
                self.assertEqual(transcript(campaign), original)
            added = copy.deepcopy(document)
            added['targets'] = [dict(added['targets'][0], id='new-target')]
            with fixed.Campaign(added, directory) as campaign:
                report = campaign.run(stage='solve', attempts=256, pairBudget=0, seconds=2)
                self.assertEqual(report['status'], 'complete')
                self.assertEqual(int(report['targets']['new-target']['scalar']), expected['target-0'])
                self.assertEqual(report['reuse'].get('pair_candidates_built', 0), 0)

    def test_partial_pair_build_and_interrupted_collection_match_reference(self):
        document, expected = fixture(9, seed=1009)
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as reference:
            with fixed.Campaign(document, directory) as campaign:
                first = campaign.run(stage='pairs', pairBudget=7)
                self.assertEqual(first['status'], 'pair_budget')
                self.assertEqual(first['reuse']['pair_candidates_built'], 7)
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    campaign.decompose(campaign.params.generator, 2)
            with fixed.Campaign(document, directory) as campaign:
                report = campaign.run(stage='collect', attempts=1, pairBudget=10000, seconds=2)
                committed = report['attempts_saved']
            with fixed.Campaign(document, directory) as campaign:
                report = campaign.run(attempts=256, pairBudget=0, seconds=2)
                self.assertEqual(report['status'], 'complete')
                rows = transcript(campaign)
                self.assertGreaterEqual(report['attempts_saved'], committed)
            with fixed.Campaign(document, reference, memory=True) as campaign:
                ref = campaign.run(attempts=257, pairBudget=10000, seconds=2)
                self.assertEqual(ref['status'], 'complete')
                self.assertEqual(transcript(campaign), rows)
                self.assertEqual(report['targets'], ref['targets'])

    def test_direct_target_mode_without_precomputed_logs(self):
        document, expected = fixture(9, seed=1013)
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory) as campaign:
                report = campaign.run(stage='solve', attempts=256, pairBudget=10000, seconds=2)
                self.assertEqual(report['status'], 'complete')
                self.assertFalse(report['logs_available'])
                for name, scalar in expected.items():
                    self.assertEqual(int(report['targets'][name]['scalar']), scalar)

    def test_all_pair_queries_match_independent_exhaustive_oracle(self):
        for m, summands in ((5, 2), (5, 3), (9, 2), (9, 3)):
            document, _ = fixture(m, summands=summands)
            with fixed.Campaign(document, '.', memory=True) as campaign:
                self.assertTrue(campaign.buildPairs(10000))
                p = campaign.params
                # Independent full group-sum enumeration includes repeated
                # points but excludes inverse-cancelling pairs.
                reachable = set()
                for i, left in enumerate(campaign.points):
                    for j in range(i, len(campaign.points)):
                        right = campaign.points[j]
                        if left == p.curve.neg(right):
                            continue
                        total = p.curve.add(left, right)
                        if summands == 2:
                            reachable.add(total)
                        else:
                            for third in campaign.points[j:]:
                                if third not in (p.curve.neg(left), p.curve.neg(right)):
                                    reachable.add(p.curve.add(total, third))
                for scalar in range(1, p.prime):
                    target = p.curve.mul(p.generator, scalar)
                    witness, details = campaign.decompose(target, 2)
                    self.assertEqual(witness is not None, target in reachable)
                    self.assertIn(details['status'], ('verified', 'unsat'))

    def test_invalid_parameters_and_target_rebinding(self):
        document, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory):
                pass
            changed = copy.deepcopy(document)
            changed['summands'] = 2
            with self.assertRaisesRegex(ValueError, 'parameters differ'):
                fixed.Campaign(changed, directory)
            changed = copy.deepcopy(document)
            changed['targets'][0].update(changed['generator'])
            with self.assertRaisesRegex(ValueError, 'another point'):
                fixed.Campaign(changed, directory)
        for path, value in [(('curve', 'subgroup_order'), '13'), (('generator', 'x'), '0x100000000'),
                            (('curve', 'basis'), 'unspecified')]:
            changed = copy.deepcopy(document)
            changed[path[0]][path[1]] = value
            with self.assertRaises(ValueError):
                fixed.Parameters(changed, fixed.engine.Ledger())

    def test_corruption_rejected(self):
        document, _ = fixture()
        mutations = [
            ('UPDATE pairs SET point=? WHERE serial=0', ('bad',), 'pair-table checksum'),
            ('DELETE FROM pairs WHERE serial=0', (), 'pair-table record'),
            ('UPDATE relations SET coefficients=?', ('[0]',), 'relation coefficients'),
            ('UPDATE relations SET witness=?', ('[999,999,999]',), 'witness point'),
            ('UPDATE metadata SET value=? WHERE name=\'logs\'', ('[0]',), 'logarithm certificate'),
            ('UPDATE solutions SET scalar=?', ('0',), 'scalar certificate'),
        ]
        for sql, values, message in mutations:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                with fixed.Campaign(document, directory) as campaign:
                    self.assertEqual(campaign.run(attempts=256, seconds=2)['status'], 'complete')
                    with campaign.db:
                        campaign.db.execute(sql, values)
                with fixed.Campaign(document, directory) as campaign:
                    with self.assertRaisesRegex(ValueError, message):
                        if 'relations' in sql:
                            campaign.matrix()
                        elif 'pairs' in sql:
                            campaign.buildPairs(0)
                        else:
                            campaign.run(attempts=256, seconds=2)

    def test_transaction_rolls_back_witness_and_probe_together(self):
        document, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory) as campaign:
                campaign.buildPairs(10000)
                campaign.db.execute("CREATE TRIGGER interrupted BEFORE INSERT ON attempts BEGIN SELECT RAISE(ABORT, 'simulated interruption'); END")
                with self.assertRaises(sqlite3.IntegrityError):
                    campaign.collect(10, 2)
                self.assertEqual(campaign.db.execute('SELECT COUNT(*) FROM relations').fetchone()[0], 0)
                campaign.db.execute('DROP TRIGGER interrupted')
            with fixed.Campaign(document, directory) as campaign:
                self.assertEqual(campaign.run(attempts=256, seconds=2)['status'], 'complete')

    def test_single_writer_lock(self):
        document, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory):
                with self.assertRaisesRegex(ValueError, 'in use'):
                    fixed.Campaign(document, directory)

    def test_fixed_131_basis_points_and_bounded_resume(self):
        document = fixed.readJson(ROOT / 'docs/ic/params/ecc2k130-fixed.json')
        p = fixed.Parameters(document, fixed.engine.Ledger())
        self.assertEqual([p.onb.toCoords(v) for v in p.generator],
            [0x5cdd9d226e6977edb83e0790d2530939f, 0x74fd41d580ce1af22415d9bb8bbf0d331])
        pb = field.Pb(131, fixed.integer(document['curve']['polynomial']))
        def convert(value):
            answer = 0
            for i, image in enumerate(p.images):
                if value >> i & 1:
                    answer ^= image
            return p.onb.fromCoords(answer)
        rng = random.Random(1019)
        for _ in range(16):
            left, right = rng.getrandbits(131), rng.getrandbits(131)
            self.assertEqual(convert(pb.mul(left, right)), p.onb.mul(convert(left), convert(right)))
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory) as campaign:
                first = campaign.run(stage='pairs', pairBudget=11)
                self.assertEqual(first['orbit_columns'], 14)
                self.assertEqual(first['signed_base_points'], 3668)
                self.assertEqual(first['status'], 'pair_budget')
                self.assertLess(first['coverage_ceiling']['fraction'], 1e-28)
            with fixed.Campaign(document, directory) as campaign:
                second = campaign.run(stage='pairs', pairBudget=13)
                self.assertEqual(second['reuse']['pair_candidates_built'], 13)
                self.assertEqual(second['pair_table']['j'], 24)
                self.assertGreater(second['pair_table']['serial'], first['pair_table']['serial'])
                self.assertFalse(second['logs_available'])

    def test_sat_path_and_budget_retention(self):
        document, expected = fixture()
        with tempfile.TemporaryDirectory() as directory:
            with fixed.Campaign(document, directory, solver='sat') as campaign:
                report = campaign.run(attempts=64, pairBudget=0, seconds=.25)
                self.assertEqual(report['status'], 'complete')
                for name, scalar in expected.items():
                    self.assertEqual(int(report['targets'][name]['scalar']), scalar)
                self.assertIsNone(report['pair_table'])
        with fixed.Campaign(document, '.', solver='sat', memory=True) as campaign:
            with patch.object(campaign, 'decompose', return_value=(None, {'status': 'external_timeout'})):
                report = campaign.run(stage='collect', attempts=3)
            self.assertEqual(report['status'], 'insufficient_relations')
            self.assertEqual(report['attempts_saved'], 3)
            self.assertEqual(report['relations_saved'], 0)


if __name__ == '__main__':
    unittest.main()
