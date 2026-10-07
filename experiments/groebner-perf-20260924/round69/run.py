"""Retain exact controls and balanced identity-stage diagnostics on frozen inputs."""
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import numpy as np
from inputs import generate, FIXTURE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDIT_SOURCES = ('round44/tagged_reference.py', 'round34/affine_reference.py',
                 'round43/reference.py', 'round27/reference.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def parse_csv(path):
    return [{k: v if k == 'status' else float(v) if k.endswith('_seconds') or k.startswith('load_') else int(v)
             for k, v in row.items()} for row in csv.DictReader(path.open())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-unavailable', action='store_true')
    parser.add_argument('--physical-hardware', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    assert status == '', 'Commit the experiment before measuring.'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    sources = dict(receipt['sources'])
    for path in [FIXTURE, *(HERE.parent / v for v in AUDIT_SOURCES), *(HERE / 'fixtures').iterdir()]:
        sources[str(path.relative_to(HERE.parent))] = sha(path)
    for relative, digest in sources.items():
        path = HERE.parent / relative
        assert sha(path) == digest
        blob = subprocess.check_output(['git', 'show', commit + ':' + str(path.relative_to(ROOT))], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == digest
    for section in ('binaries', 'generated'):
        for relative, digest in receipt[section].items():
            assert sha(HERE / 'build' / relative) == digest
    shutil.copytree(HERE / 'build', out / 'build')
    report = {'schema': 'independent-multiplier-diagnostic/1', 'status': 'RUNNING',
              'source_commit': commit, 'source_status': status, 'sources': sources,
              'build_receipt_sha256': sha(HERE / 'build/receipt.json'),
              'architecture': platform.machine(), 'platform': platform.platform(),
              'python': platform.python_version(), 'numpy': np.__version__, 'cpu_count': os.cpu_count(),
              'physical_hardware': True if args.physical_hardware else None,
              'metal_enabled': receipt['metal_enabled'], 'controls': [], 'records': [],
              'timing_eligible': False, 'host_isolation_receipt': None, 'aggregate_speedup': None,
              'scope': 'Exact independent multiplier identities only. Per-call validation, full coefficient/proof/index upload, result initialization, dispatch, wait, readback and failure accounting charged. Original-ANF reconstruction, proof selection, allocation/pipeline setup and separate exact comparisons excluded and retained. Not a complete query or IC/rho measurement.'}
    if platform.system() == 'Darwin':
        report['hardware'] = subprocess.check_output(['/usr/sbin/sysctl', 'hw.model', 'machdep.cpu.brand_string',
                                                      'hw.physicalcpu', 'hw.logicalcpu', 'hw.memsize'], text=True)
    write(out / 'report.json', report)
    try:
        with (out / 'probe.log').open('w') as log:
            probe = subprocess.run([str(HERE / 'build/test'), '--probe'], stdout=log, stderr=subprocess.STDOUT)
        report['probe'] = {'exit_code': probe.returncode, 'log_sha256': sha(out / 'probe.log')}
        assert probe.returncode in (0, 77)
        report['metal_available'] = probe.returncode == 0
        if receipt['metal_enabled'] and not report['metal_available'] and not args.allow_unavailable:
            raise RuntimeError('Requested physical Metal unavailable')
        for name in ('test', 'test-ubsan', 'test-unavailable', 'test-unavailable-ubsan'):
            with (out / (name + '.log')).open('w') as log:
                result = subprocess.run([str(HERE / 'build' / name)], stdout=log, stderr=subprocess.STDOUT)
            report['controls'].append({'name': name, 'exit_code': result.returncode, 'log_sha256': sha(out / (name + '.log'))})
            write(out / 'report.json', report)
            assert result.returncode == 0, name
        inputs = generate(out / 'inputs')
        plan = {'schema': 'independent-multiplier-panel/1', 'inputs': inputs,
                'arms': ['cpu_factored_local', 'metal_record', 'metal_coefficient'],
                'orders': list(itertools.permutations(range(3))) * 3, 'warmup_order': [0, 1, 2],
                'absent_device_policy': 'Retain unavailable device and execute only arm 0 at its original positions.',
                'timing_eligible': False, 'host_isolation_receipt': None, 'aggregate_speedup': None}
        write(out / 'plan.json', plan)
        report['plan_sha256'] = sha(out / 'plan.json')
        for item in inputs:
            for binary in ('bench', 'bench-ubsan'):
                path = out / (item['name'] + '-' + binary + '.csv')
                with path.open('w') as output, path.with_suffix('.stderr').open('w') as errors:
                    result = subprocess.run([str(HERE / 'build' / binary), item['input_path']], stdout=output, stderr=errors)
                record = {'name': item['name'], 'binary': binary, 'exit_code': result.returncode,
                          'output_sha256': sha(path), 'stderr_sha256': sha(path.with_suffix('.stderr'))}
                report['records'].append(record)
                write(out / 'report.json', report)
                assert result.returncode == 0, record
                rows = parse_csv(path)
                assert len(rows) == (57 if report['metal_available'] else 19) and all(row['status'] == 'PASS' for row in rows)
                record['rows'] = rows
                arms = range(3) if report['metal_available'] else (0,)
                record['median_ms'] = {str(a): statistics.median(row['outer_seconds'] * 1000 for row in rows if row['arm'] == a and not row['warmup']) for a in arms}
                record['paired_difference_ms'] = {str(a): [1000 * (next(v['outer_seconds'] for v in rows if v['trial'] == t and v['arm'] == a)
                                                                 - next(v['outer_seconds'] for v in rows if v['trial'] == t and v['arm'] == 0)) for t in range(18)] for a in arms if a}
                write(out / 'report.json', report)
                print('PANEL_PASS', item['name'], binary, record['median_ms'], flush=True)
        for relative, digest in sources.items():
            assert sha(HERE.parent / relative) == digest
        report['status'] = 'PASS'
    except BaseException as error:
        report.update(status='FAIL', error=repr(error))
        raise
    finally:
        write(out / 'report.json', report)


if __name__ == '__main__':
    main()
