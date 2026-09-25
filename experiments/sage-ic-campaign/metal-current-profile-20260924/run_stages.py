"""Run frozen stage profile in fresh installed Sage/Metal processes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


here = Path(__file__).resolve().parent
root = here.parents[2]
sage = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary/sage')
profile = here / 'profile_stages.py'
intent = json.loads((here / 'intent-stages.json').read_text())
parent_intent = json.loads((here / 'intent.json').read_text())
assert hashlib.sha256(profile.read_bytes()).hexdigest() == intent['profile_script_sha256']
assert hashlib.sha256((here / 'intent.json').read_bytes()).hexdigest() == \
    intent['parent_intent_sha256']
assert parent_intent['source_sha256']['binary_hardware.py'] == \
    'a895cf65a28f52e1b7703a7121213b394f9cb814338bdfe104dd48fa728d2de0'
out = here / 'run-stages-001'
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-profile'
env['SAGE_BINARY_USE_INSTALLED'] = '1'
env.pop('SAGE_BINARY_NATIVE', None)
env.pop('SAGE_BINARY_CODEC', None)
for i, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [str(sage), '-python', str(profile),
               '--degree', str(case['degree']), '--points', str(case['points']),
               '--power', str(case['power']), '--seed', str(case['seed']),
               '--out', str(receipt)]
    start = time.perf_counter()
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
        raise SystemExit('FAILED cell %d: %s' % (i, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    assert raw['source_sha256'] == parent_intent['source_sha256']['binary_hardware.py']
    assert raw['loaded_artifacts']['installed']
    print('stage cell %d n=%d p=%d complete' % (i, case['points'], case['power']),
          flush=True)
