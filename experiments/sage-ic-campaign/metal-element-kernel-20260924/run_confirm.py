"""Run frozen independent kernel confirmation cells in fresh Sage processes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
SAGE = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary/sage')
intent = json.loads((HERE / 'intent-confirm-v2.json').read_text())
for name, expected in intent['source_sha256'].items():
    if name in ('libelement.dylib', 'installed-native.dylib'):
        path = (Path('/private/tmp/codex-metal-element-kernel/libelement.dylib')
                if name == 'libelement.dylib' else
                Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary/local/var/'
                     'lib/sage/venv-python3.14/lib/python3.14/site-packages/'
                     'sage/schemes/elliptic_curves/_binary_hardware_native.dylib'))
    else:
        path = HERE / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name

out = HERE / 'confirm-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-element'
for i, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [str(SAGE), '-python', str(HERE / 'pilot.py'),
               '--points', str(case['points']), '--groups', str(case['groups']),
               '--seed', str(case['seed']), '--rounds', str(case['rounds']),
               '--out', str(receipt)]
    start = time.perf_counter()
    with (out / ('cell-%02d.log' % i)).open('w') as log:
        try:
            result = subprocess.run(command, env=env, stdout=log,
                                    stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_case_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('cell-%02d-parent.json' % i)).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - start,
        'command': command,
    }, indent=2) + '\n')
    if status != 0:
        raise RuntimeError('confirm cell %d failed: %s' % (i, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    print('cell %d: %s' % (i, raw['median_operation_ns']), flush=True)
