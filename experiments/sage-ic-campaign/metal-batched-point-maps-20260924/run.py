"""Run the frozen independent-batch cells in fresh Sage processes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
SAGE_ROOT = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary')
intent = json.loads((HERE / 'intent.json').read_text())
paths = {
    'baseline.py': HERE / 'baseline/binary_hardware.py',
    'candidate.py': HERE / 'source/binary_hardware.py',
    'benchmark.py': HERE / 'benchmark.py',
    'run.py': HERE / 'run.py',
    'installed.py': SAGE_ROOT / 'src/sage/schemes/elliptic_curves/binary_hardware.py',
    'native.dylib': (SAGE_ROOT / 'local/var/lib/sage/venv-python3.14/lib/python3.14/'
                     'site-packages/sage/schemes/elliptic_curves/_binary_hardware_native.dylib'),
}
for name, expected in intent['source_sha256'].items():
    actual = hashlib.sha256(paths[name].read_bytes()).hexdigest()
    assert actual == expected, (name, actual)

out = HERE / 'run-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-batch'
for index, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % index)
    command = [str(SAGE_ROOT / 'sage'), '-python', str(HERE / 'benchmark.py'),
               '--points', str(case['points']), '--groups', str(case['groups']),
               '--seed', str(case['seed']), '--rounds', str(case['rounds']),
               '--out', str(receipt)]
    start = time.perf_counter()
    with (out / ('cell-%02d.log' % index)).open('w') as log:
        try:
            result = subprocess.run(command, env=env, stdout=log,
                                    stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_case_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('cell-%02d-parent.json' % index)).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - start,
        'command': command,
    }, indent=2) + '\n')
    if status != 0:
        raise RuntimeError('cell %d failed: %s' % (index, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    print('cell %d: %s' % (index, raw['median_operation_ns']), flush=True)
