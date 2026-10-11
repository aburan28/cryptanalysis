"""Audit ordered-pair N41 public query against its frozen sources and formula."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import ordered

HERE = Path(__file__).resolve().parent
OUT = HERE/'ordered'


def main():
    ordered.configure()
    base = ordered.base
    p = base.protocol()
    f = base.fixture()
    control = json.loads((OUT/'control_result.json').read_text())
    result = json.loads((OUT/'query_result.json').read_text())
    assert p['factor_base_B'] == 256
    assert p['method_refinement'] == 'canonical numeric mask order within each same-rotation pair'
    assert all(f['known_masks'][2*i] < f['known_masks'][2*i+1] for i in range(4))
    assert control['status'] == 'PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT'
    assert control['protocol_sha256'] == result['protocol_sha256'] == base.sha(OUT/'protocol.json')
    c, m, _ = base.build(p['raw_target_preimage_z'])
    assert m['ordered_pair_forbids'] == 1984
    with tempfile.NamedTemporaryFile(prefix='n41_ordered_audit_', suffix='.xcnf',
                                     dir='/private/tmp') as stream:
        formula = Path(stream.name)
        c.write(formula)
        assert formula.stat().st_size == result['formula']['bytes']
        assert base.sha(formula) == result['formula']['sha256']
    stdout = gzip.decompress((OUT/'solver.stdout.gz').read_bytes())
    stderr = gzip.decompress((OUT/'solver.stderr.gz').read_bytes())
    assert hashlib.sha256(stdout).hexdigest() == result['stdout_sha256']
    assert hashlib.sha256(stderr).hexdigest() == result['stderr_sha256']
    assert base.sha(OUT/'solver.stdout.gz') == result['stdout_gzip_sha256']
    assert base.sha(OUT/'solver.stderr.gz') == result['stderr_gzip_sha256']
    if result['status'] == 'BOUNDED_UNKNOWN':
        assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
    phases = result['phase_seconds']
    residual = phases['total']-sum(phases[k] for k in ('construction','write_and_hash','solver'))
    assert residual >= -0.01
    audit = {'status': 'AUDITED_N41_ORDERED_TERMINAL_RECEIPT',
             'query_status': result['status'],
             'protocol_sha256': base.sha(OUT/'protocol.json'),
             'formula_sha256': result['formula']['sha256'],
             'formula_bytes': result['formula']['bytes'],
             'source_lock_verified': True, 'formula_rebuilt_exactly': True,
             'compressed_logs_verified': True, 'ordered_pair_forbids': 1984,
             'factor_base_B': p['factor_base_B'],
             'phase_seconds': {**phases, 'post_solver_log_capture': residual}}
    base.save(OUT/'terminal_audit.json', audit)
    print(json.dumps({'status': audit['status'], 'query_status': result['status'],
                      'formula_bytes': audit['formula_bytes'],
                      'phase_seconds': audit['phase_seconds']}))


if __name__ == '__main__':
    main()
