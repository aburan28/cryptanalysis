#!/usr/bin/env python3
"""Read-only identity, archive, hardware and run-record checks."""

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'n83-compact-orbit-k899-20261012'
ARCHIVE = HERE.parent / 'fb-archive'
BUILD_PROVENANCE = HERE / 'build_provenance.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    workload = json.loads((HERE / 'workload.json').read_text())
    workload_id = workload.pop('workload_id')
    assert workload_id == digest(workload)[:12]
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['status'] == 'PASS' and verification['censored_arms'] == []
    assert all(verification['checks'].values())
    hardware_path = HERE / 'hardware.json'
    hardware = json.loads(hardware_path.read_text())
    assert hardware['gpu']['devices'] == []
    assert hardware['gpu']['measurement_class'] == 'cpu_only_secondary_control'
    assert hardware['execution']['protocol_sha256'] == sha(HERE / 'protocol.json')
    assert hardware['execution']['binary_manifest_sha256'] == sha(HERE / 'binary_manifest.json')
    provenance = json.loads(BUILD_PROVENANCE.read_text())
    binaries = json.loads((HERE / 'binary_manifest.json').read_text())
    assert provenance['byte_identical'] is True
    assert provenance['executed_binary_sha256'] == provenance['rebuilt_binary_sha256'] == {
        'ic': binaries['ic_sha256'], 'rho': binaries['rho_sha256']}
    for name, value in hardware['execution']['arm_execution_sha256'].items():
        assert value == sha(HERE / 'runs' / name / 'execution.json')
    identities = json.loads((HERE / 'identity_bindings.json').read_text())
    rows = json.loads((HERE / 'measurements.json').read_text())
    assert len(rows) == 2 and {row['effective_columns'] for row in rows} == {899, 900}
    with (ARCHIVE / 'index.csv').open(newline='') as stream:
        archives = list(csv.DictReader(stream))
    bindings = []
    for row in rows:
        k = row['effective_columns']
        candidate = json.loads((HERE / f'candidate_K{k}.json').read_text())
        candidate_id = candidate.pop('candidate_id')
        curve = candidate['curve'].copy()
        curve_id = curve.pop('curve_id')
        curve_sha = digest({'field': candidate['field'], 'curve': curve})
        curve_uid = 'urn:ec-record:1:sha256:' + curve_sha
        candidate_sha = digest(candidate)
        candidate_uid = 'urn:ec-candidate:1:sha256:' + candidate_sha
        assert curve_id == 'EC1N83Ckb1a1h' + curve_sha[:12]
        assert candidate_id == (f'IC1N83Ckb1a1fb{166 * k}'
            'PDP4rootRCguidedLAgaussTDdirectISO0h' + candidate_sha[:12])
        assert row['candidate_id'] == candidate_id and row['candidate_uid'] == candidate_uid
        assert row['curve_id'] == workload['curve_id'] == curve_id
        assert row['curve_uid'] == curve_uid
        assert row['field_sha256'] == digest(candidate['field'])
        assert row['workload_id'] == workload_id
        assert row['run_id'] == f'{candidate_id}W{workload_id}R1'
        assert row['actual_factor_base_points'] == 166 * k
        assert row['hardware_receipt_sha256'] == sha(hardware_path)
        assert row['source_build_receipt_sha256'] == sha(BUILD_PROVENANCE)
        assert row['gpu'] == hardware['gpu']
        assert row['correctness_receipt_sha256'] == sha(HERE / 'verification.json')
        replay_path = (PRIOR if k == 899 else HERE) / 'full_base_replay.json'
        replay = json.loads(replay_path.read_text())
        assert replay['status'] == 'PASS'
        assert row['full_base_replay_sha256'] == sha(replay_path)
        arm = HERE / 'runs' / f'K{k}'
        base = json.loads((arm / 'base.jsonl').read_text())
        assert candidate['factor_base']['ordered_base_dump_sha256'] == sha(arm / 'base.jsonl')
        matched = [item for item in replay['records'] if item['K'] == k]
        assert len(matched) == 1
        assert matched[0]['base_sha256'] == sha(arm / 'base.jsonl')
        assert matched[0]['point_and_label_rows_checked'] == 166 * k
        points = sorted(base['factor_base_point_coordinates'],
                        key=lambda point: (int(point[0]), int(point[1])))
        point_sha = digest(points)
        assert candidate['factor_base']['enumerated_set_sha256'] == point_sha
        archived = [item for item in archives if item['enumerated_set_sha256'] == point_sha]
        assert len(archived) == 1 and archived[0]['curve_id'] == curve_id
        assert archived[0]['fb_points'] == str(166 * k)
        assert (ARCHIVE / archived[0]['path']).is_file()
        target = json.loads((arm / 'target.jsonl').read_text())
        assert row['target'] == target['target'] == workload['public_targets'][0]
        assert abs(sum(row['ic_online_phases_ms'].values()) - row['ic_online_ms']) <= 0.02
        assert row['ic_peak_rss_bytes_sampled'] <= 12884901888
        assert row['controlled_speedup'] is None
        bindings.append({'candidate_id': candidate_id, 'candidate_uid': candidate_uid,
                         'candidate_sha256': candidate_sha, 'curve_uid': curve_uid})
    assert identities['curve_id'] == workload['curve_id']
    assert identities['curve_uid'] == rows[0]['curve_uid'] == rows[1]['curve_uid']
    assert identities['curve_sha256'] == rows[0]['curve_uid'].rsplit(':', 1)[1]
    assert identities['field_sha256'] == rows[0]['field_sha256'] == rows[1]['field_sha256']
    assert identities['workload_id'] == workload_id
    assert identities['candidate_bindings'] == bindings
    assert identities['rho_arms'] == [
        {'arm': name, 'curve_uid': identities['curve_uid'],
         'target_sha256': workload['target_sha256']}
        for name in ('rho_before', 'rho_after')]
    assert sha(HERE / 'runs/K899/base.jsonl') == sha(PRIOR / 'runs/K899/base.jsonl')
    print(json.dumps({'status': 'PASS', 'workload_id': workload_id,
                      'curve_uid': identities['curve_uid'],
                      'candidate_ids': [row['candidate_id'] for row in rows]}))


if __name__ == '__main__':
    main()
