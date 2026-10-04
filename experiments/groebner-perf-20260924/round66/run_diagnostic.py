"""Retain all ordered kernel controls; timings cannot establish query speedup."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    subprocess.run([sys.executable, str(HERE/'prepare_inputs.py'), '--validation',
                    str(args.validation), '--output', str(args.output/'inputs')], check=True)
    receipt = json.loads((HERE/'build/receipt.json').read_text())
    bound = {str(HERE/name): digest for name, digest in receipt['sources'].items()}
    bound.update({str(HERE/'build'/name): digest for name, digest in receipt['binaries'].items()})
    bound[str(HERE/'build/receipt.json')] = sha(HERE/'build/receipt.json')
    plan = json.loads((args.output/'inputs/plan.json').read_text())
    result = {'status': 'RUNNING', 'plan_sha256': sha(args.output/'inputs/plan.json'),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
              'source_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=HERE, text=True),
              'architecture': platform.machine(), 'platform': platform.platform(),
              'timing_eligible': False, 'host_isolation_receipt': None, 'aggregate_speedup': None,
              'executed_bindings': bound, 'controls': [], 'records': []}
    assert not result['source_status'], 'Commit the frozen experiment before measuring.'
    for name in ('test-constant', 'test-constant-ubsan'):
        with (args.output/(name+'.log')).open('w') as log:
            run = subprocess.run([str(HERE/'build'/name)], stdout=log, stderr=subprocess.STDOUT)
        result['controls'].append({'name': name, 'exit_code': run.returncode})
        if run.returncode:
            (args.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
            raise RuntimeError('control failed')
    for item in plan['records']:
        path = args.output/'inputs'/(item['name']+'.bin')
        assert sha(path) == item['input_sha256']
        for binary in ('bench-constant', 'bench-constant-ubsan'):
            output = args.output/(item['name']+'-'+binary+'.csv')
            errors = output.with_suffix('.stderr')
            load_start = os.getloadavg()
            with output.open('w') as log, errors.open('w') as err:
                run = subprocess.run([str(HERE/'build'/binary), str(path)], stdout=log, stderr=err)
            record = {'name': item['name'], 'binary': binary, 'exit_code': run.returncode,
                      'load_start': load_start, 'load_end': os.getloadavg(),
                      'output_sha256': sha(output), 'stderr_sha256': sha(errors),
                      'timing_eligible': False, 'kernel_only': True}
            result['records'].append(record)
            (args.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')
            if run.returncode: raise RuntimeError('kernel control failed')
            rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(output.open())]
            assert len(rows) == 90
            for i, row in enumerate(rows):
                assert row['trial'] == i//3 and row['position'] == i%3
                assert row['arm'] == plan['arm_orders'][i//3][i%3] and row['valid'] == 1
            record['rows'] = rows
            record['median_ns'] = {str(arm): statistics.median(row['wall_ns'] for row in rows if row['arm'] == arm) for arm in (0,1,2)}
            print('KERNEL_PANEL_PASS', item['name'], binary, record['median_ns'], flush=True)
    for path, digest in bound.items(): assert sha(Path(path)) == digest, path
    result['status'] = 'PASS'
    (args.output/'report.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
