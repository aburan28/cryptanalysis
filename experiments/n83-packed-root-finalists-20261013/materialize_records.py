#!/usr/bin/env python3
"""Bind the verified secondary panel to canonical IC1 and run identities."""

import copy
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'n83-packed-root-capacity-20261013'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one_row(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    return rows[0]


def write_once(path, value):
    with path.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write('\n')


def main():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    verified = json.loads((HERE / 'verification.json').read_text())
    assert verified['status'] == 'PASS' and verified['complete_arm_count'] == 2
    assert verified['censored_arms'] == []
    analysis = json.loads((HERE / 'analysis.json').read_text())
    assert analysis['target_count'] == protocol['target_count']
    assert analysis['decision_by_frozen_rule'] in ('K1200', 'K1271', 'unresolved')
    hardware = json.loads((HERE / 'hardware.json').read_text())
    assert hardware['gpu']['measurement_class'] == 'cpu_only_secondary_control'
    binary = json.loads((HERE / 'binary_manifest.json').read_text())
    prior_build = json.loads((PRIOR / 'build_provenance.json').read_text())
    assert prior_build['byte_identical'] is True
    assert prior_build['executed_binary_sha256']['ic'] == binary['ic_sha256']
    source_template = json.loads((PRIOR / 'candidate_K1200.json').read_text())
    source_template.pop('candidate_id')
    assert source_template['implementation']['source_commit'] == protocol['source_commit']
    field, curve = source_template['field'], source_template['curve']
    curve_id = curve['curve_id']
    curve_record = dict(curve)
    curve_record.pop('curve_id')
    curve_sha256 = digest({'field': field, 'curve': curve_record})
    assert curve_id == 'EC1N83Ckb1a1h' + curve_sha256[:12]
    curve_uid = 'urn:ec-record:1:sha256:' + curve_sha256
    field_sha256 = digest(field)
    public_targets = [json.loads(line) for line in (HERE / 'targets.jsonl').read_text().splitlines()]
    sidecar = json.loads((HERE / 'validation_sidecar.json').read_text())
    workload = {
        'schema_version': 1, 'curve_id': curve_id,
        'target_count': protocol['target_count'], 'public_targets': public_targets,
        'input_law': 'deterministic uniform_nonzero_scalar_proposal_mod_r; 256 fresh finalist public points',
        'seed_sha256': sidecar['seed_sha256'],
        'cold_or_warm': 'one_fresh_process_per_candidate_with_empty_index_and_logs; 256 sequential warm targets after shared setup',
        'target_sha256': protocol['targets_sha256']}
    workload_id = digest(workload)[:12]
    write_once(HERE / 'workload.json', {'workload_id': workload_id, **workload})
    measurements = []
    bindings = []
    for k in sorted(int(name[1:]) for name in verified['per_target']):
        name = f'K{k}'
        arm = HERE / 'runs' / name
        base = one_row(arm / 'base.jsonl')
        summary = one_row(arm / 'stdout.txt')
        targets = [json.loads(line) for line in (arm / 'targets.jsonl').read_text().splitlines()]
        execution = json.loads((arm / 'execution.json').read_text())
        points = base['factor_base_point_coordinates']
        assert len(points) == 166 * k and len(targets) == protocol['target_count']
        candidate = copy.deepcopy(source_template)
        factor_base = candidate['factor_base']
        factor_base['enumerated_set_sha256'] = digest(sorted(points,
            key=lambda point: (int(point[0]), int(point[1]))))
        factor_base['ordered_base_dump_sha256'] = sha(arm / 'base.jsonl')
        factor_base['source_base_hash_blake3'] = base['base_hash']
        factor_base['actual_usable_points'] = 166 * k
        factor_base['effective_columns'] = k
        candidate['relation_collection']['stop_criterion'] = f'rank_{k}'
        candidate['relation_linear_algebra']['columns'] = k
        candidate['relation_linear_algebra']['rank_criterion'] = k
        candidate_sha256 = digest(candidate)
        candidate_id = (f'IC1N83Ckb1a1fb{166 * k}PDP4rootRCguidedLAgaussTDdirectISO0h'
                        + candidate_sha256[:12])
        candidate_uid = 'urn:ec-candidate:1:sha256:' + candidate_sha256
        write_once(HERE / f'candidate_K{k}.json', {'candidate_id': candidate_id, **candidate})
        bindings.append({'candidate_id': candidate_id, 'candidate_uid': candidate_uid,
                         'candidate_sha256': candidate_sha256, 'curve_uid': curve_uid})
        if k in (1000, 1100):
            replay = HERE / 'full_base_replay.json'
        elif k in (1200, 1271):
            replay = PRIOR / 'full_base_replay.json'
        elif k == 900:
            replay = HERE.parent / 'n83-packed-root-k900-20261013/full_base_replay.json'
        elif k == 899:
            replay = HERE.parent / 'n83-compact-orbit-k899-20261012/full_base_replay.json'
        else:
            replay = HERE.parent / 'n83-compact-orbit-size-sweep-20261012/full_base_replay.json'
        phases = [
            {field: row[field] for field in (
                'target_query_ms', 'target_pdp_ms', 'target_relation_check_ms',
                'target_descent_ms', 'target_recovery_check_ms')}
            for row in targets]
        online = [float(row['target_ms']) for row in targets]
        probes = [int(row['probes']) for row in targets]
        measurements.append({
            'candidate_id': candidate_id, 'candidate_uid': candidate_uid,
            'curve_id': curve_id, 'curve_uid': curve_uid,
            'field_sha256': field_sha256,
            'workload_id': workload_id, 'run_id': f'{candidate_id}W{workload_id}R1',
            'status': 'verified_secondary_multi_target',
            'target_count': protocol['target_count'],
            'actual_factor_base_points': 166 * k, 'effective_columns': k,
            'public_targets': public_targets, 'target_probes': probes,
            'target_online_ms_exploratory': online,
            'target_online_phases_ms': phases,
            'mean_target_probes': statistics.mean(probes),
            'median_target_probes': statistics.median(probes),
            'ic_full_process_wall_s': execution['process_wall_s'],
            'ic_index_build_ms': summary['timing_ms']['index_build'],
            'ic_rank_ms': summary['timing_ms']['rank_stage'],
            'ic_final_la_ms': summary['timing_ms']['linear_algebra'],
            'ic_rank_attempts': summary['rank_attempts'],
            'ic_rank_relations': summary['rank_relations'],
            'ic_rank_failures': summary['rank_failures'],
            'ic_rank_rows_without_gain': summary['rank_rows_without_gain'],
            'ic_peak_rss_bytes_sampled': execution['sampled_peak_rss_bytes'],
            'rho_online_ms': None, 'controlled_speedup': None,
            'host_tier': 'local_shared_exploratory', 'gpu': hardware['gpu'],
            'hardware_receipt_sha256': sha(HERE / 'hardware.json'),
            'source_build_receipt_sha256': sha(PRIOR / 'build_provenance.json'),
            'correctness_receipt_sha256': sha(HERE / 'verification.json'),
            'full_base_replay_sha256': sha(replay)})
    write_once(HERE / 'measurements.json', measurements)
    write_once(HERE / 'identity_bindings.json', {
        'schema': 'n83_a1_identity_bindings_v1',
        'curve_id': curve_id, 'curve_uid': curve_uid,
        'curve_sha256': curve_sha256, 'field_sha256': field_sha256,
        'workload_id': workload_id, 'candidate_bindings': bindings})
    print(json.dumps({'curve_id': curve_id, 'workload_id': workload_id,
                      'candidate_ids': [row['candidate_id'] for row in measurements]}, indent=2))


if __name__ == '__main__':
    main()
