#!/usr/bin/env python3
"""Recompute Q1438 receipt totals and replay recorded leaf trace decisions."""

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
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
from field import Onb  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def states(rows):
    return {(sample['row'], sample['x_bits'])
            for row in rows
            for sample in row['result']['early_state_samples']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((HERE / 'measurements.json').read_text())
    prior = json.loads((Q1437 / 'measurements.json').read_text())
    assert data['proposal_id'] == 'Q1438'
    assert data['candidate_id'] is None and data['run_id'] is None
    assert sha(args.binary) == data['binary_sha256']
    assert sha(HERE / 'run.py') == data['runner_source_sha256']
    assert sha(Q1437 / 'insearch.cpp') == data['source_sha256']
    assert sha(Q1437 / 'measurements.json') == data[
        'q1437_measurement_sha256']
    assert [tuple(spec[key] for key in ('degree', 'seed', 'branch'))
            for spec in data['schedule']] == [
                (53, 2, 'seededpos'), (53, 2, 'seededspread'),
                (83, 8, 'seededpos'), (83, 8, 'seededspread')]
    assert len(data['attempts']) == 4
    rejected = 0
    per_run = []
    for spec, row in zip(data['schedule'], data['attempts']):
        assert all(row[key] == spec[key] for key in spec)
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row['result']
        assert result['decision_seed'] == row['seed']
        assert result['status'] == row['exit_code']
        assert row['status_label'] == 'BOUNDED_UNKNOWN'
        assert row['early_limit'] == 128
        assert row['conflict_cap'] == 5000 and row['wall_cap_seconds'] == 30
        assert row['isogeny'] == 'none'
        events = sum(result['field_api_calls'].values())
        assert events == row['field_api_method_entry_events']
        assert math.isclose(math.log2(events),
                            row['field_api_method_entry_log2'])
        assert len(result['early_state_samples']) + result[
            'early_state_samples_truncated'] == result['early_queries']
        field = Onb(row['degree'])
        for sample in result['leaf_rejection_samples']:
            xcoords = sum(int(bit) << i for i, bit in
                          enumerate(sample['x_bits']))
            x = field.fromCoords(xcoords)
            assert x and field.trace(field.add(x,
                                               field.sqr(field.inv(x)))) == 1
            rejected += 1
        per_run.append({'degree': row['degree'], 'branch': row['branch'],
                        'checked_row4': sum(s['row'] == 4 for s in
                                            result['early_state_samples']),
                        'checked_row5': sum(s['row'] == 5 for s in
                                            result['early_state_samples']),
                        'field_api_events': events})
    for n in (53, 83):
        earlier = [row for row in prior['attempts'] if row['degree'] == n]
        newer = [row for row in data['attempts'] if row['degree'] == n]
        total = next(c for c in data['cumulative_campaigns']
                     if c['degree'] == n)
        old_api = next(c['total_field_api_method_entry_events']
                       for c in prior['campaigns'] if c['degree'] == n)
        new_api = sum(row['field_api_method_entry_events'] for row in newer)
        assert total['screen_api_events'] == old_api
        assert total['deeper_api_events'] == new_api
        assert total['cumulative_api_events'] == old_api + new_api
        assert math.isclose(total['cumulative_api_log2'],
                            math.log2(old_api + new_api))
        old, new = states(earlier), states(newer)
        assert total['screen_distinct_states'] == len(old)
        assert total['deeper_distinct_states'] == len(new)
        assert total['marginal_new_distinct_states'] == len(new - old)
        assert total['cumulative_distinct_states'] == len(old | new)
    receipt = {'status': 'PASS', 'runs': per_run,
               'replayed_leaf_rejections': rejected,
               'q1437_locked_control_status': json.loads(
                   (Q1437 / 'validation.json').read_text())['status']}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
