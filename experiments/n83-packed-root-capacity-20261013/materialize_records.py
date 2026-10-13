#!/usr/bin/env python3
"""Materialize canonical IC1 identities and one-target rows from verified runs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'n83-packed-root-k900-20261013'
BUILD_PROVENANCE = HERE / 'build_provenance.json'
R = 8569786107849059
H = 1128547018
N = 83


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
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['status'] == 'PASS'
    assert verification['censored_arms'] == []
    assert verification['checks']['K900_answer']
    hardware = json.loads((HERE / 'hardware.json').read_text())
    assert hardware['gpu']['measurement_class'] == 'cpu_only_secondary_control'
    provenance = json.loads(BUILD_PROVENANCE.read_text())
    assert provenance['byte_identical'] is True
    manifest = json.loads((HERE / 'binary_manifest.json').read_text())
    assert provenance['executed_binary_sha256'] == {
        'ic': manifest['ic_sha256'], 'rho': manifest['rho_sha256']}
    assert sha(HERE / 'runs/K900/base.jsonl') == sha(PRIOR / 'runs/K900/base.jsonl')
    full_base_replay = json.loads((PRIOR / 'full_base_replay.json').read_text())
    assert full_base_replay['status'] == 'PASS'
    new_base_replay = json.loads((HERE / 'full_base_replay.json').read_text())
    assert new_base_replay['status'] == 'PASS'
    assert [row['K'] for row in new_base_replay['records']] == [1200, 1271]
    for row in new_base_replay['records']:
        assert row['base_sha256'] == sha(HERE / f"runs/K{row['K']}/base.jsonl")
    fixture = json.loads((HERE / 'validation_sidecar.json').read_text())
    target = one_row(HERE / 'target.jsonl')
    assert target == fixture['point']
    field = {'p': 2, 'n': N, 'basis': 'polynomial',
             'defining_polynomial_int': (1 << N) | (1 << 7) | (1 << 4) | (1 << 2) | 1,
             'element_encoding': 'decimal strings of polynomial coefficient bitmasks'}
    curve = {'model': 'y^2+x*y=x^3+x^2+1',
             'coefficients': {'a1': 1, 'a2': 1, 'a3': 0, 'a4': 0, 'a6': 1},
             'curve_order': R * H, 'trace': (1 << N) + 1 - R * H,
             'r': R, 'cofactor': H,
             'G': ['6614244651398184860292015', '8868260410029249391539529'],
             'target_group': 'prime_order_r_subgroup'}
    curve_id = 'EC1N83Ckb1a1h' + digest({'field': field, 'curve': curve})[:12]
    curve_sha256 = digest({'field': field, 'curve': curve})
    curve_uid = 'urn:ec-record:1:sha256:' + curve_sha256
    field_sha256 = digest(field)
    curve['curve_id'] = curve_id
    workload = {'schema_version': 1, 'curve_id': curve_id,
                'target_count': 1, 'public_targets': [target],
                'input_law': 'deterministic uniform_nonzero_scalar_proposal_mod_r; fifth_fresh_public_point',
                'seed_sha256': fixture['seed_sha256'],
                'cold_or_warm': 'one_fresh_process_per_candidate_with_empty_index_and_logs',
                'target_sha256': protocol['target_sha256']}
    workload_id = digest(workload)[:12]
    write_once(HERE / 'workload.json', {'workload_id': workload_id, **workload})
    rho_rows = [json.loads((HERE / 'runs' / name / 'rho.json').read_text())
                for name in ('rho_before', 'rho_after')]
    rho_online_mean = sum(float(row['online_ms']) for row in rho_rows) / 2
    measurements = []
    candidate_bindings = []
    for k in (900, 1200, 1271):
        name = f'K{k}'
        arm = HERE / 'runs' / name
        base = one_row(arm / 'base.jsonl')
        target_row = one_row(arm / 'target.jsonl')
        summary_rows = [json.loads(line) for line in (arm / 'stdout.txt').read_text().splitlines()
                        if line.strip().startswith('{') and 'compact_orbit_dlp_summary' in line]
        assert len(summary_rows) == 1
        summary = summary_rows[0]
        execution = json.loads((arm / 'execution.json').read_text())
        points = base['factor_base_point_coordinates']
        set_digest = digest(sorted(points, key=lambda pair: (int(pair[0]), int(pair[1]))))
        manifest = {
            'schema_version': 1,
            'field': field, 'curve': curve,
            'isogeny': 'none',
            'endomorphism': {'endomorphism_order_conductor': None,
                            'frobenius_order_conductor': None,
                            'volcano_levels': None, 'status': 'unproved_not_used'},
            'factor_base': {
                'recipe': 'scan polynomial x from one; rational lifts; cofactor projection; first K distinct signed-Frobenius orbits',
                'raw_x_start': 1, 'subspace': None, 'nominal_dimension': None,
                'enumerated_set_sha256': set_digest,
                'ordered_base_dump_sha256': sha(arm / 'base.jsonl'),
                'source_base_hash_blake3': base['base_hash'],
                'actual_usable_points': 166 * k,
                'effective_columns': k,
                'quotient_rule': 'sign and all 83 Frobenius powers; 166 usable points per column',
                'subgroup_filter': 'cofactor_1128547018_projection; discard_identity',
            },
            'point_decomposition': {
                'm': 4, 'family': 'root',
                'variant': 'S3_pair_root_index_four_summand_first_verified_witness_packed_u128_slot',
                'summation_chain': 'two indexed leaves and two query leaves via S3 root lookup',
                'weil_descent_encoding': 'none', 'equation_order': 'none',
                'solver_source_sha256': protocol['ic_source_sha256'],
                'monomial_order': 'none', 'internal_matrix_kernel': 'none',
                'index_cache_policy': 'reusable_target_independent',
                'query_stop': 'scan_finite_root_index_once_until_verified_relation'},
            'relation_collection': {
                'query_distribution': 'guided_scalar_times_G_minus_first_pivotless_base_rep',
                'verification': 'curve_group_sum_and_folded_row',
                'duplicate_policy': 'echelon_rank_gain',
                'stop_criterion': f'rank_{k}',
                'source_digest': protocol['ic_source_sha256']},
            'relation_linear_algebra': {
                'modulus': R, 'columns': k,
                'row_rule': 'signed_frobenius_coefficients_mod_r',
                'orbit_quotient': 'sign_and_frobenius',
                'rank_criterion': k, 'solver': 'gauss',
                'implementation': 'incremental_echelon',
                'block_parameters': 'none', 'preconditioner': 'none',
                'source_digest': protocol['ic_source_sha256']},
            'target_descent': {
                'policy': 'direct_four_summand_target_relation_after_factor_logs',
                'success': 'independent_scalar_replay',
                'source_digest': protocol['ic_source_sha256']},
            'implementation': {
                'source_commit': protocol['source_commit'],
                'source_sha256': {'ic': protocol['ic_source_sha256'],
                                  'cargo_lock': protocol['cargo_lock_sha256']},
                'algorithm_flags': {'rank_threads': protocol['rank_threads'],
                                    'target_threads': protocol['target_threads'],
                                    'packed_root_table': True},
                'release_profile': 'cargo_release_locked_offline'},
        }
        candidate_id = (f'IC1N83Ckb1a1fb{166 * k}PDP4rootRCguidedLAgaussTDdirectISO0h'
                        + digest(manifest)[:12])
        candidate_sha256 = digest(manifest)
        candidate_bindings.append({'candidate_id': candidate_id,
            'candidate_uid': 'urn:ec-candidate:1:sha256:' + candidate_sha256,
            'candidate_sha256': candidate_sha256, 'curve_uid': curve_uid})
        write_once(HERE / f'candidate_K{k}.json', {'candidate_id': candidate_id, **manifest})
        online_ms = float(target_row['target_ms'])
        phases = {key: target_row[key] for key in ('target_query_ms', 'target_pdp_ms',
            'target_relation_check_ms', 'target_descent_ms', 'target_recovery_check_ms')}
        measurements.append({
            'candidate_id': candidate_id, 'workload_id': workload_id,
            'run_id': f'{candidate_id}W{workload_id}R1',
            'status': 'verified_single_target',
            'curve_id': curve_id, 'actual_factor_base_points': 166 * k,
            'curve_uid': curve_uid, 'field_sha256': field_sha256,
            'candidate_uid': 'urn:ec-candidate:1:sha256:' + candidate_sha256,
            'effective_columns': k,
            'target': target, 'ic_online_ms': online_ms,
            'ic_online_phases_ms': phases,
            'ic_full_process_wall_s': execution['process_wall_s'],
            'ic_index_build_ms': summary['timing_ms']['index_build'],
            'ic_rank_ms': summary['timing_ms']['rank_stage'],
            'ic_final_la_ms': summary['timing_ms']['linear_algebra'],
            'ic_rank_attempts': summary['rank_attempts'],
            'ic_rank_relations': summary['rank_relations'],
            'ic_rank_failures': summary['rank_failures'],
            'ic_rank_rows_without_gain': summary['rank_rows_without_gain'],
            'ic_target_probes': target_row['probes'],
            'ic_peak_rss_bytes_sampled': execution['sampled_peak_rss_bytes'],
            'rho_policy': protocol['rho_policy'],
            'rho_online_ms_before_after': [float(row['online_ms']) for row in rho_rows],
            'rho_online_mean_ms': rho_online_mean,
            'exploratory_rho_over_ic_online_ratio': rho_online_mean / online_ms,
            'controlled_speedup': None,
            'host_tier': 'local_shared_exploratory',
            'gpu': hardware['gpu'],
            'hardware_receipt_sha256': sha(HERE / 'hardware.json'),
            'source_build_receipt_sha256': sha(BUILD_PROVENANCE),
            'correctness_receipt_sha256': sha(HERE / 'verification.json'),
            'full_base_replay_sha256': sha((PRIOR if k == 900 else HERE) / 'full_base_replay.json'),
        })
    write_once(HERE / 'measurements.json', measurements)
    write_once(HERE / 'identity_bindings.json', {
        'schema': 'n83_a1_identity_bindings_v1',
        'curve_id': curve_id, 'curve_uid': curve_uid,
        'curve_sha256': curve_sha256, 'field_sha256': field_sha256,
        'workload_id': workload_id, 'candidate_bindings': candidate_bindings,
        'rho_arms': [{'arm': name, 'curve_uid': curve_uid,
                      'target_sha256': protocol['target_sha256']}
                     for name in ('rho_before', 'rho_after')],
    })
    print(json.dumps({'curve_id': curve_id, 'workload_id': workload_id,
                      'candidate_ids': [row['candidate_id'] for row in measurements]}, indent=2))


if __name__ == '__main__':
    main()
