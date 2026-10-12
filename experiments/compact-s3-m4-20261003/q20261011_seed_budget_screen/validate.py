#!/usr/bin/env python3
"""Validate Q1444 fixed-budget seed receipts and cumulative accounting."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
Q1443 = STAGE / 'q20261011_api_budget_stop'
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
from field import Onb  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((HERE / 'measurements.json').read_text())
    prior = json.loads((Q1443 / 'measurements.json').read_text())
    assert data['proposal_id'] == 'Q1444'
    assert data['candidate_id'] is None and data['run_id'] is None
    assert sha(HERE / 'run.py') == data['runner_source_sha256']
    assert sha(Q1443 / 'insearch.cpp') == data['solver_source_sha256']
    assert sha(Q1443 / 'build.sh') == data['build_script_sha256']
    assert sha(args.binary) == data['binary_sha256'] == prior['binary_sha256']
    assert sha(Q1443 / 'measurements.json') == data[
        'prior_measurement_sha256']
    assert sha(STAGE / 'q20261011_operation_account/counted_onb.py') == data[
        'counted_field_source_sha256']
    assert [(r['degree'], r['seed']) for r in data['schedule']] == [
        (53, 5), (53, 9), (83, 10), (83, 14)]
    assert len(data['attempts']) == 4
    rejected = 0
    output = []
    for spec, row in zip(data['schedule'], data['attempts']):
        assert row['degree'] == spec['degree'] and row['seed'] == spec['seed']
        assert row['mode'] == 'ordinary' and row['branch'] == 'seededpos'
        assert row['early_limit'] == 1
        assert row['api_budget'] == 500000
        assert row['conflict_cap'] == 5000
        assert row['wall_cap_seconds'] == 180
        assert row['isogeny'] == 'none'
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row['result']
        assert result['status'] == row['exit_code'] == 0
        assert row['status_label'] == 'BOUNDED_UNKNOWN'
        assert result['final_link_matches'] == 0
        assert result['decision_seed'] == row['seed']
        assert result['api_budget'] == row['api_budget']
        assert len(result['early_state_samples']) + result[
            'early_state_samples_truncated'] == result['early_queries']
        calls = result['field_api_calls']
        events = sum(calls.values())
        assert row['field_api_method_entry_events'] == events
        assert math.isclose(row['field_api_method_entry_log2'],
                            math.log2(events))
        if row['degree'] == 53:
            assert result['api_budget_hit'] and not result['wall_cap_hit']
            assert 0 <= events - 500000 <= 500
        else:
            assert result['wall_cap_hit'] and not result['api_budget_hit']
            assert events < 500000
        assert row['api_budget_overshoot'] == max(0, events - 500000)
        field = Onb(row['degree'])
        for sample in result['leaf_rejection_samples']:
            xcoords = sum(int(bit) << i for i, bit in
                          enumerate(sample['x_bits']))
            x = field.fromCoords(xcoords)
            assert x and field.trace(field.add(x,
                                               field.sqr(field.inv(x)))) == 1
            rejected += 1
        output.append({'degree': row['degree'], 'seed': row['seed'],
                       'api_events': events,
                       'api_budget_hit': result['api_budget_hit'],
                       'final_link_checks': result['final_link_checks']})
    for n in (53, 83):
        earlier = next(c['cumulative_api_events']
                       for c in prior['cumulative_campaigns']
                       if c['degree'] == n)
        rows = [r for r in data['attempts'] if r['degree'] == n]
        new = sum(r['field_api_method_entry_events'] for r in rows)
        summary = next(c for c in data['cumulative_campaigns']
                       if c['degree'] == n)
        assert summary['prior_archived_api_events'] == earlier
        assert summary['frozen_new_api_events'] == new
        assert summary['cumulative_api_events'] == earlier + new
        assert math.isclose(summary['cumulative_api_log2'],
                            math.log2(earlier + new))
        for source, saved in zip(rows, summary['new_seed_results']):
            assert saved['seed'] == source['seed']
            assert saved['field_api_events'] == source[
                'field_api_method_entry_events']
            assert saved['final_link_checks'] == source['result'][
                'final_link_checks']
            rate = (source['result']['final_link_checks'] * 1e6 /
                    source['field_api_method_entry_events'])
            assert math.isclose(saved[
                'final_checks_per_million_api_events'], rate)
    for n in (53, 83):
        selected = [r for r in [*prior['attempts'], *data['attempts']]
                    if r['degree'] == n and r['early_limit'] == 1]
        states = [(s['row'], s['x_bits']) for row in selected
                  for s in row['result']['early_state_samples']]
        assert len(states) == len(set(states)) == 3
    receipt = {'status': 'PASS', 'replayed_leaf_rejections': rejected,
               'distinct_cap1_middle_states_per_field': 3,
               'attempts': output}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
