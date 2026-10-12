#!/usr/bin/env python3
"""Replay Q1443 controls, budget stops, field traces, and work ledger."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
Q1442 = STAGE / 'q20261011_fixed_conflict_caps'
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from field import Onb  # noqa: E402
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_row(row):
    log = HERE / row['log']
    assert sha(log) == row['log_sha256']
    result = json.loads(log.read_text().splitlines()[0])
    assert result == row['result']
    assert result['status'] == row['exit_code']
    assert result['api_budget'] == row['api_budget']
    assert len(result['early_state_samples']) + result[
        'early_state_samples_truncated'] == result['early_queries']
    total = sum(result['field_api_calls'].values())
    assert total == row['field_api_method_entry_events']
    assert math.isclose(math.log2(total),
                        row['field_api_method_entry_log2'])
    return result, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((HERE / 'measurements.json').read_text())
    prior = json.loads((Q1442 / 'followup.json').read_text())
    assert data['proposal_id'] == 'Q1443'
    assert data['candidate_id'] is None and data['run_id'] is None
    assert sha(HERE / 'run.py') == data['runner_source_sha256']
    assert sha(HERE / 'insearch.cpp') == data['solver_source_sha256']
    assert sha(HERE / 'build.sh') == data['build_script_sha256']
    assert sha(args.binary) == data['binary_sha256']
    assert sha(Q1442 / 'followup.json') == data['prior_measurement_sha256']
    assert sha(STAGE / 'q20261011_operation_account/counted_onb.py') == data[
        'counted_field_source_sha256']
    assert len(data['controls']) == 2
    for row in data['controls']:
        result, _ = check_row(row)
        assert row['mode'] == 'control'
        assert row['api_budget'] == 0 and not result['api_budget_hit']
        assert row['status_label'] == 'ALGEBRAIC_MODEL'
        prefix = Path('/private/tmp/q1430_n53_control.json'
                      if row['degree'] == 53 else
                      '/private/tmp/q1430_control.json')
        assert row['s3_verification'] == verify(prefix, HERE / row['log'])
    assert [(r['degree'], r['seed'], r['early_limit'])
            for r in data['attempts']] == [
                (53, 2, 1), (53, 2, 8), (83, 8, 1), (83, 8, 8)]
    assert len(data['attempts']) == 4
    rejected = 0
    max_overshoot = 0
    for row in data['attempts']:
        result, total = check_row(row)
        assert row['mode'] == 'ordinary' and row['branch'] == 'seededpos'
        assert row['isogeny'] == 'none'
        assert row['api_budget'] == 500000
        assert row['conflict_cap'] == 5000 and row['wall_cap_seconds'] == 180
        assert row['status_label'] == 'BOUNDED_UNKNOWN'
        assert result['status'] == 0
        assert result['api_budget_hit'] and not result['wall_cap_hit']
        assert result['conflicts'] < 5000
        assert result['final_link_matches'] == 0
        assert 0 <= total - 500000 <= 500
        assert row['api_budget_overshoot'] == total - 500000
        max_overshoot = max(max_overshoot, total - 500000)
        field = Onb(row['degree'])
        for sample in result['leaf_rejection_samples']:
            xcoords = sum(int(bit) << i for i, bit in
                          enumerate(sample['x_bits']))
            x = field.fromCoords(xcoords)
            assert x and field.trace(field.add(x,
                                               field.sqr(field.inv(x)))) == 1
            rejected += 1
    comparisons = []
    for n in (53, 83):
        rows = [row for row in data['attempts'] if row['degree'] == n]
        summary = next(c for c in data['cumulative_campaigns']
                       if c['degree'] == n)
        earlier = next(c['cumulative_api_events']
                       for c in prior['cumulative_campaigns']
                       if c['degree'] == n)
        smoke = 49328 if n == 53 else 0
        new = sum(row['field_api_method_entry_events'] for row in rows)
        assert summary['prior_archived_api_events'] == earlier
        assert summary['unfrozen_smoke_api_events'] == smoke
        assert summary['frozen_new_api_events'] == new
        assert summary['cumulative_api_events'] == earlier + smoke + new
        assert math.isclose(summary['cumulative_api_log2'],
                            math.log2(earlier + smoke + new))
        for row in rows:
            rate = (row['result']['final_link_checks'] * 1e6 /
                    row['field_api_method_entry_events'])
            assert math.isclose(summary[
                'final_checks_per_million_api_events'][
                    str(row['early_limit'])], rate)
        comparisons.append({'degree': n,
                            'cap1_final_checks': rows[0]['result'][
                                'final_link_checks'],
                            'cap8_final_checks': rows[1]['result'][
                                'final_link_checks'],
                            'cumulative_api_events': summary[
                                'cumulative_api_events']})
    receipt = {'status': 'PASS', 'locked_controls': 2,
               'replayed_leaf_rejections': rejected,
               'max_api_budget_overshoot': max_overshoot,
               'comparisons': comparisons}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
