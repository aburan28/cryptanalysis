"""Verify the committed append-only evidence inventory and final correctness trace."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from ic_query import HERE, ROOT
from audit import audit_report, require


def main():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name, expected in inventory['artifacts'].items():
        path = (ROOT/name).resolve()
        require(path.is_relative_to(ROOT), 'artifact outside repository')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'artifact digest '+name)
    subprocess.run(['git','ls-files','--error-unmatch',*inventory['artifacts']],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    report = json.loads(gzip.decompress((HERE/'results/correctness-final.json.gz').read_bytes()))
    require(report['correctness_only'] and not report['timing_admission_eligible'], 'correctness trace promoted to timing evidence')
    for path in HERE.glob('*.py'):
        require(report['source_sha256'][str(path.relative_to(ROOT))] == hashlib.sha256(path.read_bytes()).hexdigest(), 'final source binding '+path.name)
    audit = audit_report(report)
    require(all(w['all_attempts_verified'] for w in audit['workloads']), 'retained correctness failure')
    require(audit == json.loads((HERE/'results/correctness-final-audit.json').read_text()), 'retained audit differs')
    print(json.dumps({'verified_artifacts':len(inventory['artifacts']),
                      'independent_basis_proofs':audit['independent_unique_basis_proofs'],
                      'independent_curve_witnesses':audit['independent_unique_curve_witnesses'],
                      'scope':'Correctness only; local measurement was not admitted.'}, indent=2))


if __name__ == '__main__': main()
