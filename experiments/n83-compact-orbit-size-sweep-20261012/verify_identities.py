#!/usr/bin/env python3
"""Read-only hash and record checks for the two complete IC candidates."""

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-base-size-crypto-20261012'))


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
    rows = json.loads((HERE / 'measurements.json').read_text())
    rows_v2 = json.loads((HERE / 'measurements_v2.json').read_text())
    full_base_replay_path = HERE / 'full_base_replay.json'
    full_base_replay = json.loads(full_base_replay_path.read_text())
    assert full_base_replay['status'] == 'PASS'
    assert len(rows_v2) == len(rows)
    historical_k600 = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/base_n83_K600.jsonl'
    assert sha(historical_k600) == sha(HERE / 'runs/K600/base.jsonl')
    assert len(rows) == 2
    assert {row['effective_columns'] for row in rows} == {600, 800}
    verification = json.loads((HERE / 'verification_v2.json').read_text())
    assert verification['status'] == 'PASS'
    for row, enriched in zip(rows, rows_v2):
        assert all(enriched[key] == value for key, value in row.items())
        assert enriched['full_base_replay_sha256'] == sha(full_base_replay_path)
        assert enriched['full_base_replay_status'] == 'PASS'
        k = row['effective_columns']
        candidate = json.loads((HERE / f'candidate_K{k}.json').read_text())
        candidate_id = candidate.pop('candidate_id')
        curve = candidate['curve'].copy()
        curve_id = curve.pop('curve_id')
        assert curve_id == 'EC1N83Ckb1a1h' + digest({'field': candidate['field'], 'curve': curve})[:12]
        expected_prefix = f'IC1N83Ckb1a1fb{166 * k}PDP4rootRCguidedLAgaussTDdirectISO0h'
        assert candidate_id == expected_prefix + digest(candidate)[:12]
        assert row['candidate_id'] == candidate_id
        assert row['curve_id'] == curve_id == workload['curve_id']
        assert row['workload_id'] == workload_id
        assert row['run_id'] == f'{candidate_id}W{workload_id}R1'
        assert row['actual_factor_base_points'] == 166 * k
        assert row['correctness_receipt_sha256'] == sha(HERE / 'verification_v2.json')
        arm = HERE / 'runs' / f'K{k}'
        base = json.loads((arm / 'base.jsonl').read_text())
        assert candidate['factor_base']['ordered_base_dump_sha256'] == sha(arm / 'base.jsonl')
        matching_replay = [item for item in full_base_replay['records'] if item['K'] == k]
        assert len(matching_replay) == 1
        assert matching_replay[0]['base_sha256'] == sha(arm / 'base.jsonl')
        assert matching_replay[0]['point_and_label_rows_checked'] == 166 * k
        sorted_points = sorted(base['factor_base_point_coordinates'],
                               key=lambda point: (int(point[0]), int(point[1])))
        assert candidate['factor_base']['enumerated_set_sha256'] == digest(sorted_points)
        target = json.loads((arm / 'target.jsonl').read_text())
        assert row['target'] == target['target'] == workload['public_targets'][0]
        assert abs(sum(row['ic_online_phases_ms'].values()) - row['ic_online_ms']) <= 0.02
        assert row['ic_peak_rss_bytes_sampled'] <= 12884901888
        assert row['controlled_speedup'] is None
    print(json.dumps({'status': 'PASS', 'curve_id': workload['curve_id'],
                      'workload_id': workload_id,
                      'candidate_ids': [row['candidate_id'] for row in rows]}))


if __name__ == '__main__':
    main()
