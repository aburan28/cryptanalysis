"""Check exact exploratory multiplication pilot receipts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
paths = {
    'field': ROOT / 'experiments/sage-ic-campaign/pb-squaring-20260924/source/field-local.py',
    'curves': ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/baseline/curves-local.py',
}
data = json.loads((HERE / 'run-001.json').read_text())
assert data['source_sha256'] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in paths.items()
}
assert len(data['rows']) == 8
for row in data['rows']:
    assert row['exact_output_agreement'] is True
    assert row['degree'] in (11, 15, 53, 131)
    assert row['operation'] in ('field_mul', 'point_scalar')
    assert set(row['samples_ns']) == {'baseline', 'sparse', 'nibble'}
    for name, samples in row['samples_ns'].items():
        assert len(samples) == 12 and all(value > 0 for value in samples)
        assert row['median_ns'][name] == statistics.median(samples)
    for name in ('sparse', 'nibble'):
        assert row['speedup'][name] == row['median_ns']['baseline'] / row['median_ns'][name]
assert all(row['speedup']['nibble'] < 1 for row in data['rows']
           if row['degree'] in (11, 15) and row['operation'] == 'field_mul')
print('Held polynomial-basis multiplication pilot verified')
