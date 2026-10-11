"""Audit exact trace-gated N131 formula against its frozen public query."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run_trace

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def main():
    protocol = run_trace.base.checked_protocol()
    trace = json.loads((BASE/'trace_gate_result.json').read_text())
    control = json.loads((HERE/'control_result.json').read_text())
    correction = json.loads((HERE/'accounting_correction.json').read_text())
    query = json.loads((HERE/'query_result.json').read_text())
    first = json.loads((BASE/'query_result.json').read_text())
    assert trace['status'] == 'PASS_TRACE_ZERO_TARGET_PREIMAGE_GATE'
    assert trace['admissible_raw_preimage_indices'] == [0, 2]
    assert control['status'] == 'PASS_FULL_N131_EIGHT_SLOT_ASSIGNMENT'
    assert query['solver_started'] and not query['solver_rss_exceeded']
    assert query['target'] == first['target'] == protocol['public_target']
    assert query['public_workload_id'] == first['public_workload_id']
    assert query['source_sha256']['protocol.json'] == run_trace.base.sha(HERE/'protocol.json')
    assert correction['status'] == 'PASS_EXCLUSIVE_PHASE_RECONCILIATION'
    assert correction['amended_query_result_sha256'] == run_trace.base.sha(HERE/'query_result.json')
    c, meta, elapsed = run_trace.build(protocol['raw_target_preimage_z'])
    with tempfile.NamedTemporaryFile(suffix='.xcnf', dir='/private/tmp') as stream:
        formula = Path(stream.name)
        c.write(formula)
        assert formula.stat().st_size == query['formula']['bytes']
        assert run_trace.base.sha(formula) == query['formula']['sha256']
    assert query['formula']['direct_trace_zero_rows'] == 6
    assert query['formula']['excluded_trace_one_raw_preimages'] == 2
    assert query['formula']['and_gates'] == first['formula']['and_gates']
    assert query['formula']['native_xor_rows'] >= first['formula']['native_xor_rows']
    phases = query['phase_seconds']
    assert phases['post_solver_log_capture'] == correction['post_solver_log_capture_seconds']
    assert abs(sum(phases[k] for k in ('construction', 'write_and_hash',
                                      'solver', 'post_solver_log_capture'))
               - phases['total']) < 1e-9
    stdout = gzip.open(HERE/'solver.stdout.gz', 'rb').read()
    stderr = gzip.open(HERE/'solver.stderr.gz', 'rb').read()
    assert hashlib.sha256(stdout).hexdigest() == query['stdout_sha256']
    assert hashlib.sha256(stderr).hexdigest() == query['stderr_sha256']
    assert run_trace.base.sha(HERE/'solver.stdout.gz') == query['stdout_gzip_sha256']
    assert run_trace.base.sha(HERE/'solver.stderr.gz') == query['stderr_gzip_sha256']
    restarts = stdout.count(b'c rst ')
    if query['status'] == 'BOUNDED_UNKNOWN':
        assert restarts > 0
        assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
    result = {'status': 'PASS', 'query_status': query['status'],
              'public_workload_id': protocol['public_workload_id'],
              'formula_sha256': query['formula']['sha256'],
              'formula_bytes': query['formula']['bytes'],
              'solver_restart_lines': restarts,
              'direct_trace_zero_rows': 6,
              'admissible_raw_preimage_indices': [0, 2],
              'source_sha256': {'protocol.json': run_trace.base.sha(HERE/'protocol.json'),
                                'query_result.json': run_trace.base.sha(HERE/'query_result.json')}}
    (HERE/'terminal_audit.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
