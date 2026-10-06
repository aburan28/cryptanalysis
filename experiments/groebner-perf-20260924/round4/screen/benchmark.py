"""Paired single-query stage measurements; never a complete IC/rho comparison."""
import argparse
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import sys
import time

from packed_query import PackedQuery
from descent_plan import DescentPlan
from descend import make_instance, descend, GF2n, Curve, sumpoly
from solve_dual import solve_dual

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def summary(rows, boundary, arm, reference):
    paired = [(row[reference], row[arm]) for row in rows if row['boundary'] == boundary and not row['warmup']]
    valid = all(a['result'].get('verified') and b['result'].get('verified') and
                a['result']['basis_sha256'] == b['result']['basis_sha256'] and
                a['result']['assignment'] == b['result']['assignment'] for a, b in paired)
    answer = {'boundary': boundary, 'arm': arm, 'reference': reference, 'verified_pairs': valid, 'pairs': len(paired)}
    for clock in ('wall_ns', 'cpu_ns'):
        answer[clock] = {'reference_median_ms': statistics.median(a[clock] for a, _ in paired)/1e6,
                         'candidate_median_ms': statistics.median(b[clock] for _, b in paired)/1e6}
        if valid:
            logs = [math.log(a[clock]/b[clock]) for a, b in paired]
            rng = random.Random(2026092506)
            bootstrap = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
            answer[clock].update(paired_geomean_speedup=math.exp(statistics.mean(logs)),
                                 paired_bootstrap_95pct=[bootstrap[49], bootstrap[1949]])
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=9)
    parser.add_argument('--seeds', type=int, nargs='+', default=[101,201,202,203,204,205])
    parser.add_argument('--output', type=Path, default=HERE/'results/packed-query.json')
    args = parser.parse_args()
    if args.repetitions < 2:
        parser.error('at least two paired repetitions required')
    report = {'scope': 'Single-query planted PDP stage diagnostics; no complete IC or natural-yield claim',
              'candidate_id': None, 'IC_online_ms': None, 'rho_online_ms': None,
              'host': {'platform': platform.platform(), 'python': sys.version, 'python_executable': sys.executable,
                       'logical_cpus': os.cpu_count(), 'load_start': os.getloadavg()},
              'boundaries': {
                  'frozen_anf': 'Start with an already descended coefficient dictionary; include packing, solving, independent certification, original equation evaluation and curve replay. Excludes target-dependent descent.',
                  'with_descent': 'Start with the frozen public target coordinate and fixed ring/curve; include fresh descent, packing, solving, independent certification, original equation evaluation and curve replay. Ring-only plans and library/workspace setup excluded and recorded separately. No log recovery.'},
              'cache_policy': 'Ring-only structural plans and cleared scratch storage. No coefficients, roots or bases reused.',
              'inputs': [], 'rows': [], 'summary': []}
    rng = random.Random(2026092507)
    start = time.perf_counter_ns()
    field = GF2n(31)
    curve = Curve(field, 1)
    polynomial = sumpoly.load(4)
    plan = DescentPlan(31, field.mod, 1, 3, 6)
    report['ring_plan_setup_ns'] = time.perf_counter_ns()-start
    start = time.perf_counter_ns()
    packed = PackedQuery(18,31)
    report['packed_workspace_setup_ns'] = time.perf_counter_ns()-start
    def fresh(instance):
        with PackedQuery(18,31) as query:
            return query.solve(instance)
    try:
        for seed in args.seeds:
            start = time.perf_counter_ns()
            instance = make_instance(31,3,6,seed=seed)
            fixture_ns = time.perf_counter_ns()-start
            fixture = {'n': instance.n, 'mod': instance.mod, 'b': instance.b, 'm': instance.m, 'ell': instance.l,
                       'xR': instance.xR, 'anf': sorted(instance.anf.items()),
                       'points': [[p.x,p.y,p.inf] for p in instance.points], 'seed': seed}
            workload = digest(fixture)
            report['inputs'].append({'seed': seed, 'workload_sha256': workload, 'fixture_setup_ns': fixture_ns,
                                     'target_x': instance.xR, 'anf_terms': len(instance.anf)})
            # Full dictionary parity with the original equation construction is
            # outside timing; both timed paths still independently certify/replay.
            if plan.descend(instance.xR) != instance.anf:
                raise AssertionError('prepared descent differs from original equations')
            for boundary in ('frozen_anf', 'with_descent'):
                arms = (['legacy', 'packed_fresh', 'packed_reuse'] if boundary == 'frozen_anf' else
                        ['legacy', 'legacy_plan', 'packed_plan'])
                for repetition in range(args.repetitions+1):
                    order = arms[:]
                    rng.shuffle(order)
                    row = {'seed': seed, 'workload_sha256': workload, 'boundary': boundary,
                           'repetition': repetition, 'warmup': repetition == 0, 'order': order,
                           'load': os.getloadavg()}
                    for arm in order:
                        current = instance
                        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                        descent_ns = 0
                        try:
                            if boundary == 'with_descent':
                                anf = (descend(polynomial, field, curve, 3, 6, instance.xR) if arm == 'legacy'
                                       else plan.descend(instance.xR))
                                current = replace(instance, anf=anf)
                                descent_ns = time.perf_counter_ns()-wall
                            result = (solve_dual(current, verifier='native') if arm.startswith('legacy') else
                                      fresh(current) if arm == 'packed_fresh' else packed.solve(current))
                        except Exception as error:
                            result = {'status': 'exception', 'verified': False, 'detail': repr(error)}
                        row[arm] = {'wall_ns': time.perf_counter_ns()-wall, 'cpu_ns': time.process_time_ns()-cpu,
                                    'descent_ns': descent_ns, 'result': result}
                    report['rows'].append(row)
                    args.output.write_text(json.dumps(report, indent=2)+'\n')
                print(seed, boundary, 'finished', flush=True)
            selected = [r for r in report['rows'] if r['seed'] == seed]
            for boundary, arm, reference in [('frozen_anf','packed_reuse','legacy'),
                    ('frozen_anf','packed_reuse','packed_fresh'), ('with_descent','packed_plan','legacy'),
                    ('with_descent','packed_plan','legacy_plan')]:
                report['summary'].append({'seed': seed, **summary(selected,boundary,arm,reference)})
    finally:
        packed.close()
    report['source_sha256'] = {}
    sources = list(HERE.glob('*.py')) + list(HERE.glob('*.cpp')) + [
        HERE.parent/'round2/solve_dual.py', HERE.parent/'round2/boolean_dual.cpp',
        HERE.parent.parent/'pdp-scaling/descend.py', HERE.parent.parent/'pdp-scaling/gf2n.py',
        HERE.parent.parent/'pdp-scaling/sumpoly.py', HERE.parent.parent/'pdp-scaling/boolean_certificate.cpp',
        HERE.parent.parent/'pdp-scaling/boolean_basis.py', HERE.parent.parent/'pdp-scaling/boolean_certificate_native.py']
    for path in sources:
        report['source_sha256'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report['host']['load_end'] = os.getloadavg()
    report['status'] = 'PASS' if all(s['verified_pairs'] for s in report['summary']) else 'FAIL'
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['summary'], indent=2))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
