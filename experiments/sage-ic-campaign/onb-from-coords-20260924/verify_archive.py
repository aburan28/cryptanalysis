"""Check the coordinate-packing source, exact outputs, and stage gates."""

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
    ('baseline/field.py', '0fe128a2aa80b9601b307be0f3b1e94f0206944b5f7cf3e7b9782583b1345e39'),
    ('field-v1.py', 'e651d6118573fdfc2d6fe3a4b19e720aa6affd7d303fa9fb4201b11e8655bc54'),
):
    assert hashlib.sha256((here / name).read_bytes()).hexdigest() == expected, name
source = root / 'ecc2k130/codegen/field.py'
accepted = '148d795b6216254813e7dbe189e1290ae286dd9edb2b0a3c3fe2870788c81918'
if hashlib.sha256(source.read_bytes()).hexdigest() != accepted:
    text = source.read_text()
    tree = ast.parse(text)
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    nodes = (
        ('reverseByte', next(node for node in tree.body
                             if isinstance(node, ast.FunctionDef) and node.name == 'reverseByte'),
         'b3ada0cde25bc3e98a63bbb5a2cb1bef4c07fb3e0449c9c09deb6e427fc76118'),
        ('_reverseBytes', next(node for node in tree.body
                               if isinstance(node, ast.Assign) and any(
                                   isinstance(target, ast.Name) and target.id == '_reverseBytes'
                                   for target in node.targets)),
         '961c2faf2f3a13140244a7b1f248aca43a2f9b4cb5796c445a409dd6d89af369'),
        ('fromCoords', next(node for node in cls.body
                            if isinstance(node, ast.FunctionDef) and node.name == 'fromCoords'),
         '1e6c188a74cd7f03a38894ecde400972d80d64d584127b9db11f9f4694cc3dfa'),
    )
    for name, node, expected in nodes:
        actual = hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest()
        assert actual == expected, (name, actual)

exact = subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
assert '6866' in exact
live = json.loads(subprocess.check_output([sys.executable, str(here / 'point_build.py')], text=True))
assert live['inputs'] == 64 and live['rounds'] == 11
for name in ('run-v2-a.json', 'run-v2-b.json'):
    rows = json.loads((here / name).read_text())
    assert [(row['m'], row['pattern']) for row in rows] == \
        [(5, 'random'), (9, 'random'), (131, 'random'),
         (131, 'sparse_one'), (131, 'sparse_two'), (131, 'dense')]
    for row in rows:
        assert math.isclose(row['old_ns'] / row['new_ns'], row['speedup'])
        floor = .95 if row['m'] in (5, 9) else \
            (2 if row['pattern'] in ('sparse_one', 'sparse_two') else 1.1)
        assert row['speedup'] >= floor, (name, row)
for name in ('point-build-v2-a.json', 'point-build-v2-b.json'):
    row = json.loads((here / name).read_text())
    assert row['input_sha256'] == live['input_sha256']
    assert row['successful_points'] == live['successful_points']
    assert math.isclose(row['paired_speedup'], statistics.median(a / b for a, b in row['pairs']))
assert 'Ran 5 tests' in (here / 'local-ic-tests.log').read_text()
print('ONB coordinate-packing archive and exact outputs verified')
