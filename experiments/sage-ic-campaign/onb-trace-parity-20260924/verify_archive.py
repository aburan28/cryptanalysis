"""Check the trace source, exact outputs, and recorded timing receipts."""

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
source = root / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-local.py'
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == \
    '191584f34e0092922cf8747d075a0791df702b6153923285b48736d96b0c6c03'
assert hashlib.sha256(source.read_bytes()).hexdigest() in (
    '7e9c9e14fcd215ec75414a43e28472fc206721be451f0a2e5c47b99c0676613c',
    'dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e',
    '2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd',
)
original = ast.parse(baseline.read_text())
candidate = ast.parse(source.read_text())
for tree in (original, candidate):
    onb = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    onb.body = [node for node in onb.body
                if not (isinstance(node, ast.FunctionDef) and
                        node.name in ('trace', 'frob', '__init__', 'inv'))]
assert ast.dump(original) == ast.dump(candidate)

intent = json.loads((here / 'intent.json').read_text())
assert intent['baseline_field_sha256'] == hashlib.sha256(baseline.read_bytes()).hexdigest()
assert '4639' in subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
live = json.loads(subprocess.check_output([sys.executable, str(here / 'benchmark.py')], text=True))
expected_cases = [('trace', 5), ('trace', 9), ('trace', 131),
                  ('point_from_x_invalid', 131), ('point_from_x_valid', 131)]
assert [(row['case'], row['degree']) for row in live] == expected_cases
for run in ('run-a.json', 'run-b.json'):
    rows = json.loads((here / run).read_text())
    assert [(row['case'], row['degree']) for row in rows] == expected_cases
    for row, current in zip(rows, live):
        assert row['input_sha256'] == current['input_sha256']
        assert row['inputs'] == current['inputs']
        assert row['rounds'] == 9
        assert row['repeat'] == (8 if row['case'] == 'trace' else 2)
        assert len(row['pairs']) == 9
        paired = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(row['paired_speedup'], paired)
        gate = float(intent['acceptance'][
            'degree_131_trace_speedup_minimum' if row['case'] == 'trace' and row['degree'] == 131
            else 'degree_5_and_9_trace_speedup_minimum' if row['case'] == 'trace'
            else 'point_from_x_invalid_speedup_minimum' if row['case'] == 'point_from_x_invalid'
            else 'point_from_x_valid_speedup_minimum'])
        assert paired >= gate, (run, row['case'], paired)

cold = json.loads((here / 'cold-trace.json').read_text())
for name, rows in cold['raw'].items():
    assert len(rows) == 7
    assert math.isclose(cold['median_ns'][name],
                        statistics.median(row['cold_trace_ns'] for row in rows))
    assert all(row['answer'] == 0 for row in rows)
    expected = [2] if name == 'incumbent' else []
    assert all(row['cached_exponents_after'] == expected for row in rows)
assert '4639' in (here / 'exact-python39.log').read_text()
assert '4639' in (here / 'exact-python313.log').read_text()
assert 'Ran 14 tests' in (here / 'python39-artifact.log').read_text()
assert 'Ran 3 tests' in (here / 'local-ic-tests.log').read_text()
print('ONB trace-parity archive and exact outputs verified')
