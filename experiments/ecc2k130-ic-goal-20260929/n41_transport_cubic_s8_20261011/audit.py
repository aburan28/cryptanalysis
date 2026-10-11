"""Rebuild the public formula and audit the frozen N41 terminal receipt."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    p = run.protocol()
    f = run.fixture()
    control = json.loads((HERE/'control_result.json').read_text())
    result = json.loads((HERE/'query_result.json').read_text())
    assert control['status'] == 'PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT'
    assert control['protocol_sha256'] == result['protocol_sha256'] == run.sha(HERE/'protocol.json')
    assert result['target_original'] == p['public_target_original']
    assert result['target_transported'] == p['public_target_transported']
    assert result['formula']['target_selector_cross_term'] == f['target_selector_cross_term']
    c, _, _ = run.build(p['raw_target_preimage_z'])
    with tempfile.NamedTemporaryFile(prefix='n41_cubic_audit_', suffix='.xcnf',
                                     dir='/private/tmp') as stream:
        formula = Path(stream.name)
        c.write(formula)
        assert formula.stat().st_size == result['formula']['bytes']
        assert run.sha(formula) == result['formula']['sha256']
    stdout = gzip.decompress((HERE/'solver.stdout.gz').read_bytes())
    stderr = gzip.decompress((HERE/'solver.stderr.gz').read_bytes())
    assert hashlib.sha256(stdout).hexdigest() == result['stdout_sha256']
    assert hashlib.sha256(stderr).hexdigest() == result['stderr_sha256']
    assert run.sha(HERE/'solver.stdout.gz') == result['stdout_gzip_sha256']
    assert run.sha(HERE/'solver.stderr.gz') == result['stderr_gzip_sha256']
    assert result['solver_started'] and result['peak_combined_rss_bytes'] < run.RSS_CAP
    if result['status'] == 'BOUNDED_UNKNOWN':
        assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
    phases = result['phase_seconds']
    residual = phases['total']-sum(phases[k] for k in ('construction','write_and_hash','solver'))
    assert residual >= -0.01
    screen = json.loads((HERE.parent/'n131_w18_four_pairs/screen.json').read_text())
    exact_B = screen['n41']['fixed_union_usable_points_B']
    assert exact_B == 256
    assert p['factor_base_B'] == 128
    amendment = {'status': 'AUDITED_N41_TERMINAL_RECEIPT',
                 'query_status': result['status'],
                 'protocol_sha256': run.sha(HERE/'protocol.json'),
                 'formula_sha256': result['formula']['sha256'],
                 'formula_bytes': result['formula']['bytes'],
                 'source_lock_verified': True, 'formula_rebuilt_exactly': True,
                 'compressed_logs_verified': True,
                 'source_census_sha256': run.sha(HERE.parent/'n131_w18_four_pairs/screen.json'),
                 'base_count_correction': {
                     'protocol_factor_base_B': 128,
                     'exact_distinct_nonidentity_subgroup_points_B': exact_B,
                     'reason': 'Four disjoint rotations, 32 rational masks and two curve signs per rotation; the source census counts 64 projected points per rotation.',
                     'formula_affected': False},
                 'phase_seconds': {**phases, 'post_solver_log_capture': residual},
                 'phase_sum_matches_total': abs(sum(phases[k] for k in ('construction','write_and_hash','solver'))+residual-phases['total']) < 1e-9}
    run.save(HERE/'terminal_audit.json', amendment)
    print(json.dumps({'status': amendment['status'], 'query_status': result['status'],
                      'corrected_B': exact_B, 'phase_seconds': amendment['phase_seconds']}))


if __name__ == '__main__':
    main()
