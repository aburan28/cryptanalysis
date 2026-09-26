"""Check runner source sync, exact outputs and frozen stage receipts."""

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
for name, expected in (
    ('field.py', '81d0397473a2a55b06a04b19991382a2c3dd1c73ba515921dd7305a10b72dc5f'),
    ('curves.py', '5009571a52299e67a84b49fe7921929e2bc1c3330df61d1fa5fd44ad1c89c225'),
):
    assert hashlib.sha256((here / 'baseline' / name).read_bytes()).hexdigest() == expected
runner_field = root / 'ecc2k130/runner/codegen/field.py'
runner_curves = root / 'ecc2k130/runner/codegen/curves.py'
local_field = root / 'ecc2k130/codegen/field.py'
local_curves = root / 'ecc2k130/codegen/curves.py'
assert runner_field.read_bytes() == local_field.read_bytes()
assert hashlib.sha256((root / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-runner.py').read_bytes()).hexdigest() == (
    '2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd')
# The live synchronized curve can gain later arithmetic methods. Keep the
# frozen baseline hash above and check that NormalView and the local prefix
# retain the structural relationship this archive established.
runner_tree = ast.parse(runner_curves.read_text())
local_tree = ast.parse(local_curves.read_text())
normal_view = runner_tree.body[-1]
assert isinstance(normal_view, ast.ClassDef) and normal_view.name == 'NormalView'
original_tree = ast.parse((here / 'baseline/curves.py').read_text())
assert ast.dump(normal_view) == ast.dump(original_tree.body[-1])
runner_tree.body.pop()
assert ast.dump(runner_tree) == ast.dump(local_tree)

intent = json.loads((here / 'intent.json').read_text())
assert intent['baseline_field_sha256'] == hashlib.sha256(
    (here / 'baseline/field.py').read_bytes()).hexdigest()
assert '4152' in subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
live = json.loads(subprocess.check_output([sys.executable, str(here / 'benchmark.py')], text=True))
cases = ['mul', 'frob1', 'from_coords', 'to_coords', 'point_from_x', 'point_dbl']
assert [row['case'] for row in live] == cases
for run in ('run-a.json', 'run-b.json'):
    rows = json.loads((here / run).read_text())
    assert [row['case'] for row in rows] == cases
    for row, current in zip(rows, live):
        assert row['input_sha256'] == current['input_sha256']
        assert row['inputs'] == current['inputs']
        assert row['repeat'] == current['repeat']
        assert row['rounds'] == 7 and len(row['pairs']) == 7
        paired = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(paired, row['paired_speedup'])
        gate = float(intent['acceptance'][{
            'mul': 'field_multiply_speedup_minimum',
            'frob1': 'field_frobenius_speedup_minimum',
            'point_from_x': 'runner_point_recovery_speedup_minimum',
            'point_dbl': 'runner_point_doubling_speedup_minimum',
        }[row['case']]]) if row['case'] in ('mul', 'frob1', 'point_from_x', 'point_dbl') else 1.0
        assert paired >= gate, (run, row['case'], paired)

cold = json.loads((here / 'cold-point.json').read_text())
for outcome, groups in cold['raw'].items():
    for variant, rows in groups.items():
        assert len(rows) == 7
        assert math.isclose(cold['median_ns'][outcome][variant],
                            statistics.median(row['cold_point_from_x_ns'] for row in rows))
        expected = [] if variant == 'incumbent' else [2, 4] if outcome == 'valid' else [2]
        assert all(row['cached_exponents_after'] == expected for row in rows)
assert '4152' in (here / 'exact-python313.log').read_text()
assert '4152' in (here / 'exact-python39.log').read_text()
assert 'Ran 3 tests' in (here / 'runner-ic-tests.log').read_text()
assert 'Ran 14 tests' in (here / 'python39-artifact.log').read_text()
print('runner ONB sync archive and exact outputs verified')
