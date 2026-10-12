#!/usr/bin/env python3
"""Replay coupled-middle receipts and cumulative one-target accounting."""

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
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from field import Onb  # noqa: E402
from verify_model import verify  # noqa: E402


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
    assert data['proposal_id'] == 'Q1439'
    assert data['candidate_id'] is None and data['run_id'] is None
    assert sha(args.binary) == data['binary_sha256']
    assert sha(HERE / 'insearch.cpp') == data['source_sha256']
    assert sha(HERE / 'run.py') == data['runner_source_sha256']
    assert sha(Q1437 / 'measurements.json') == data[
        'q1437_measurement_sha256']
    assert sha(Q1438 / 'measurements.json') == data[
        'q1438_measurement_sha256']
    assert len(data['controls']) == 2
    for row in data['controls']:
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        prefix = Path('/private/tmp/q1430_n53_control.json'
                      if row['degree'] == 53 else
                      '/private/tmp/q1430_control.json')
        assert verify(prefix, log)['status'] == 'verified_s3'
        result = json.loads(log.read_text().splitlines()[0])
        assert row['coupled_middle_decisions'] == result[
            'coupled_middle_decisions']
    assert [(r['degree'], r['seed'], r['branch'])
            for r in data['attempts']] == [
                (53, 2, 'seededcoupled'), (83, 8, 'seededcoupled')]
    rejected = 0
    output = []
    for row in data['attempts']:
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row['result']
        assert result['status'] == row['exit_code'] == 0
        assert row['status_label'] == 'BOUNDED_UNKNOWN'
        assert row['early_limit'] == 128
        assert row['conflict_cap'] == 5000
        assert row['wall_cap_seconds'] == 30
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
        output.append({'degree': row['degree'],
                       'coupled_middle_decisions': result[
                           'coupled_middle_decisions'],
                       'final_link_checks': result['final_link_checks'],
                       'field_api_events': events})
        n = row['degree']
        earlier = ([r for r in screen['attempts'] if r['degree'] == n] +
                   [r for r in deep['attempts'] if r['degree'] == n])
        total = next(c for c in data['cumulative_campaigns']
                     if c['degree'] == n)
        prior_api = next(c['cumulative_api_events']
                         for c in deep['cumulative_campaigns']
                         if c['degree'] == n)
        old_states, new_states = states(earlier), states([row])
        assert total['prior_api_events'] == prior_api
        assert total['coupled_api_events'] == events
        assert total['cumulative_api_events'] == prior_api + events
        assert total['prior_distinct_states'] == len(old_states)
        assert total['coupled_distinct_states'] == len(new_states)
        assert total['marginal_new_distinct_states'] == len(
            new_states - old_states)
        assert total['cumulative_distinct_states'] == len(
            old_states | new_states)
    receipt = {'status': 'PASS', 'ordinary_runs': output,
               'replayed_leaf_rejections': rejected,
               'locked_controls': 2}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
