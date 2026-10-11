"""Rebuild the trace-pruned public XCNF and audit its solver receipt."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    protocol = run.checked_protocol()
    binding = json.loads((HERE/'binding_audit.json').read_text())
    control = json.loads((HERE/'control_result.json').read_text())
    query = json.loads((HERE/'query_result.json').read_text())
    assert binding['status'] == 'PASS_STANDARD_TRACE_TWO_PREIMAGE_BINDING'
    assert binding['source_sha256']['protocol.json'] == run.sha(HERE/'protocol.json')
    assert control['status'] == 'PASS_FULL_N131_EIGHT_SLOT_ASSIGNMENT'
    assert query['solver_started'] and query['target'] == protocol['public_target']
    assert query['public_workload_id'] == protocol['public_workload_id']
    assert query['source_sha256']['protocol.json'] == run.sha(HERE/'protocol.json')
    c, meta, elapsed = run.build(protocol['raw_target_preimage_z'])
    with tempfile.NamedTemporaryFile(suffix='.xcnf', dir='/private/tmp') as stream:
        path = Path(stream.name)
        c.write(path)
        assert path.stat().st_size == query['formula']['bytes']
        assert run.sha(path) == query['formula']['sha256']
    for key in ('variables', 'and_gates', 'clauses', 'native_xor_rows'):
        assert run.profile(c, meta, elapsed)[key] == query['formula'][key]
    stdout = gzip.open(HERE/'solver.stdout.gz', 'rb').read()
    stderr = gzip.open(HERE/'solver.stderr.gz', 'rb').read()
    assert hashlib.sha256(stdout).hexdigest() == query['stdout_sha256']
    assert hashlib.sha256(stderr).hexdigest() == query['stderr_sha256']
    assert run.sha(HERE/'solver.stdout.gz') == query['stdout_gzip_sha256']
    assert run.sha(HERE/'solver.stderr.gz') == query['stderr_gzip_sha256']
    restarts = stdout.count(b'c rst ')
    if query['status'] == 'BOUNDED_UNKNOWN':
        assert restarts > 0 and b's SATISFIABLE' not in stdout
        assert b's UNSATISFIABLE' not in stdout
    phases = query['phase_seconds']
    residual = phases['total'] - sum(phases[key] for key in
                                     ('construction', 'write_and_hash', 'solver'))
    assert 0 <= residual < 10
    result = {'status': 'PASS_FORMULA_AND_SOLVER_RECEIPT',
              'query_status': query['status'],
              'formula_sha256': query['formula']['sha256'],
              'formula_bytes': query['formula']['bytes'],
              'solver_restart_lines': restarts,
              'unallocated_post_solver_seconds': residual,
              'source_sha256': {'terminal_verify.py': run.sha(Path(__file__)),
                                'protocol.json': run.sha(HERE/'protocol.json'),
                                'query_result.json': run.sha(HERE/'query_result.json')}}
    (HERE/'terminal_audit.json').write_text(json.dumps(result, sort_keys=True,
                                                      indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
