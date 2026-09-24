"""Check the coordinate source, exact outputs, and recorded stage gates."""

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
baseline = '12bd1f54d807456f30a421acc8ae69614842f5bce174962b904547378e6493f0'
assert hashlib.sha256((here / 'baseline/field.py').read_bytes()).hexdigest() == baseline
source = root / 'ecc2k130/codegen/field.py'
accepted = '0fe128a2aa80b9601b307be0f3b1e94f0206944b5f7cf3e7b9782583b1345e39'
if hashlib.sha256(source.read_bytes()).hexdigest() != accepted:
    source_text = source.read_text()
    cls = next(node for node in ast.parse(source_text).body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'toCoords')
    digest = hashlib.sha256(ast.get_source_segment(source_text, method).encode()).hexdigest()
    assert digest == '7ce69fbcd9f8f24c0612ab4e674fa70ddc58f40763c45c892be26f3428a0562b'

exact = subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
assert '7055' in exact
live = json.loads(subprocess.check_output([sys.executable, str(here / 'point_recovery.py')], text=True))
assert live['inputs'] == 48 and live['rounds'] == 11
for name in ('run-a.json', 'run-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(row['m'], row['pattern']) for row in rows] == \
        [(5, 'random'), (9, 'random'), (131, 'random'),
         (131, 'sparse'), (131, 'audit_trace')]
    for row in rows:
        assert math.isclose(row['old_ns'] / row['new_ns'], row['speedup'])
        floor = 2 if row['pattern'] == 'audit_trace' else \
            (5 if row['m'] == 131 else 1.2)
        assert row['speedup'] >= floor, (name, row)
for name in ('point-recovery-a.json', 'point-recovery-b.json'):
    row = json.loads((here / name).read_text())
    assert row['input_sha256'] == live['input_sha256']
    assert row['successful_points'] == live['successful_points']
    assert math.isclose(row['paired_speedup'], statistics.median(a / b for a, b in row['pairs']))
assert 'Ran 5 tests' in (here / 'local-ic-tests.log').read_text()
print('ONB coordinate archive and exact outputs verified')
