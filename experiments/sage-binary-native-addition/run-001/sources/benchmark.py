"""Matched complete-API measurements; run with the local Sage launcher."""
import argparse
import cProfile
import hashlib
import importlib.util
import itertools
import json
import math
import platform
import pstats
import random
import resource
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl
from sage.version import version

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent/'sage-binary-hardware'))
from public_points import generate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def incumbent():
    spec = importlib.util.spec_from_file_location('incumbent', HERE/'baseline/binary_batch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixtures(case):
    start = time.perf_counter()
    set_random_seed(case['seed'])
    field = GF(2**case['degree'], 'z')
    curve = EllipticCurve(field, [1, 1, 0, 0, 1])
    points, attempts = generate(curve, 2*case['side'], case['seed'])
    left, right = points[:case['side']], points[case['side']:]
    expected = [P+Q for P in left for Q in right]
    setup = time.perf_counter()-start
    return curve, left, right, expected, dict(
        setup_seconds=setup, fixture_attempts=attempts,
        modulus=str(field.modulus()), input_sha256=hashlib.sha256(str(points).encode()).hexdigest(),
        output_sha256=hashlib.sha256(str(expected).encode()).hexdigest())


def functions(case, curve, left, right):
    modules = {'incumbent': incumbent(), 'candidate': binary_batch}
    if case['api'] == 'cartesian':
        return {k: lambda m=m: m.add_cartesian(curve, left, right) for k,m in modules.items()}
    return {k: lambda m=m: m.add_pairs(curve, [(P,Q) for P in left for Q in right])
            for k,m in modules.items()}


def checked(function, expected, calls):
    cpu = time.process_time_ns()
    start = time.perf_counter_ns()
    for _ in range(calls):
        actual = function()
        if actual != expected:
            raise AssertionError('output mismatch')
        del actual
    wall = time.perf_counter_ns()-start
    cpu = time.process_time_ns()-cpu
    return dict(wall_seconds=wall/1e9/calls, cpu_seconds=cpu/1e9/calls)


def worker(args):
    case = json.loads(args.case)
    curve, left, right, expected, metadata = fixtures(case)
    arms = functions(case, curve, left, right)
    if args.rss_arm:
        checked(arms[args.rss_arm], expected, 12)
        write(args.worker_out, dict(arm=args.rss_arm,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, **metadata))
        return
    for fn in arms.values():
        checked(fn, expected, 1)
    orders = list(itertools.permutations(arms))*6
    random.Random(case['seed']+case['degree']+case['side']).shuffle(orders)
    rounds = []
    for order in orders:
        rounds.append({'order':list(order), 'arms':{
            arm:checked(arms[arm], expected, 4) for arm in order}})
    write(args.worker_out, dict(case=case, rounds=rounds, **metadata,
        exact_output_agreement=True, completed_outputs=len(expected)*4*12*2,
        max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        sage_version=version, machine=platform.machine(),
        installed_sha256={p:sha(p) for p in (binary_batch.__file__, binary_batch_ntl.__file__)}))


def summary(rows, criteria):
    rng = random.Random(413129)
    result = {'cells':[]}
    for row in rows:
        wall = [r['arms']['incumbent']['wall_seconds']/r['arms']['candidate']['wall_seconds']
                for r in row['rounds']]
        cpu = [r['arms']['candidate']['cpu_seconds']/r['arms']['incumbent']['cpu_seconds']
               for r in row['rounds']]
        result['cells'].append(dict(**row['case'], speedup=math.exp(statistics.median(list(map(math.log, wall)))),
            cpu_ratio=statistics.median(cpu),
            incumbent_ms=1000*statistics.median([r['arms']['incumbent']['wall_seconds'] for r in row['rounds']]),
            candidate_ms=1000*statistics.median([r['arms']['candidate']['wall_seconds'] for r in row['rounds']])))
    for phase in ('primary', 'confirmation'):
        selected = [row for row in rows if row['case']['phase']==phase]
        logs = [[math.log(r['arms']['incumbent']['wall_seconds']/r['arms']['candidate']['wall_seconds'])
                 for r in row['rounds']] for row in selected]
        boot = []
        for _ in range(criteria['bootstrap_samples']):
            # Each cell has its own fresh process and independently timed rounds.
            boot.append(math.exp(statistics.mean(
                statistics.median(rng.choices(cell, k=len(cell))) for cell in logs)))
        boot.sort()
        speedup = math.exp(statistics.mean(statistics.median(cell) for cell in logs))
        lower, upper = boot[int(.025*len(boot))], boot[int(.975*len(boot))]
        result[phase] = dict(geomean_speedup=speedup, bootstrap_95=[lower,upper],
            pass_gate=speedup>criteria[phase+'_geomean_speedup_min'] and lower>1)
    result['per_cell_gate'] = all(c['speedup']>=criteria['per_cell_speedup_min'] for c in result['cells'])
    result['cpu_gate'] = all(c['cpu_ratio']<=criteria['cpu_candidate_over_incumbent_max'] for c in result['cells'])
    return result


def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    sources = args.out/'sources'
    sources.mkdir()
    intent = json.loads((HERE/'intent-v1.json').read_text())
    if sha(HERE/'intent-v1.json') != (HERE/'intent-v1.sha256').read_text().split()[0]:
        raise AssertionError('intent changed')
    if sha(HERE/'baseline/binary_batch.py') != intent['incumbent_revision_and_binary_hash']['source_sha256']:
        raise AssertionError('incumbent changed')
    source_dir = ROOT/'third_party/sage-binary/src/sage/schemes/elliptic_curves'
    if sha(source_dir/'binary_batch.py') != sha(binary_batch.__file__):
        raise AssertionError('source differs from installed module')
    paths = [Path(__file__), HERE/'test_native.py', HERE/'intent-v1.json',
             source_dir/'binary_batch.py', source_dir/'binary_batch_ntl.pyx',
             source_dir/'meson.build', Path(binary_batch_ntl.__file__),
             HERE.parent/'sage-binary-hardware/public_points.py']
    for path in paths:
        shutil.copy2(path, sources/path.name)
    shutil.copy2(HERE/'baseline/binary_batch.py', sources/'incumbent.py')
    cases = [dict(c, phase=phase) for phase,key in
             [('primary','primary_cases'),('confirmation','new_confirmation_cases')]
             for c in intent[key]]
    write(args.out/'execution-plan.json', dict(intent_sha256=sha(HERE/'intent-v1.json'),
        cases=cases, source_sha256={p.name:sha(p) for p in sources.iterdir()},
        platform=platform.platform(), sage_version=version,
        executable=sys.executable, installed_module=binary_batch.__file__,
        installed_native=binary_batch_ntl.__file__))
    rows=[]
    for i, case in enumerate(cases):
        output = args.out/f'cell-{i:02d}.json'
        command = [sys.executable, str(Path(__file__).resolve()), '--case', json.dumps(case), '--worker-out', str(output)]
        start = time.perf_counter()
        with (args.out/f'cell-{i:02d}.log').open('w') as log:
            try:
                process=subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            except subprocess.TimeoutExpired:
                write(args.out/f'cell-{i:02d}-parent.json', dict(timeout=True, command=command))
                raise
        write(args.out/f'cell-{i:02d}-parent.json', dict(returncode=process.returncode,
            elapsed_seconds=time.perf_counter()-start, command=command))
        if process.returncode:
            raise RuntimeError(f'worker failed: {output}')
        row=json.loads(output.read_text()); rows.append(row)
        ratio=statistics.median([r['arms']['incumbent']['wall_seconds']/r['arms']['candidate']['wall_seconds'] for r in row['rounds']])
        print(f"{case['phase']} GF(2^{case['degree']}) {case['side']**2} {case['api']}: {ratio:.3f}x",flush=True)
    rss={}
    for api in ('pairs', 'cartesian'):
        rss[api]={}
        for arm in ('incumbent','candidate'):
            case=dict(degree=131, side=64, api=api, seed=2026092403)
            out=args.out/f'rss-{api}-{arm}.json'
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--case',json.dumps(case),
                '--worker-out',str(out),'--rss-arm',arm],check=True,timeout=180)
            rss[api][arm]=json.loads(out.read_text())['max_rss_bytes']
    report=summary(rows,intent['criteria'])
    report['rss_bytes']=rss
    report['rss_gate']=all(r['candidate']<=max(1.05*r['incumbent'],r['incumbent']+2*1024**2) for r in rss.values())
    report['decision']='PASS_LOCAL' if all([report['primary']['pass_gate'],report['confirmation']['pass_gate'],
        report['per_cell_gate'],report['cpu_gate'],report['rss_gate']]) else 'HOLD'
    write(args.out/'summary.json',report)
    # Diagnostic profiles are collected only after all uninstrumented timings.
    case=dict(degree=131,side=64,api='cartesian',seed=2026092404)
    curve,left,right,expected,_=fixtures(case)
    for arm,fn in functions(case,curve,left,right).items():
        profiler=cProfile.Profile();profiler.enable()
        checked(fn,expected,10)
        profiler.disable()
        with (args.out/f'profile-{arm}.txt').open('w') as stream:
            pstats.Stats(profiler,stream=stream).sort_stats('tottime').print_stats(30)
    print(json.dumps({k:v for k,v in report.items() if k!='cells'},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path)
    parser.add_argument('--case')
    parser.add_argument('--worker-out',type=Path)
    parser.add_argument('--rss-arm',choices=['incumbent','candidate'])
    args=parser.parse_args()
    worker(args) if args.case else run(args)
