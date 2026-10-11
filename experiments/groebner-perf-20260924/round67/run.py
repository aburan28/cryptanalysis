"""Run and retain the transform-only panel; no complete-query or isolated speed claim."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import struct
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-unavailable', action='store_true', help='Record unavailable requested Metal and run portable controls.')
    parser.add_argument('--physical-hardware', action='store_true', help='Only set for a known physical, untranslated local host.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=HERE, text=True)
    assert not status, 'Commit the complete experiment before measuring.'
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    bound = {str(HERE / name): digest for name, digest in receipt['sources'].items()}
    bound.update({str(HERE / 'build' / name): digest for name, digest in receipt['binaries'].items()})
    bound.update({str(HERE / 'build' / name): digest for name, digest in receipt['generated'].items()})
    bound[str(HERE / 'build/receipt.json')] = sha(HERE / 'build/receipt.json')
    fixture = HERE.parent / 'round40/fixtures/inputs.json.gz'
    bound[str(fixture)] = sha(fixture)
    bound[str(HERE.parent / 'round51/producer.cpp')] = sha(HERE.parent / 'round51/producer.cpp')
    for name, digest in bound.items():
        assert sha(Path(name)) == digest, name
    for name in receipt['sources']:
        git_path = 'experiments/groebner-perf-20260924/round67/' + name
        committed = subprocess.check_output(['git', 'show', 'HEAD:' + git_path], cwd=HERE)
        assert hashlib.sha256(committed).hexdigest() == receipt['sources'][name], git_path
    shutil.copytree(HERE / 'build', out / 'build')
    result = {
        'status': 'RUNNING', 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        'source_status': status, 'architecture': platform.machine(), 'platform': platform.platform(),
        'cpu_count': os.cpu_count(), 'physical_hardware': True if args.physical_hardware else None,
        'metal_enabled': receipt['metal_enabled'],
        'host_isolation_receipt': None, 'timing_eligible': False, 'aggregate_speedup': None,
        'scope': 'Producer uint32 branch-major ascending subset transform only. GPU copy-in, command encoding, synchronization and copy-out charged. Input scatter, context setup and exact output checks outside the transform timer. Not a verified complete query.',
        'bindings': bound, 'controls': [], 'records': [],
    }
    if platform.system() == 'Darwin':
        result['hardware'] = subprocess.check_output(['/usr/sbin/sysctl', 'hw.model', 'machdep.cpu.brand_string',
                                                      'hw.physicalcpu', 'hw.logicalcpu', 'hw.memsize'], text=True)
    write(out / 'report.json', result)
    try:
        with (out / 'probe.log').open('w') as log:
            probe = subprocess.run([str(HERE / 'build/test'), '--probe'], stdout=log, stderr=subprocess.STDOUT)
        result['probe'] = {'exit_code': probe.returncode, 'log_sha256': sha(out / 'probe.log')}
        write(out / 'report.json', result)
        if probe.returncode not in (0, 77): raise RuntimeError('Metal probe failed')
        if receipt['metal_enabled'] and probe.returncode == 77 and not args.allow_unavailable:
            raise RuntimeError('Requested Metal unavailable; no implicit fallback')
        result['metal_available'] = probe.returncode == 0
        names = ['test-unavailable', 'test-unavailable-ubsan']
        if result['metal_available']: names = ['test', 'test-ubsan', *names]
        for name in names:
            with (out / (name + '.log')).open('w') as log:
                run = subprocess.run([str(HERE / 'build' / name)], stdout=log, stderr=subprocess.STDOUT)
            result['controls'].append({'name': name, 'exit_code': run.returncode, 'log_sha256': sha(out / (name + '.log'))})
            write(out / 'report.json', result)
            if run.returncode: raise RuntimeError(name + ' failed')
        if result['metal_available']:
            inputs = {item['name']: item for item in json.loads(gzip.decompress(fixture.read_bytes()))}
            names = ['n31-m3-ell6-seed101', 'n31-m3-ell8-seed201', 'n31-m3-ell9-seed201']
            orders = list(itertools.permutations(range(3))) * 3
            plan = {'arms': ['cpu', 'metal_staged', 'metal_tiled'], 'arm_orders': orders,
                    'warmup_order': [0, 1, 2], 'warmup_retained': True, 'workloads': [],
                    'timing_eligible': False, 'host_isolation_receipt': None, 'aggregate_speedup': None}
            (out / 'inputs').mkdir()
            for name in names:
                item = inputs[name]
                x, y, equations = 2 * item['ell'], item['ell'], item['n']
                terms = item['reference_anf']
                assert x + y == item['nvars'] and 0 < equations <= 32
                path = out / 'inputs' / (name + '.bin')
                with path.open('wb') as output:
                    output.write(struct.pack('<5Q', 0x3736524e52454b, x, y, equations, len(terms)))
                    for mask, coefficient in terms:
                        assert type(mask) is int and 0 <= mask < (1 << (x + y))
                        assert type(coefficient) is int and 0 <= coefficient < (1 << equations)
                        assert (mask >> x).bit_count() <= 2
                        output.write(struct.pack('<2Q', mask, coefficient))
                plan['workloads'].append({'name': name, 'x': x, 'y': y, 'equations': equations,
                                          'terms': len(terms), 'input_sha256': sha(path),
                                          'fixture_sha256': sha(fixture), 'workload_sha256': item['workload_sha256']})
            write(out / 'plan.json', plan)
            result['plan_sha256'] = sha(out / 'plan.json')
            for workload in plan['workloads']:
                for binary in ('bench', 'bench-ubsan'):
                    output = out / (workload['name'] + '-' + binary + '.csv')
                    errors = output.with_suffix('.stderr')
                    load_start = os.getloadavg()
                    with output.open('w') as log, errors.open('w') as error:
                        run = subprocess.run([str(HERE / 'build' / binary), str(out / 'inputs' / (workload['name'] + '.bin'))], stdout=log, stderr=error)
                    record = {'name': workload['name'], 'binary': binary, 'exit_code': run.returncode,
                              'load_start': load_start, 'load_end': os.getloadavg(),
                              'output_sha256': sha(output), 'stderr_sha256': sha(errors)}
                    result['records'].append(record)
                    write(out / 'report.json', result)
                    if run.returncode: raise RuntimeError('transform panel failed')
                    float_fields = {'wall', 'copy_in', 'encode', 'wait', 'copy_out', 'device', 'verification'}
                    rows = [{key: (float(value) if key in float_fields else int(value)) for key, value in row.items()}
                            for row in csv.DictReader(output.open())]
                    assert len(rows) == 57
                    for index, row in enumerate(rows):
                        trial, position = index // 3 - 1, index % 3
                        order = plan['warmup_order'] if trial == -1 else orders[trial]
                        assert (row['trial'], row['position'], row['arm'], row['valid']) == (trial, position, order[position], 1)
                        if row['arm']:
                            size = (1 << workload['x']) * (1 + workload['y'] * (workload['y'] + 1) // 2) * 4
                            dispatches = workload['x'] if row['arm'] == 1 else workload['x'] - 3
                            assert row['input_bytes'] == row['output_bytes'] == row['scratch_bytes'] == size
                            assert row['encoded_dispatches'] == row['submitted_dispatches'] == row['completed_dispatches'] == dispatches
                    record['rows'] = rows
                    record['median_ms'] = {str(arm): statistics.median(row['wall'] * 1000 for row in rows if row['arm'] == arm and row['trial'] >= 0)
                                           for arm in range(3)}
                    # Every paired difference is retained, without a promoted aggregate speed ratio.
                    record['paired_difference_ms'] = {str(arm): [1000 * (next(r['wall'] for r in rows if r['trial'] == trial and r['arm'] == arm)
                                                                                 - next(r['wall'] for r in rows if r['trial'] == trial and r['arm'] == 0))
                                                                 for trial in range(18)] for arm in (1, 2)}
                    write(out / 'report.json', result)
                    print('PANEL_PASS', workload['name'], binary, record['median_ms'], flush=True)
        for name, digest in bound.items(): assert sha(Path(name)) == digest, name
        result['status'] = 'PASS'
    except BaseException as error:
        result['status'] = 'FAIL'
        result['error'] = repr(error)
        raise
    finally:
        write(out / 'report.json', result)


if __name__ == '__main__':
    main()
