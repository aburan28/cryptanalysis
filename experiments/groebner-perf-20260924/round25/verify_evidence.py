"""Verify retained correctness evidence and its exact source and journal binding."""
import gzip
import hashlib
import json
import subprocess

from sparse_ic import HERE, ROOT
from audit import audit, require


def main():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name, digest in inventory.items():
        path = (ROOT/name).resolve()
        require(path.is_relative_to(ROOT), 'artifact path')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'artifact digest '+name)
    subprocess.run(['git', 'ls-files', '--error-unmatch', *inventory], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    path = HERE/'results/correctness-final.json.gz'
    report = json.loads(gzip.decompress(path.read_bytes()))
    require(report['correctness_only'] and not report['timing_admission_eligible'],
            'correctness is not a timing claim')
    for source in HERE.glob('*.py'):
        require(report['source_sha256'][str(source.relative_to(ROOT))] ==
                hashlib.sha256(source.read_bytes()).hexdigest(), 'final source '+source.name)
    summary = audit(path)
    require(summary == json.loads((HERE/'results/audit-final.json').read_text()),
            'retained audit mismatch')
    require(all(w['all_attempts_verified'] for w in summary['workloads']), 'correctness results')
    print(json.dumps({'artifacts': len(inventory),
        'independent_basis_proofs': summary['independent_unique_basis_proofs'],
        'independent_curve_witnesses': summary['independent_unique_curve_witnesses'],
        'journal_recovered': True, 'scope': 'Retained correctness evidence, not performance'}, indent=2))


if __name__ == '__main__':
    main()
