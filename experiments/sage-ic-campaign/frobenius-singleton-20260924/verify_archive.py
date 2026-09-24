"""Audit the incremental native singleton patch and frozen local evidence."""
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
PR78 = ROOT / 'experiments/sage-ic-campaign/frobenius-hom-20260924'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


profile_intent = read('intent-profile-v1.json')
failed_intent = read('intent-candidate-v1.json')
intent = read('intent-candidate-v2.json')
install1 = read('install-001/install.json')
install2 = read('install-002/install.json')
for name, expected in profile_intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
assert digest(HERE / 'baseline/hom_frobenius.py') == digest(PR78 / 'source/hom_frobenius.py')
assert digest(HERE / 'baseline/binary_batch_ntl.pyx') == digest(PR78 / 'baseline/binary_batch_ntl.pyx')
assert digest(HERE / 'baseline/hom_frobenius.py') == failed_intent['incumbent_source_sha256'] == intent['incumbent_source_sha256']
assert digest(HERE / 'candidate-v1/hom_frobenius.py') == failed_intent['candidate_source_sha256'] == install1['installed_sha256']
assert digest(HERE / 'source/hom_frobenius.py') == intent['candidate_source_sha256'] == install2['installed_python_sha256']
assert digest(HERE / 'source/binary_batch_ntl.pyx') == intent['candidate_native_source_sha256'] == install2['source_native_sha256']
assert install2['installed_binary_sha256'] == install2['built_binary_sha256']
assert install2['previous_binary_sha256'] == profile_intent['native_binary_sha256']

with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary) / 'src/sage/schemes/elliptic_curves'
    base.mkdir(parents=True)
    for name in ('hom_frobenius.py', 'binary_batch_ntl.pyx'):
        shutil.copy2(HERE / 'baseline' / name, base / name)
    patch = HERE / 'native-singleton.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    for name in ('hom_frobenius.py', 'binary_batch_ntl.pyx'):
        assert (base / name).read_bytes() == (HERE / 'source' / name).read_bytes()

profile = read('run-001/summary.json')
profile_execution = read('run-001/execution.json')
assert profile_execution['intent_sha256'] == digest(HERE / 'intent-profile-v1.json')
assert profile_execution['script_sha256'] == digest(HERE / 'profile.py')
assert profile['all_exact'] and len(profile['cells']) == len(profile_intent['cases'])
assert profile['verified_outputs'] == sum(
    read(f'run-001/cell-{i:02d}.json')['verified_outputs']
    for i in range(len(profile_intent['cases'])))
assert 'FAILED (failures=' in (HERE / 'tests-hom-v1.log').read_text()

run = HERE / 'run-002'
execution = read('run-002/execution.json')
assert execution['intent_sha256'] == digest(HERE / 'intent-candidate-v2.json')
assert execution['benchmark_sha256'] == digest(HERE / 'benchmark.py')
assert execution['candidate_source_sha256'] == intent['candidate_source_sha256']
assert execution['candidate_binary_sha256'] == install2['installed_binary_sha256']
cases = [dict(spec, phase=phase, seed=intent['seed_base_' + phase] + index)
         for phase in ('primary', 'confirmation')
         for index, spec in enumerate(intent[phase + '_cases'])]
rows = []
for index, case in enumerate(cases):
    row = json.loads((run / f'cell-{index:02d}.json').read_text())
    parent = json.loads((run / f'cell-{index:02d}-parent.json').read_text())
    assert parent == {'case': case, 'status': 0}
    assert row['case'] == case and row['exact_output_agreement']
    assert row['incumbent_source_sha256'] == intent['incumbent_source_sha256']
    assert row['candidate_source_sha256'] == intent['candidate_source_sha256']
    assert row['candidate_binary_sha256'] == install2['installed_binary_sha256']
    assert len(row['trials']) == intent['rounds']
    assert row['verified_outputs'] == case['points'] * (1 + intent['rounds']*2*2)
    for metric in ('warm_seconds', 'cold_total_seconds'):
        logs = [math.log(trial['arms']['incumbent'][metric] /
                         trial['arms']['candidate'][metric])
                for trial in row['trials']]
        assert math.isclose(math.exp(statistics.median(logs)),
                            row['speedup'][metric], rel_tol=1e-12)
    rows.append(row)
summary = read('run-002/summary.json')
assert summary['all_outputs_exact'] and len(summary['cells']) == len(rows)
assert summary['total_verified_outputs'] == sum(row['verified_outputs'] for row in rows)
for item, row in zip(summary['cells'], rows):
    assert item == {'case': row['case'], 'speedup': row['speedup']}
for phase in ('primary', 'confirmation'):
    gains = [row['speedup']['warm_seconds'] for row in rows
             if row['case']['phase'] == phase]
    assert math.exp(statistics.mean(map(math.log, gains))) > 1.05
assert min(row['speedup']['warm_seconds'] for row in rows) >= .98

old_rss = read('rss-incumbent.json')
new_rss = read('rss-candidate.json')
assert old_rss['verified_outputs'] == new_rss['verified_outputs'] == 6 * 4096
assert new_rss['peak_rss_bytes'] - old_rss['peak_rss_bytes'] <= max(
    .05 * old_rss['peak_rss_bytes'], 2 * 1024 * 1024)
for name, count in (('tests-hom-v2.log', 4), ('tests-native-v2.log', 2)):
    log = (HERE / name).read_text()
    assert f'Ran {count} tests' in log and '\nOK\n' in log
assert '[116 tests' in (HERE / 'doctest-hom-v2.log').read_text()
assert 'All tests passed!' in (HERE / 'doctest-hom-v2.log').read_text()
assert 'Linking target' in (HERE / 'build-v2.log').read_text()
print('PASS: native singleton patch, held context failure, nine accepted paired cells and exactness.')
