"""Run cold paired arms in separate Sage processes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
SAGE_ROOT = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary')
intent = json.loads((HERE / 'intent-cold.json').read_text())
for name, expected in intent['source_sha256'].items():
    actual = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
    assert actual == expected, (name, actual)

out = HERE / 'run-cold-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-batch'
for index, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % index)
    command = [str(SAGE_ROOT / 'sage'), '-python', str(HERE / 'cold.py'),
               '--points', str(case['points']), '--groups', str(case['groups']),
               '--seed', str(case['seed']), '--arm', case['arm'],
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
        raise RuntimeError('cold cell %d failed: %s' % (index, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    print('cold cell %d: %s %.3f ms' % (
        index, case['arm'], raw['setup_plus_operation_ns']/1e6), flush=True)
