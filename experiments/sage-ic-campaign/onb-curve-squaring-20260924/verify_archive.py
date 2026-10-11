"""Verify the curve-square source, exact outputs, and cold/warm receipts."""

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
    ('baseline/field.py', '148d795b6216254813e7dbe189e1290ae286dd9edb2b0a3c3fe2870788c81918'),
    ('baseline-v3/field.py', '191584f34e0092922cf8747d075a0791df702b6153923285b48736d96b0c6c03'),
    ('field-v1.py', '58ae53f27f9b2aa62f6d219667f50fc159661731f8a1fc44a7a7c27a8d4a55e0'),
    ('baseline/curves.py', 'eeb52de0491669572a7ecd2be6e19480d84d077fe9134d2a5efdb9f04a1dae17'),
    ('curves-v1.py', 'd7ccabe5688f4706b972a1c6508e7316f4c478e2fb2437e735734a4c6ee9d8d0'),
):
    actual = hashlib.sha256((here / name).read_bytes()).hexdigest()
    assert actual == expected, (name, actual)
field = root / 'experiments/sage-ic-campaign/pb-euclid-inverse-20260924/baseline/field-local.py'
# The field snapshot is the exact source preceding the later Pb inverse change.
# Exclude separately verified ONB methods from the historical structure check.
original_field = ast.parse((here / 'baseline-v3/field.py').read_text())
current_field = ast.parse(field.read_text())
for tree in (original_field, current_field):
    onb = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    onb.body = [node for node in onb.body
                if not (isinstance(node, ast.FunctionDef) and
                        node.name in ('trace', 'frob', '__init__', 'inv'))]
assert ast.dump(original_field) == ast.dump(current_field)
curves = root / 'ecc2k130/codegen/curves.py'
accepted = 'd7ccabe5688f4706b972a1c6508e7316f4c478e2fb2437e735734a4c6ee9d8d0'
if hashlib.sha256(curves.read_bytes()).hexdigest() != accepted:
    source = curves.read_text()
    cls = next(node for node in ast.parse(source).body
               if isinstance(node, ast.ClassDef) and node.name == 'Curve')
    for name, expected in (
        ('onCurve', '541f760df59925407f5988438d16094c185be0452ed389d760a7fd065b84390c'),
        ('dbl', 'b0fef120833065d0e477e7d4c00c45ebcdfc82d761406dce8ad3ba7d33042221'),
        ('add', 'f9175d263f9403c28ba6bfcf60191834f69bd35835914e55a3f0d1d0173e487e'),
        ('pointFromX', 'b9fd18ea7e67076701ad7891d65531319b952785db6bb5321a26223331cb4039'),
    ):
        method = next(node for node in cls.body
                      if isinstance(node, ast.FunctionDef) and node.name == name)
        actual = hashlib.sha256(ast.get_source_segment(source, method).encode()).hexdigest()
        assert actual == expected, (name, actual)

exact = subprocess.check_output([sys.executable, str(here / 'verify_v3.py')], text=True)
assert '1080' in exact
live = json.loads(subprocess.check_output([
    sys.executable, str(here / 'benchmark.py'),
    '--incumbent-field', str(here / 'baseline-v3/field.py'),
    '--incumbent-curves', str(here / 'baseline/curves.py'),
    '--candidate-field', str(field), '--candidate-curves', str(curves)], text=True))
assert len(live) == 8
for name in ('run-v3-a.json', 'run-v3-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(row['case'], row['m']) for row in rows] == \
        [(row['case'], row['m']) for row in live]
    for row in rows:
        paired = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(paired, row['paired_speedup'])
        floor = (.95 if row['case'] == 'sqr' or row['case'] == 'scalar_mul_17' else 1.05)
        assert paired >= floor, (name, row['case'])

cold = json.loads((here / 'cold-dbl.json').read_text())
assert all(len(cold['raw'][variant]) == 7 for variant in ('incumbent', 'candidate'))
for variant, runs in cold['raw'].items():
    assert math.isclose(cold['median_ns'][variant],
                        statistics.median(run['cold_dbl_ns'] for run in runs))
assert all(run['cached_exponents_after'] == [2] for run in cold['raw']['candidate'])
assert all(run['cached_exponents_after'] == [] for run in cold['raw']['incumbent'])
assert 'Ran 5 tests' in (here / 'local-ic-tests-v3.log').read_text()
assert 'Ran 14 tests' in (here / 'python39-artifact.log').read_text()
print('ONB curve-squaring archive and exact outputs verified')
