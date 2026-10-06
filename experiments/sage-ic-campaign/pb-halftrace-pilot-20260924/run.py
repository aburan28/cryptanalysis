"""Run frozen half-trace cold/warm cells in separate processes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--run', choices=('primary', 'confirm'), required=True)
args = parser.parse_args()
intent = json.loads((HERE / 'intent.json').read_text())
paths = {
    'field': ROOT / 'experiments/sage-ic-campaign/pb-squaring-20260924/source/field-local.py',
    'curves': ROOT / 'experiments/sage-ic-campaign/pb-trace-mask-20260924/source/curves-local.py',
    'pilot': HERE / 'pilot.py',
}
for name, expected in intent['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name
out = HERE / ('run-' + args.run + '-001')
out.mkdir(exist_ok=True)
for case in intent['cases']:
    if case['run'] != args.run:
        continue
    receipt = out / ('degree-%d.json' % case['degree'])
    command = [sys.executable, str(HERE / 'pilot.py'),
               '--degree', str(case['degree']), '--seed', str(case['seed']),
               '--out', str(receipt)]
    started = time.perf_counter()
    with (out / ('degree-%d.log' % case['degree'])).open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_case_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('degree-%d-parent.json' % case['degree'])).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - started,
        'command': command,
    }, indent=2) + '\n')
    if status != 0:
        raise RuntimeError('degree %d failed: %s' % (case['degree'], status))
    print((out / ('degree-%d.log' % case['degree'])).read_text().strip(), flush=True)
