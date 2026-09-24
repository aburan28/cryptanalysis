"""Portable patch, provenance, exact-output receipt, and timing checks."""

import hashlib
import json
from difflib import unified_diff
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
intent = json.loads((HERE / 'intent.json').read_text())
cold_intent = json.loads((HERE / 'intent-cold.json').read_text())
for name, expected in intent['source_sha256'].items():
    if name == 'installed.py' or name == 'native.dylib':
        continue
    path = HERE / ({'baseline.py': 'baseline/binary_hardware.py',
                    'candidate.py': 'source/binary_hardware.py',
                    'benchmark.py': 'benchmark.py',
                    'run.py': 'run.py'}[name])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
for name, expected in cold_intent['source_sha256'].items():
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
assert intent['source_sha256']['baseline.py'] == intent['source_sha256']['installed.py']
assert 'batched Sage point checks passed' in (HERE / 'test-batches.log').read_text()

source_path = 'src/sage/schemes/elliptic_curves/binary_hardware.py'
patch = ''.join(unified_diff(
    (HERE / 'baseline/binary_hardware.py').read_text().splitlines(keepends=True),
    (HERE / 'source/binary_hardware.py').read_text().splitlines(keepends=True),
    fromfile='a/' + source_path, tofile='b/' + source_path))
assert patch == (HERE / 'metal-batched-point-maps.patch').read_text()

for i, case in enumerate(intent['cases']):
    parent = json.loads((HERE / 'run-001' / ('cell-%02d-parent.json' % i)).read_text())
    raw = json.loads((HERE / 'run-001' / ('cell-%02d.json' % i)).read_text())
    assert parent['case'] == case and parent['status'] == 0
    assert raw['exact_output_agreement']
    assert all(raw['case'][key] == case[key]
               for key in ('points', 'groups', 'seed', 'rounds'))
    assert raw['source_sha256'] == {
        'baseline': intent['source_sha256']['baseline.py'],
        'candidate': intent['source_sha256']['candidate.py'],
        'native': intent['source_sha256']['native.dylib'],
    }
    assert len(raw['input_sha256']) == 64
    assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['working_set_bytes']
    assert set(raw['samples']) == set(intent['arms'])
    for arm, samples in raw['samples'].items():
        assert [sample['round'] for sample in samples] == list(range(case['rounds']))
        for sample in samples:
            assert sample['validated_ns'] == sum(sample[key] for key in (
                'operation_ns', 'verification_ns', 'cleanup_ns'))
            assert sample['operation_ns'] > 0
            if arm.startswith('metal'):
                assert sample['last_gpu_seconds'] is not None
                assert sample['last_gpu_seconds'] > 0
        assert raw['median_operation_ns'][arm] == statistics.median(
            sample['operation_ns'] for sample in samples)
    median = raw['median_operation_ns']
    assert median['metal_batched'] < median['metal_separate']
    assert median['cpu_batched'] < median['metal_batched']

seen = set()
for i, case in enumerate(cold_intent['cases']):
    parent = json.loads((HERE / 'run-cold-001' / ('cell-%02d-parent.json' % i)).read_text())
    raw = json.loads((HERE / 'run-cold-001' / ('cell-%02d.json' % i)).read_text())
    assert parent['case'] == case and parent['status'] == 0
    assert raw['exact_output_agreement']
    assert all(raw[key] == case[key] for key in ('points', 'groups', 'seed', 'arm'))
    assert raw['setup_plus_operation_ns'] == raw['setup_ns'] + raw['operation_ns']
    assert raw['setup_ns'] > 0 and raw['operation_ns'] > 0
    assert raw['source_sha256'] == intent['source_sha256']['candidate.py']
    assert raw['native_sha256'] == intent['source_sha256']['native.dylib']
    assert 0 < raw['peak_rss_bytes'] <= cold_intent['resource_budget']['working_set_bytes']
    seen.add((case['points'], case['groups'], case['seed'], case['arm']))
for points, groups, seed in ((1024, 4, 2026092401), (4096, 16, 2026092402)):
    for arm in intent['arms']:
        assert (points, groups, seed, arm) in seen
print('Sage batched point-map patch and warm/cold receipts verified')
