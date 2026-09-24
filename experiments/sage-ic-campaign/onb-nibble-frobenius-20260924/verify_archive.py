"""Check adaptive Frobenius source, exact outputs and frozen cold/warm gates."""

import ast
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
baseline = here / 'baseline/field.py'
local = root / 'ecc2k130/codegen/field.py'
runner = root / 'ecc2k130/runner/codegen/field.py'
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == \
    '7e9c9e14fcd215ec75414a43e28472fc206721be451f0a2e5c47b99c0676613c'
assert local.read_bytes() == runner.read_bytes()
assert hashlib.sha256(local.read_bytes()).hexdigest() in (
    'dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e',
    '2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd',
)
original = ast.parse(baseline.read_text())
candidate = ast.parse(local.read_text())
for tree in (original, candidate):
    onb = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    onb.body = [node for node in onb.body if not (
        isinstance(node, ast.FunctionDef) and node.name in ('__init__', 'frob', 'inv'))]
assert ast.dump(original) == ast.dump(candidate)

spec = importlib.util.spec_from_file_location('accepted_field', local)
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)
for m in (5, 9, 131):
    f = field.Onb(m)
    value = f.fromCoords(31)
    for k in (1, 2):
        exponent = pow(2, k, f.n)
        expected = f.frob(value, k)
        if m == 131:
            assert exponent not in f.frobPositions
            for _ in range(34):
                assert f.frob(value, k) == expected
            assert exponent not in f.frobPositions
            assert f.frob(value, k) == expected
        assert exponent in f.frobPositions

assert '53368' in subprocess.check_output([
    sys.executable, str(root / 'experiments/sage-ic-campaign/onb-frobenius-20260924/verify.py')],
    text=True)
intent = json.loads((here / 'intent-adaptive.json').read_text())
assert intent['baseline_field_sha256'] == hashlib.sha256(baseline.read_bytes()).hexdigest()
live = json.loads(subprocess.check_output([sys.executable, str(here / 'adaptive_compare.py')], text=True))
cases = [(x['case'], x['degree']) for x in live]
assert cases == [('frob1', 5), ('frob2', 5), ('frob1', 9), ('frob2', 9),
                 ('frob1', 131), ('frob2', 131), ('point_from_x', 131)]
for name in ('adaptive-run-a.json', 'adaptive-run-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(x['case'], x['degree']) for x in rows] == cases
    for row, current in zip(rows, live):
        assert row['inputs'] == current['inputs'] and row['repeat'] == current['repeat']
        assert len(row['pairs']) == 9
        ratio = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(ratio, row['speed_fraction_of_parent'])
        gate = float(intent['acceptance'][
            'warm_point_from_x_speed_at_least_fraction_of_parent' if row['case'] == 'point_from_x'
            else 'degree_5_and_9_speed_at_least_fraction_of_parent' if row['degree'] in (5, 9)
            else 'warm_frobenius_speed_at_least_fraction_of_parent'])
        assert ratio >= gate, (name, row['case'], row['degree'], ratio)

for name in ('adaptive-cold.json', 'adaptive-cold-b.json'):
    cold = json.loads((here / name).read_text())
    for outcome, groups in cold['raw'].items():
        for variant, rows in groups.items():
            assert len(rows) == 7
            assert math.isclose(cold['median_ns'][outcome][variant],
                                statistics.median(row['cold_ns'] for row in rows))
            expected = [2, 4] if variant == 'parent' and outcome == 'valid' else \
                [2] if variant == 'parent' else [4] if outcome == 'valid' else []
            assert all(row['cached_exponents_after'] == expected for row in rows)
    assert cold['median_ns']['valid']['adaptive'] <= float(intent['acceptance'][
        'first_valid_point_from_x_time_at_most_fraction_of_parent']) * \
        cold['median_ns']['valid']['parent']

probe = json.loads((here / 'probe-a.json').read_text())
assert len(probe) == 10
for width in (4, 5, 6, 7):
    assert any(row['warm_speed_fraction_of_parent'] < .80
               for row in probe if row['width'] == width)
for number in ('53368', '4639', '4152'):
    assert number in (here / 'exact-python39.log').read_text()
assert 'Ran 14 tests' in (here / 'python39-artifact.log').read_text()
assert 'Ran 3 tests' in (here / 'runner-ic-tests.log').read_text()
print('adaptive ONB Frobenius archive and exact outputs verified')
