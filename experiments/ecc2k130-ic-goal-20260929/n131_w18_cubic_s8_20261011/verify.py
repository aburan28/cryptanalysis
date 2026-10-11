"""Audit the frozen N131 source-bound formula and bounded query receipt."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    protocol = run.checked_protocol()
    control = json.loads((HERE/'control_result.json').read_text())
    audit = json.loads((HERE/'audit_result.json').read_text())
    sage_control = json.loads((HERE/'sage_control_result.json').read_text())
    transport = json.loads((HERE/'transport_audit_result.json').read_text())
    trace_gate = json.loads((HERE/'trace_gate_result.json').read_text())
    correction = json.loads((HERE/'accounting_correction.json').read_text())
    query = json.loads((HERE/'query_result.json').read_text())
    assert protocol['candidate_id'] is None
    assert control['status'] == 'PASS_FULL_N131_EIGHT_SLOT_ASSIGNMENT'
    assert audit['status'] == 'PASS_EXACT_SOURCE_AND_GROUP_AUDIT'
    assert audit['mask_domain_checked'] == 262144
    assert audit['membership_disagreements'] == 0
    assert sage_control['status'] == 'PASS_CHECKED_SAGE_N131_EIGHT_SLOT_GROUP_WITNESS'
    assert sage_control['source_points_checked'] == 8
    assert transport['status'] == 'PASS_SAGE_1_PLUS_FROBENIUS_FACTOR_BASE_TRANSPORT'
    assert transport['source_masks_checked'] == 64
    assert trace_gate['admissible_raw_preimage_indices'] == [0, 2]
    assert json.loads((HERE/'sage_runtime_info.json').read_text())['status'] == 'verified'
    assert transport['source_sha256']['transport_audit_sage.py'] == run.sha(HERE/'transport_audit_sage.py')
    assert sage_control['source_sha256']['verify_fixture_sage.py'] == run.sha(HERE/'verify_fixture_sage.py')
    assert query['solver_started'] and not query['solver_rss_exceeded']
    assert query['target'] == protocol['public_target']
    assert query['public_workload_id'] == protocol['public_workload_id']
    assert query['source_sha256']['protocol.json'] == run.sha(HERE/'protocol.json')
    assert correction['status'] == 'PASS_EXCLUSIVE_PHASE_RECONCILIATION'
    assert correction['amended_query_result_sha256'] == run.sha(HERE/'query_result.json')
    assert correction['source_sha256']['reconcile_accounting.py'] == run.sha(HERE/'reconcile_accounting.py')
    c, m, elapsed = run.build(protocol['raw_target_preimage_z'])
    with tempfile.NamedTemporaryFile(suffix='.xcnf', dir='/private/tmp') as stream:
        formula = Path(stream.name)
        c.write(formula)
        assert formula.stat().st_size == query['formula']['bytes']
        assert run.sha(formula) == query['formula']['sha256']
    for key in ('bdd_nodes', 'source_and_gates', 'source_product_and_gates',
                'pair_link_and_gates', 'nontrivial_column_collision_pairs'):
        assert control['formula'][key] == query['formula'][key]
    for key in ('variables', 'and_gates', 'clauses', 'native_xor_rows'):
        assert query['formula'][key] == run.profile(c, m, elapsed)[key]
    phases = query['phase_seconds']
    assert phases['post_solver_log_capture'] == correction['post_solver_log_capture_seconds']
    assert abs(sum(phases[key] for key in ('construction', 'write_and_hash',
                                          'solver', 'post_solver_log_capture'))
               - phases['total']) < 1e-9
    stdout = gzip.open(HERE/'solver.stdout.gz', 'rb').read()
    stderr = gzip.open(HERE/'solver.stderr.gz', 'rb').read()
    assert hashlib.sha256(stdout).hexdigest() == query['stdout_sha256']
    assert hashlib.sha256(stderr).hexdigest() == query['stderr_sha256']
    assert run.sha(HERE/'solver.stdout.gz') == query['stdout_gzip_sha256']
    assert run.sha(HERE/'solver.stderr.gz') == query['stderr_gzip_sha256']
    restart_lines = stdout.count(b'c rst ')
    if query['status'] == 'BOUNDED_UNKNOWN':
        assert restart_lines > 0
        assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
    result = {'status': 'PASS', 'public_workload_id': protocol['public_workload_id'],
              'query_status': query['status'], 'formula_sha256': query['formula']['sha256'],
              'formula_bytes': query['formula']['bytes'],
              'solver_restart_lines': restart_lines,
              'source_mask_domain_checked': audit['mask_domain_checked'],
              'source_sha256': {'protocol.json': run.sha(HERE/'protocol.json'),
                                'query_result.json': run.sha(HERE/'query_result.json')}}
    (HERE/'terminal_audit.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
