"""Audit the scalar-add Sage patch, held trials, and accepted receipts."""
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
PR79 = ROOT / 'experiments/sage-ic-campaign/frobenius-singleton-20260924'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


profile_intent = read('intent-profile-v1.json')
guard_intent = read('intent-guard-v1.json')
intents = [read(f'intent-candidate-v{v}.json') for v in (1, 2, 3, 4)]
for name, expected in profile_intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
assert digest(HERE / 'baseline/binary_batch_ntl.pyx') == digest(PR79 / 'source/binary_batch_ntl.pyx')
assert guard_intent['incumbent_source_sha256'] == digest(HERE / 'baseline/ell_point.py')
for intent in intents:
    assert intent['incumbent_source_sha256'] == digest(HERE / 'baseline/ell_point.py')
assert digest(HERE / 'source/ell_point.py') == intents[3]['candidate_source_sha256']
assert digest(HERE / 'source/binary_batch_ntl.pyx') == intents[3]['candidate_native_source_sha256']
for version in (1, 2, 3):
    receipt = read(f'install-00{version}/install.json')
    assert receipt['source_sha256'] == receipt['installed_sha256'] == intents[version-1]['candidate_source_sha256']
install = read('install-004/install.json')
assert install['source_python_sha256'] == install['installed_python_sha256'] == intents[3]['candidate_source_sha256']
assert install['source_native_sha256'] == intents[3]['candidate_native_source_sha256']
assert install['installed_binary_sha256'] == install['built_binary_sha256']
assert install['previous_binary_sha256'] == intents[3]['incumbent_native_binary_sha256']

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary) / 'src/sage/schemes/elliptic_curves'
    base.mkdir(parents=True)
    for name in ('ell_point.py', 'binary_batch_ntl.pyx'):
        shutil.copy2(HERE / 'baseline' / name, base / name)
    patch = HERE / 'scalar-add.patch'
    subprocess.run(['git', 'apply', '--unidiff-zero', '--check', str(patch)],
                   cwd=temporary, check=True)
    subprocess.run(['git', 'apply', '--unidiff-zero', str(patch)],
                   cwd=temporary, check=True)
    for name in ('ell_point.py', 'binary_batch_ntl.pyx'):
        assert (base / name).read_bytes() == (HERE / 'source' / name).read_bytes()

for version in (1, 2, 3):
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / 'src/sage/schemes/elliptic_curves/ell_point.py'
        target.parent.mkdir(parents=True)
        shutil.copy2(HERE / 'baseline/ell_point.py', target)
        patch = HERE / f'held-v{version}.patch'
        subprocess.run(['git', 'apply', '--unidiff-zero', '--check', str(patch)],
                       cwd=temporary, check=True)
        subprocess.run(['git', 'apply', '--unidiff-zero', str(patch)],
                       cwd=temporary, check=True)
        assert digest(target) == intents[version-1]['candidate_source_sha256']

for directory, intent_name, script_name in (
        ('run-001', 'intent-profile-v1.json', 'profile.py'),
        ('run-002', 'intent-guard-v1.json', 'guard_profile.py')):
    execution = read(f'{directory}/execution.json')
    summary = read(f'{directory}/summary.json')
    assert execution['intent_sha256'] == digest(HERE / intent_name)
    assert execution['script_sha256'] == digest(HERE / script_name)
    assert summary['all_exact']
    assert summary['verified_outputs'] == sum(
        read(f'{directory}/cell-{i:02d}.json')['verified_outputs']
        for i in range(len(summary['cells'])))
guard = read('run-002/summary.json')
assert min(cell['speedup'] for cell in guard['cells']
           if cell['case']['field'] != 'binary') < .98


def check_run(directory, version, runner):
    intent = intents[version-1]
    execution = read(f'{directory}/execution.json')
    assert execution['intent_sha256'] == digest(HERE / f'intent-candidate-v{version}.json')
    assert execution['benchmark_sha256'] == digest(HERE / runner)
    assert execution['candidate_source_sha256'] == intent['candidate_source_sha256']
    if version == 4:
        assert execution['candidate_binary_sha256'] == install['installed_binary_sha256']
    cases = [dict(spec, phase=phase, seed=intent['seed_base_' + phase] + index)
             for phase in ('primary', 'confirmation')
             for index, spec in enumerate(intent[phase + '_cases'])]
    rows = []
    for index, case in enumerate(cases):
        row = read(f'{directory}/cell-{index:02d}.json')
        parent = read(f'{directory}/cell-{index:02d}-parent.json')
        assert parent == {'case': case, 'status': 0}
        assert row['case'] == case and row['exact_outputs']
        assert row['incumbent_source_sha256'] == intent['incumbent_source_sha256']
        assert row['candidate_source_sha256'] == intent['candidate_source_sha256']
        if version == 4:
            assert row['candidate_binary_sha256'] == install['installed_binary_sha256']
        assert len(row['trials']) == intent['rounds']
        assert row['verified_outputs'] == case['pairs'] * (1 + intent['rounds']*2)
        logs = [math.log(t['seconds']['incumbent'] / t['seconds']['candidate'])
                for t in row['trials']]
        assert math.isclose(math.exp(statistics.median(logs)), row['speedup'],
                            rel_tol=1e-12)
        rows.append(row)
    summary = read(f'{directory}/summary.json')
    assert summary['all_exact'] and len(summary['cells']) == len(rows)
    assert summary['verified_outputs'] == sum(row['verified_outputs'] for row in rows)
    for item, row in zip(summary['cells'], rows):
        assert item == {'case': row['case'], 'speedup': row['speedup']}
    return rows


held1 = check_run('run-003', 1, 'benchmark.py')
held2 = check_run('run-004', 2, 'benchmark_v2.py')
for rows in (held1, held2):
    assert min(row['speedup'] for row in rows if row['case']['field'] != 'binary') < .98
assert 'FAILED (failures=' in (HERE / 'tests-add-v3.log').read_text()
accepted = check_run('run-005', 4, 'benchmark_v4.py')
assert len(accepted) == 8
for subset in ([row for row in accepted if row['case']['phase'] == 'primary'],
               [row for row in accepted if row['case']['phase'] == 'confirmation'
                and row['case']['field'] == 'binary']):
    gains = [row['speedup'] for row in subset]
    assert math.exp(statistics.mean(map(math.log, gains))) > 1.05
    assert min(gains) >= .98
assert min(row['speedup'] for row in accepted
           if row['case']['field'] != 'binary') >= .98
old_rss = read('rss-incumbent.json')
new_rss = read('rss-candidate.json')
assert old_rss['verified_outputs'] == new_rss['verified_outputs'] == 6*4096
assert new_rss['peak_rss_bytes'] - old_rss['peak_rss_bytes'] <= max(
    .05*old_rss['peak_rss_bytes'], 2*1024*1024)
assert 'Ran 4 tests' in (HERE / 'tests-add-v4-final.log').read_text()
assert '\nOK\n' in (HERE / 'tests-add-v4-final.log').read_text()
assert '[1077 tests' in (HERE / 'doctest-ell-point-v4.log').read_text()
assert 'All tests passed!' in (HERE / 'doctest-ell-point-v4.log').read_text()
assert 'Linking target' in (HERE / 'build-v4.log').read_text()
print('PASS: scalar-add patch, three held prototypes, eight accepted paired cells, memory and exactness.')
