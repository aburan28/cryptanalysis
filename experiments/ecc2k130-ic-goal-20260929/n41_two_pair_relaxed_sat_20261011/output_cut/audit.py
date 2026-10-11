"""Read-only audit of frozen supplied-output SAT and linear completion panels."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cut  # noqa: E402
import linear_oracle  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cp = json.loads((HERE/'protocol.json').read_text())
    lp = json.loads((HERE/'linear_protocol.json').read_text())
    assert cp['source_sha256'] == {name: sha(path) for name, path in cut.sources().items()}
    assert lp['source_sha256'] == {name: sha(path) for name, path in linear_oracle.sources().items()}
    assert lp['first_pair_reciprocal_z'] == cp['first_pair_reciprocal_z']
    control = json.loads((HERE/'control.json').read_text())
    assert control['status'] == 'PASS_FULL_PINNED_ASSIGNMENT'
    assert control['pinned_units'] == 41
    assert control['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
    statuses = {}
    for label in ('positive', 'control_0'):
        result = json.loads((HERE/f'{label}.result.json').read_text())
        assert result['status'] == 'BOUNDED_UNKNOWN' and result['solver_wall_killed']
        assert not result['solver_rss_killed']
        assert result['phase_seconds_exploratory']['solver'] >= 30
        assert result['target'] == cp['targets'][label]
        assert result['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
        stdout = (HERE/f'{label}.stdout').read_bytes()
        stderr = (HERE/f'{label}.stderr').read_bytes()
        assert result['stdout_sha256'] == hashlib.sha256(stdout).hexdigest()
        assert result['stderr_sha256'] == hashlib.sha256(stderr).hexdigest()
        assert b'c Parsing time:' in stdout and b'c rst ' in stdout
        assert not any(line.startswith(b's ') for line in stdout.splitlines())
        phase = result['phase_seconds_exploratory']
        assert abs(sum(phase[key] for key in ('construction', 'write_and_hash',
                                              'solver', 'post_solver'))-phase['total']) < 1e-6
        c, meta, _, _ = cut.build(result['target'], cp['first_pair_reciprocal_z'])
        assert len(c.clauses) == result['formula']['cnf_clauses']
        assert len(c.xors) == result['formula']['xor_rows']
        with tempfile.NamedTemporaryFile(prefix='n41_output_cut_audit_',
                                         suffix='.xcnf', dir='/private/tmp', delete=False) as stream:
            formula = Path(stream.name)
        try:
            c.write(formula)
            assert sha(formula) == result['formula']['sha256']
            assert formula.stat().st_size == result['formula']['bytes']
        finally:
            formula.unlink(missing_ok=True)
        statuses[label] = {'sat_status': result['status'],
                           'formula_sha256': result['formula']['sha256'],
                           'restart_rows': stdout.count(b'c rst ')}
    linear = json.loads((HERE/'linear_result.json').read_text())
    replay = json.loads((HERE/'sage_replay.json').read_text())
    assert linear['status'] == 'PASS_SUPPLIED_OUTPUT_COMPLETION_PANEL'
    assert replay['status'] == 'PASS_INDEPENDENT_SAGE_GROUP_AND_GF2_REPLAY'
    assert linear['source_sha256']['linear_protocol.json'] == sha(HERE/'linear_protocol.json')
    assert replay['source_sha256']['linear_result.json'] == sha(HERE/'linear_result.json')
    for row in linear['queries']:
        assert row['status'] == ('RELAXED_SUM_HIT' if row['label'] == 'positive'
                                 else 'COMPLETE_RELAXED_NO_SUM')
        statuses[row['label']]['linear_status'] = row['status']
        statuses[row['label']]['linear_query_ns'] = row['target_dependent_ns_exploratory']
    record = {'status': 'PASS_FROZEN_OUTPUT_CUT_AND_SAGE_LINEAR_COMPLETION_AUDIT',
              'candidate_id': None, 'queries': statuses,
              'source_sha256': {'audit.py': sha(HERE/'audit.py'),
                                'protocol.json': sha(HERE/'protocol.json'),
                                'linear_protocol.json': sha(HERE/'linear_protocol.json'),
                                'sage_replay.json': sha(HERE/'sage_replay.json')}}
    (HERE/'audit.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
