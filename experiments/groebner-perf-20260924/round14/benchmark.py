"""Paired complete planted queries: Python layout, native dict, native packed."""
import argparse
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time

from native_descent import HERE, DescentPlan, NativeDescent, packed_query
from descend import GF2n, make_instance

ROOT = HERE.parents[2]
ARMS = ('python', 'native-dict', 'native-packed')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=15)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.repetitions < 2:
        parser.error('at least two repetitions')
    report = {'schema': 1, 'scope': 'Single planted PDP controls, no IC recovery or natural-yield claim',
        'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
        'arms': ARMS, 'repetitions': args.repetitions,
        'boundary': 'Supplied target coordinate through fresh descent, packing, native basis, independent coefficient decoder/certificate, original equation checks, curve replay and untouched reference ANF evaluation.',
        'setup_policy': 'Library/workspace and fixed ring layout setup separate; every target coefficient, numeric solver table and checker state fresh. Fixture generation excluded.',
        'limits': {'max_variables': 20, 'max_solver_roots': 256, 'hard_wall_timeout': False,
                   'native_table_bytes': 256*1024*1024, 'native_edges': 1000000, 'native_slots': 2000000},
        'host': {'platform': platform.platform(), 'python': sys.version, 'logical_cpus': os.cpu_count(),
                 'load_start': os.getloadavg()}, 'setup': [], 'inputs': [], 'rows': []}
    if sys.platform == 'darwin':
        report['host']['cpu'] = subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'], text=True).strip()
        report['host']['memory_bytes'] = int(subprocess.check_output(['sysctl','-n','hw.memsize'], text=True))
    paths = list(HERE.glob('*.py')) + list(HERE.glob('*.cpp'))
    for directory, names in (
        ('round4', ('packed_query.py','descent_plan.py','packed_dual.cpp','packed_certificate.cpp','build.py')),
        ('round2', ('solve_dual.py','boolean_dual.cpp'))):
        paths.extend(HERE.parent/directory/name for name in names)
    paths.extend(HERE.parent.parent/'pdp-scaling'/name for name in
                 ('descend.py','sumpoly.py','gf2n.py','boolean_certificate.cpp','boolean_certificate_native.py'))
    report['source_snapshot'] = {str(p.relative_to(ROOT)): p.read_text() for p in paths}
    report['source_sha256'] = {name: hashlib.sha256(s.encode()).hexdigest() for name,s in report['source_snapshot'].items()}
    report['build_receipt'] = json.loads((HERE/'build/receipt.json').read_text())
    rng = random.Random(2026092602)
    shapes = [(31,3,6,seed) for seed in range(101,107)] + [(31,3,3,101),(31,3,4,101),(11,3,2,101),(83,3,2,101)]
    plans, queries = {}, {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_bytes(gzip.compress(json.dumps(report, separators=(',', ':')).encode(), mtime=0))
    try:
        for n,m,ell,seed in shapes:
            start = time.perf_counter_ns(); original = make_instance(n,m,ell,seed=seed)
            fixture_ns = time.perf_counter_ns()-start
            key = (n,original.mod,original.b,m,ell)
            if key not in plans:
                start = time.perf_counter_ns(); old = DescentPlan(*key)
                old_setup = time.perf_counter_ns()-start
                start = time.perf_counter_ns(); native = NativeDescent(*key)
                native_setup = time.perf_counter_ns()-start
                start = time.perf_counter_ns(); query = packed_query(m*ell,n)
                query_setup = time.perf_counter_ns()-start
                plans[key] = old,native; queries[key] = query
                report['setup'].append({'ring': key, 'python_ns': old_setup, 'native_ns': native_setup,
                    'query_ns': query_setup, 'native_layout': native.layout_stats, 'native_binary_sha256': native.binary_sha256})
            old,native = plans[key]; query = queries[key]
            assert old.descend(original.xR) == native.descend(original.xR) == original.anf
            fixture = {'name': f'n{n}-m{m}-ell{ell}-seed{seed}', 'n': n, 'mod': original.mod,
                'b': original.b, 'm': m, 'ell': ell, 'seed': seed, 'target_x': original.xR,
                'reference_anf': sorted(original.anf.items()),
                'reference_points': [vars(p) for p in original.points], 'nvars': original.nvars}
            workload = digest(fixture)
            report['inputs'].append({**fixture, 'workload_sha256': workload, 'fixture_ns': fixture_ns})
            for repetition in range(args.repetitions+1):
                order = list(ARMS); rng.shuffle(order)
                row = {'name': fixture['name'], 'workload_sha256': workload, 'repetition': repetition,
                       'warmup': repetition==0, 'order': order, 'load': os.getloadavg()}
                for arm in order:
                    cpu = time.process_time_ns(); start = time.perf_counter_ns()
                    descended = solved = start
                    try:
                        anf = old.descend(original.xR) if arm=='python' else (
                            native.descend(original.xR) if arm=='native-dict' else native.descend_packed(original.xR))
                        descended = time.perf_counter_ns()
                        result = query.solve(replace(original, anf=anf))
                        solved = time.perf_counter_ns()
                        if result.get('verified') and original.evaluate(result['assignment']):
                            result.update(status='reference-equation-failed', verified=False)
                    except Exception as error:
                        result = {'status': 'exception', 'verified': False, 'detail': repr(error)}
                        # Unfinished portions remain in their phase, not discarded.
                        if descended==start: descended=time.perf_counter_ns()
                        if solved==start: solved=time.perf_counter_ns()
                    end = time.perf_counter_ns()
                    row[arm] = {'wall_ns': end-start, 'cpu_ns': time.process_time_ns()-cpu,
                        'phases_ns': {'descent': descended-start, 'solve_and_checks': solved-descended,
                                      'reference_replay': end-solved}, 'result': result}
                report['rows'].append(row); save()
            print(fixture['name'], {a: row[a]['result']['status'] for a in ARMS}, flush=True)
    finally:
        for _,native in plans.values(): native.close()
        for query in queries.values(): query.close()
    report['host']['load_end'] = os.getloadavg()
    report['memory'] = {'parent_high_water': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        'unit': 'bytes' if sys.platform=='darwin' else 'KiB', 'per_query_peak': None}
    report['status'] = 'RECORDED'; save()


if __name__ == '__main__':
    main()
