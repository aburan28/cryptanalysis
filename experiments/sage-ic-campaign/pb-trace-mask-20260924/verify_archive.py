"""Check frozen polynomial-basis trace-mask sources and timing receipts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PATHS = {
    'baseline-local': HERE / 'baseline/curves-local.py',
    'baseline-runner': HERE / 'baseline/curves-runner.py',
    'candidate-local': HERE / 'source/curves-local.py',
    'candidate-runner': HERE / 'source/curves-runner.py',
    'field-local': ROOT / 'ecc2k130/codegen/field.py',
    'field-runner': ROOT / 'ecc2k130/runner/codegen/field.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
primary = json.loads((HERE / 'intent-primary.json').read_text())
confirm = json.loads((HERE / 'intent-confirm.json').read_text())
assert primary['source_sha256'] == confirm['source_sha256']
for name, expected in primary['source_sha256'].items():
    assert hashlib.sha256(PATHS[name].read_bytes()).hexdigest() == expected, name
for variant in ('local', 'runner'):
    live = ROOT / ('ecc2k130/' + ('runner/' if variant == 'runner' else '') +
                   'codegen/curves.py')
    assert live.read_bytes() == PATHS['candidate-' + variant].read_bytes()
assert 'polynomial-basis trace-mask checks passed' in (
    HERE / 'test-trace.log').read_text()

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
        variant = case['variant']
        assert raw['source_sha256'] == {
            'baseline': intent['source_sha256']['baseline-' + variant],
            'candidate': intent['source_sha256']['candidate-' + variant],
            'field': intent['source_sha256']['field-' + variant],
        }
        assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['peak_rss_bytes']
        assert set(raw['results']) == {'point_from_x', 'field_trace'}
        masks = set()
        for name, result in raw['results'].items():
            masks.add(result['trace_mask_hex'])
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
            assert speedup >= {'point_from_x': 1.5,
                               'field_trace': 50}[name], (run, i, name, speedup)
            if name == 'point_from_x':
                first_speedup = (result['first_call_ns']['baseline'] /
                                 result['first_call_ns']['candidate'])
                assert first_speedup >= 1.2, (run, i, first_speedup)
        assert len(masks) == 1
        assert 0 < int(masks.pop(), 16) < (1 << case['degree'])
        seen.add((run, variant, case['degree'], case['seed']))
assert len(seen) == 16
assert set(case['seed'] for case in primary['cases']).isdisjoint(
    case['seed'] for case in confirm['cases'])
print('Local and runner polynomial-basis trace-mask archive verified')
