"""Check exact sources and paired complete factor-base receipts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
intent = json.loads((HERE / 'intent.json').read_text())
paths = {
    'field': ROOT / 'ecc2k130/runner/codegen/field.py',
    'baseline-curves-local': HERE / 'baseline/curves-local.py',
    'baseline-curves-runner': HERE / 'baseline/curves-runner.py',
    'candidate-curves-local': HERE / 'source/curves-local.py',
    'candidate-curves-runner': HERE / 'source/curves-runner.py',
    'baseline-indexcalc': HERE / 'baseline/indexcalc.py',
    'candidate-indexcalc': HERE / 'source/indexcalc.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
for name, expected in intent['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name
assert (ROOT / 'ecc2k130/codegen/curves.py').read_bytes() == paths[
    'candidate-curves-local'].read_bytes()
assert (ROOT / 'ecc2k130/runner/codegen/curves.py').read_bytes() == paths[
    'candidate-curves-runner'].read_bytes()
assert (ROOT / 'ecc2k130/runner/codegen/indexcalc.py').read_bytes() == paths[
    'candidate-indexcalc'].read_bytes()
assert 'explicit bulk half-trace checks passed' in (HERE / 'test-bulk.log').read_text()
assert len(intent['cases']) == 8
seen = set()
by_degree = {}
for case in intent['cases']:
    directory = HERE / ('run-' + case['run'] + '-001')
    stem = 'degree-%d' % case['degree']
    parent = json.loads((directory / (stem + '-parent.json')).read_text())
    raw = json.loads((directory / (stem + '.json')).read_text())
    assert parent['status'] == 0 and parent['case'] == case
    assert raw['exact_output_agreement'] is True
    assert all(raw['case'][key] == case[key]
               for key in ('degree', 'weight', 'order', 'rounds'))
    assert raw['source_sha256'] == {
        'field': intent['source_sha256']['field'],
        'baseline-curves': intent['source_sha256']['baseline-curves-runner'],
        'candidate-curves': intent['source_sha256']['candidate-curves-runner'],
        'baseline-indexcalc': intent['source_sha256']['baseline-indexcalc'],
        'candidate-indexcalc': intent['source_sha256']['candidate-indexcalc'],
    }
    assert raw['actual_base_points'] > 0 and raw['orbits'] > 0
    assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['peak_rss_bytes']
    assert set(raw['first_call_ns']) == {'baseline', 'candidate'}
    assert all(value > 0 for value in raw['first_call_ns'].values())
    for arm, samples in raw['samples'].items():
        assert arm in ('baseline', 'candidate')
        assert [sample['round'] for sample in samples] == list(range(case['rounds']))
        for sample in samples:
            assert sample['operation_ns'] > 0
            assert sample['validated_ns'] == sum(sample[key] for key in (
                'operation_ns', 'verification_ns', 'cleanup_ns'))
        assert raw['median_operation_ns'][arm] == statistics.median(
            sample['operation_ns'] for sample in samples)
    speedup = (raw['median_operation_ns']['baseline'] /
               raw['median_operation_ns']['candidate'])
    if case['degree'] == 53:
        assert speedup >= 1.5
    if case['degree'] == 131:
        assert speedup >= 2.5
    by_degree.setdefault(case['degree'], set()).add((raw['actual_base_points'],
                                                      raw['orbits']))
    seen.add((case['run'], case['degree']))
assert len(seen) == 8
assert all(len(values) == 1 for values in by_degree.values())
print('Explicit polynomial-basis IC factor-base archive verified')
