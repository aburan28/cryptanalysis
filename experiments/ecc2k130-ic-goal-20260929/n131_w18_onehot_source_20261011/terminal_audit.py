"""Read-only terminal receipt and solver activity audit."""

import gzip
import hashlib
import json
from pathlib import Path

import solve

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'solver_protocol.json').read_text())
    result = json.loads((HERE/'solver_result.json').read_text())
    assert protocol['source_sha256'] == {key: sha(value) for key, value in solve.paths().items()}
    assert result['source_sha256']['solver_protocol.json'] == sha(HERE/'solver_protocol.json')
    assert result['formula_sha256'] == protocol['expected_formula_sha256']
    assert result['public_target'] == protocol['public_target']
    assert result['workload_id'] == protocol['workload_id']
    assert result['solver_flags'] == protocol['solver_flags']
    assert result['stdout_gzip_sha256'] == sha(HERE/'solver.stdout.gz')
    assert result['stderr_gzip_sha256'] == sha(HERE/'solver.stderr.gz')
    stdout = gzip.decompress((HERE/'solver.stdout.gz').read_bytes())
    stderr = gzip.decompress((HERE/'solver.stderr.gz').read_bytes())
    assert result['stdout_sha256'] == hashlib.sha256(stdout).hexdigest()
    assert result['stderr_sha256'] == hashlib.sha256(stderr).hexdigest()
    parsing_seen = b'c Parsing time:' in stdout
    solver_activity = any(token in stdout for token in
                          (b'c [gauss]', b'c [matrix]', b'c sum restarts',
                           b'c ------- FINAL TOTAL SEARCH STATS'))
    terminal = ([line.decode(errors='replace').strip() for line in stdout.splitlines()
                 if line.startswith(b's ')])
    if result['status'] == 'BOUNDED_UNKNOWN':
        assert parsing_seen and solver_activity
        assert all(x in ('s INDETERMINATE',) for x in terminal)
        assert result['phase_seconds_exploratory']['solver'] >= 590
        assert not result['solver_rss_killed']
    if result['status'] == 'SAT_PENDING_GROUP_REPLAY':
        assert terminal == ['s SATISFIABLE']
        assert (HERE/'model_decoded.json').is_file()
    if result['status'] == 'UNSAT':
        assert terminal == ['s UNSATISFIABLE']
    phases = result['phase_seconds_exploratory']
    assert all(value >= 0 for value in phases.values())
    assert abs(sum(phases[name] for name in ('construction', 'write_and_hash',
                                            'solver', 'post_solver')) - phases['total']) < 1e-6
    record = {'status': 'PASS_RECEIPT_AND_SOLVER_ACTIVITY',
              'solver_status': result['status'], 'parsing_seen': parsing_seen,
              'solver_activity': solver_activity, 'terminal_lines': terminal,
              'stderr_bytes': len(stderr), 'stdout_bytes': len(stdout),
              'source_sha256': {'solver_protocol.json': sha(HERE/'solver_protocol.json'),
                                'solver_result.json': sha(HERE/'solver_result.json'),
                                'terminal_audit.py': sha(HERE/'terminal_audit.py')}}
    (HERE/'terminal_audit.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
