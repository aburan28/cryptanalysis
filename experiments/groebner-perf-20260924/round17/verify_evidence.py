"""Check live source identities and retained local correctness/admission evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    inventory = json.loads((HERE / 'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
    for filename in ('final-validation.log', 'audit-validation.log'):
        log = (HERE / 'results' / filename).read_text()
        assert '\nOK\n' in log and '\nFAILED' not in log, filename
    receipt = json.loads((HERE / 'results/build-receipt.json').read_text())
    for name, expected in receipt['source_sha256'].items():
        assert hashlib.sha256((HERE.parents[2] / name).read_bytes()).hexdigest() == expected, name
    admission = json.loads((HERE / 'results/paired-attempt1.json.gz.admission.json').read_text())
    assert not admission['admitted'] and admission['timed_attempts'] == 0
    assert admission['load'][0] > admission['logical_cpus'] * admission['max_load_per_cpu']
    assert not (HERE / 'results/paired-attempt1.json.gz').exists()
    print(json.dumps({'status': 'VERIFIED', 'measured_speedup': None, 'timed_attempts': 0,
                      'scope': 'Correctness and evidence integrity; benchmark not admitted'}))


if __name__ == '__main__':
    main()
