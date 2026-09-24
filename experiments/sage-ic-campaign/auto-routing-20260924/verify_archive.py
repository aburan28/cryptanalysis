"""Audit the CPU auto-route patch and retained cold/controls evidence."""
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
BASE = ROOT / 'experiments/sage-binary-hardware/source/binary_hardware.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


intent = json.loads((HERE / 'intent-candidate-v1.json').read_text())
install = json.loads((HERE / 'install-001/install.json').read_text())
assert digest(BASE) == intent['incumbent_hardware_source_sha256']
assert digest(HERE / 'baseline/binary_hardware.py') == digest(BASE)
assert digest(HERE / 'source/binary_hardware.py') == install['source_sha256'] == install['installed_sha256']
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'src/sage/schemes/elliptic_curves/binary_hardware.py'
    path.parent.mkdir(parents=True)
    shutil.copy2(BASE, path)
    patch = HERE / 'auto-cpu.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    assert path.read_bytes() == (HERE / 'source/binary_hardware.py').read_bytes()

transfer = ROOT / 'experiments/sage-ic-campaign/metal-transfer-20260924'
transfer_intent = json.loads((transfer / 'intent-v1.json').read_text())
transfer_run = transfer / 'run-001'
execution = json.loads((transfer_run / 'execution.json').read_text())
assert execution['intent_sha256'] == digest(transfer / 'intent-v1.json')
assert execution['profile_sha256'] == digest(transfer / 'profile.py')
summary = json.loads((transfer_run / 'summary.json').read_text())
assert summary['all_outputs_exact'] and len(summary['cells']) == 4
for index in range(4):
    row = json.loads((transfer_run / f'cell-{index:02d}.json').read_text())
    assert json.loads((transfer_run / f'cell-{index:02d}-parent.json').read_text())['status'] == 0
    assert row['exact_output_agreement'] and row['source_sha256'] == transfer_intent['incumbent_source_sha256']
    assert row['binary_sha256'] == transfer_intent['incumbent_binary_sha256']
    assert len(row['gpu_seconds']) == 48 and all(len(v) == 48 for v in row['phase_seconds'].values())
    assert 0 <= row['median_gpu_seconds'] <= row['median_phase_seconds']['table']


def check_run(name, intent_name, script_name, expected_source, expected_trials, warm_calls):
    run = HERE / name
    execution = json.loads((run / 'execution.json').read_text())
    assert execution['intent_sha256'] == digest(HERE / intent_name)
    assert execution['benchmark_sha256'] == digest(HERE / script_name)
    rows = []
    for index in range(10):
        row = json.loads((run / f'cell-{index:02d}.json').read_text())
        assert json.loads((run / f'cell-{index:02d}-parent.json').read_text())['status'] == 0
        assert row['exact_output_agreement'] and len(row['trials']) == expected_trials
        if expected_source is not None:
            assert row['candidate_source_sha256'] == expected_source
        assert row['verified_outputs'] == row['case']['points'] * expected_trials * 2 * warm_calls
        for key in ('cold_total_seconds', 'warm_seconds'):
            logs = [math.log(t['arms']['sage'][key] /
                             t['arms']['auto' if expected_source is not None else 'cpu'][key])
                    for t in row['trials']]
            measured = row['speedup_auto_vs_sage' if expected_source is not None else 'speedup_cpu_vs_sage'][key]
            assert math.isclose(math.exp(statistics.median(logs)), measured, rel_tol=1e-12)
        rows.append(row)
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['all_outputs_exact'] and summary['total_verified_outputs'] == sum(r['verified_outputs'] for r in rows)
    return rows


exploratory = HERE / 'run-001'
exp_intent = json.loads((HERE / 'intent-exploratory-v1.json').read_text())
assert json.loads((exploratory / 'execution.json').read_text())['intent_sha256'] == digest(HERE / 'intent-exploratory-v1.json')
for index in range(10):
    row = json.loads((exploratory / f'cell-{index:02d}.json').read_text())
    assert row['exact_output_agreement'] and len(row['trials']) == 12
    assert row['hardware_source_sha256'] == exp_intent['incumbent_hardware_source_sha256']
    assert json.loads((exploratory / f'cell-{index:02d}-parent.json').read_text())['status'] == 0

first = check_run('run-002', 'intent-candidate-v1.json', 'benchmark_auto.py', install['source_sha256'], 12, 5)
second = check_run('run-003', 'intent-candidate-v2.json', 'benchmark_auto_v2.py', install['source_sha256'], 48, 9)
assert any(r['speedup_auto_vs_sage']['cold_total_seconds'] < .98 for r in first if not r['route_expected'])
assert any(r['speedup_auto_vs_sage']['cold_total_seconds'] < .98 for r in second if not r['route_expected'])
routed = [r['speedup_auto_vs_sage']['cold_total_seconds'] for r in second if r['route_expected']]
assert len(routed) == 6 and min(routed) >= 1.10
assert math.exp(statistics.mean(map(math.log, routed))) > 1.25

control = HERE / 'control-001'
control_intent = json.loads((HERE / 'intent-control-v3.json').read_text())
execution = json.loads((control / 'execution.json').read_text())
assert execution['intent_sha256'] == digest(HERE / 'intent-control-v3.json')
assert execution['script_sha256'] == digest(HERE / 'control_overhead.py')
for index in range(3):
    row = json.loads((control / f'cell-{index:02d}.json').read_text())
    assert row['all_outputs_exact'] and row['direct_sage_function_calls'] == 1
    assert row['candidate_source_sha256'] == control_intent['candidate_source_sha256']
    assert len(row['samples']) == control_intent['batches']
    assert row['branch_delta_seconds'] <= 5e-6 and row['branch_fraction'] <= .001

sage = json.loads((HERE / 'rss-sage.json').read_text())
auto = json.loads((HERE / 'rss-auto.json').read_text())
assert sage['verified_outputs'] == auto['verified_outputs'] == 12 * 4096
assert sage['selected_backend'] == 'sage' and auto['selected_backend'] == 'cpu'
assert auto['peak_rss_bytes'] - sage['peak_rss_bytes'] <= max(.05 * sage['peak_rss_bytes'], 2 * 1024 * 1024)
for name, count in (('tests-auto.log', 3), ('tests-hardware.log', 6)):
    log = (HERE / name).read_text()
    assert f'Ran {count} tests' in log and '\nOK\n' in log
print('PASS: auto-route patch, four Metal diagnostics, ten cold-map cells, routed confirmation, retained noisy controls, branch overhead, RSS and tests.')
