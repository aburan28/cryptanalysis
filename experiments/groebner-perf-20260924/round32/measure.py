"""Paired complete public-point queries, preserving independent certification."""
import argparse
import base64
import ctypes
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

from query import BaselineQuery, QuadraticQuery, CertifiedQuery
from sparse_checker import Curve, GF2n, Point
from certified import HERE

CPU_ARMS = ('sparse', 'conditional-quadratic', 'quadratic-proof-cpu')
ARMS = (*CPU_ARMS, 'conditional-quadratic-metal', 'quadratic-proof-metal')
LARGE_SHAPES = [(31, 3, 7, 201), (31, 3, 8, 201)]
LARGE_CPU_ARMS = ('quadratic-proof-cpu',)
LARGE_ARMS = (*LARGE_CPU_ARMS, 'quadratic-proof-metal')
SHAPES = [(31, 3, 6, seed) for seed in range(101, 107)] + [(31, 3, 5, 101), (11, 3, 3, 101), (83, 3, 2, 101)]
from descend import make_instance
from certificate_journal import Journal

ROOT = HERE.parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def timing_eligible(report, cpus, limit):
    return (not report.get('correctness_only',False) and report.get('status') == 'RECORDED' and report['admission']['admitted'] and bool(report['rows'])
            and report['admission']['load'][0] <= cpus * limit
            and all(max(row['load'][0],row['load_end'][0]) <= cpus * limit for row in report['rows'])
            and report['host']['load_end'][0] <= cpus * limit)


def sources():
    paths = [p for ext in ('*.py', '*.hpp', '*.h', '*.cpp', '*.metal', '*.mm') for p in HERE.glob(ext)]
    paths += [p for ext in ('*.py', '*.hpp', '*.h', '*.cpp', '*.metal', '*.mm') for p in (HERE.parent/'round31').glob(ext)]
    paths += [HERE.parent/'round27'/name for name in ('interpolation.hpp', 'conditional.py', 'full_query.py', 'branch_journal.py', 'reference.py')]
    paths += [p for ext in ('*.py', '*.hpp') for p in (HERE.parent/'round23').glob(ext)]
    paths += list((HERE.parent / 'round18').glob('*.py')) + list((HERE.parent / 'round18').glob('*.cpp'))
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
    # Bind the complete native dependency-build receipt, including the producer.
    receipt = json.loads((HERE.parent/'round20/build/receipt.json').read_text())
    paths += [ROOT/name for name in receipt['source_sha256']]
    return {str(p.relative_to(ROOT)): p.read_text() for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correctness-only',action='store_true',help='Record exact query evidence without performance eligibility')
    parser.add_argument('--repetitions', type=int, default=15)
    parser.add_argument('--metal', action='store_true', help='Include requested Metal arms')
    parser.add_argument('--large-controls', action='store_true', help='21/24-variable correctness controls; requires --correctness-only')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-load-per-cpu', type=float, default=1.0)
    parser.add_argument('--admission-wait-seconds', type=int, default=0,
                        help='wait at most this long for admission, sampling every 30 seconds')
    args = parser.parse_args()
    if args.large_controls and not args.correctness_only:
        parser.error('large controls require --correctness-only until a stronger wide CPU baseline is paired')
    arms = (LARGE_ARMS if args.metal else LARGE_CPU_ARMS) if args.large_controls else (ARMS if args.metal else CPU_ARMS)
    shapes = LARGE_SHAPES if args.large_controls else SHAPES
    if not 0 <= args.admission_wait_seconds <= 300:
        parser.error('admission wait must be 0..300 seconds')
    if not 2 <= args.repetitions <= 101:
        parser.error('2..101 paired repetitions required')
    if not math.isfinite(args.max_load_per_cpu) or args.max_load_per_cpu <= 0:
        parser.error('load limit must be finite and positive')
    admission_path = args.output.with_suffix(args.output.suffix + '.admission.json')
    if args.output.exists() or admission_path.exists():
        parser.error('retained output/admission cannot be overwritten')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cpus = os.cpu_count() or 1
    samples, started = [], time.monotonic()
    while True:
        load = os.getloadavg()
        samples.append({'elapsed_seconds': time.monotonic()-started, 'load': load})
        if args.correctness_only or load[0] <= cpus * args.max_load_per_cpu or time.monotonic()-started >= args.admission_wait_seconds:
            break
        print('waiting for load admission', samples[-1], flush=True)
        time.sleep(max(0, min(30, args.admission_wait_seconds-(time.monotonic()-started))))
    admission = {'logical_cpus': cpus, 'load': load, 'max_load_per_cpu': args.max_load_per_cpu,
                 'admitted': not args.correctness_only and load[0] <= cpus * args.max_load_per_cpu, 'timed_attempts': 0, 'wait_limit_seconds': args.admission_wait_seconds, 'samples': samples}
    admission_path.write_text(json.dumps(admission, indent=2) + '\n')
    if not admission['admitted'] and not args.correctness_only:
        print(json.dumps({'status': 'NOT_ADMITTED', 'admission': str(admission_path), 'timed_attempts': 0}))
        raise SystemExit(2)
    if sys.platform == 'darwin' and ctypes.CDLL(None).pthread_set_qos_class_self_np(0x19, 0):
        raise RuntimeError('USER_INITIATED QoS failed')
    snapshot = sources()
    report = {'schema': 'round32-branch-certificates/1', 'large_controls': args.large_controls, 'correctness_only':args.correctness_only, 'scope': 'Single public-point PDP component controls; planted fixtures, no IC recovery or natural-yield claim',
              'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
              'arms': arms, 'repetitions': args.repetitions, 'admission': admission,
              'boundary': 'Public point through validation, fresh packed descent, basis computation, independent basis certificate, original-equation checks, independent full-point curve replay and untouched reference-ANF evaluation.',
              'setup_policy': 'Fixed ring/field/workspace setup and fixture generation separate in both arms. No target answer reuse. Python witness auditing is separate, recorded outside online timing.',
              'limits': {'variables': 24 if args.large_controls else 20, 'roots': 256, 'conditional_branch_bits': 20, 'producer_variables': 30, 'certified_variables': 30, 'checker_enumeration_budget': 4194304, 'checker_basis_budget': 1000000, 'specialization_table_bytes': 67108864, 'enumeration_budget': 4194304, 'residual_variables': 10, 'native_replay_field_degree': 63,
                         'replay_requires_odd_degree': True, 'curve_sign_points': 12, 'hard_wall_timeout': False, 'sparse_root_limit': 256, 'sparse_membership_budget': 65536},
              'host': {'platform': platform.platform(), 'python': sys.version,
                       'logical_cpus': cpus, 'load_start': load,
                       'qos': 'USER_INITIATED' if sys.platform == 'darwin' else 'default'},
              'source_snapshot': snapshot,
              'source_sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in snapshot.items()},
              'build_receipts': {str(r): json.loads((HERE.parent / f'round{r}/build/receipt.json').read_text())
                                 for r in (14, 15, 17, 18, 20, 23, 31, 32)}, 'inputs': [], 'setup': [], 'candidates': {}, 'proofs': {}, 'rows': [], 'status': 'RUNNING'}
    if sys.platform == 'darwin':
        report['host']['cpu'] = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
        report['host']['memory_bytes'] = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True))
    rng = random.Random(2026092706)
    workspaces, fixtures = {}, []

    journal = Journal(args.output)
    save = lambda: journal.checkpoint(report)

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
                for arm in arms:
                    start = time.perf_counter_ns()
                    if arm == 'sparse':
                        current = BaselineQuery(*key, arm='sparse')
                    elif arm.startswith('quadratic-proof-'):
                        current = CertifiedQuery(*key, backend=arm.removeprefix('quadratic-proof-'))
                    else:
                        current = QuadraticQuery(*key, backend='metal' if arm.endswith('-metal') else 'cpu')
                    workspaces[key][arm] = current
                    setup['arms'][arm] = {'wall_ns': time.perf_counter_ns()-start,
                                         'replay_backend': current.replay.backend,
                                         'replay_binary_sha256': current.replay.binary_sha256,
                                         'descent_binary_sha256': current.descent.binary_sha256,
                                         'checker_binary_sha256': current.checker.binary_sha256,
                                         'proof_mode': getattr(current.checker, 'mode', None)}
                    if arm != 'sparse':
                        setup['arms'][arm]['device'] = current.basis.producer.device
            fixture = {'name': f'n{n}-m{m}-ell{ell}-seed{seed}', 'n': n, 'mod': original.mod,
                       'b': original.b, 'm': m, 'ell': ell, 'seed': seed, 'target': vars(target),
                       'nvars': original.nvars, 'reference_anf': sorted(original.anf.items()),
                       'fixture_points': [vars(p) for p in original.points]}
            workload = digest(fixture)
            report['inputs'].append({**fixture, 'workload_sha256': workload, 'fixture_ns': fixture_ns})
            fixtures.append((original,oracle,target,key,fixture,workload))
        # Immutable fixture and setup metadata is now complete before the first
        # checkpoint. Numerical solving still starts fresh for each new query.
        save()
        for original,oracle,target,key,fixture,workload in fixtures:
            for repetition in range(args.repetitions + 1):
                order = list(arms)
                rng.shuffle(order)
                row = {'name': fixture['name'], 'workload_sha256': workload, 'workload_id': workload, 'repetition': repetition,
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
                    # Export already-verified immutable proof evidence outside
                    # the clock. Proof generation, its immutable copy/hash and
                    # independent checking were all charged inside solve().
                    if 'proof_bytes' in answer:
                        raw = answer.pop('proof_bytes')
                        identifier = answer['proof_sha256']
                        payload = {'byteorder': answer['proof_byteorder'], 'base64': base64.b64encode(raw).decode(), 'bytes': len(raw)}
                        if identifier in report['proofs']:
                            assert report['proofs'][identifier] == payload
                        report['proofs'][identifier] = payload
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
                row['load_end'] = os.getloadavg()
                save()
            print(fixture['name'], {a: row[a]['result']['status'] for a in arms}, flush=True)
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
            'criterion': 'Initial, all group-start/end and final one-minute loads <= predeclared threshold; necessary but insufficient for an uncontended host.'}
        journal.finish(report)


if __name__ == '__main__':
    main()
