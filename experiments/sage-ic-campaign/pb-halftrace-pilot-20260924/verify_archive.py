"""Check frozen half-trace pilot sources, exactness, and cold/warm receipts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
intent = json.loads((HERE / 'intent.json').read_text())
paths = {
    'field': ROOT / 'experiments/sage-ic-campaign/pb-squaring-20260924/source/field-local.py',
    'curves': ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/source/curves-local.py',
    'pilot': HERE / 'pilot.py',
}
for name, expected in intent['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name
assert len(intent['cases']) == 8
seen = set()
for case in intent['cases']:
    run = HERE / ('run-' + case['run'] + '-001')
    stem = 'degree-%d' % case['degree']
    parent = json.loads((run / (stem + '-parent.json')).read_text())
    raw = json.loads((run / (stem + '.json')).read_text())
    assert parent['status'] == 0 and parent['case'] == case
    assert raw['case']['degree'] == case['degree']
    assert raw['case']['seed'] == case['seed']
    assert raw['case']['warm_rounds'] == 8
    assert raw['source_sha256'] == intent['source_sha256']
    assert raw['exact_output_agreement'] is True
    assert 0 < raw['peak_rss_bytes'] <= intent['resource_budget']['peak_rss_bytes']
    assert set(raw['first_call_ns']) == {'baseline', 'candidate'}
    assert set(raw['cold_batch_ns']) == {'64', '256', '1024'}
    for group in (raw['first_call_ns'], *raw['cold_batch_ns'].values()):
        assert set(group) == {'baseline', 'candidate'}
        assert all(value > 0 for value in group.values())
    for name, samples in raw['warm_256_samples_ns'].items():
        assert name in ('baseline', 'candidate')
        assert len(samples) == 8 and all(value > 0 for value in samples)
        assert raw['warm_256_median_ns'][name] == statistics.median(samples)
    if case['degree'] in (53, 131):
        cold64 = raw['cold_batch_ns']['64']
        assert cold64['baseline'] < cold64['candidate']
    if case['degree'] == 131:
        cold1024 = raw['cold_batch_ns']['1024']
        assert cold1024['baseline'] / cold1024['candidate'] > 2
        warm = raw['warm_256_median_ns']
        assert warm['baseline'] / warm['candidate'] > 5
    seen.add((case['run'], case['degree'], case['seed']))
assert len(seen) == 8
print('Held polynomial-basis half-trace pilot verified')
