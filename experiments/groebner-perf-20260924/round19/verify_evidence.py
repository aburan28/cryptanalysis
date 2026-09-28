"""Verify retained device correctness, source identities and rejected timing."""
import hashlib
import json
from pathlib import Path

from build import generated_sources

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, name
    correctness = json.loads((HERE/'results/correctness.json').read_text())
    assert correctness['status'] == 'PASS'
    for name, expected in correctness['source_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, name
    receipt = json.loads((HERE/'results/build-receipt.json').read_text())
    for name, expected in receipt['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    assert receipt['generated_sha256'] == {name: hashlib.sha256(text.encode()).hexdigest()
        for name, text in generated_sources().items()}
    for filename in ('integration-initial.log','final-validation.log','final-contract-validation.log'):
        log = (HERE/'results'/filename).read_text()
        assert '\nOK\n' in log and '\nFAILED' not in log, filename
        assert 'Complete CPU/GPU query comparisons: 20' in log
        assert 'GPU/direct-reference certificate comparisons: 96 direct equation evaluations: 8352' in log
    for filename in ('tile-final-optimized256.log','tile-final-ubsan64.log'):
        log = (HERE/'results'/filename).read_text()
        assert 'PASS cases=24 truth_words=737928 root_words=82192 device=Apple M4 Pro static_shared_bytes=32768' in log, filename
    tile = json.loads((HERE/'results/tile-build-receipt.json').read_text())
    for name, expected in tile['source_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == expected, name
    rejected = json.loads((HERE/'results/local-paired.json.gz.admission.json').read_text())
    assert not rejected['admitted'] and rejected['timed_attempts'] == 0
    assert rejected['load'][0] > rejected['logical_cpus'] * rejected['max_load_per_cpu']
    assert not (HERE/'results/local-paired.json.gz').exists()
    print(json.dumps({'status': 'VERIFIED', 'complete_query_comparisons': 20,
        'certificate_comparisons': 96, 'direct_equation_checks': 8352,
        'local_timed_attempts': 0, 'qualified_gpu_speedup': None,
        'scope': 'Exact component correctness; no admitted GPU speedup or full IC claim'}))


if __name__ == '__main__': main()
