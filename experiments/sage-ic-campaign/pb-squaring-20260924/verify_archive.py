"""Check frozen polynomial-basis square sources, correctness, and receipts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PATHS = {
    'baseline-local': HERE / 'baseline/field-local.py',
    'baseline-runner': HERE / 'baseline/field-runner.py',
    'candidate-local': HERE / 'source/field-local.py',
    'candidate-runner': HERE / 'source/field-runner.py',
    'curves-local': ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/baseline/curves-local.py',
    'curves-runner': ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/baseline/curves-runner.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
primary = json.loads((HERE / 'intent-primary.json').read_text())
confirm = json.loads((HERE / 'intent-confirm.json').read_text())
assert primary['source_sha256'] == confirm['source_sha256']
for name, expected in primary['source_sha256'].items():
    assert hashlib.sha256(PATHS[name].read_bytes()).hexdigest() == expected, name
for variant in ('local', 'runner'):
    assert (ROOT / ('ecc2k130/' + ('runner/' if variant == 'runner' else '') +
                    'codegen/field.py')).read_bytes() == PATHS['candidate-' + variant].read_bytes()
assert 'polynomial-basis square checks passed' in (HERE / 'test-square.log').read_text()

seen = set()
for intent, run in ((primary, 'run-primary-001'),
                    (confirm, 'run-confirm-001')):
    assert len(intent['cases']) == 8
    for i, case in enumerate(intent['cases']):
        parent = json.loads((HERE / run / ('cell-%02d-parent.json' % i)).read_text())
        raw = json.loads((HERE / run / ('cell-%02d.json' % i)).read_text())
        assert parent['status'] == 0 and parent['case'] == case
        assert raw['exact_output_agreement'] is True
        assert all(raw['case'][key] == case[key]
                   for key in ('variant', 'degree', 'seed', 'rounds'))
        assert int(raw['scalar_hex'], 16).bit_length() == 32
        variant = case['variant']
        assert raw['source_sha256'] == {
            'baseline': intent['source_sha256']['baseline-' + variant],
            'candidate': intent['source_sha256']['candidate-' + variant],
            'curves': intent['source_sha256']['curves-' + variant],
        }
        assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['peak_rss_bytes']
        assert raw['point_attempts'] > 0
        assert set(raw['results']) == {'field_square', 'point_scalar'}
        for name, result in raw['results'].items():
            assert set(result['first_call_ns']) == {'baseline', 'candidate'}
            assert all(value > 0 for value in result['first_call_ns'].values())
            assert set(result['samples']) == {'baseline', 'candidate'}
            for arm, samples in result['samples'].items():
                assert [sample['round'] for sample in samples] == list(range(case['rounds']))
                for sample in samples:
                    assert sample['operation_ns'] > 0
                    assert sample['validated_ns'] == sum(sample[key] for key in (
                        'operation_ns', 'verification_ns', 'cleanup_ns'))
                assert result['median_operation_ns'][arm] == statistics.median(
                    sample['operation_ns'] for sample in samples)
            speedup = (result['median_operation_ns']['baseline'] /
                       result['median_operation_ns']['candidate'])
            assert speedup >= {'field_square': 1.3,
                               'point_scalar': 1.15}[name], (run, i, name, speedup)
        seen.add((run, variant, case['degree'], case['seed']))
assert len(seen) == 16
assert set(case['seed'] for case in primary['cases']).isdisjoint(
    case['seed'] for case in confirm['cases'])
print('Local and runner polynomial-basis squaring archive verified')
