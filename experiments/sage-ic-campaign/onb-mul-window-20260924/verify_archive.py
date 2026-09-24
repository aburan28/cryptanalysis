"""Verify the multiplication source, exact outputs, and recorded stage gates."""

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
    ('baseline/field.py', 'c8a39e9a28df54138d094e649f5bf5db1ac5390bbfe23fc28d9620a5fbbeb8c7'),
    ('field-v1.py', '22c109bf6dd0fafe60b83e19ccb3ac9387c237addf7599885859e0c19aeda51f'),
):
    actual = hashlib.sha256((here / name).read_bytes()).hexdigest()
    assert actual == expected, (name, actual)
source = root / 'ecc2k130/codegen/field.py'
accepted = '12bd1f54d807456f30a421acc8ae69614842f5bce174962b904547378e6493f0'
if hashlib.sha256(source.read_bytes()).hexdigest() != accepted:
    # A descendant branch may optimize another method in the same field file.
    cls = next(node for node in ast.parse(source.read_text()).body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'mul')
    digest = hashlib.sha256(ast.dump(method, include_attributes=False).encode()).hexdigest()
    assert digest == '918603425bd80238b48bd39c55979a5725ad0017ed13a3b6960c8a538da278cb'

verification = subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
assert '3087' in verification
live = json.loads(subprocess.check_output([sys.executable, str(here / 'point_ops.py')], text=True))
assert len(live) == 5 and len({row['input_sha256'] for row in live}) == 1
assert live[0]['input_sha256'] == 'cdcb6074437b37c45f63c4dcc85d6696247a8bdb57241ee2816f21545bb257fb'

field_cases = [(5, 'random'), (9, 'random'), (131, 'random'),
               (131, 'sparse'), (131, 'dense')]
for name in ('run-v2-a.json', 'run-v2-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(row['m'], row['pattern']) for row in rows] == field_cases
    for row in rows:
        assert math.isclose(row['old_ns'] / row['new_ns'], row['speedup'])
        floor = (1.25 if row['pattern'] == 'random' and row['m'] == 131 else
                 1.15 if row['pattern'] == 'dense' else .95)
        assert row['speedup'] >= floor, (name, row)

for name in ('point-ops-v4-a.json', 'point-ops-v4-b.json'):
    rows = json.loads((here / name).read_text())
    assert [row['case'] for row in rows] == \
        ['pointFromX', 'add', 'dbl', 'scalar_mul_17', 'frob_control']
    for row in rows:
        paired = statistics.median(a / b for a, b in row['pairs'])
        assert math.isclose(paired, row['paired_speedup'])
        assert row['input_sha256'] == live[0]['input_sha256']
        assert len(row['pairs']) == 11
        assert paired >= (.95 if row['case'] == 'frob_control' else 1.05), (name, row)
assert 'Ran 5 tests' in (here / 'local-ic-tests.log').read_text()
print('ONB multiplication archive and exact outputs verified')
