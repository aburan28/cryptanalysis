"""Run frozen instrumented Metal bridge cells in fresh Sage processes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


here = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--run', default='run-001')
args = parser.parse_args()
sage = Path('/Volumes/SSD990/cryptanalysis/third_party/sage-binary/sage')
native = Path('/private/tmp/codex-metal-host-timing/libinstrumented.dylib')
baseline = json.loads((here / 'intent.json').read_text())
intent = json.loads((here / 'intent-run.json').read_text())
for name, path in (
    ('instrumented_source_sha256', here / 'source/instrumented_metal.mm'),
    ('profile_script_sha256', here / 'profile_bridge.py'),
    ('build_script_sha256', here / 'build.sh'),
    ('instrumented_binary_sha256', native),
):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == intent[name], name
for name, expected in baseline['baseline_source_sha256'].items():
    assert hashlib.sha256((here / 'source' / name).read_bytes()).hexdigest() == expected
out = here / args.run
out.mkdir(exist_ok=False)
env = os.environ.copy()
env['DOT_SAGE'] = '/private/tmp/codex-sage-metal-profile'
env.pop('SAGE_BINARY_NATIVE', None)
env.pop('SAGE_BINARY_CODEC', None)
for i, case in enumerate(baseline['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [str(sage), '-python', str(here / 'profile_bridge.py'),
               '--degree', str(case['degree']), '--points', str(case['points']),
               '--power', str(case['power']), '--seed', str(case['seed']),
               '--native', str(native), '--out', str(receipt)]
    start = time.perf_counter()
    with (out / ('cell-%02d.log' % i)).open('w') as log:
        try:
            result = subprocess.run(command, env=env, stdout=log,
                                    stderr=subprocess.STDOUT,
                                    timeout=baseline['resource_budget']['per_cell_seconds'])
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
    assert raw['instrumented_native_sha256'] == intent['instrumented_binary_sha256']
    assert raw['installed_native_sha256'] == baseline['installed_native_sha256']
    print('host cell %d n=%d complete' % (i, case['points']), flush=True)
