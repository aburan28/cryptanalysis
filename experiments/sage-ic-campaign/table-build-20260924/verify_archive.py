"""Audit the standalone Sage table patch and its frozen local measurements."""
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


def read(name):
    return json.loads((HERE / name).read_text())


first = read('intent-independent-v1.json')
accepted_intent = read('intent-independent-v2.json')
metal_intent = read('intent-metal-independent-v1.json')
install = read('install-independent-001/install.json')
for intent in (first, accepted_intent, metal_intent):
    assert intent['incumbent_source_sha256'] == digest(BASE)
    assert intent['candidate_source_sha256'] == digest(HERE / 'source/binary_hardware.py')
assert (HERE / 'baseline-pr75/binary_hardware.py').read_bytes() == BASE.read_bytes()
assert install['source_sha256'] == install['installed_sha256'] == accepted_intent['candidate_source_sha256']

with tempfile.TemporaryDirectory() as temporary:
    target = Path(temporary) / 'src/sage/schemes/elliptic_curves/binary_hardware.py'
    target.parent.mkdir(parents=True)
    shutil.copy2(BASE, target)
    patch = HERE / 'vector-table.patch'
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=temporary, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=temporary, check=True)
    assert target.read_bytes() == (HERE / 'source/binary_hardware.py').read_bytes()


def check_run(directory, intent_name, runner_name, rounds, warm_calls):
    intent = read(intent_name)
    run = HERE / directory
    execution = json.loads((run / 'execution.json').read_text())
    assert execution['intent_sha256'] == digest(HERE / intent_name)
    assert execution['benchmark_sha256'] == digest(HERE / runner_name)
    assert execution['candidate_source_sha256'] == intent['candidate_source_sha256']
    rows = []
    cases = [dict(spec, phase=phase,
                  seed=intent['seed_base_primary' if phase == 'primary'
                              else 'seed_base_confirmation'] + index)
             for phase in ('primary', 'confirmation')
             for index, spec in enumerate(intent[phase + '_cases'])]
    for index, case in enumerate(cases):
        row = json.loads((run / f'cell-{index:02d}.json').read_text())
        parent = json.loads((run / f'cell-{index:02d}-parent.json').read_text())
        assert parent == {'case': case, 'status': 0}
        assert row['case'] == case and row['exact_table_agreement'] and row['exact_output_agreement']
        assert row['incumbent_source_sha256'] == intent['incumbent_source_sha256']
        assert row['candidate_source_sha256'] == intent['candidate_source_sha256']
        assert len(row['trials']) == rounds
        assert row['verified_outputs'] == case['points'] * rounds * 2 * (warm_calls + 1)
        for metric in ('table_seconds', 'cold_total_seconds', 'warm_seconds'):
            logs = [math.log(trial['arms']['incumbent'][metric] /
                             trial['arms']['candidate'][metric]) for trial in row['trials']]
            assert math.isclose(math.exp(statistics.median(logs)),
                                row['speedup'][metric], rel_tol=1e-12)
        rows.append(row)
    summary = json.loads((run / 'summary.json').read_text())
    assert len(summary['cells']) == len(rows)
    assert summary['all_tables_exact'] and summary['all_outputs_exact']
    assert summary['total_verified_outputs'] == sum(row['verified_outputs'] for row in rows)
    for item, row in zip(summary['cells'], rows):
        assert item == {'case': row['case'], 'speedup': row['speedup']}
    return rows


held = check_run('run-004', 'intent-independent-v1.json', 'benchmark_independent.py', 12, 4)
assert min(row['speedup']['cold_total_seconds'] for row in held) < .98
accepted = check_run('run-005', 'intent-independent-v2.json', 'benchmark_independent_v2.py', 48, 8)
assert len(accepted) == 9
for phase in ('primary', 'confirmation'):
    gains = [row['speedup']['cold_total_seconds'] for row in accepted
             if row['case']['phase'] == phase]
    assert math.exp(statistics.mean(map(math.log, gains))) > 1.05
assert min(row['speedup']['cold_total_seconds'] for row in accepted) >= .98
metal = check_run('run-006', 'intent-metal-independent-v1.json',
                  'benchmark_metal_independent.py', 12, 4)
assert len(metal) == 4

old_rss = read('rss-independent-incumbent.json')
new_rss = read('rss-independent-candidate.json')
assert old_rss['verified_outputs'] == new_rss['verified_outputs'] == 12 * 4096
assert new_rss['peak_rss_bytes'] - old_rss['peak_rss_bytes'] <= max(
    .05 * old_rss['peak_rss_bytes'], 2 * 1024 * 1024)
for name, count in (('tests-table-independent.log', 2),
                    ('tests-hardware-independent.log', 6)):
    log = (HERE / name).read_text()
    assert f'Ran {count} tests' in log and '\nOK\n' in log
print('PASS: table patch, held pilot, nine accepted CPU cells, four Metal diagnostics, memory and exactness.')
