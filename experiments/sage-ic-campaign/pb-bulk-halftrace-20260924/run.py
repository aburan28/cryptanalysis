"""Run frozen polynomial-basis factor-base cells in fresh processes."""

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
    'field': ROOT / 'ecc2k130/runner/codegen/field.py',
    'baseline-curves-local': HERE / 'baseline/curves-local.py',
    'baseline-curves-runner': HERE / 'baseline/curves-runner.py',
    'candidate-curves-local': HERE / 'source/curves-local.py',
    'candidate-curves-runner': HERE / 'source/curves-runner.py',
    'baseline-indexcalc': HERE / 'baseline/indexcalc.py',
    'candidate-indexcalc': HERE / 'source/indexcalc.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
for name, expected in intent['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name
out = HERE / ('run-' + args.run + '-001')
out.mkdir(exist_ok=False)
for case in intent['cases']:
    if case['run'] != args.run:
        continue
    stem = 'degree-%d' % case['degree']
    receipt = out / (stem + '.json')
    command = [sys.executable, str(HERE / 'benchmark.py'),
               '--degree', str(case['degree']), '--weight', str(case['weight']),
               '--order', case['order'], '--rounds', str(case['rounds']),
               '--out', str(receipt)]
    started = time.perf_counter()
    with (out / (stem + '.log')).open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_case_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / (stem + '-parent.json')).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - started,
        'command': command,
    }, indent=2) + '\n')
    if status != 0:
        raise RuntimeError('degree %d failed: %s' % (case['degree'], status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    ns = raw['median_operation_ns']
    print('m%d weight%d: %d points, %d orbits, %.3fx' % (
        case['degree'], case['weight'], raw['actual_base_points'],
        raw['orbits'], ns['baseline'] / ns['candidate']), flush=True)
