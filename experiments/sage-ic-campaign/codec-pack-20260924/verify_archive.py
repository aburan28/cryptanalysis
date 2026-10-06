"""Audit the incremental pack patch, held trial, and accepted paired run."""
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
BASE = ROOT / 'experiments/sage-ic-campaign/codec-output-20260924/source/binary_hardware_codec.pyx'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-candidate-v2.json').read_text())
install1 = json.loads((HERE / 'install-001/install.json').read_text())['files']
install2 = json.loads((HERE / 'install-002/install.json').read_text())['files']
assert digest(BASE) == intent['incumbent']['source_sha256']
assert digest(HERE / 'baseline/binary_hardware_codec.pyx') == digest(BASE)
assert digest(HERE / 'candidate-v1/binary_hardware_codec.pyx') == install1[0]['sha256'] == intent['v1_candidate']['source_sha256']
assert install1[1]['sha256'] == intent['v1_candidate']['binary_sha256']
assert digest(HERE / 'source/binary_hardware_codec.pyx') == install2[0]['sha256']
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'src/sage/schemes/elliptic_curves/binary_hardware_codec.pyx'
    path.parent.mkdir(parents=True)
    shutil.copy2(BASE, path)
    patch = HERE / 'codec-pack.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    assert path.read_bytes() == (HERE / 'source/binary_hardware_codec.pyx').read_bytes()

profile = json.loads((HERE / 'run-001/summary.json').read_text())
assert profile['all_outputs_exact'] and len(profile['cells']) == 6
profile_outputs = 0
for index in range(6):
    row = json.loads((HERE / f'run-001/cell-{index:02d}.json').read_text())
    parent = json.loads((HERE / f'run-001/cell-{index:02d}-parent.json').read_text())
    assert parent['status'] == 0 and row['exact_output_agreement']
    assert row['source_sha256'] == digest(BASE)
    assert row['binary_sha256'] == intent['incumbent']['binary_sha256']
    assert len(row['rounds']) == 12 and all(len(values) == 48 for values in row['phase_seconds'].values())
    assert math.isclose(sum(row['median_phase_seconds'].values()), row['total_median_seconds'], rel_tol=1e-12)
    profile_outputs += row['verified_outputs']
assert profile_outputs == profile['total_verified_outputs']


def check_benchmark(directory, intent_name, runner_name, installed_files):
    run = HERE / directory
    execution = json.loads((run / 'execution.json').read_text())
    assert execution['intent_sha256'] == digest(HERE / intent_name)
    assert execution['benchmark_sha256'] == digest(HERE / runner_name)
    assert execution['incumbent_binary_sha256'] == intent['incumbent']['binary_sha256']
    assert execution['candidate_source_sha256'] == installed_files[0]['sha256']
    assert execution['candidate_binary_sha256'] == installed_files[1]['sha256']
    rows = []
    for index in range(12):
        row = json.loads((run / f'cell-{index:02d}.json').read_text())
        parent = json.loads((run / f'cell-{index:02d}-parent.json').read_text())
        assert parent['status'] == 0 and row['all_outputs_exact']
        assert row['incumbent_binary_sha256'] == intent['incumbent']['binary_sha256']
        assert row['candidate_binary_sha256'] == installed_files[1]['sha256']
        assert row['verified_outputs'] == row['case']['points'] * row['calls_per_sample'] * 24
        assert len(row['rounds']) == 12
        logs = [math.log(s['seconds']['incumbent'] / s['seconds']['candidate'])
                for s in row['rounds']]
        assert math.isclose(math.exp(statistics.median(logs)), row['speedup'], rel_tol=1e-12)
        rows.append(row)
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['all_outputs_exact'] and summary['total_verified_outputs'] == sum(r['verified_outputs'] for r in rows)
    assert len(summary['cells']) == len(rows)
    for cell, row in zip(summary['cells'], rows):
        assert cell['case'] == row['case'] and cell['backend'] == row['backend']
        assert math.isclose(cell['speedup'], row['speedup'], rel_tol=1e-12)
    return rows


held = check_benchmark('run-002', 'intent-candidate-v1.json', 'benchmark.py', install1)
assert min(row['speedup'] for row in held) < 0.98
accepted = check_benchmark('run-003', 'intent-candidate-v2.json', 'benchmark_v2.py', install2)
for phase in ('primary', 'confirmation'):
    gains = [row['speedup'] for row in accepted if row['case']['phase'] == phase]
    assert math.exp(statistics.mean(map(math.log, gains))) > 1.05
assert min(row['speedup'] for row in accepted) >= 0.98
old_rss = json.loads((HERE / 'rss-v2-incumbent.json').read_text())
new_rss = json.loads((HERE / 'rss-v2-candidate.json').read_text())
assert old_rss['verified_outputs'] == new_rss['verified_outputs'] == 12 * 4096
assert new_rss['peak_rss_bytes'] - old_rss['peak_rss_bytes'] <= max(
    .05 * old_rss['peak_rss_bytes'], 2 * 1024 * 1024)
for name, count in (('tests-pack-v2.log', 3), ('tests-output-v2.log', 2), ('tests-hardware-v2.log', 6)):
    log = (HERE / name).read_text()
    assert f'Ran {count} tests' in log and '\nOK\n' in log
print('PASS: pack patch, six phase profiles, held first trial, twelve accepted paired cells, memory and correctness gates.')
