"""Matched complete-query CPU/CUDA panel; retain every failed observation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', choices=('f4', 'f5'), default='f4')
    parser.add_argument('--cell', action='append', default=[])
    parser.add_argument('--reps', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--sides', choices=('both', 'host'), default='both')
    parser.add_argument('--min-words', type=int, default=1)
    args = parser.parse_args()
    assert args.reps > 0 and args.timeout > 0 and args.min_words >= 0
    # First three verified-positive x values in the frozen 0:9:2 scan.
    # These are correctness controls; the panel does not estimate relation yield.
    cells = args.cell or ['0:9:2:12:5', '0:9:2:14:5', '0:9:2:22:5']
    for cell in cells:
        values = cell.split(':')
        assert len(values) == 5 and all(value.isdecimal() for value in values)
    args.output.mkdir(parents=True, exist_ok=False)
    binary = args.binary.resolve()
    report = dict(status='RUNNING', engine=args.engine, binary=str(binary), binary_sha256=sha(binary),
        host=dict(architecture=platform.machine(), platform=platform.platform(),
                  cpu=platform.processor()), cells=cells, reps=args.reps,
        timeout_seconds=args.timeout, min_words=args.min_words,
        rows=[], matched_pairs=[], timing_eligible=False, qualified_speedup=None)
    save(args.output/'report.json', report)
    for rep in range(args.reps):
        sides = ('host',) if args.sides == 'host' else (('host', 'cuda') if rep % 2 == 0 else ('cuda', 'host'))
        for cell in cells:
            a, n, m, x, d = cell.split(':')
            for side in sides:
                tag = f'{args.engine}-k{a}n{n}m{m}x{x}d{d}-{side}-{rep+1}'
                target = args.output/(tag+'.json')
                command = [str(binary), '--engine', args.engine,
                           '--cell', ':'.join((a,n,m,x)), '--degree', d,
                           '--out', str(target)]
                env = os.environ.copy()
                env.update(F4_F2_ECHELON=side, F4_F2_ECHELON_MIN_WORDS=str(args.min_words),
                           F4_F2_ECHELON_VERBOSE='1', KIC_F4_INHERIT='0')
                started = time.monotonic()
                try:
                    done = subprocess.run(command, env=env, capture_output=True, text=True,
                                          timeout=args.timeout)
                    execution = 'completed' if done.returncode == 0 and target.exists() else 'process-failure'
                    stdout, stderr, code = done.stdout, done.stderr, done.returncode
                except subprocess.TimeoutExpired as error:
                    execution = 'timeout'
                    stdout = (error.stdout or b'').decode(errors='replace') if isinstance(error.stdout, bytes) else error.stdout or ''
                    stderr = (error.stderr or b'').decode(errors='replace') if isinstance(error.stderr, bytes) else error.stderr or ''
                    code = None
                (args.output/(tag+'.log')).write_text(stdout+'\nSTDERR\n'+stderr)
                row = dict(cell=cell, repetition=rep+1, side=side, execution=execution,
                           exit_code=code, outer_seconds=time.monotonic()-started,
                           command=command, env={key:env[key] for key in (
                               'F4_F2_ECHELON','F4_F2_ECHELON_MIN_WORDS','F4_F2_ECHELON_VERBOSE','KIC_F4_INHERIT')},
                           log=tag+'.log')
                if execution == 'completed':
                    data = json.loads(target.read_text())
                    row.update(result=target.name, sha256=sha(target), status=data['status'],
                               online_ns=data['online_ns'], offloaded_matrices=data['gpu']['matrices'])
                report['rows'].append(row)
                save(args.output/'report.json', report)
                print(cell, rep+1, side, execution, row.get('status'), flush=True)
            if args.sides == 'both':
                left, right = report['rows'][-2:]
                pair = dict(cell=cell, repetition=rep+1, status='UNQUALIFIED', ratio=None)
                if all(row['execution'] == 'completed' for row in (left,right)):
                    outputs = {row['side']: json.loads((args.output/row['result']).read_text())
                               for row in (left,right)}
                    host, cuda = outputs['host'], outputs['cuda']
                    phases_exact = all(sum(result['phase_ns'][key] for key in (
                        'target_conversion', 'system_build', 'solve_including_callback',
                        'offload_summary')) == result['online_ns'] and
                        result['phase_ns']['independent_equation_and_curve_callback_subset']
                        <= result['phase_ns']['solve_including_callback']
                        for result in (host, cuda))
                    same = (host['input'] == cuda['input'] and host['status'] == cuda['status']
                        and host['result']['accepted_assignment'] == cuda['result']['accepted_assignment']
                        and host['result']['target_points'] == cuda['result']['target_points']
                        and phases_exact)
                    pair['same_verified_result'] = same
                    pair['same_algebra_shape'] = all(
                        host['algebra'][key] == cuda['algebra'][key]
                        for key in ('calls', 'rows', 'cols', 'f5_skipped', 'rows_pruned'))
                    pair['gpu_executed'] = cuda['gpu']['matrices'] > 0 and cuda['gpu']['device'] is not None
                    if (same and pair['gpu_executed'] and host['status'] == 'verified-decomposition'
                            and host['result']['accepted_assignment'] is not None
                            and host['result']['independent_equation_checks'] > 0
                            and cuda['result']['independent_equation_checks'] > 0):
                        pair.update(status='EXPLORATORY_VALID_PAIR',
                                    ratio=host['online_ns']/cuda['online_ns'])
                report['matched_pairs'].append(pair)
                save(args.output/'report.json', report)
    report['status'] = 'PASS' if all(row['execution'] == 'completed' for row in report['rows']) else 'INCOMPLETE'
    save(args.output/'report.json', report)


if __name__ == '__main__':
    main()
