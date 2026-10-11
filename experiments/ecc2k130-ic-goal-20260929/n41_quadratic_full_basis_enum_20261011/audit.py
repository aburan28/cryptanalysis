"""Audit the full-basis source, point-set equality, and nine queries."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    paths = {'source': HERE/'full_basis_compare.cpp',
             'binary': HERE/'full_basis_compare_native',
             'runner': HERE/'run.py',
             'helper': ROOT.parent/'koblitz-s5-invariant-20260924/three_pair_s7_native.cpp',
             'targets': HERE/'targets.txt',
             'prior_receipt': ROOT/'n41_direct_relaxed_pair_join_20261011/receipt.json',
             'prior_quadratic_receipt': ROOT/'n41_quadratic_pair_enum_20261011/receipt.json',
             'prior_quadratic_source': ROOT/'n41_quadratic_pair_enum_20261011/quadratic_compare.cpp',
             'prior_basis_receipt': ROOT/'n41_quadratic_basis_enum_20261011/receipt.json'}
    assert protocol['sha256'] == {name: sha(path) for name, path in paths.items()}
    run = json.loads((HERE/'execution.json').read_text())
    result = json.loads((HERE/'receipt.json').read_text())
    prior = json.loads(paths['prior_quadratic_receipt'].read_text())
    first_basis = json.loads(paths['prior_basis_receipt'].read_text())
    assert run['status'] == 'COMPLETE' and run['returncode'] == 0
    assert run['source_sha256']['protocol.json'] == sha(HERE/'protocol.json')
    assert run['receipt_sha256'] == sha(HERE/'receipt.json')
    assert run['stdout_sha256'] == sha(HERE/'run.stdout')
    assert run['stderr_sha256'] == sha(HERE/'run.stderr')
    assert run['peak_combined_rss_bytes'] <= protocol['limits']['rss_bytes']
    assert run['wall_seconds'] <= protocol['limits']['wall_seconds']
    assert result['status'] == 'PASS_EXACT_FULL_BASIS_QUADRATIC_ENUMERATION'
    assert result['full_set_equal'] is True
    assert result['old_points'] == result['new_points'] == prior['old_points'] == prior['new_points'] == 128656
    assert result['quadratic_root_candidates'] == prior['quadratic_root_candidates'] == 128385
    assert result['quadratic_residual_passes'] == prior['quadratic_residual_passes'] == 128385
    assert result['halftrace_basis_calls'] == 6 * 2047
    assert result['direct_halftrace_calls_avoided'] > result['halftrace_basis_calls']
    assert result['halftrace_basis_calls'] == first_basis['halftrace_basis_calls']
    assert result['direct_halftrace_calls_avoided'] == first_basis['direct_halftrace_calls_avoided']
    assert result['residual_basis_halftrace_calls'] == 7 * 2047
    assert result['direct_residual_halftrace_calls_avoided'] == 2 * result['direct_halftrace_calls_avoided']
    assert len(result['queries']) == len(prior['queries']) == 9
    for current, previous in zip(result['queries'], prior['queries']):
        for key in ('label', 'status', 'probes'):
            assert current[key] == previous[key]
    audit = {'status': 'PASS_EXACT_FULL_BASIS_ENUMERATION_AUDIT',
             'points': result['new_points'], 'queries': len(result['queries']),
             'basis_halftrace_calls': result['halftrace_basis_calls'],
             'reference_halftrace_calls_avoided': result['direct_halftrace_calls_avoided'],
             'residual_basis_halftrace_calls': result['residual_basis_halftrace_calls'],
             'reference_residual_halftrace_calls_avoided': result['direct_residual_halftrace_calls_avoided'],
             'source_sha256': {'audit.py': sha(Path(__file__)),
                               'protocol.json': sha(HERE/'protocol.json'),
                               'receipt.json': sha(HERE/'receipt.json'),
                               'execution.json': sha(HERE/'execution.json')}}
    (HERE/'audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True)+'\n')
    print(json.dumps(audit, sort_keys=True))


if __name__ == '__main__':
    main()
