#!/usr/bin/env python3
"""Replay Q1437 receipts, field traces, and locked seeded controls."""

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
from verify_model import verify  # noqa: E402
from field import Onb  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay_control(binary, n, seed):
    prefix = Path('/private/tmp/q1430_n53_control' if n == 53 else
                  '/private/tmp/q1430_control')
    target = STAGE / 'q20261010_final_link' / f'n{n}_control.targets'
    log = HERE / 'runs' / f'n{n}_control_seed{seed:02d}.log'
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(target), str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'seededpos', str(seed),
               'satpivot', 'selector', '5', 'eager',
               str(3 if n == 53 else 5), '1000', '10']
    run = subprocess.run(command, cwd=ROOT, capture_output=True,
                         text=True, timeout=40, check=False)
    assert run.returncode == 10, run.stderr or run.stdout
    log.write_text(run.stdout)
    replay = verify(prefix.with_suffix('.json'), log)
    assert replay['status'] == 'verified_s3'
    result = json.loads(run.stdout.splitlines()[0])
    assert result['decision_seed'] == seed
    return {'degree': n, 'seed': seed, 'status': 'verified_s3',
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
            'field_api_method_entry_events':
                sum(result['field_api_calls'].values())}


def validate_receipts(measurements, binary):
    assert measurements['proposal_id'] == 'Q1437'
    assert measurements['candidate_id'] is None
    assert measurements['run_id'] is None
    assert measurements['binary_sha256'] == sha(binary)
    assert measurements['source_sha256'] == sha(HERE / 'insearch.cpp')
    assert measurements['counted_field_source_sha256'] == sha(
        STAGE / 'q20261011_operation_account/counted_onb.py')
    assert measurements['field_source_sha256'] == sha(
        ROOT / 'ecc2k130/codegen/field.py')
    assert len(measurements['attempts']) == 32
    replayed_rejections = 0
    summaries = []
    for n in (53, 83):
        rows = [row for row in measurements['attempts']
                if row['degree'] == n]
        assert [row['seed'] for row in rows] == list(range(16))
        assert len({row['target_file_sha256'] for row in rows}) == 1
        assert len({row['cnf_sha256'] for row in rows}) == 1
        assert len({row['factor_base_enumerated_set_sha256']
                    for row in rows}) == 1
        summary = next(row for row in measurements['campaigns']
                       if row['degree'] == n)
        assert summary['attempts'] == 16 and summary['target_count'] == 1
        states = set()
        for row in rows:
            log = HERE / row['log']
            assert sha(log) == row['log_sha256']
            result = json.loads(log.read_text().splitlines()[0])
            assert result == row['result']
            assert row['branch'] == 'seededpos'
            assert row['conflict_cap'] == 500
            assert row['wall_cap_seconds'] == (5 if n == 53 else 10)
            assert row['isogeny'] == 'none'
            assert result['decision_seed'] == row['seed']
            assert result['status'] == row['exit_code']
            assert row['status_label'] == ('ALGEBRAIC_MODEL' if result['status'] == 10
                                           else 'UNSAT' if result['status'] == 20
                                           else 'BOUNDED_UNKNOWN')
            if result['status'] == 10:
                assert row['s3_verification'] == verify(
                    Path('/private/tmp/q1430_n53_ordinary.json' if n == 53 else
                         '/private/tmp/q1430_ordinary.json'), log)
            calls = result['field_api_calls']
            assert sum(calls.values()) == row['field_api_events'][
                'field_api_method_entry_events']
            assert math.isclose(math.log2(sum(calls.values())),
                                row['field_api_events'][
                                    'field_api_method_entry_log2'])
            assert len(result['early_state_samples']) + result[
                'early_state_samples_truncated'] == result['early_queries']
            states.update((s['row'], s['x_bits'])
                          for s in result['early_state_samples'])
            field = Onb(n)
            for sample in result['leaf_rejection_samples']:
                xcoords = sum(int(bit) << i for i, bit in
                              enumerate(sample['x_bits']))
                x = field.fromCoords(xcoords)
                assert x and field.trace(field.add(x,
                                                   field.sqr(field.inv(x)))) == 1
                replayed_rejections += 1
        assert summary['distinct_recorded_early_states'] == len(states)
        assert summary['total_field_api_method_entry_events'] == sum(
            row['field_api_events']['field_api_method_entry_events']
            for row in rows)
        assert summary['total_conflicts'] == sum(
            row['result']['conflicts'] for row in rows)
        assert summary['total_process_wall_seconds'] == sum(
            row['process_wall_seconds'] for row in rows)
        summaries.append({'degree': n, 'distinct_early_states': len(states),
                          'total_api_events': summary[
                              'total_field_api_method_entry_events']})
    return summaries, replayed_rejections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    measurements = json.loads((HERE / 'measurements.json').read_text())
    summaries, rejected = validate_receipts(measurements, args.binary)
    controls = [replay_control(args.binary, 53, 0),
                replay_control(args.binary, 83, 1)]
    receipt = {'status': 'PASS', 'campaigns': summaries,
               'replayed_leaf_rejections': rejected,
               'locked_controls': controls}
    (HERE / 'validation.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
