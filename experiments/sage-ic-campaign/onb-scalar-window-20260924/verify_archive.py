"""Portable ONB source, exact-call, timing, and resource receipt checks."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
paths = {
    'baseline-local': HERE / 'baseline/curves-local.py',
    'baseline-runner': HERE / 'baseline/curves-runner.py',
    'candidate-local': HERE / 'source/curves-local.py',
    'candidate-runner': HERE / 'source/curves-runner.py',
    'field-local': ROOT / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-local.py',
    'field-runner': ROOT / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-runner.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
primary = json.loads((HERE / 'intent-primary.json').read_text())
confirm = json.loads((HERE / 'intent-confirm.json').read_text())
assert primary['source_sha256'] == confirm['source_sha256']
for name, expected in primary['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name
# Source hashes above bind this experiment's exact candidate. The live curve
# files may be superseded by a later arithmetic PR with its own source gate.
assert 'signed-window scalar checks passed' in (HERE / 'test-window.log').read_text()
assert 'OK' in (HERE / 'test-runner.log').read_text()
full_log = (HERE / 'test-runner-full.log').read_text()
assert 'ModuleNotFoundError: No module named \'pysat\'' in full_log
assert 'FileNotFoundError' in full_log and 'ecc2k130-fixed.json' in full_log

seen = set()
for intent, run in ((primary, 'run-primary-001'),
                    (confirm, 'run-confirm-001')):
    for i, case in enumerate(intent['cases']):
        parent = json.loads((HERE / run / ('cell-%02d-parent.json' % i)).read_text())
        raw = json.loads((HERE / run / ('cell-%02d.json' % i)).read_text())
        assert parent['status'] == 0 and parent['case'] == case
        assert raw['exact_output_agreement']
        assert all(raw['case'][key] == case[key]
                   for key in ('variant', 'degree', 'bits', 'seed', 'rounds'))
        assert int(raw['scalar_hex'], 16).bit_length() == case['bits']
        variant = case['variant']
        assert raw['source_sha256'] == {
            'baseline': intent['source_sha256']['baseline-' + variant],
            'candidate': intent['source_sha256']['candidate-' + variant],
            'field': intent['source_sha256']['field-' + variant],
        }
        assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['peak_rss_bytes']
        assert set(raw['samples']) == {'baseline', 'candidate'}
        for arm, samples in raw['samples'].items():
            assert [sample['round'] for sample in samples] == list(range(case['rounds']))
            for sample in samples:
                assert sample['validated_ns'] == sum(sample[key] for key in (
                    'operation_ns', 'verification_ns', 'cleanup_ns'))
                assert sample['operation_ns'] > 0
            assert raw['median_operation_ns'][arm] == statistics.median(
                sample['operation_ns'] for sample in samples)
        speedup = (raw['median_operation_ns']['baseline'] /
                   raw['median_operation_ns']['candidate'])
        if case['bits'] == 16:
            assert speedup >= .98
        else:
            assert speedup >= 1.05
        seen.add((run, variant, case['degree'], case['bits'], case['seed']))
assert len(seen) == 16
assert set(case['seed'] for case in primary['cases']).isdisjoint(
    case['seed'] for case in confirm['cases'])
print('Local and runner ONB signed-window source, tests, and receipts verified')
