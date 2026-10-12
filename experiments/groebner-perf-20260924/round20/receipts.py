"""Full-DLP wall receipts; uncounted native operations remain explicitly null."""
from collections import Counter
import hashlib
import platform
import resource
import sys

from ic_query import HERE, ROOT, PHASES, ONLINE, sha256_hex

_path = sys.path[:]
try:
    sys.path.insert(0, str(ROOT/'experiments/ic-candidate-catalog'))
    from analyze import validate_run
    from profile import wilson95
finally:
    sys.path[:] = _path


def receipt(prepared, cid, manifest, wid, workload, result, rho, run_number, elapsed_ns):
    q, prep = prepared, prepared.preparation
    attempts = prep['attempts']
    mix = Counter(a['status'] for a in attempts)
    verified = result['verified'] and rho['verified']
    status = result['status'] if result['status'] != 'complete' or verified else 'error'
    run_id = f'{cid}W{wid}R{run_number}'
    limits = {**workload['resource_limits'], 'online_clock': 'perf_counter_ns',
              'native_threads': 1, 'independent_scalar_replay': 'Python double-and-add'}
    eid = 'ENV1h'+sha256_hex(limits)[:12]
    online = None
    if result['online_wall_ns'] is not None:
        online = {'ic_online_ns': result['online_wall_ns'], 'rho_online_ns': rho['online_wall_ns'],
                  'phase_wall_ns': result['phase_wall_ns'], 'public_target': workload['target'],
                  'speedup': rho['online_wall_ns']/result['online_wall_ns'] if verified else None,
                  'interval': 'first public-target validation through independent Python scalar replay',
                  'bookkeeping_charged_to_target_descent_ns': result['bookkeeping_ns']}
    cold = dict(prep['phase_wall_ns'])
    if result['phase_wall_ns'] is not None:
        cold['target_descent'] += sum(result['phase_wall_ns'][p] for p in ONLINE if p != 'target_recovery_check')
        cold['recovery_check'] += result['phase_wall_ns']['target_recovery_check']
    statuses = {'verified_decomposition': 'pdp_verified', 'proved_unsat': 'pdp_proved_unsat',
                'budget': 'pdp_budget', 'error': 'pdp_error', 'lift_rejected': 'pdp_lift_rejected'}
    counts = {'ordinary_queries': len(attempts), 'solved_queries': mix['verified_decomposition'],
              'verified_decompositions': mix['verified_decomposition'],
              'verified_relations': sum(len(a['relations']) for a in attempts),
              'novel_rows': sum(a['novel_rows'] for a in attempts),
              'effective_columns': q.fb.effective_columns, 'final_rank': prep['final_rank'],
              'pdp_attempts': len(attempts), 'pdp_timeout': 0,
              'targets': 1, 'targets_verified': int(verified), 'descent_attempts': len(result['attempts'])}
    counts.update({key: mix[name] for name, key in statuses.items()})
    query = q.backend.query
    binaries = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in (
        ('producer', query.basis.solver_path), ('certificate', query.basis.verifier_path),
        ('descent', query.descent.path), ('curve_replay', query.replay.path))}
    certificate = ({k: result[k] for k in ('target', 'scalar', 'replayed_point')} if result['verified'] else None)
    row = {'schema_version': 1, 'kind': 'full_dlp', 'accounting_mode': 'verified_online_wall',
           'status': status, 'candidate_id': cid, 'proposal_id': None, 'run_id': run_id,
           'workload_id': wid, 'pair_block_id': f'W{wid}R{run_number}',
           'source_curve_ref': q.curve.curve_id, 'profile_id': f'round20-n{q.curve.n}-m3-ell{q.ell}-{q.arm}',
           'isogeny_route_ref': 'none', 'subgroup_order': str(q.curve.r), 'counts': counts,
           'phase_wall_ns': cold, 'phase_operations': dict.fromkeys(PHASES),
           'total_operations': None, 'rho_operations': None, 'rho_floor_operations': None,
           'operation_unit': None, 'unknown_operation_reason': 'Native packed descent, basis and certificate work is not fully metered; wall times are measured directly.',
           'ratio_to_rho': None, 'ratio_to_floor': None, 'S_rps': None, 'S_ec_add': None,
           'online': online, 'rho_measured': rho, 'verified_scalar': verified,
           'scalar_certificate': certificate, 'scalar_certificate_ref': run_id+'#scalar_certificate' if verified else None,
           'preparation': prep, 'target_result': result, 'selected_binary_sha256': binaries,
           'wall_ns': elapsed_ns, 'charged_preparation_and_online_ns': sum(cold.values()),
           'wall_scope': 'object preparation start to target completion; paired scheduling gaps may be present outside exclusive phases',
           'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024),
           'memory_scope': 'process high-water RSS, not a per-query allocation peak',
           'resource_envelope': limits,
           'stage': {'actual_base_points': q.fb.usable_points, 'geometric_points': q.fb.geometric_points,
                     'folded_columns': q.fb.effective_columns, 'nominal_dimension': q.ell,
                     'factor_base_sha256': q.fb.digest, 'column_logs_verified': prep.get('column_replay'),
                     'yield_numerator': mix['verified_decomposition'], 'yield_denominator': len(attempts),
                     'yield_wilson95': wilson95(mix['verified_decomposition'], len(attempts)),
                     'collection_wall_ns_per_novel_row': sum(cold[p] for p in ('queries','pdp','relation_check','matrix_build'))/counts['novel_rows'] if counts['novel_rows'] else None},
           'provenance': {'workload_fixture_sha256': sha256_hex(workload),
                          'source_sha256': sha256_hex(manifest['implementation']['sources_sha256']),
                          'host_id': platform.node(), 'resource_envelope_id': eid,
                          'calibration_id': 'perf-counter-ns-paired-local-wall-v1'}}
    return validate_run(row)
