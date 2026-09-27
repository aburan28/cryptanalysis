"""Check live source identities and retained local correctness/admission evidence."""
import hashlib
import json
from pathlib import Path

from audit import audit

HERE = Path(__file__).resolve().parent


def main():
    inventory = json.loads((HERE / 'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
    for filename in ('final-validation.log', 'audit-validation.log', 'combined-validation.log'):
        log = (HERE / 'results' / filename).read_text()
        assert '\nOK\n' in log and '\nFAILED' not in log, filename
    receipt = json.loads((HERE / 'results/build-receipt.json').read_text())
    for name, expected in receipt['source_sha256'].items():
        assert hashlib.sha256((HERE.parents[2] / name).read_bytes()).hexdigest() == expected, name
    admission = json.loads((HERE / 'results/paired-attempt1.json.gz.admission.json').read_text())
    assert not admission['admitted'] and admission['timed_attempts'] == 0
    assert admission['load'][0] > admission['logical_cpus'] * admission['max_load_per_cpu']
    assert not (HERE / 'results/paired-attempt1.json.gz').exists()
    measured = audit(HERE / 'results/ci-ubuntu-run36294322020/paired.json.gz')
    assert measured['timing_admission_eligible']
    assert measured['statuses'] == {'python:solved': 320, 'native-or-python:solved': 320}
    runner = json.loads((HERE / 'results/ci-ubuntu-run36294322020/runner.json').read_text())
    run = json.loads((HERE / 'results/ci-run36294322020.json').read_text())
    assert run['id'] == int(runner['GITHUB_RUN_ID']) == 36294322020
    assert run['status'] == 'completed' and run['conclusion'] == 'success'
    rejected = json.loads((HERE / 'results/ci-macos-run36294322020/paired.json.gz.admission.json').read_text())
    assert not rejected['admitted'] and rejected['timed_attempts'] == 0
    assert not (HERE / 'results/ci-macos-run36294322020/paired.json.gz').exists()
    print(json.dumps({'status': 'VERIFIED', 'local_timed_attempts': 0,
                      'ci_verified_attempts': 640, 'ci_timing_admission_eligible': True,
                      'scope': 'Paired CPU component measurements on one Linux runner; no IC recovery or GPU win'}))


if __name__ == '__main__':
    main()
