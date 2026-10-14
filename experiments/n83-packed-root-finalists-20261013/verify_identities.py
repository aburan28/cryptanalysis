#!/usr/bin/env python3
"""Read-only canonical identity, run, and archive binding checks."""

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / 'fb-archive'
PRIOR = HERE.parent / 'n83-packed-root-capacity-20261013'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay_path(k):
    if k in (1000, 1100):
        return HERE / 'full_base_replay.json'
    if k in (1200, 1271):
        return PRIOR / 'full_base_replay.json'
    if k == 900:
        return HERE.parent / 'n83-packed-root-k900-20261013/full_base_replay.json'
    if k == 899:
        return HERE.parent / 'n83-compact-orbit-k899-20261012/full_base_replay.json'
    return HERE.parent / 'n83-compact-orbit-size-sweep-20261012/full_base_replay.json'


def main():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    workload = json.loads((HERE / 'workload.json').read_text())
    workload_id = workload.pop('workload_id')
    assert workload_id == digest(workload)[:12]
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['status'] == 'PASS' and verification['censored_arms'] == []
    assert all(verification['checks'].values())
    hardware_path = HERE / 'hardware.json'
    hardware = json.loads(hardware_path.read_text())
    assert hardware['gpu']['devices'] == []
    assert hardware['execution']['protocol_sha256'] == sha(HERE / 'protocol.json')
    assert hardware['execution']['binary_manifest_sha256'] == sha(HERE / 'binary_manifest.json')
    prior_build = PRIOR / 'build_provenance.json'
    provenance = json.loads(prior_build.read_text())
    binaries = json.loads((HERE / 'binary_manifest.json').read_text())
    assert provenance['byte_identical'] is True
    assert provenance['executed_binary_sha256']['ic'] == binaries['ic_sha256']
    for name, value in hardware['execution']['arm_execution_sha256'].items():
        assert value == sha(HERE / 'runs' / name / 'execution.json')
    identities = json.loads((HERE / 'identity_bindings.json').read_text())
    measurements = json.loads((HERE / 'measurements.json').read_text())
    assert len(protocol['arms']) == len(measurements) == 2
    assert {row['effective_columns'] for row in measurements} == {1200, 1271}
    with (ARCHIVE / 'index.csv').open(newline='') as stream:
        archives = list(csv.DictReader(stream))
    bindings = []
    for row in measurements:
        k = row['effective_columns']
        name = f'K{k}'
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
        assert row['source_build_receipt_sha256'] == sha(prior_build)
        assert row['correctness_receipt_sha256'] == sha(HERE / 'verification.json')
        assert row['gpu'] == hardware['gpu']
        replay_file = replay_path(k)
        replay = json.loads(replay_file.read_text())
        assert replay['status'] == 'PASS'
        assert row['full_base_replay_sha256'] == sha(replay_file)
        arm = HERE / 'runs' / name
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
        target_rows = [json.loads(line) for line in (arm / 'targets.jsonl').read_text().splitlines()]
        assert len(target_rows) == row['target_count'] == workload['target_count'] == 256
        assert row['public_targets'] == workload['public_targets']
        assert row['target_probes'] == [item['probes'] for item in target_rows]
        assert row['target_online_ms_exploratory'] == [item['target_ms'] for item in target_rows]
        for index, target in enumerate(target_rows):
            assert target['target'] == workload['public_targets'][index]
            assert abs(sum(row['target_online_phases_ms'][index].values())
                       - row['target_online_ms_exploratory'][index]) <= max(
                           0.02, row['target_online_ms_exploratory'][index] * 1e-8)
        assert row['ic_peak_rss_bytes_sampled'] <= protocol['sampled_rss_cap_bytes']
        assert row['controlled_speedup'] is None and row['rho_online_ms'] is None
        bindings.append({'candidate_id': candidate_id, 'candidate_uid': candidate_uid,
                         'candidate_sha256': candidate_sha, 'curve_uid': curve_uid})
    assert identities['curve_id'] == workload['curve_id']
    assert identities['curve_uid'] == measurements[0]['curve_uid']
    assert identities['curve_sha256'] == measurements[0]['curve_uid'].rsplit(':', 1)[1]
    assert identities['field_sha256'] == measurements[0]['field_sha256']
    assert identities['workload_id'] == workload_id
    assert identities['candidate_bindings'] == bindings
    print(json.dumps({'status': 'PASS', 'workload_id': workload_id,
                      'curve_uid': identities['curve_uid'],
                      'candidate_ids': [row['candidate_id'] for row in measurements]}))


if __name__ == '__main__':
    main()
