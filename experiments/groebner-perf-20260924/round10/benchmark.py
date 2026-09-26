"""Paired complete PDP-query diagnostics, including fresh descent and verification."""
import argparse
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys
import time

from hybrid_query import HybridQuery, HERE
from packed_query import PackedQuery
from descent_plan import DescentPlan
from descend import make_instance

ROOT = HERE.parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions',type=int,default=15)
    parser.add_argument('--ells',type=int,nargs='+',default=[2,3,4])
    parser.add_argument('--seeds',type=int,nargs='+',default=[1,2,3,4,5])
    parser.add_argument('--output',type=Path,default=HERE/'results/query-comparison.json')
    args = parser.parse_args()
    if args.repetitions<2 or not set(args.ells)<=set((2,3,4)):
        parser.error('repetitions >= 2, ell in 2,3,4 required')
    arms = ['cpu','gpu-direct','gpu-indirect','evaluation']
    report = {'schema':1,'scope':'Planted PDP controls; complete query through verified decomposition, no logarithm recovery',
        'candidate_id':None,'IC_online_ms':None,'rho_online_ms':None,
        'boundary':'Start with frozen public target coordinate; fresh descent, packed transport, complete basis computation, independent certification, original equation replay, curve replay and untouched reference equation check. Exclude separately recorded ring-only setup and fixture construction.',
        'cache_policy':'Fixed capacity 8192 selected before target. Ring orders and commands reused; no numeric state, coefficients, pivots, roots or basis reused.',
        'capacity':8192,'signature_limit':8,'arms':arms,'repetitions':args.repetitions,
        'host':{'platform':platform.platform(),'python':sys.version,'logical_cpus':os.cpu_count(),
                'load_start':os.getloadavg()},'setup':[],'inputs':[],'rows':[]}
    # All code involved in timed computation is identified before measurement.
    sources = [HERE/name for name in ('benchmark.py','hybrid_query.py','hybrid_query.mm','gpu_workspace.hpp')]
    sources += [HERE.parent/'round7/local_panel.metal']
    sources += [HERE.parent/'round4'/name for name in ('packed_query.py','packed_dual.cpp','packed_certificate.cpp','descent_plan.py')]
    sources += [HERE.parent/'round2'/name for name in ('boolean_dual.cpp','solve_dual.py')]
    sources += [HERE.parent.parent/'pdp-scaling'/name for name in ('boolean_f5b_m4ri.cpp','boolean_f5b_native.cpp',
        'descend.py','gf2n.py','sumpoly.py','boolean_certificate.cpp','boolean_basis.py','boolean_certificate_native.py')]
    report['source_sha256'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    rng = random.Random(2026092512)
    args.output.parent.mkdir(exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    for ell in args.ells:
        nvars = 3*ell
        with ExitStack() as stack:
            queries = {}
            for arm in arms:
                start = time.perf_counter_ns()
                queries[arm] = stack.enter_context(PackedQuery(nvars,31) if arm=='evaluation' else
                    HybridQuery(nvars,31,backend=arm,capacity=8192))
                report['setup'].append({'nvars':nvars,'arm':arm,'wall_ns':time.perf_counter_ns()-start})
            # The defining modulus is fixed by the fixture's public field policy.
            from descend import GF2n
            field = GF2n(31)
            start = time.perf_counter_ns()
            plan = DescentPlan(31,field.mod,1,3,ell)
            report['setup'].append({'nvars':nvars,'arm':'descent-plan','wall_ns':time.perf_counter_ns()-start})
            for seed in args.seeds:
                start = time.perf_counter_ns()
                instance = make_instance(31,3,ell,seed=seed)
                fixture_ns = time.perf_counter_ns()-start
                fixture = {'n':31,'mod':instance.mod,'b':instance.b,'m':3,'ell':ell,'seed':seed,
                    'target_x':instance.xR,'anf':sorted(instance.anf.items())}
                workload = digest(fixture)
                assert plan.descend(instance.xR)==instance.anf
                report['inputs'].append({**fixture,'workload_sha256':workload,'fixture_ns':fixture_ns})
                for repetition in range(args.repetitions+1):
                    order = arms[:];rng.shuffle(order)
                    row = {'nvars':nvars,'seed':seed,'workload_sha256':workload,
                        'repetition':repetition,'warmup':repetition==0,'order':order,'load':os.getloadavg()}
                    for arm in order:
                        wall,cpu = time.perf_counter_ns(),time.process_time_ns()
                        descent_ns = 0
                        try:
                            current = replace(instance,anf=plan.descend(instance.xR))
                            descent_ns = time.perf_counter_ns()-wall
                            result = queries[arm].solve(current)
                            if result.get('verified') and instance.evaluate(result['assignment']):
                                result.update(status='reference-equation-failed',verified=False)
                        except Exception as error:
                            result = {'status':'exception','verified':False,'detail':repr(error)}
                        row[arm] = {'wall_ns':time.perf_counter_ns()-wall,'cpu_ns':time.process_time_ns()-cpu,
                                    'descent_ns':descent_ns,'result':result}
                    report['rows'].append(row);save()
                print(nvars,seed,'complete',flush=True)
    report['host']['load_end'] = os.getloadavg()
    report['status'] = 'PASS' if all(all(r[a]['result'].get('verified') for a in arms) and
        len({r[a]['result']['basis_sha256'] for a in arms})==1 and
        len({r[a]['result']['assignment'] for a in arms})==1 for r in report['rows']) else 'FAIL'
    save()
    if report['status']!='PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
