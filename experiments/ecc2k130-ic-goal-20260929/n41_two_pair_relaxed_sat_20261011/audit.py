"""Independent source, formula, search, and exact-panel binding audit."""

import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    assert protocol['source_sha256'] == {name: sha(path) for name, path in run.sources().items()}
    panel = run.panel()
    control = json.loads((HERE/'control.json').read_text())
    positive = panel['queries'][0]
    assert control['status'] == 'PASS_EXACT_POSITIVE_BOOLEAN_ASSIGNMENT'
    assert control['target'] == positive['target']
    assert control['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
    for i, witness in enumerate((positive['left_witness'], positive['right_witness'])):
        field = run.circuit.old.Field()
        expected = field.frob(witness['reciprocal_z'], run.circuit.ROTATIONS[i])
        assert control['rotated_pair_reciprocals'][i] == expected
        point = positive['left_point'] if i == 0 else positive['right_point']
        assert field.mul(point[0], expected) == 1
    reports = {}
    for label in protocol['target_labels']:
        result = json.loads((HERE/f'{label}.result.json').read_text())
        target = protocol['targets'][label]
        assert result['target'] == target
        assert result['label'] == label
        assert result['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
        assert result['solver_flags'] == protocol['solver_flags']
        assert result['status'] == 'BOUNDED_UNKNOWN' and result['solver_wall_killed']
        assert not result['solver_rss_killed']
        assert result['phase_seconds_exploratory']['solver'] >= 45
        stdout = (HERE/f'{label}.stdout').read_bytes()
        stderr = (HERE/f'{label}.stderr').read_bytes()
        assert hashlib.sha256(stdout).hexdigest() == result['stdout_sha256']
        assert hashlib.sha256(stderr).hexdigest() == result['stderr_sha256']
        assert b'c Parsing time:' in stdout and b'c rst ' in stdout
        assert not any(line.startswith(b's ') for line in stdout.splitlines())
        phase = result['phase_seconds_exploratory']
        assert abs(sum(phase[x] for x in ('construction', 'write_and_hash',
                                         'solver', 'post_solver'))-phase['total']) < 1e-6
        c, meta, _, _ = run.build(target)
        assert c.next_var-1 == result['formula']['variables']
        assert len(c.clauses) == result['formula']['cnf_clauses']
        assert len(c.xors) == result['formula']['xor_rows']
        with tempfile.NamedTemporaryFile(prefix='n41_relaxed_audit_', suffix='.xcnf',
                                         dir='/private/tmp', delete=False) as stream:
            formula = Path(stream.name)
        try:
            c.write(formula)
            assert sha(formula) == result['formula']['sha256']
            assert formula.stat().st_size == result['formula']['bytes']
        finally:
            formula.unlink(missing_ok=True)
        reports[label] = {'status': result['status'], 'target': target,
                          'formula_sha256': result['formula']['sha256'],
                          'restart_rows': stdout.count(b'c rst '),
                          'exact_panel_status': next(x['status'] for x in panel['queries']
                                                     if x['label'] == label)}
    record = {'status': 'PASS_EXACT_INPUT_FORMULA_AND_BOUNDED_SEARCH_AUDIT',
              'candidate_id': None, 'queries': reports,
              'positive_assignment_clauses': control['assignment_check']['clauses'],
              'positive_assignment_xor_rows': control['assignment_check']['xor_rows'],
              'source_sha256': {'protocol.json': sha(HERE/'protocol.json'),
                                'control.json': sha(HERE/'control.json'),
                                'audit.py': sha(HERE/'audit.py')}}
    (HERE/'audit.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
