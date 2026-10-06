"""Frozen public Frobenius comparison with complete conversion/verification cost."""
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import statistics
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measured(function, expected, equal):
    started=time.perf_counter_ns()
    value=function()
    computed=time.perf_counter_ns()
    valid=equal(value,expected)
    checked=time.perf_counter_ns()
    del value
    finished=time.perf_counter_ns()
    if not valid:
        raise AssertionError('output mismatch')
    return {'operation_seconds':(computed-started)*1e-9,
            'verification_seconds':(checked-computed)*1e-9,
            'cleanup_seconds':(finished-checked)*1e-9,
            'validated_seconds':(finished-started)*1e-9}


def worker(args):
    import numpy as np
    from sage.all import GF, EllipticCurve, set_random_seed
    from sage.version import version
    from sage.schemes.elliptic_curves.binary_batch import frobenius_points
    from load_hardware import FrobeniusPlan, SOURCE, artifacts
    set_random_seed(args.seed)
    cell_start=time.perf_counter()
    F=GF(2**args.degree,'z')
    E=EllipticCurve(F,[1,1,0,0,1])
    from public_points import generate
    points,generation_attempts=generate(E,args.points,args.seed)
    if len(points)>=4:
        points[0]=E(0);points[1]=E(0,1);points[2]=points[3]
    input_seconds=time.perf_counter()-cell_start
    print('input_generation_complete',input_seconds,flush=True)
    expected=frobenius_points(E,points,args.power)
    plans={}
    cold={}
    metadata={}
    for backend in ('cpu','metal'):
        start=time.perf_counter()
        plan=FrobeniusPlan(E,args.power,backend,cpu_threads=1)
        initialized=time.perf_counter()
        first=measured(lambda:plan.apply(points),expected,lambda a,b:a==b)
        cold[backend]={'setup_seconds':initialized-start,'first_apply':first,
                       'setup_plus_first_validated_seconds':time.perf_counter()-start}
        metadata[backend]={'device':plan.device_name,'codec':plan.codec,
                           'table_seconds':plan.table_seconds,'table_bytes':plan._table.nbytes,
                           'table_sha256':hashlib.sha256(plan._table.tobytes()).hexdigest()}
        plans[backend]=plan
    assert metadata['cpu']['table_sha256']==metadata['metal']['table_sha256']
    functions={'sage':lambda:frobenius_points(E,points,args.power),
               'cpu':lambda:plans['cpu'].apply(points),
               'metal':lambda:plans['metal'].apply(points)}
    # Same inputs and complete API output for all three arms; all six arm
    # permutations occur twice. No tuning is performed on confirmation cells.
    orders=list(itertools.permutations(functions))*2
    random.Random(args.seed+args.degree+args.points+args.power).shuffle(orders)
    full={name:[] for name in functions}
    for order in orders:
        for name in order:
            full[name].append(measured(functions[name],expected,lambda a,b:a==b))
    packed,flags=plans['cpu'].pack_points(points)
    packed_expected,_=plans['cpu'].pack_points(expected)
    packed_timings={'cpu':[],'metal':[]}
    for repeat in range(12):
        order=('cpu','metal') if repeat%2==0 else ('metal','cpu')
        for name in order:
            sample=measured(lambda:plans[name].apply_words(packed),packed_expected,np.array_equal)
            sample['gpu_seconds']=plans[name].last_gpu_seconds
            packed_timings[name].append(sample)
    cleanup={}
    for name,plan in plans.items():
        start=time.perf_counter();plan.close();cleanup[name]=time.perf_counter()-start
    row={'phase':args.phase,'seed':args.seed,'degree':args.degree,'points':args.points,
         'power_requested':args.power,'power_normalized':args.power%args.degree,
         'modulus':str(F.modulus()),'sage_version':version,
         'loaded_artifacts':artifacts(),'source_sha256':sha(SOURCE),'input_setup_seconds':input_seconds,
         'input_generator':'odd-degree half-trace with independent equation and Sage membership checks',
         'input_generation_attempts':generation_attempts,
         'input_sha256':hashlib.sha256(packed.tobytes()+flags.tobytes()).hexdigest(),
         'output_sha256':hashlib.sha256(packed_expected.tobytes()+flags.tobytes()).hexdigest(),
         'completed_points_per_call':len(expected),'exact_output_agreement':True,
         'metadata':metadata,'cold':cold,'full_api':full,'execution_orders':orders,
         'packed':packed_timings,'plan_cleanup_seconds':cleanup,
         'peak_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         'worker_seconds':time.perf_counter()-cell_start}
    args.out.write_text(json.dumps(row,indent=2)+'\n')


def bootstrap_ratio(base,candidate,seed):
    values=[math.log(a/b) for a,b in zip(base,candidate)]
    rng=random.Random(seed)
    samples=sorted(math.exp(statistics.median([rng.choice(values) for _ in values]))
                   for _ in range(4000))
    return [samples[100],samples[3899]]


def summarize(row):
    full={name:[r['validated_seconds'] for r in samples] for name,samples in row['full_api'].items()}
    med={name:statistics.median(values) for name,values in full.items()}
    result={'phase':row['phase'],'degree':row['degree'],'points':row['points'],
            'power':row['power_requested'],'power_normalized':row['power_normalized'],
            'full_medians_seconds':med,'full_speedup':{},'confidence_95':{},'gate':{},
            'break_even_calls':{}}
    for i,name in enumerate(('cpu','metal')):
        ratio=med['sage']/med[name]
        interval=bootstrap_ratio(full['sage'],full[name],row['seed']+i)
        result['full_speedup'][name]=ratio
        result['confidence_95'][name]=interval
        result['gate'][name]='PASS_LOCAL_CELL' if ratio>1.02 and interval[0]>1 else 'HOLD'
        saving=med['sage']-med[name]
        result['break_even_calls'][name]=(math.ceil(row['cold'][name]['setup_seconds']/saving)
                                           if saving>0 else None)
    packed={name:statistics.median(s['validated_seconds'] for s in samples)
            for name,samples in row['packed'].items()}
    result['packed_gpu_speedup_vs_native_cpu']=packed['cpu']/packed['metal']
    result['full_gpu_speedup_vs_native_cpu']=med['cpu']/med['metal']
    return result


def parent(args):
    args.out.mkdir(parents=True,exist_ok=False)
    sources=args.out/'sources';sources.mkdir()
    source_dir=HERE.parents[1]/'third_party/sage-binary/src/sage/schemes/elliptic_curves'
    snapshots=list(source_dir.glob('binary_hardware*'))+[Path(__file__),HERE/'load_hardware.py',
                                                      HERE/'public_points.py',args.intent]
    for path in snapshots:
        if path.is_file():shutil.copy2(path,sources/path.name)
    from load_hardware import artifacts
    intent=json.loads(args.intent.read_text())
    execution={'intent_sha256':sha(args.intent),
               'source_sha256':{p.name:sha(p) for p in sources.iterdir()},
               'loaded_artifacts':artifacts(),
               'method':'complete Sage-point API with validation and output cleanup; separate packed metric',
               'rounds':12,'cloud_spend':0,'automatic_gpu_promotion':False}
    (args.out/'execution-plan.json').write_text(json.dumps(execution,indent=2)+'\n')
    cases=[('primary',intent['primary_cases']['seed'],m,n,k) for m in (19,67,131) for n in (1024,16384) for k in (1,7,65)]
    cases += [('confirmation',intent['confirmation_cases']['seed'],m,4096,k) for m in (31,131) for k in (7,65)]
    rows=[];failures=[]
    env=os.environ.copy()
    if env.get('SAGE_BINARY_USE_INSTALLED')!='1':
        env['SAGE_BINARY_CODEC']=str(next(HERE.glob('binary_hardware_codec*.so')))
    for index,(phase,seed,m,n,k) in enumerate(cases):
        output=args.out/f'cell-{index:02d}.json'
        command=[sys.executable,str(Path(__file__).resolve()),'--worker','--phase',phase,
                 '--seed',str(seed),'--degree',str(m),'--points',str(n),'--power',str(k),'--out',str(output)]
        start=time.perf_counter()
        with (args.out/f'cell-{index:02d}.log').open('w') as log:
            try:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=300)
                status=result.returncode
            except subprocess.TimeoutExpired:
                status='timeout'
        receipt={'command':command,'status':status,'parent_seconds':time.perf_counter()-start}
        (args.out/f'cell-{index:02d}-parent.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if status!=0:
            failures.append(receipt)
            print('FAILED',phase,m,n,k,status,flush=True)
            break
        row=json.loads(output.read_text());rows.append(summarize(row))
        print(f'{phase} m={m} n={n} k={k}: CPU {rows[-1]["full_speedup"]["cpu"]:.3f}x, '
              f'Metal {rows[-1]["full_speedup"]["metal"]:.3f}x Sage; '
              f'packed Metal/CPU {rows[-1]["packed_gpu_speedup_vs_native_cpu"]:.3f}x',flush=True)
    (args.out/'summary.json').write_text(json.dumps({'rows':rows,'failures':failures,
        'complete':len(rows)==len(cases),'execution_plan_sha256':sha(args.out/'execution-plan.json')},indent=2)+'\n')
    if failures:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--intent',type=Path,default=HERE/'intent-v2.json')
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--degree',type=int)
    parser.add_argument('--points',type=int)
    parser.add_argument('--power',type=int)
    parser.add_argument('--seed',type=int)
    parser.add_argument('--phase')
    args=parser.parse_args()
    worker(args) if args.worker else parent(args)
