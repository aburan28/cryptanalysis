"""Check the tracked source, held snapshots, arithmetic, and timing receipts."""

import ast
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path


here = Path(__file__).resolve().parent
root = here.parents[2]
sources = {
    'baseline/field.py': '81d0397473a2a55b06a04b19991382a2c3dd1c73ba515921dd7305a10b72dc5f',
    'field-v1.py': '261599ed60b776e9f3d58682e2e3d44e01e78ec85f55b6809d424f36ae623b0f',
    'field-v2.py': '28fe300abd32c9b7b1233895d03ef06edc386116806c2006989cbe96f9bb7dae',
    'field-v3.py': 'af8ea9303e63580cf324dbe92fd72443d87e0cfd3e74a4260337552fae3fe934',
    'field-v4.py': 'c437d4f00b0c3faba2785d22a0a0fa36309c503cf6f93eb245ca797aa351e719',
}
for name, expected in sources.items():
    actual = hashlib.sha256((here / name).read_bytes()).hexdigest()
    assert actual == expected, (name, actual)
accepted = root / 'ecc2k130/codegen/field.py'
accepted_hash = hashlib.sha256(accepted.read_bytes()).hexdigest()
if accepted_hash not in (
    'c8a39e9a28df54138d094e649f5bf5db1ac5390bbfe23fc28d9620a5fbbeb8c7',
    # The adaptive descendant pins this exact new source in its own archive.
    'dded18a11f243fa269277bfe3513f12a83e9eb28300becf08c9f3d6b5634a07e',
    # The public inversion descendant pins this exact source separately.
    '2784e218bed1e9ed0af70955ef7e9983d216ef5f3eea00851949665325de97bd',
):
    # A descendant branch may optimize another method in the same field file.
    source_text = accepted.read_text()
    cls = next(node for node in ast.parse(source_text).body
               if isinstance(node, ast.ClassDef) and node.name == 'Onb')
    for name, expected in (
        ('__init__', '500bbeb9208034a5b17f610925d3596f653c692dc9c57e6ba7556d5af4eaa562'),
        ('frob', 'f30fc85250a43263e2bd2d56f61f45c6367a344d0361798adc4e3d2e5c248820'),
    ):
        method = next(node for node in cls.body
                      if isinstance(node, ast.FunctionDef) and node.name == name)
        actual = hashlib.sha256(ast.get_source_segment(source_text, method).encode()).hexdigest()
        assert actual == expected, (name, actual)

verification = subprocess.check_output([sys.executable, str(here / 'verify.py')], text=True)
assert '53368' in verification
portable = json.loads(subprocess.check_output(
    [sys.executable, str(here / 'point_recovery_portable.py')], text=True))
assert portable['input_sha256'] == \
    'ebeacda4622103812d32493a4e5924e3f9e705e7ca55a4a983fb06e3b70eb1e9'
assert portable['successful_points'] == 25

for name in ('run-v5-a.json', 'run-v5-b.json'):
    rows = json.loads((here / name).read_text())
    for row in rows:
        assert math.isclose(row['old_ns'] / row['new_ns'], row['speedup'])
        if row['case'] == 'frob' and row['m'] in (5, 9):
            assert row['speedup'] >= .95, (name, row)
    wide = [row['speedup'] for row in rows if row['case'] == 'frob' and row['m'] == 131]
    assert len(wide) == 2 and math.sqrt(wide[0] * wide[1]) >= 1.15
    halftrace = next(row for row in rows if row['case'] == 'halftrace')
    assert halftrace['speedup'] >= 1.10
for name in ('point-recovery-portable-a.json', 'point-recovery-portable-b.json'):
    result = json.loads((here / name).read_text())
    assert result['input_sha256'] == portable['input_sha256']
    assert result['successful_points'] == 25
    assert result['speedup'] >= 1.05
    assert math.isclose(result['old_ns'] / result['new_ns'], result['speedup'])

cold = json.loads((here / 'cold-memory.json').read_text())
extra = cold['traced_memory']['candidate']['peak_traced_bytes'] - \
    cold['traced_memory']['incumbent']['peak_traced_bytes']
assert 0 < extra <= 4 * 1024 * 1024
assert all(len(cold['raw'][name]) == 5 for name in ('incumbent', 'candidate'))
print('ONB Frobenius archive and exact outputs verified')
