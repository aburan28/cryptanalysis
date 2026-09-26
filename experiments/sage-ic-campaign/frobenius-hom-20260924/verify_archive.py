"""Audit the Frobenius-isogeny Sage patch and its frozen local evidence."""
import hashlib
import json
import math
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


profile_intent = read('intent-profile-v1.json')
first = read('intent-candidate-v1.json')
accepted_intent = read('intent-candidate-v2.json')
install1 = read('install-001/install.json')
install2 = read('install-002/install.json')
for name, expected in profile_intent['baseline_hashes'].items():
    assert digest(HERE / 'baseline' / name) == expected
assert digest(HERE / 'baseline/hom_frobenius.py') == first['incumbent_source_sha256'] == accepted_intent['incumbent_source_sha256']
assert digest(HERE / 'candidate-v1/hom_frobenius.py') == first['candidate_source_sha256'] == install1['installed_sha256']
assert digest(HERE / 'source/hom_frobenius.py') == accepted_intent['candidate_source_sha256'] == install2['installed_sha256']
assert install2['previous_sha256'] == install1['installed_sha256']
with tempfile.TemporaryDirectory() as temporary:
    target = Path(temporary) / 'src/sage/schemes/elliptic_curves/hom_frobenius.py'
    target.parent.mkdir(parents=True)
    shutil.copy2(HERE / 'baseline/hom_frobenius.py', target)
    patch = HERE / 'frobenius-hom.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    assert target.read_bytes() == (HERE / 'source/hom_frobenius.py').read_bytes()

profile = read('run-001/summary.json')
execution = read('run-001/execution.json')
assert execution['intent_sha256'] == digest(HERE / 'intent-profile-v1.json')
assert execution['script_sha256'] == digest(HERE / 'profile.py')
assert profile['all_exact'] and len(profile['cells']) == len(profile_intent['cases'])
assert profile['verified_outputs'] == sum(
    read(f'run-001/cell-{index:02d}.json')['verified_outputs']
    for index in range(len(profile_intent['cases'])))


def check_run(directory, intent_name, runner_name):
    intent = read(intent_name)
    run = HERE / directory
    execution = json.loads((run / 'execution.json').read_text())
    assert execution['intent_sha256'] == digest(HERE / intent_name)
    assert execution['benchmark_sha256'] == digest(HERE / runner_name)
    assert execution['candidate_source_sha256'] == intent['candidate_source_sha256']
    cases = [dict(spec, phase=phase,
                  seed=intent['seed_base_' + phase] + index)
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
        assert len(row['trials']) == intent['rounds']
        assert row['verified_outputs'] == case['points'] * (1 + intent['rounds']*2*2)
        for trial in row['trials']:
            for arm in ('incumbent', 'candidate'):
                arm_data = trial['arms'][arm]
                assert math.isclose(arm_data['cold_total_seconds'],
                                    arm_data['construct_seconds'] + arm_data['first_seconds'],
                                    rel_tol=1e-10, abs_tol=1e-9)
        for metric in ('warm_seconds', 'cold_total_seconds'):
            logs = [math.log(trial['arms']['incumbent'][metric] /
                             trial['arms']['candidate'][metric])
                    for trial in row['trials']]
            assert math.isclose(math.exp(statistics.median(logs)),
                                row['speedup'][metric], rel_tol=1e-12)
        rows.append(row)
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['all_outputs_exact'] and len(summary['cells']) == len(rows)
    assert summary['total_verified_outputs'] == sum(row['verified_outputs'] for row in rows)
    for item, row in zip(summary['cells'], rows):
        assert item == {'case': row['case'], 'speedup': row['speedup']}
    return rows


first_rows = check_run('run-002', 'intent-candidate-v1.json', 'benchmark.py')
accepted = check_run('run-003', 'intent-candidate-v2.json', 'benchmark_v2.py')
assert len(first_rows) == len(accepted) == 10
for phase in ('primary', 'confirmation'):
    gains = [row['speedup']['warm_seconds'] for row in accepted
             if row['case']['phase'] == phase]
    assert math.exp(statistics.mean(map(math.log, gains))) > 1.05
assert min(row['speedup']['warm_seconds'] for row in accepted) >= .98

old_rss = read('rss-incumbent.json')
new_rss = read('rss-candidate.json')
assert old_rss['verified_outputs'] == new_rss['verified_outputs'] == 6 * 4096
assert new_rss['peak_rss_bytes'] - old_rss['peak_rss_bytes'] <= max(
    .05 * old_rss['peak_rss_bytes'], 2 * 1024 * 1024)
assert 'FAILED (failures=1)' in (HERE / 'tests-hom-v1.log').read_text()
assert 'test_custom_point_class_and_cached_guard' in (HERE / 'tests-hom-v1.log').read_text()
test_log = (HERE / 'tests-hom-v2.log').read_text()
assert 'Ran 4 tests' in test_log and '\nOK\n' in test_log
doctest_log = (HERE / 'doctest-hom-v2.log').read_text()
assert '[116 tests' in doctest_log and 'All tests passed!' in doctest_log
print('PASS: Frobenius-isogeny patch, failed first guard, ten accepted paired cells, RSS and exactness.')
