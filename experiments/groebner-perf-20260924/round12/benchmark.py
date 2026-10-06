"""Frozen reduction ablations and full PDP controls; retain every bounded failure."""
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

from query import load,anf_from_equations,HERE
from workloads import workloads
sys.path.insert(0,str(HERE.parent/'round4'))
from descent_plan import DescentPlan
from packed_query import PackedQuery
from descend import make_instance,verify_solution,GF2n

ROOT=HERE.parents[2]
LIMITS=dict(max_work=20_000_000,max_nodes=500_000,max_rows=4096,batch=64,
            max_check_work=20_000_000,max_retained_terms=2_000_000)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extraction(instance,result):
    """Identical bounded root extraction for all four algebraic-proof arms.

    This supplementary PDP path scans <=4096 assignments. The algebraic
    certificate itself never enumerates, and no wider root-finding claim is made.
    """
    if not result.get('verified'):
        return result
    result['algebra_verified']=True;result['verified']=False
    start=time.perf_counter();checked=0
    for assignment in range(1<<instance.nvars):
        if any(sum((m&assignment)==m for m in row)%2 for row in result['basis']):
            continue
        checked+=1
        if instance.evaluate(assignment)==0 and verify_solution(instance,assignment):
            result.update(status='solved',verified=True,assignment=assignment)
            break
    if not result['verified']:result['status']='gb-no-verified-solution'
    result.update(extraction_seconds=time.perf_counter()-start,assignments_checked=checked)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions',type=int,default=15)
    parser.add_argument('--budget-repetitions',type=int,default=3)
    parser.add_argument('--output',type=Path,default=HERE/'results/comparison.json.gz')
    args=parser.parse_args()
    if min(args.repetitions,args.budget_repetitions)<2:parser.error('at least two repetitions')
    setup_start=time.perf_counter_ns();queries={name:load(name) for name in ("baseline","pivots","ordered","combined")}
    library_setup_ns=time.perf_counter_ns()-setup_start
    rng=random.Random(2026092516)
    report={'schema':1,'scope':'Sparse reduction ablations, algebra certification and planted PDP controls; no full IC or natural-yield claim',
        'candidate_id':None,'IC_online_ms':None,'rho_online_ms':None,'limits':LIMITS,
        'timeout_policy':'All arms run in-process with operation/node/row/retention budgets and no hard wall timeout.',
        'boundaries':{
            'algebra':'Start with identical frozen packed ANF coefficients in every arm; include packing, solving, transport and checking through materialized independently certified basis. Fixture construction and library load excluded.',
            'pdp':'Start with frozen public target coordinate; include fresh descent, input preparation, basis/proof production, independent certification, bounded root extraction, original equation evaluation, curve replay, and untouched reference ANF replay. Exclude reusable ring-only setup and fixture construction.'},
        'cache_policy':'Library/configuration and ring-only descent plans; no numeric producer/checker state or target answers reused.',
        'repetition_policy':'15 measured repetitions by default on structured algebra and 6-variable PDP controls; 3 on the predeclared difficult algebra and 9/12-variable PDP controls. Each arm has one retained warmup. Policy does not depend on observed results.',
        'host':{'platform':platform.platform(),'python':sys.version,'logical_cpus':os.cpu_count(),
                'load_start':os.getloadavg()},'inputs':[],
        'setup':[{'arm':'packed-proof-libraries','wall_ns':library_setup_ns}],'rows':[]}
    if sys.platform=='darwin':
        report['host']['cpu']=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
        report['host']['physical_memory_bytes']=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))
    sources=list(HERE.glob('*.py'))+list(HERE.glob('*.cpp'))
    sources += [HERE.parent/'round11'/name for name in ('packed_proof.py','packed_producer.cpp','proof_abi.h','native_checker.cpp')]
    sources += [HERE.parent/'round5'/name for name in ('native_f4.cpp','native_f4.py','algebraic_certificate.py','workloads.py')]
    sources += [HERE.parent/'round4'/name for name in ('descent_plan.py','packed_query.py','packed_dual.cpp','packed_certificate.cpp')]
    sources += [HERE.parent/'round2'/name for name in ('solve_dual.py','boolean_dual.cpp')]
    sources += [HERE.parent.parent/'pdp-scaling'/name for name in ('descend.py','gf2n.py','sumpoly.py',
        'boolean_certificate.cpp','boolean_certificate_native.py')]
    report['build_receipt']=json.loads((HERE/'build/receipt.json').read_text())
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    def save():
        args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    cases=[]
    for case in workloads():
        cases.append({**case,'boundary':'algebra','anf':anf_from_equations(case['equations']),
                      'repetitions':args.budget_repetitions if case['name'].startswith(('random','planted')) else args.repetitions})
    field=GF2n(31)
    plans={};evaluation={}
    for ell in (2,3,4):
        start=time.perf_counter_ns();plans[ell]=DescentPlan(31,field.mod,1,3,ell)
        evaluation[ell]=PackedQuery(3*ell,31)
        report['setup'].append({'ell':ell,'wall_ns':time.perf_counter_ns()-start})
        for seed in range(1,6):
            start=time.perf_counter_ns();instance=make_instance(31,3,ell,seed=seed)
            assert plans[ell].descend(instance.xR)==instance.anf
            cases.append({'name':f'pdp-{3*ell}-seed-{seed}','boundary':'pdp','nvars':3*ell,
                'equations':instance.equations(),'anf':instance.anf,'instance':instance,
                'fixture_ns':time.perf_counter_ns()-start,'seed':seed,
                'repetitions':args.repetitions if ell==2 else args.budget_repetitions})
    try:
        for case in cases:
            fixture={k:v for k,v in case.items() if k not in ('instance','anf','repetitions','fixture_ns')}
            if case['boundary']=='pdp':
                instance=case['instance']
                fixture.update(n=instance.n,mod=instance.mod,b=instance.b,m=instance.m,ell=instance.l,target_x=instance.xR)
            fixture['equations']=[sorted(row) for row in case['equations']]
            workload=digest(fixture)
            report['inputs'].append({**fixture,'workload_sha256':workload,'repetitions':case['repetitions'],
                                     'fixture_ns':case.get('fixture_ns')})
            arms=list(queries)
            if case['boundary']=='pdp':arms.append('evaluation')
            for repetition in range(case['repetitions']+1):
                order=arms[:];rng.shuffle(order)
                row={'name':case['name'],'boundary':case['boundary'],'workload_sha256':workload,
                     'repetition':repetition,'warmup':repetition==0,'order':order,'load':os.getloadavg()}
                for arm in order:
                    wall,cpu=time.perf_counter_ns(),time.process_time_ns();descent_ns=0
                    try:
                        n=case['nvars'];anf=case['anf'];eq_count=len(case['equations'])
                        if case['boundary']=='pdp':
                            original=case['instance'];anf=plans[original.l].descend(original.xR)
                            current=replace(original,anf=anf);descent_ns=time.perf_counter_ns()-wall
                        if arm=='evaluation':
                            result=evaluation[current.l].solve(current)
                        else:
                            result=queries[arm].compute(n,eq_count,anf,**LIMITS)
                        if case['boundary']=='pdp' and arm!='evaluation':result=extraction(current,result)
                        if case['boundary']=='pdp' and result.get('verified') and original.evaluate(result['assignment']):
                            result.update(status='reference-equation-failed',verified=False)
                    except Exception as error:
                        result={'status':'exception','verified':False,'detail':repr(error)}
                    charged_wall=time.perf_counter_ns()-wall;charged_cpu=time.process_time_ns()-cpu
                    # Evidence formatting is outside all timed intervals.
                    if 'basis' in result:
                        result['basis_sha256']=hashlib.sha256(json.dumps(
                            [sorted(g) for g in result.pop('basis')],sort_keys=True).encode()).hexdigest()
                    if result.get('proof') is not None:
                        proof=result.pop('proof');result['proof_sha256']=digest(proof)
                        result['proof_nodes']=len(proof['nodes'])
                    row[arm]={'wall_ns':charged_wall,'parent_cpu_ns':charged_cpu,
                              'descent_ns':descent_ns,'result':result}
                report['rows'].append(row);save()
            print(case['name'],{a:row[a]['result']['status'] for a in arms},flush=True)
    finally:
        for solver in evaluation.values():solver.close()
    report['host']['load_end']=os.getloadavg()
    report['memory_high_water']={'unit':'bytes' if sys.platform=='darwin' else 'KiB',
        'parent':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'child':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'per_case_peak':None,'simultaneous_total_peak':None}
    report['status']='RECORDED';save()


if __name__=='__main__':
    main()
