import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import indexcalc_fixed as fixed
import indexcalc_selector as selector
from test_indexcalc_fixed import fixture


def modelFor(campaign, arm='pairs', seconds=.25):
    m = campaign.params.onb.m
    return {'format': selector.FORMAT, 'features': list(selector.FEATURES),
            'arms': selector.ARMS, 'fallback': 'pairs', 'tree': {'arm': arm},
            'domains': {selector.domain(campaign, seconds): {
                'x_weight': [0, m], 'x_frobenius_distance': [0, m],
                'rank_fraction': [0, 1], 'direct_target': [0, 1]}}}


def data():
    records = []
    for i in range(240):
        group = selector.digest(['synthetic-test', i])
        feature = i % 2
        gain = int(i % 3 != 0)
        records.append({'format': selector.FORMAT, 'domain': 'a' * 64,
                        'query_id': str(i), 'repetition': 0, 'orbit': group,
                        'split': selector.split(group), 'origin': 'natural',
                        'features': {'x_weight': feature + 1, 'x_frobenius_distance': 2,
                                     'rank_fraction': 0, 'direct_target': 0},
                        'outcomes': {arm: {'elapsed_ns': 100 if (arm == 'pairs') == bool(feature) else 10000,
                                          'gain': gain, 'verified': bool(gain),
                                          'status': 'verified' if gain else 'budget'}
                                     for arm in selector.ARMS}})
    return records


class SelectorTests(unittest.TestCase):
    def test_rank_labels_reduce_current_rows(self):
        from indexcalc_selector_bench import rank
        self.assertEqual(rank([[1, 1], [2, 2]], 7), 1)
        self.assertEqual(rank([[1, 1, 0], [2, 2, 0], [3, 4, 1]], 7), 2)
        self.assertEqual(rank([[0, 1], [1, 1], [4, 5]], 7), 2)

    def test_cost_sensitive_tree_and_locked_holdout(self):
        records = data()
        document, report = selector.train(records)
        self.assertEqual(document['validation']['decision'], 'tree')
        self.assertLess(report['splits']['confirmation']['selector']['penalized_loss_ns'],
                        report['splits']['confirmation']['pairs']['penalized_loss_ns'])
        changed = copy.deepcopy(records)
        for r in changed:
            if r['split'] == 'confirmation':
                for o in r['outcomes'].values():
                    o.update(elapsed_ns=12345, gain=0, verified=False)
        second, _ = selector.train(changed)
        self.assertEqual(document['tree'], second['tree'])
        self.assertEqual(document['domains'], second['domains'])
        self.assertEqual(document['validation'], second['validation'])

    def test_no_signal_rejected_and_controls_excluded(self):
        records = data()
        for r in records:
            for o in r['outcomes'].values():
                o.update(gain=0, verified=False)
        planted = copy.deepcopy(data()[0])
        planted.update(query_id='control', origin='planted', split='train')
        while selector.split(planted['orbit']) != 'train':
            planted['orbit'] = selector.digest(planted['orbit'])
        for o in planted['outcomes'].values():
            o.update(gain=1, verified=True)
        with self.assertRaisesRegex(ValueError, 'natural rank gains'):
            selector.train(records + [planted])
        records = data()
        control = copy.deepcopy(records[0])
        control.update(query_id='control', origin='planted')
        document, _ = selector.train(records + [control])
        self.assertEqual(document['training']['planted_excluded'], 1)

    def test_degenerate_portfolio_keeps_constant_and_errors_retained(self):
        records = data()
        for r in records:
            for arm, o in r['outcomes'].items():
                o['elapsed_ns'] = 100 if arm == 'pairs' else 1000
        document, _ = selector.train(records)
        self.assertEqual(document['tree'], {'arm': 'pairs'})
        self.assertEqual(document['validation']['decision'], 'constant_no_routing_gain')
        records[0]['outcomes']['pairs']['status'] = 'error'
        with self.assertRaisesRegex(ValueError, 'errors invalidate'):
            selector.train(records)

    def test_orbits_do_not_leak_across_generators_or_signs(self):
        document, _ = fixture(9)
        with fixed.Campaign(document, '.', memory=True) as c:
            target = c.params.generator
            group = selector.orbit(c, target)
            for _ in range(9):
                self.assertEqual(group, selector.orbit(c, target))
                self.assertEqual(group, selector.orbit(c, c.params.curve.neg(target)))
                target = c.params.curve.frob(target)
            original_domain = selector.domain(c, .25)
        document, _ = fixture(9, seed=9001)
        with fixed.Campaign(document, '.', memory=True) as c:
            self.assertEqual(original_domain, selector.domain(c, .25))

    def test_fallback_budget_and_witness_verification(self):
        document, _ = fixture(9)
        with fixed.Campaign(document, '.', memory=True) as c:
            c.buildPairs(10000)
            original = c.decomposeExact
            calls = []
            def solve(target, seconds, solver):
                calls.append((solver, seconds))
                if solver == 'sat':
                    return None, {'status': 'external_timeout'}
                return original(target, seconds, solver)
            target = c.params.curve.add(c.points[0], c.points[0])
            target = c.params.curve.add(target, c.points[0])
            with patch.object(c, 'decomposeExact', side_effect=solve):
                witness, details = c.decomposePolicy(target, .25, 'sat-short')
            self.assertEqual(details['calls'][0]['result']['status'], 'external_timeout')
            self.assertEqual(calls, [('sat', .025), ('pairs', .225)])
            self.assertIsNotNone(witness)
            c.verify(witness, target)

    def test_learned_campaign_partial_resume_replay_and_ood(self):
        document, expected = fixture(9)
        with tempfile.TemporaryDirectory() as temp:
            model_path = Path(temp) / 'model.json'
            directory = Path(temp) / 'campaign'
            with fixed.Campaign(document, '.', memory=True) as c:
                model = modelFor(c)
                model_path.write_text(json.dumps(model))
                loaded = selector.Model(model)
                values = selector.features(c, c.params.generator)
                self.assertEqual(loaded.select('b' * 64, values)[1], 'unseen_parameters_or_budget')
                values['x_weight'] = 999
                self.assertEqual(loaded.select(selector.domain(c, .25), values)[1], 'unseen_feature_range')
            with fixed.Campaign(document, directory, 'learned', selectorModel=model_path) as c:
                report = c.run(attempts=256, pairBudget=7)
                self.assertEqual(report['status'], 'pair_budget')
                self.assertEqual(report['attempts_saved'], 0)
            with fixed.Campaign(document, directory, 'learned', selectorModel=model_path) as c:
                report = c.run(attempts=256, pairBudget=10000)
                self.assertEqual(report['status'], 'complete')
                self.assertGreater(report['reuse']['selector_queries'], 0)
                for name, scalar in expected.items():
                    self.assertEqual(int(report['targets'][name]['scalar']), scalar)
                for (encoded,) in c.db.execute('SELECT result FROM attempts'):
                    self.assertEqual(json.loads(encoded)['selector']['model_sha256'], selector.digest(model))
            with fixed.Campaign(document, directory, 'learned', selectorModel=model_path) as c:
                with patch.object(c, 'decompose', side_effect=AssertionError('replayed')):
                    self.assertEqual(c.run(pairBudget=0)['status'], 'complete')

    def test_invalid_model_rejected_without_executing_content(self):
        document, _ = fixture()
        with fixed.Campaign(document, '.', memory=True) as c:
            model = modelFor(c)
        for key, value in [('tree', {'arm': 'shell'}), ('features', ['scalar']),
                           ('fallback', 'sat-short'), ('tree', {'feature': 'x_weight', 'threshold': float('nan'), 'left': {}, 'right': {}})]:
            bad = copy.deepcopy(model)
            bad[key] = value
            with self.assertRaises(ValueError):
                selector.Model(bad)
        with self.assertRaisesRegex(ValueError, 'selector-model'):
            fixed.Campaign(document, '.', 'learned', memory=True)


if __name__ == '__main__':
    unittest.main()
