"""Portable source, binary-identity, exact-output, and host-phase checks."""

import hashlib
import json
from pathlib import Path
import statistics


here = Path(__file__).resolve().parent
root = here.parents[2]
intent = json.loads((here / 'intent.json').read_text())
run_intent = json.loads((here / 'intent-run.json').read_text())
recheck = json.loads((here / 'intent-recheck.json').read_text())
for name, expected in intent['baseline_source_sha256'].items():
    assert hashlib.sha256((here / 'source' / name).read_bytes()).hexdigest() == expected
for name, source in (
    ('instrumented_source_sha256', here / 'source/instrumented_metal.mm'),
    ('profile_script_sha256', here / 'profile_bridge.py'),
    ('build_script_sha256', here / 'build.sh'),
):
    assert hashlib.sha256(source.read_bytes()).hexdigest() == run_intent[name]
benchmark = root / 'experiments/sage-binary-hardware/benchmark.py'
assert hashlib.sha256(benchmark.read_bytes()).hexdigest() == recheck['benchmark_sha256']
assert recheck['installed_native_sha256'] == intent['installed_native_sha256']

for run in ('run-001', 'run-002'):
    for i, case in enumerate(intent['cases']):
        parent = json.loads((here / run / ('cell-%02d-parent.json' % i)).read_text())
        raw = json.loads((here / run / ('cell-%02d.json' % i)).read_text())
        assert parent['status'] == 0 and parent['case'] == case
        assert (raw['degree'], raw['points'], raw['power'], raw['seed']) == \
            (case['degree'], case['points'], case['power'], case['seed'])
        assert raw['exact_output_agreement']
        assert raw['installed_native_sha256'] == intent['installed_native_sha256']
        assert raw['instrumented_native_sha256'] == run_intent['instrumented_binary_sha256']
        assert raw['peak_rss'] <= intent['resource_budget']['working_set_bytes']
        assert all(len(raw['samples'][name]) == 12 for name in ('installed', 'instrumented'))
        for name, samples in raw['samples'].items():
            assert [sample['round'] for sample in samples] == list(range(12))
            for sample in samples:
                assert sample['validated_ns'] == sum(sample[k] for k in (
                    'operation_ns', 'verification_ns', 'cleanup_ns'))
                assert sample['device_seconds'] > 0
                if name == 'instrumented':
                    bridge = sample['bridge_seconds']
                    assert set(bridge) == set(run_intent['timing_categories'])
                    assert all(value >= 0 for value in bridge.values())
                    assert sum(bridge[k] for k in run_intent['timing_categories'][:-1]) <= \
                        bridge['bridge_total'] + 1e-8
                    assert bridge['bridge_total'] * 1e9 <= sample['operation_ns']
                    assert sample['device_seconds'] <= bridge['submit_wait']
        installed = statistics.median(x['validated_ns'] for x in raw['samples']['installed'])
        instrumented = statistics.median(x['validated_ns'] for x in raw['samples']['instrumented'])
        assert .5 < installed / instrumented < 1.5
        phases = raw['samples']['instrumented']
        assert statistics.median(x['bridge_seconds']['submit_wait'] for x in phases) > \
            statistics.median(x['bridge_seconds']['input_copy'] +
                              x['bridge_seconds']['output_copy'] for x in phases)

initial = root / 'experiments/sage-ic-campaign/metal-current-profile-20260924/run-001'
for i, (case, original_number) in enumerate(zip(recheck['cases'], (0, 1, 4, 5))):
    parent = json.loads((here / 'run-recheck-001' /
                         ('cell-%02d-parent.json' % i)).read_text())
    raw = json.loads((here / 'run-recheck-001' /
                      ('cell-%02d.json' % i)).read_text())
    original = json.loads((initial / ('cell-%02d.json' % original_number)).read_text())
    assert parent['status'] == 0 and parent['case'] == case
    assert (raw['degree'], raw['points'], raw['power_requested'], raw['seed']) == \
        (case['degree'], case['points'], case['power'], case['seed'])
    assert raw['exact_output_agreement'] and original['exact_output_agreement']
    assert raw['source_sha256'] == recheck['installed_module_sha256']
    assert raw['loaded_artifacts']['files']['native']['sha256'] == \
        recheck['installed_native_sha256']
    assert raw['input_sha256'] == original['input_sha256']
    assert raw['output_sha256'] == original['output_sha256']
    assert all(len(raw['full_api'][name]) == 12 for name in ('sage', 'cpu', 'metal'))
    median = {name: statistics.median(sample['validated_seconds'] for sample in samples)
              for name, samples in raw['full_api'].items()}
    assert median['cpu'] < median['metal']
print('Metal bridge host phases and identical-seed rechecks verified')
