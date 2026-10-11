"""Audit the incremental Sage codec patch and paired timing receipts."""
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FOUNDATION = ROOT / 'experiments/sage-binary-hardware/source/binary_hardware_codec.pyx'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-v2.json').read_text())
assert digest(FOUNDATION) == intent['incumbent']['source_sha256']
assert digest(HERE / 'baseline/binary_hardware_codec.pyx') == intent['incumbent']['source_sha256']
assert digest(HERE / 'source/binary_hardware_codec.pyx') == intent['candidate']['source_sha256']
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx'
    path.parent.mkdir(parents=True)
    shutil.copy2(FOUNDATION, path)
    patch = HERE / 'codec-output.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    assert path.read_bytes() == (HERE / 'source/binary_hardware_codec.pyx').read_bytes()

install = json.loads((HERE / 'install-001/install.json').read_text())
assert install['files'][0]['sha256'] == intent['candidate']['source_sha256']
assert install['files'][1]['sha256'] == intent['candidate']['binary_sha256']
execution = json.loads((HERE / 'run-002/execution.json').read_text())
assert execution['intent_sha256'] == digest(HERE / 'intent-v2.json')
assert execution['benchmark_sha256'] == digest(HERE / 'benchmark_v2.py')
assert execution['incumbent_binary_sha256'] == intent['incumbent']['binary_sha256']
assert execution['candidate_binary_sha256'] == intent['candidate']['binary_sha256']
assert execution['candidate_source_sha256'] == intent['candidate']['source_sha256']

rows = []
for index in range(12):
    row = json.loads((HERE / f'run-002/cell-{index:02d}.json').read_text())
    parent = json.loads((HERE / f'run-002/cell-{index:02d}-parent.json').read_text())
    assert parent['status'] == 0
    assert row['all_outputs_exact'] and row['verified_outputs'] == row['case']['points'] * row['calls_per_sample'] * 24
    assert row['incumbent_binary_sha256'] == intent['incumbent']['binary_sha256']
    assert row['candidate_binary_sha256'] == intent['candidate']['binary_sha256']
    assert len(row['rounds']) == 12
    ratios = []
    for sample in row['rounds']:
        assert set(sample['order']) == {'incumbent', 'candidate'}
        assert all(value > 0 for value in sample['seconds'].values())
        ratios.append(math.log(sample['seconds']['incumbent'] / sample['seconds']['candidate']))
    assert math.isclose(math.exp(statistics.median(ratios)), row['speedup'], rel_tol=1e-12)
    rows.append(row)

summary = json.loads((HERE / 'run-002/summary.json').read_text())
assert summary['all_outputs_exact'] and summary['total_verified_outputs'] == sum(r['verified_outputs'] for r in rows)
assert len(summary['cells']) == len(rows)
for cell, row in zip(summary['cells'], rows):
    assert cell['case'] == row['case'] and cell['backend'] == row['backend']
    assert math.isclose(cell['speedup'], row['speedup'], rel_tol=1e-12)
for phase in ('primary', 'confirmation'):
    selected = [row['speedup'] for row in rows if row['case']['phase'] == phase]
    assert math.exp(statistics.mean(map(math.log, selected))) > 1.05
assert min(row['speedup'] for row in rows) >= 0.98

rss_old = json.loads((HERE / 'rss-incumbent.json').read_text())
rss_new = json.loads((HERE / 'rss-candidate.json').read_text())
assert rss_old['verified_outputs'] == rss_new['verified_outputs'] == 12 * 4096
assert rss_new['peak_rss_bytes'] - rss_old['peak_rss_bytes'] <= max(
    0.05 * rss_old['peak_rss_bytes'], 2 * 1024 * 1024)
pilot = json.loads((HERE / 'run-001/summary.json').read_text())
assert len(pilot['cells']) == 12 and min(c['speedup'] for c in pilot['cells']) < 0.98
pilot_intent = json.loads((HERE / 'intent-v1.json').read_text())
pilot_execution = json.loads((HERE / 'run-001/execution.json').read_text())
assert pilot_execution['intent_sha256'] == digest(HERE / 'intent-v1.json')
assert pilot_execution['benchmark_sha256'] == digest(HERE / 'benchmark.py')
assert pilot_execution['candidate_source_sha256'] == intent['candidate']['source_sha256']
assert pilot_execution['candidate_binary_sha256'] == intent['candidate']['binary_sha256']
assert pilot_intent['incumbent']['binary_sha256'] == intent['incumbent']['binary_sha256']
assert 'Ran 2 tests' in (HERE / 'tests-codec.log').read_text()
assert 'Ran 6 tests' in (HERE / 'tests-full.log').read_text()
print('PASS: codec patch, exact 12-cell paired measurements, confirmation, memory gate, and retained pilot failure.')
