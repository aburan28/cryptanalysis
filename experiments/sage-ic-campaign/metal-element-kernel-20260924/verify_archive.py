"""Portable source, binary identity, and exact kernel-pilot receipt checks."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
v1 = json.loads((HERE / 'intent-pilot.json').read_text())
v2 = json.loads((HERE / 'intent-pilot-v2.json').read_text())
confirm = json.loads((HERE / 'intent-confirm-v2.json').read_text())
assert v1 == json.loads((HERE / 'candidate-v1/intent-pilot.json').read_text())


def source_hashes(intent, version):
    for name, expected in intent['source_sha256'].items():
        if name == 'libelement.dylib' or name == 'installed-native.dylib':
            continue
        path = HERE / name
        if version == 1 and name in ('source/binary_hardware.py',
                                     'source/binary_hardware_metal.mm'):
            path = HERE / 'candidate-v1' / Path(name).name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    assert intent['source_sha256']['libelement.dylib'] == \
        v1['source_sha256']['libelement.dylib']
    assert intent['source_sha256']['installed-native.dylib'] == \
        v1['source_sha256']['installed-native.dylib']


def check_run(intent, run):
    for i, case in enumerate(intent['cases']):
        raw = json.loads((HERE / run / ('cell-%02d.json' % i)).read_text())
        if run == 'confirm-001':
            parent = json.loads((HERE / run /
                                 ('cell-%02d-parent.json' % i)).read_text())
            assert parent['case'] == case and parent['status'] == 0
        assert raw['exact_output_agreement']
        assert all(raw['case'][key] == case[key]
                   for key in ('points', 'groups', 'seed', 'rounds'))
        assert raw['source_sha256'] == {
            'baseline': intent['source_sha256']['baseline/binary_hardware.py'],
            'candidate': intent['source_sha256']['source/binary_hardware.py'],
            'bridge': intent['source_sha256']['source/binary_hardware_metal.mm'],
            'native': intent['source_sha256']['installed-native.dylib'],
            'element': intent['source_sha256']['libelement.dylib'],
        }
        assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['working_set_bytes']
        assert set(raw['samples']) == {'metal_word', 'metal_element',
                                       'cpu_batched', 'sage_flat'}
        for arm, samples in raw['samples'].items():
            assert [sample['round'] for sample in samples] == list(range(case['rounds']))
            for sample in samples:
                assert sample['validated_ns'] == sum(sample[key] for key in (
                    'operation_ns', 'verification_ns', 'cleanup_ns'))
                assert sample['operation_ns'] > 0
                if arm.startswith('metal'):
                    assert sample['device_seconds'] is not None
                    assert sample['device_seconds'] > 0
            assert raw['median_operation_ns'][arm] == statistics.median(
                sample['operation_ns'] for sample in samples)


source_hashes(v1, 1)
source_hashes(v2, 2)
source_hashes(confirm, 2)
check_run(v1, 'pilot-001')
check_run(v2, 'pilot-002')
check_run(confirm, 'confirm-001')
assert sum(json.loads((HERE / 'confirm-001' /
                       ('cell-%02d.json' % i)).read_text())['median_operation_ns']['metal_element'] >
           json.loads((HERE / 'confirm-001' /
                       ('cell-%02d.json' % i)).read_text())['median_operation_ns']['metal_word']
           for i in range(len(confirm['cases']))) >= 3
print('Held exact Metal element-kernel pilots and confirmation verified')
