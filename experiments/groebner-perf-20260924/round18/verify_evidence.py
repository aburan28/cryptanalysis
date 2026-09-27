"""Check retained correctness/admission and exact native source/build bindings."""
import hashlib
import json
from pathlib import Path

from audit import audit

HERE = Path(__file__).resolve().parent


def main():
    inventory = json.loads((HERE / 'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
    for filename in ('combined-validation.log', 'final-validation.log'):
        log = (HERE / 'results' / filename).read_text()
        assert '\nOK\n' in log and '\nFAILED' not in log, filename
        assert 'Random packed certificates: 240 direct evaluations: 7328' in log
    for filename in ('initial-validation.log', 'core-validation.log'):
        assert '\nFAILED' in (HERE / 'results' / filename).read_text(), filename
    receipt = json.loads((HERE / 'results/build-receipt.json').read_text())
    for name, expected in receipt['source_sha256'].items():
        assert hashlib.sha256((HERE.parents[2] / name).read_bytes()).hexdigest() == expected, name
    admission = json.loads((HERE / 'results/paired-attempt1.json.gz.admission.json').read_text())
    assert not admission['admitted'] and admission['timed_attempts'] == 0
    assert admission['load'][0] > admission['logical_cpus'] * admission['max_load_per_cpu']
    assert not (HERE / 'results/paired-attempt1.json.gz').exists()
    measured = audit(HERE / 'results/ci-ubuntu-run36297433854/paired.json.gz')
    assert measured['timing_admission_eligible']
    assert measured['statuses'] == {arm + ':solved': 320 for arm in (
        'baseline', 'packed-replay', 'zeta-certificate', 'combined')}
    runner = json.loads((HERE / 'results/ci-ubuntu-run36297433854/runner.json').read_text())
    run = json.loads((HERE / 'results/ci-run36297433854.json').read_text())
    assert run['id'] == int(runner['GITHUB_RUN_ID']) == 36297433854
    assert run['status'] == 'completed' and run['conclusion'] == 'success'
    rejected = json.loads((HERE / 'results/ci-macos-run36297433854/paired.json.gz.admission.json').read_text())
    assert not rejected['admitted'] and rejected['timed_attempts'] == 0
    assert not (HERE / 'results/ci-macos-run36297433854/paired.json.gz').exists()
    print(json.dumps({'status': 'VERIFIED', 'local_timed_attempts': 0,
                      'ci_verified_attempts': 1280, 'ci_timing_admission_eligible': True,
                      'scope': 'Four-arm CPU component measurement; no full IC recovery or GPU win'}))


if __name__ == '__main__': main()
