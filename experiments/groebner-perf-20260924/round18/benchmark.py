"""Paired complete public-point queries, preserving independent certification."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

from truth_query import ARMS, TruthQuery
from packed_checker import HERE, Curve, GF2n, Point
from descend import make_instance

ROOT = HERE.parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def timing_eligible(report, cpus, limit):
    return (report.get('status') == 'RECORDED' and report['admission']['admitted'] and bool(report['rows'])
            and all(row['load'][0] <= cpus * limit for row in report['rows'])
            and report['host']['load_end'][0] <= cpus * limit)


def sources():
    paths = list(HERE.glob('*.py')) + list(HERE.glob('*.cpp'))
    paths += list((HERE.parent / 'round17').glob('*.py')) + list((HERE.parent / 'round17').glob('*.c'))
    paths += list((HERE.parent / 'round15/reference').glob('*.cpp'))
    for directory, names in (
        ('round15', ('ordered_query.py', 'ordered_certificate.cpp', 'build.py')),
        ('round14', ('native_descent.py', 'contraction.cpp', 'build.py')),
        ('round4', ('packed_query.py', 'descent_plan.py', 'packed_dual.cpp', 'packed_certificate.cpp', 'build.py')),
        ('round2', ('solve_dual.py', 'boolean_dual.cpp'))):
        paths += [HERE.parent / directory / name for name in names]
    paths += [HERE.parent.parent / 'pdp-scaling' / name for name in
              ('descend.py', 'sumpoly.py', 'gf2n.py', 'boolean_certificate.cpp', 'boolean_certificate_native.py')]
    paths += [HERE.parent.parent / 'pdp-degree-heuristics/pdpkernel.c']
    return {str(p.relative_to(ROOT)): p.read_text() for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=15)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-load-per-cpu', type=float, default=1.0)
    args = parser.parse_args()
    if args.repetitions < 2:
        parser.error('at least two paired repetitions')
    if not math.isfinite(args.max_load_per_cpu) or args.max_load_per_cpu <= 0:
        parser.error('load limit must be finite and positive')
    admission_path = args.output.with_suffix(args.output.suffix + '.admission.json')
    if args.output.exists() or admission_path.exists():
        parser.error('retained output/admission cannot be overwritten')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    load, cpus = os.getloadavg(), os.cpu_count() or 1
    admission = {'logical_cpus': cpus, 'load': load, 'max_load_per_cpu': args.max_load_per_cpu,
                 'admitted': load[0] <= cpus * args.max_load_per_cpu, 'timed_attempts': 0}
    admission_path.write_text(json.dumps(admission, indent=2) + '\n')
    if not admission['admitted']:
        print(json.dumps({'status': 'NOT_ADMITTED', 'admission': str(admission_path), 'timed_attempts': 0}))
        raise SystemExit(2)
    snapshot = sources()
    report = {'schema': 2, 'scope': 'Single public-point PDP component controls; planted fixtures, no IC recovery or natural-yield claim',
              'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
              'arms': ARMS, 'repetitions': args.repetitions, 'admission': admission,
              'boundary': 'Public point through validation, fresh packed descent, basis computation, independent basis certificate, original-equation checks, independent full-point curve replay and untouched reference-ANF evaluation.',
              'setup_policy': 'Fixed ring/field/workspace setup and fixture generation separate in both arms. No target answer reuse. Python witness auditing is separate, recorded outside online timing.',
              'limits': {'variables': 20, 'roots': 256, 'native_replay_field_degree': 63,
                         'replay_requires_odd_degree': True, 'curve_sign_points': 12, 'hard_wall_timeout': False},
              'host': {'platform': platform.platform(), 'python': sys.version,
                       'logical_cpus': cpus, 'load_start': load},
              'source_snapshot': snapshot,
              'source_sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in snapshot.items()},
              'build_receipts': {str(r): json.loads((HERE.parent / f'round{r}/build/receipt.json').read_text())
                                 for r in (14, 15, 17, 18)}, 'inputs': [], 'setup': [], 'rows': [], 'status': 'RUNNING'}
    if sys.platform == 'darwin':
        report['host']['cpu'] = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
        report['host']['memory_bytes'] = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True))
    rng = random.Random(2026092705)
    shapes = [(31, 3, 6, seed) for seed in range(101, 107)] + [(31, 3, 3, 101), (31, 3, 4, 101), (11, 3, 2, 101), (83, 3, 2, 101)]
    workspaces = {}

    def save():
        temporary = args.output.with_suffix(args.output.suffix + '.tmp')
        temporary.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), compresslevel=1, mtime=0))
        temporary.replace(args.output)

    try:
        for n, m, ell, seed in shapes:
            start = time.perf_counter_ns()
            original = make_instance(n, m, ell, seed=seed)
            oracle = Curve(GF2n(n, original.mod), original.b)
            target = oracle.sum(original.points)
            fixture_ns = time.perf_counter_ns() - start
            key = (n, original.mod, original.b, m, ell)
            if key not in workspaces:
                workspaces[key] = {}
                setup = {'ring': key, 'arms': {}}
                report['setup'].append(setup)
                for arm in ARMS:
                    start = time.perf_counter_ns()
                    current = TruthQuery(*key, arm=arm)
                    workspaces[key][arm] = current
                    setup['arms'][arm] = {'wall_ns': time.perf_counter_ns()-start,
                                         'replay_backend': current.replay.backend,
                                         'replay_binary_sha256': current.replay.binary_sha256,
                                         'descent_binary_sha256': current.descent.binary_sha256}
            fixture = {'name': f'n{n}-m{m}-ell{ell}-seed{seed}', 'n': n, 'mod': original.mod,
                       'b': original.b, 'm': m, 'ell': ell, 'seed': seed, 'target': vars(target),
                       'nvars': original.nvars, 'reference_anf': sorted(original.anf.items()),
                       'fixture_points': [vars(p) for p in original.points]}
            workload = digest(fixture)
            report['inputs'].append({**fixture, 'workload_sha256': workload, 'fixture_ns': fixture_ns})
            for repetition in range(args.repetitions + 1):
                order = list(ARMS)
                rng.shuffle(order)
                row = {'name': fixture['name'], 'workload_sha256': workload, 'repetition': repetition,
                       'warmup': repetition == 0, 'order': order, 'load': os.getloadavg()}
                report['rows'].append(row)
                save()
                for arm in order:
                    cpu, start = time.process_time_ns(), time.perf_counter_ns()
                    solved = start
                    try:
                        answer = workspaces[key][arm].solve(target)
                        solved = time.perf_counter_ns()
                        if answer.get('verified') and original.evaluate(answer['assignment']):
                            answer.update(status='reference-equation-failed', verified=False)
                    except Exception as error:
                        answer = {'status': 'exception', 'verified': False, 'detail': repr(error)}
                        solved = time.perf_counter_ns()
                    end = time.perf_counter_ns()
                    sample = {'wall_ns': end-start, 'cpu_ns': time.process_time_ns()-cpu,
                              'phases_ns': {'public_query': solved-start, 'reference_equations': end-solved},
                              'result': answer}
                    row[arm] = sample
                    report['admission']['timed_attempts'] += 1
                    save()
                    # This audit is additional evidence, not part of either arm's
                    # measured algorithm. Both arms already replay the full curve.
                    audit_start = time.perf_counter_ns()
                    valid = False
                    if answer.get('verified'):
                        points = [Point(**p) for p in answer['curve_witness']['points']]
                        valid = (all(oracle.on_curve(p) for p in points)
                                 and [p.x for p in points] == original.x_from_assignment(answer['assignment'])
                                 and oracle.sum(points) == target)
                    sample['outside_timing_witness_audit'] = {'verified': valid,
                        'wall_ns': time.perf_counter_ns()-audit_start}
                    save()
            print(fixture['name'], {a: row[a]['result']['status'] for a in ARMS}, flush=True)
        report['status'] = 'RECORDED'
    except BaseException as error:
        report['status'] = 'INTERRUPTED'
        report['interruption'] = repr(error)
        raise
    finally:
        for arms in workspaces.values():
            for current in arms.values(): current.close()
        report['host']['load_end'] = os.getloadavg()
        report['memory'] = {'parent_high_water': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'unit': 'bytes' if sys.platform == 'darwin' else 'KiB', 'per_query_peak': None}
        report['timing_qualification'] = {'eligible': timing_eligible(report, cpus, args.max_load_per_cpu),
            'criterion': 'All group-start and final one-minute loads <= predeclared threshold; necessary but insufficient for an uncontended host.'}
        save()


if __name__ == '__main__':
    main()
