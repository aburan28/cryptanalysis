"""Run frozen Koblitz Frobenius scalar cases in fresh Python processes."""

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
parser.add_argument('--intent', choices=('intent-primary.json', 'intent-confirm.json'),
                    required=True)
parser.add_argument('--run', required=True)
args = parser.parse_args()
intent = json.loads((HERE / args.intent).read_text())
paths = {
    'baseline-local': HERE / 'baseline/curves-local.py',
    'baseline-runner': HERE / 'baseline/curves-runner.py',
    'candidate-local': HERE / 'source/curves-local.py',
    'candidate-runner': HERE / 'source/curves-runner.py',
    'field-local': ROOT / 'ecc2k130/codegen/field.py',
    'field-runner': ROOT / 'ecc2k130/runner/codegen/field.py',
    'benchmark': HERE / 'benchmark.py',
    'run': HERE / 'run.py',
}
for name, expected in intent['source_sha256'].items():
    assert hashlib.sha256(paths[name].read_bytes()).hexdigest() == expected, name

out = HERE / args.run
out.mkdir(exist_ok=False)
for i, case in enumerate(intent['cases']):
    receipt = out / ('cell-%02d.json' % i)
    command = [sys.executable, str(HERE / 'benchmark.py'),
               '--variant', case['variant'], '--degree', str(case['degree']),
               '--bits', str(case['bits']), '--seed', str(case['seed']),
               '--rounds', str(case['rounds']), '--out', str(receipt)]
    started = time.perf_counter()
    with (out / ('cell-%02d.log' % i)).open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=intent['resource_budget']['per_case_seconds'])
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    (out / ('cell-%02d-parent.json' % i)).write_text(json.dumps({
        'case': case, 'status': status,
        'parent_seconds': time.perf_counter() - started,
        'command': command,
    }, indent=2) + '\n')
    if status != 0:
        raise RuntimeError('cell %d failed: %s' % (i, status))
    raw = json.loads(receipt.read_text())
    assert raw['exact_output_agreement']
    median = raw['median_operation_ns']
    print('cell %d %s m%d %db: %.3fx' % (
        i, case['variant'], case['degree'], case['bits'],
        median['baseline']/median['candidate']), flush=True)
