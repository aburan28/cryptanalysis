"""Check Euclid inverse source, exact outputs and cold/warm receipts."""

import ast
import hashlib
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
baseline = here / 'baseline/field.py'
local = root / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-local.py'
runner = root / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-runner.py'
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == \
    'dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e'
assert local.read_bytes() == runner.read_bytes()
assert hashlib.sha256(local.read_bytes()).hexdigest() == \
    '2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd'
original = ast.parse(baseline.read_text())
candidate = ast.parse(local.read_text())
for tree in (original, candidate):
    onb = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    onb.body = [node for node in onb.body
                if not (isinstance(node, ast.FunctionDef) and node.name == 'inv')]
assert ast.dump(original) == ast.dump(candidate)

intent = json.loads((here / 'intent.json').read_text())
assert intent['baseline_field_sha256'] == hashlib.sha256(baseline.read_bytes()).hexdigest()
assert '1046' in subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
live = json.loads(subprocess.check_output([sys.executable, str(here / 'benchmark.py')], text=True))
cases = [('inv', 5), ('inv', 9), ('inv', 131),
         ('point_from_x', 131), ('point_dbl', 131)]
assert [(row['case'], row['degree']) for row in live] == cases
for name in ('run-a.json', 'run-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(row['case'], row['degree']) for row in rows] == cases
    for row, current in zip(rows, live):
        assert row['inputs'] == current['inputs']
        assert row['input_sha256'] == current['input_sha256']
        assert row['repeat'] == current['repeat'] and row['rounds'] == 9
        assert len(row['pairs']) == 9
        paired = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(paired, row['paired_speedup'])
        gate = float(intent['acceptance'][
            'degree_5_and_9_inverse_speedup_minimum' if row['degree'] in (5, 9)
            else 'degree_131_inverse_speedup_minimum' if row['case'] == 'inv'
            else 'degree_131_point_recovery_speedup_minimum' if row['case'] == 'point_from_x'
            else 'degree_131_point_doubling_speedup_minimum'])
        assert paired >= gate, (name, row['case'], paired)

for name in ('cold-a.json', 'cold-b.json'):
    cold = json.loads((here / name).read_text())
    for outcome, groups in cold['raw'].items():
        for variant, rows in groups.items():
            assert len(rows) == 7
            assert math.isclose(cold['median_ns'][outcome][variant],
                                statistics.median(row['cold_ns'] for row in rows))
            expected = [4] if outcome == 'valid' else []
            assert all(row['cached_exponents_after'] == expected for row in rows)
        assert cold['median_ns'][outcome]['candidate'] < cold['median_ns'][outcome]['parent']
assert '1046' in (here / 'exact-python39.log').read_text()
assert '1046' in (here / 'exact-python313.log').read_text()
assert 'Ran 14 tests' in (here / 'python39-artifact.log').read_text()
assert 'Ran 3 tests' in (here / 'runner-ic-tests.log').read_text()
print('public ONB Euclid inverse archive and exact outputs verified')
