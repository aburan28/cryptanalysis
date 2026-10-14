#!/usr/bin/env python3
"""Read-only canonical identity and censored-arm evidence checks."""

import hashlib
import csv
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
    curve_sha256 = digest({'field': candidate['field'], 'curve': curve})
    curve_uid = 'urn:ec-record:1:sha256:' + curve_sha256
    candidate_sha256 = digest(candidate)
    candidate_uid = 'urn:ec-candidate:1:sha256:' + candidate_sha256
    assert curve_id == 'EC1N83Ckb1a1h' + curve_sha256[:12]
    assert candidate_id == ('IC1N83Ckb1a1fb132800PDP4rootRCguidedLAgaussTDdirectISO0h'
                            + candidate_sha256[:12])
    assert row['candidate_id'] == candidate_id
    assert row['curve_id'] == curve_id == workload['curve_id']
    assert row['curve_uid'] == curve_uid
    assert row['candidate_uid'] == candidate_uid
    assert row['field_sha256'] == digest(candidate['field'])
    identities = json.loads((HERE / 'identity_bindings.json').read_text())
    assert identities['curve_id'] == curve_id
    assert identities['curve_uid'] == curve_uid
    assert identities['curve_sha256'] == curve_sha256
    assert identities['field_sha256'] == row['field_sha256']
    assert identities['workload_id'] == workload_id
    assert identities['candidate_bindings'] == [{
        'candidate_id': candidate_id, 'candidate_uid': candidate_uid,
        'candidate_sha256': candidate_sha256, 'curve_uid': curve_uid}]
    assert identities['rho_arms'] == [
        {'arm': name, 'curve_uid': curve_uid,
         'target_sha256': workload['target_sha256']}
        for name in ('rho_before', 'rho_after')]
    assert row['workload_id'] == workload_id
    assert row['run_id'] == f'{candidate_id}W{workload_id}R1'
    assert row['actual_factor_base_points'] == 132800
    assert row['effective_columns'] == 800
    assert row['correctness_receipt_sha256'] == sha(HERE / 'verification.json')
    hardware_path = HERE / 'hardware.json'
    hardware = json.loads(hardware_path.read_text())
    assert row['hardware_receipt_sha256'] == sha(hardware_path)
    assert row['gpu'] == hardware['gpu']
    assert hardware['gpu']['devices'] == []
    assert hardware['gpu']['measurement_class'] == 'cpu_only_secondary_control'
    assert hardware['execution']['protocol_sha256'] == sha(HERE / 'protocol.json')
    assert hardware['execution']['binary_manifest_sha256'] == sha(HERE / 'binary_manifest.json')
    for name, receipt_sha256 in hardware['execution']['arm_execution_sha256'].items():
        assert receipt_sha256 == sha(HERE / 'runs' / name / 'execution.json')
    proof = json.loads((HERE / 'proof_check.json').read_text())
    assert proof['toolchain'] == (HERE / 'lean-toolchain').read_text().strip()
    assert proof['source_sha256'] == sha(HERE / 'CapacityBound.lean')
    assert proof['exit_code'] == 0 and proof['stderr'] == ''
    assert len(proof['declarations']) == 3
    assert proof['stdout'].count('does not depend on any axioms') == 3
    layout = json.loads((HERE / 'slot_layout_receipt.json').read_text())
    assert layout['source_sha256'] == sha(HERE / 'slot_layout.rs')
    assert layout['slot_bytes'] == 32 and layout['program_stdout'] == '32\n'
    assert layout['target_architecture'] == hardware['hardware']['architecture']
    build = json.loads((HERE / 'build_provenance.json').read_text())
    binaries = json.loads((HERE / 'binary_manifest.json').read_text())
    assert build['source_tree_status'] == 'clean'
    assert build['source_commit'] == json.loads((HERE / 'protocol.json').read_text())['source_commit']
    assert build['build_exit_code'] == 0 and build['byte_identical'] is True
    assert build['executed_binary_sha256'] == build['rebuilt_binary_sha256'] == {
        'ic': binaries['ic_sha256'], 'rho': binaries['rho_sha256']}
    assert build['rebuild_stdout_sha256'] == sha(HERE / 'rebuild_stdout.txt')
    assert build['rebuild_stderr_sha256'] == sha(HERE / 'rebuild_stderr.txt')
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
    archive_root = HERE.parent / 'fb-archive'
    with (archive_root / 'index.csv').open(newline='') as stream:
        matching_archive = [record for record in csv.DictReader(stream)
            if record['enumerated_set_sha256'] == candidate['factor_base']['enumerated_set_sha256']]
    assert len(matching_archive) == 1
    assert matching_archive[0]['curve_id'] == curve_id
    assert matching_archive[0]['fb_points'] == '132800'
    assert (archive_root / matching_archive[0]['path']).is_file()
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
    assert censored['hardware_receipt_sha256'] == sha(hardware_path)
    assert censored['gpu'] == hardware['gpu']
    print(json.dumps({'status': 'PASS', 'curve_id': curve_id,
                      'curve_uid': curve_uid,
                      'workload_id': workload_id, 'candidate_id': candidate_id,
                      'censored_arm': 'K900'}))


if __name__ == '__main__':
    main()
