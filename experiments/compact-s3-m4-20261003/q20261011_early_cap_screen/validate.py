#!/usr/bin/env python3
"""Verify Q1440 cap-screen logs, comparator, and one-target work ledger."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
Q1437 = STAGE / 'q20261011_seeded_restart'
Q1438 = STAGE / 'q20261011_deep_seeded_budget'
Q1439 = STAGE / 'q20261011_coupled_middle'
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
from field import Onb  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def states(rows):
    return {(s['row'], s['x_bits']) for row in rows
            for s in row['result']['early_state_samples']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((HERE / 'measurements.json').read_text())
    screen = json.loads((Q1437 / 'measurements.json').read_text())
    deep = json.loads((Q1438 / 'measurements.json').read_text())
    coupled = json.loads((Q1439 / 'measurements.json').read_text())
    assert data['proposal_id'] == 'Q1440'
    assert data['candidate_id'] is None and data['run_id'] is None
    assert sha(args.binary) == data['binary_sha256'] == screen['binary_sha256']
    assert sha(HERE / 'run.py') == data['runner_source_sha256']
    assert sha(Q1437 / 'insearch.cpp') == data['source_sha256']
    for directory, key in ((Q1437, 'q1437_measurement_sha256'),
                           (Q1438, 'q1438_measurement_sha256'),
                           (Q1439, 'q1439_measurement_sha256')):
        assert sha(directory / 'measurements.json') == data[key]
    assert [(r['degree'], r['seed'], r['early_limit'])
            for r in data['schedule']] == [
                (53, 2, 8), (53, 2, 25), (83, 8, 8), (83, 8, 25)]
    assert len(data['attempts']) == 4
    rejected = 0
    for spec, row in zip(data['schedule'], data['attempts']):
        assert all(row[key] == spec[key] for key in spec)
        assert row['branch'] == 'seededpos'
        assert row['conflict_cap'] == 5000
        assert row['wall_cap_seconds'] == 30
        assert row['isogeny'] == 'none'
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row['result']
        assert result['status'] == row['exit_code'] == 0
        assert row['status_label'] == 'BOUNDED_UNKNOWN'
        assert result['wall_cap_hit']
        assert len(result['early_state_samples']) + result[
            'early_state_samples_truncated'] == result['early_queries']
        events = sum(result['field_api_calls'].values())
        assert row['field_api_method_entry_events'] == events
        assert math.isclose(row['field_api_method_entry_log2'],
                            math.log2(events))
        field = Onb(row['degree'])
        for sample in result['leaf_rejection_samples']:
            xcoords = sum(int(bit) << i for i, bit in
                          enumerate(sample['x_bits']))
            x = field.fromCoords(xcoords)
            assert x and field.trace(field.add(x,
                                               field.sqr(field.inv(x)))) == 1
            rejected += 1
    output = []
    for n in (53, 83):
        old = ([r for r in screen['attempts'] if r['degree'] == n] +
               [r for r in deep['attempts'] if r['degree'] == n] +
               [r for r in coupled['attempts'] if r['degree'] == n])
        new = [r for r in data['attempts'] if r['degree'] == n]
        summary = next(c for c in data['cumulative_campaigns']
                       if c['degree'] == n)
        earlier_api = next(c['cumulative_api_events']
                           for c in coupled['cumulative_campaigns']
                           if c['degree'] == n)
        added_api = sum(r['field_api_method_entry_events'] for r in new)
        assert summary['prior_api_events'] == earlier_api
        assert summary['new_api_events'] == added_api
        assert summary['cumulative_api_events'] == earlier_api + added_api
        assert summary['prior_distinct_states'] == len(states(old))
        assert summary['new_distinct_states'] == len(states(new))
        assert summary['marginal_new_distinct_states'] == len(
            states(new) - states(old))
        assert summary['cumulative_distinct_states'] == len(
            states(old) | states(new))
        baseline = next(r for r in deep['attempts']
                        if r['degree'] == n and r['branch'] == 'seededpos')
        for caprow, source in zip(summary['matched_cap_results'],
                                  [*new, baseline]):
            result = source['result']
            assert caprow['early_limit'] == source['early_limit']
            assert caprow['final_link_checks'] == result['final_link_checks']
            assert caprow['field_api_events'] == source[
                'field_api_method_entry_events']
            assert math.isclose(
                caprow['final_checks_per_million_api_events'],
                result['final_link_checks'] * 1e6 /
                source['field_api_method_entry_events'])
        best = max(summary['matched_cap_results'],
                   key=lambda r: r['final_checks_per_million_api_events'])
        output.append({'degree': n, 'best_cap': best['early_limit'],
                       'best_final_checks_per_million_api_events': best[
                           'final_checks_per_million_api_events'],
                       'cumulative_api_events': summary[
                           'cumulative_api_events']})
    receipt = {'status': 'PASS', 'replayed_leaf_rejections': rejected,
               'campaigns': output}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
