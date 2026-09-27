"""Verify the live experiment, retained device checks and complete-query screen."""
import hashlib
import json
from pathlib import Path

from audit import main

HERE=Path(__file__).resolve().parent


def verify():
    inventory=json.loads((HERE/'results/inventory.json').read_text())
    for name,expected in inventory.items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    admission_path=HERE/'results/spin-admission-attempt1.json.gz.admission.json'
    admission=json.loads(admission_path.read_text())
    assert not admission['admitted'] and admission['timed_attempts']==0
    assert admission['load'][0]>admission['logical_cpus']*admission['max_load_per_cpu']
    assert not (HERE/'results/spin-admission-attempt1.json.gz').exists()
    for name in ('spin-validation.log','final-validation.log','admission-validation.log'):
        log=(HERE/'results'/name).read_text()
        assert '\nOK\n' in log and '\nFAILED' not in log,name
    receipt=json.loads((HERE/'results/current-build-receipt.json').read_text())
    for name in ('gpu_certificate.mm','direct_truth.metal','gpu_query.py'):
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==receipt['source_sha256'][name],name
    main()


if __name__=='__main__': verify()
