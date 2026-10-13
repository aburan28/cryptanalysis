#!/usr/bin/env python3
"""Read-only canonical identity and censored-arm evidence checks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'n83-compact-orbit-size-sweep-20261012'


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    workload = json.loads((HERE / 'workload.json').read_text())
    workload_id = workload.pop('workload_id')
    assert workload_id == digest(workload)[:12]
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['status'] == 'CENSORED_CAP'
    assert verification['censored_arms'] == ['K900']
    assert all(value for key, value in verification['checks'].items()
               if key not in ('K900_exit', 'K900_rss'))
    rows = json.loads((HERE / 'measurements.json').read_text())
    assert len(rows) == 1
    row = rows[0]
    candidate = json.loads((HERE / 'candidate_K800.json').read_text())
    candidate_id = candidate.pop('candidate_id')
    curve = candidate['curve'].copy()
    curve_id = curve.pop('curve_id')
    assert curve_id == 'EC1N83Ckb1a1h' + digest({'field': candidate['field'], 'curve': curve})[:12]
    assert candidate_id == ('IC1N83Ckb1a1fb132800PDP4rootRCguidedLAgaussTDdirectISO0h'
                            + digest(candidate)[:12])
    assert row['candidate_id'] == candidate_id
    assert row['curve_id'] == curve_id == workload['curve_id']
    assert row['workload_id'] == workload_id
    assert row['run_id'] == f'{candidate_id}W{workload_id}R1'
    assert row['actual_factor_base_points'] == 132800
    assert row['effective_columns'] == 800
    assert row['correctness_receipt_sha256'] == sha(HERE / 'verification.json')
    prior_replay = PRIOR / 'full_base_replay.json'
    assert json.loads(prior_replay.read_text())['status'] == 'PASS'
    assert row['full_base_replay_sha256'] == sha(prior_replay)
    arm = HERE / 'runs/K800'
    assert sha(arm / 'base.jsonl') == sha(PRIOR / 'runs/K800/base.jsonl')
    assert candidate['factor_base']['ordered_base_dump_sha256'] == sha(arm / 'base.jsonl')
    base = json.loads((arm / 'base.jsonl').read_text())
    points = sorted(base['factor_base_point_coordinates'],
                    key=lambda point: (int(point[0]), int(point[1])))
    assert candidate['factor_base']['enumerated_set_sha256'] == digest(points)
    target = json.loads((arm / 'target.jsonl').read_text())
    assert row['target'] == target['target'] == workload['public_targets'][0]
    assert abs(sum(row['ic_online_phases_ms'].values()) - row['ic_online_ms']) <= 0.02
    assert row['ic_peak_rss_bytes_sampled'] <= 12884901888
    assert row['controlled_speedup'] is None
    censored = json.loads((HERE / 'censored_K900.json').read_text())
    execution = json.loads((HERE / 'runs/K900/execution.json').read_text())
    assert execution['disposition'] == 'rss_cap'
    assert execution['sampled_peak_rss_bytes'] > 12884901888
    assert censored['candidate_id'] is None and censored['run_id'] is None
    assert censored['target_online_ms'] is None
    assert censored['raw_execution_sha256'] == sha(HERE / 'runs/K900/execution.json')
    assert censored['verification_sha256'] == sha(HERE / 'verification.json')
    print(json.dumps({'status': 'PASS', 'curve_id': curve_id,
                      'workload_id': workload_id, 'candidate_id': candidate_id,
                      'censored_arm': 'K900'}))


if __name__ == '__main__':
    main()
