#!/usr/bin/env python3
"""Validate both Q1442 bounded schedules and all cumulative charges."""

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
Q1441 = STAGE / 'q20261011_small_cap_screen'
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
from field import Onb  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    first = json.loads((HERE / 'measurements.json').read_text())
    second = json.loads((HERE / 'followup.json').read_text())
    prior = json.loads((Q1441 / 'measurements.json').read_text())
    assert first['proposal_id'] == second['proposal_id'] == 'Q1442'
    assert first['candidate_id'] is None and second['candidate_id'] is None
    assert first['run_id'] is None and second['run_id'] is None
    assert first['binary_sha256'] == second['binary_sha256'] == sha(args.binary)
    assert first['source_sha256'] == second['source_sha256'] == sha(
        Q1437 / 'insearch.cpp')
    assert first['runner_source_sha256'] == sha(HERE / 'run.py')
    assert second['runner_source_sha256'] == sha(HERE / 'run_followup.py')
    assert second['prior_measurement_sha256'] == sha(HERE / 'measurements.json')
    assert first['q1441_measurement_sha256'] == sha(
        Q1441 / 'measurements.json')
    expected = [(53, 2, 1), (53, 2, 8), (83, 8, 1), (83, 8, 8)]
    rejected = 0
    for record, cap, wall in ((first, 50, 60), (second, 65, 90)):
        assert [(r['degree'], r['seed'], r['early_limit'])
                for r in record['schedule']] == expected
        assert len(record['attempts']) == 4
        for spec, row in zip(record['schedule'], record['attempts']):
            assert all(row[key] == spec[key] for key in spec)
            assert row['branch'] == 'seededpos'
            assert row['conflict_cap'] == cap
            assert row['wall_cap_seconds'] == wall
            assert row['isogeny'] == 'none'
            log = HERE / row['log']
            assert sha(log) == row['log_sha256']
            result = json.loads(log.read_text().splitlines()[0])
            assert result == row['result']
            assert result['status'] == row['exit_code'] == 0
            assert row['status_label'] == 'BOUNDED_UNKNOWN'
            assert result['final_link_matches'] == 0
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
        for n in (53, 83):
            summary = next(c for c in record['cumulative_campaigns']
                           if c['degree'] == n)
            rows = [r for r in record['attempts'] if r['degree'] == n]
            old = next(c['cumulative_api_events']
                       for c in (prior if cap == 50 else first)[
                           'cumulative_campaigns'] if c['degree'] == n)
            added = sum(r['field_api_method_entry_events'] for r in rows)
            assert summary['prior_api_events'] == old
            assert summary['new_api_events'] == added
            assert summary['cumulative_api_events'] == old + added
            assert math.isclose(summary['cumulative_api_log2'],
                                math.log2(old + added))
            for caprow, source in zip(summary['matched_cap_results'], rows):
                assert caprow['early_limit'] == source['early_limit']
                assert caprow['final_link_checks'] == source['result'][
                    'final_link_checks']
                assert caprow['field_api_events'] == source[
                    'field_api_method_entry_events']
                assert math.isclose(
                    caprow['final_checks_per_million_api_events'],
                    source['result']['final_link_checks'] * 1e6 /
                    source['field_api_method_entry_events'])
    assert all(not row['result']['wall_cap_hit'] and
               row['result']['early_queries'] == 0
               for row in first['attempts'])
    assert all(row['result']['wall_cap_hit'] and
               row['result']['conflicts'] < 65
               for row in second['attempts'])
    result = {'status': 'PASS', 'replayed_leaf_rejections': rejected,
              'first_phase': 'before_middle_state',
              'followup_phase': 'wall_capped_before_65_conflicts'}
    (HERE / 'validation.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
