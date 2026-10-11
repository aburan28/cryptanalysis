"""Extract exact internal GF(2) matrices from fixed Boolean hybrid inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
fixtures = json.loads((HERE.parent / 'fixtures.json').read_text())
matrices = []
for fixture in fixtures:
    if fixture['nvars'] != 12 or fixture['seed'] > 2: continue
    path = HERE / 'results' / (fixture['name']+'-matrix.json')
    equations = fixture['equations']
    payload = f"12 {len(equations)} 8 8\n" + ''.join(f'{len(g)} {" ".join(map(str, g))}\n' for g in equations)
    run = subprocess.run([str(HERE / 'build/capture-m4ri')], input=payload, text=True, capture_output=True,
                         env={**os.environ, 'GB_CAPTURE_MATRIX': str(path)}, check=True, timeout=30)
    matrix = json.loads(path.read_text())
    matrix['name'] = fixture['name']
    matrix['source_fixture_sha256'] = hashlib.sha256(json.dumps(fixture, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    matrices.append(matrix)
    print(matrix['name'], matrix['rows'], matrix['cols'], flush=True)
(HERE / 'matrices.json').write_text(json.dumps(matrices, separators=(',', ':'))+'\n')
