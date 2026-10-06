"""Run frozen installed-Sage CPU/Metal cells with exact source binding."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


here = Path(__file__).resolve().parent
root = here.parents[2]
installed_root = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary')
source = installed_root / 'src/sage/schemes/elliptic_curves'
package = installed_root / ('local/var/lib/sage/venv-python3.14/lib/python3.14/'
                            'site-packages/sage/schemes/elliptic_curves')
benchmark = root / 'experiments/sage-binary-hardware/benchmark.py'
loader = root / 'experiments/sage-binary-hardware/load_hardware.py'
sage = installed_root / 'sage'
intent = json.loads((here / 'intent.json').read_text())
paths = {
    'benchmark.py': benchmark,
    'load_hardware.py': loader,
    'binary_hardware.py': source / 'binary_hardware.py',
    'binary_hardware_metal.mm': source / 'binary_hardware_metal.mm',
    'binary_hardware_codec.pyx': source / 'binary_hardware_codec.pyx',
    '_binary_hardware_native.dylib': package / '_binary_hardware_native.dylib',
    'binary_hardware_codec.cpython-314-darwin.so': package / 'binary_hardware_codec.cpython-314-darwin.so',
}
for name, expected in intent['source_sha256'].items():
    actual = hashlib.sha256(paths[name].read_bytes()).hexdigest()
    assert actual == expected, (name, actual)

out = here / 'run-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-profile'
env['SAGE_BINARY_USE_INSTALLED'] = '1'
env.pop('SAGE_BINARY_NATIVE', None)
env.pop('SAGE_BINARY_CODEC', None)
sys.path.insert(0, str(benchmark.parent))
from benchmark import summarize


rows = []
for i, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [str(sage), '-python', str(benchmark), '--worker',
               '--phase', 'current-metal-profile', '--seed', str(case['seed']),
               '--degree', str(case['degree']), '--points', str(case['points']),
               '--power', str(case['power']), '--out', str(receipt)]
    start = time.perf_counter()
    status = None
    with (out / ('cell-%02d.log' % i)).open('w') as log:
        try:
            result = subprocess.run(command, env=env, stdout=log,
                                    stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_cell_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('cell-%02d-parent.json' % i)).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - start,
        'command': command}, indent=2) + '\n')
    if status != 0:
        print('FAILED cell', i, status, flush=True)
        break
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    assert raw['loaded_artifacts']['installed']
    assert raw['loaded_artifacts']['files']['module']['sha256'] == \
        intent['source_sha256']['binary_hardware.py']
    row = summarize(raw)
    rows.append(row)
    (out / 'summary.json').write_text(json.dumps({
        'rows': rows, 'complete': len(rows) == len(intent['cases']),
        'failed_cell': None if len(rows) == len(intent['cases']) else len(rows)},
        indent=2) + '\n')
    print('cell %d GF(2^%d) n=%d p=%d CPU %.3fx Metal %.3fx Metal/CPU %.3fx' % (
        i, case['degree'], case['points'], case['power'],
        row['full_speedup']['cpu'], row['full_speedup']['metal'],
        row['full_gpu_speedup_vs_native_cpu']), flush=True)
if len(rows) != len(intent['cases']):
    raise SystemExit(1)
