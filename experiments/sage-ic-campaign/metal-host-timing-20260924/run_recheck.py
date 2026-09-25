"""Repeat four frozen native/CPU/Metal point-call cells in fresh workers."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


here = Path(__file__).resolve().parent
root = here.parents[2]
sage = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary/sage')
benchmark = root / 'experiments/sage-binary-hardware/benchmark.py'
intent = json.loads((here / 'intent-recheck.json').read_text())
assert hashlib.sha256(benchmark.read_bytes()).hexdigest() == intent['benchmark_sha256']
out = here / 'run-recheck-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-profile'
env['SAGE_BINARY_USE_INSTALLED'] = '1'
env.pop('SAGE_BINARY_NATIVE', None)
env.pop('SAGE_BINARY_CODEC', None)
for i, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [str(sage), '-python', str(benchmark), '--worker',
               '--phase', 'host-timing-recheck',
               '--degree', str(case['degree']), '--points', str(case['points']),
               '--power', str(case['power']), '--seed', str(case['seed']),
               '--out', str(receipt)]
    start = time.perf_counter()
    with (out / ('cell-%02d.log' % i)).open('w') as log:
        try:
            result = subprocess.run(command, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=300)
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('cell-%02d-parent.json' % i)).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - start,
        'command': command}, indent=2) + '\n')
    if status != 0:
        raise SystemExit('FAILED cell %d: %s' % (i, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    assert raw['source_sha256'] == intent['installed_module_sha256']
    assert raw['loaded_artifacts']['files']['native']['sha256'] == \
        intent['installed_native_sha256']
    print('recheck cell %d n=%d complete' % (i, case['points']), flush=True)
