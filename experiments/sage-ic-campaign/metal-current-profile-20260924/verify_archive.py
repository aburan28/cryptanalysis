"""Portable source, exact-output, accounting, and timing receipt checks."""

import hashlib
import json
import math
from pathlib import Path
import statistics
import sys


here = Path(__file__).resolve().parent
root = here.parents[2]
intent = json.loads((here / 'intent.json').read_text())
stages_intent = json.loads((here / 'intent-stages.json').read_text())
assert hashlib.sha256((here / 'intent.json').read_bytes()).hexdigest() == \
    stages_intent['parent_intent_sha256']
assert hashlib.sha256((here / 'profile_stages.py').read_bytes()).hexdigest() == \
    stages_intent['profile_script_sha256']
for name in ('benchmark.py', 'load_hardware.py'):
    source = root / 'experiments/sage-binary-hardware' / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == intent['source_sha256'][name]
sys.path.insert(0, str(root / 'experiments/sage-binary-hardware'))
from benchmark import summarize


summary = json.loads((here / 'run-001/summary.json').read_text())
assert summary['complete'] and len(summary['rows']) == len(intent['cases']) == 8
for i, case in enumerate(intent['cases']):
    parent = json.loads((here / ('run-001/cell-%02d-parent.json' % i)).read_text())
    raw = json.loads((here / ('run-001/cell-%02d.json' % i)).read_text())
    assert parent['status'] == 0 and parent['case'] == case
    assert (raw['degree'], raw['points'], raw['power_requested'], raw['seed']) == \
        (case['degree'], case['points'], case['power'], case['seed'])
    assert raw['exact_output_agreement'] and raw['completed_points_per_call'] == case['points']
    assert raw['loaded_artifacts']['installed']
    assert raw['source_sha256'] == intent['source_sha256']['binary_hardware.py']
    files = raw['loaded_artifacts']['files']
    assert files['module']['sha256'] == intent['source_sha256']['binary_hardware.py']
    assert files['native']['sha256'] == intent['source_sha256']['_binary_hardware_native.dylib']
    assert files['codec']['sha256'] == \
        intent['source_sha256']['binary_hardware_codec.cpython-314-darwin.so']
    assert raw['metadata']['cpu']['table_sha256'] == raw['metadata']['metal']['table_sha256']
    assert all(len(raw['full_api'][name]) == 12 for name in ('sage', 'cpu', 'metal'))
    assert all(len(raw['packed'][name]) == 12 for name in ('cpu', 'metal'))
    assert raw['peak_rss'] <= intent['resource_budget']['working_set_bytes']
    for samples in raw['full_api'].values():
        for sample in samples:
            assert math.isclose(sample['validated_seconds'],
                sample['operation_seconds'] + sample['verification_seconds'] +
                sample['cleanup_seconds'], abs_tol=2e-9)
    row = summarize(raw)
    for backend in ('cpu', 'metal'):
        assert math.isclose(row['full_medians_seconds'][backend],
                            summary['rows'][i]['full_medians_seconds'][backend])
    assert row['full_speedup']['cpu'] > row['full_speedup']['metal']
    if case['power'] == 65:
        assert row['full_speedup']['metal'] > 1
    else:
        assert row['full_speedup']['metal'] < 1

assert len(stages_intent['cases']) == 4
for i, case in enumerate(stages_intent['cases']):
    parent = json.loads((here / ('run-stages-001/cell-%02d-parent.json' % i)).read_text())
    raw = json.loads((here / ('run-stages-001/cell-%02d.json' % i)).read_text())
    assert parent['status'] == 0 and parent['case'] == case
    assert (raw['degree'], raw['points'], raw['power'], raw['seed']) == \
        (case['degree'], case['points'], case['power'], case['seed'])
    assert raw['exact_output_agreement']
    assert raw['source_sha256'] == intent['source_sha256']['binary_hardware.py']
    assert raw['loaded_artifacts']['files']['native']['sha256'] == \
        intent['source_sha256']['_binary_hardware_native.dylib']
    assert raw['peak_rss'] <= stages_intent['resource_budget']['working_set_bytes']
    for backend in ('cpu', 'metal'):
        samples = raw['samples'][backend]
        assert len(samples) == 12
        assert [sample['round'] for sample in samples] == list(range(12))
        for sample in samples:
            assert sample['complete_ns'] == sum(sample[name] for name in (
                'pack_ns', 'map_ns', 'unpack_ns', 'verify_ns', 'cleanup_ns'))
            assert sample['complete_ns'] > 0
            if backend == 'metal':
                assert 0 < sample['device_seconds'] * 1e9 < sample['map_ns']
    cpu_map = statistics.median(x['map_ns'] for x in raw['samples']['cpu'])
    metal_map = statistics.median(x['map_ns'] for x in raw['samples']['metal'])
    assert metal_map > cpu_map
print('current installed Sage CPU/Metal receipts and phase accounting verified')
