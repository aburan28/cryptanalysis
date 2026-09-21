"""Profile the frozen packed control; screen grid size at equal completed work.

Profiler traces are diagnostics, never throughput samples or full-DLP results.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import time

import native_candidate_bench as bench


def tool(name, patterns):
    found=shutil.which(name)
    if found:return found
    for pattern in patterns:
        candidates=sorted(Path('/').glob(pattern))
        if candidates:return str(candidates[-1])
    raise RuntimeError(name+' is not installed')


def timing(raw, workers, steps, launches, weight):
    bench.markers(raw,'control')
    expected=workers*16*steps*launches
    geometry=f'{workers} threads x 16 slots x 1 lanes = {workers*16} walks, dp weight {weight}, {steps} steps per launch'
    if geometry not in raw:raise RuntimeError('wrong geometry')
    rows=re.findall(r'([0-9.]+) M it/s\s+(\d+) iterations\s+(\d+) dp\s+(\d+) stored\s+(\d+) dropped',raw)
    if not rows:raise RuntimeError('no completed iteration row')
    counts=[int(row[1]) for row in rows]
    if counts!=sorted(counts) or any(not 0<x<=expected for x in counts) or any(int(row[4]) for row in rows):raise RuntimeError('invalid progress counts')
    rate,count,dp,stored,dropped=rows[-1]
    if int(count)!=expected or int(dropped) or int(dp)!=int(stored):raise RuntimeError('incomplete work or dropped reports')
    final=re.findall(r'finished: ([0-9.]+) M it/s,',raw)
    if len(final)!=1 or not math.isfinite(float(final[0])) or float(final[0])<=0 or not math.isclose(float(final[0]),float(rate),rel_tol=1e-6,abs_tol=0.01):raise RuntimeError('missing or inconsistent final rate')
    return dict(rateMPerSecond=float(final[0]),iterations=expected,workers=workers,
                steps=steps,launches=launches,dpWeight=weight,records=int(stored))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--counters-only',action='store_true',help='retry hardware sections with application replay, without repeating the grid screen')
    modes.add_argument('--range-only',action='store_true',help='diagnostic marked-range replay and independent profiler smoke checks; no throughput screen')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    result=dict(valid=False,compileOnly=False,goalBPerSecond=28,profileOnly=True,
                fieldProductsPerScalarUpdate=5+5/16,fieldProductRatioToControl=1.0,
                countersOnly=args.counters_only,rangeOnly=args.range_only)
    start=time.monotonic()
    def save(): (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def stage(name):
        status={'stage':name,'elapsedSeconds':round(time.monotonic()-start)}
        (out/'progress.json').write_text(json.dumps(status)+'\n');print(json.dumps(status),flush=True);save()
    def command(name,argv,timeout=600,required=True):
        row=bench.run(argv,timeout=timeout)
        (out/(name+'.log')).write_text(row['raw'])
        result.setdefault('commands',{})[name]=row
        save()
        return bench.require(row) if required else row
    try:
        stage('hardware and profiler versions')
        identity=command('gpu',['nvidia-smi','--query-gpu=name,uuid,driver_version,compute_cap','--format=csv,noheader'])['raw'].strip().splitlines()
        if len(identity)!=1 or not identity[0].endswith('12.0') or not any(x in identity[0] for x in ['RTX PRO 6000 Blackwell Server Edition','RTX PRO 4500 Blackwell Server Edition']):raise RuntimeError('requires one supported sm_120 GPU')
        result['gpuIdentity']=identity[0];result['matchesHistoricalGpuModel']='RTX PRO 6000' in identity[0]
        os.environ['CUDA_VISIBLE_DEVICES']=identity[0].split(',')[1].strip();os.environ['CUDA_DISABLE_PTX_JIT']='1';os.environ.pop('PYTHONOPTIMIZE',None)
        command('gpu-before',['nvidia-smi','-q'])
        nvcc=tool('nvcc',['usr/local/cuda/bin/nvcc'])
        nsys=tool('nsys',['opt/nvidia/nsight-systems/*/bin/nsys','opt/nvidia/nsight-systems/*/target-linux-x64/nsys'])
        ncu=tool('ncu',['opt/nvidia/nsight-compute/*/ncu','usr/local/cuda*/NsightCompute-*/ncu'])
        for name,path in [('nvcc',nvcc),('nsys',nsys),('ncu',ncu)]:command(name+'-version',[path,'--version'])
        if 'V13.3.73' not in result['commands']['nvcc-version']['raw']:raise RuntimeError('nvcc must be 13.3.73')
        stage('compile control and correctness probes')
        (bench.ROOT/'generated').mkdir(exist_ok=True);command('generate',['make','generate'],180)
        _,result['build']=bench.compile_mode('control',nvcc,out,profile_range=args.range_only);save()
        binary=out/'control/client'
        stage('device correctness and checkpoint integration')
        for probe in ('arithmetic','storage','sigma'):command(probe,[out/'control'/probe])
        command('integration',[sys.executable,'codegen/testpackedclient.py',binary],900)
        if args.range_only:
            stage('independent profiler smoke workload')
            smoke=out/'profiler-smoke'
            command('smoke-build',[nvcc,'-O3','-gencode','arch=compute_120,code=sm_120','src/testprofilersmoke.cu','-o',smoke])
            command('smoke-correctness',[smoke])
            for replay in ('kernel','app-range'):
                command('smoke-ncu-'+replay,[ncu,'--metrics','gpu__time_duration.sum','--replay-mode',replay,'--launch-count','1','--clock-control','none','--force-overwrite','--export',out/('smoke-'+replay),smoke],300,required=False)
        stage('Nsight Systems timeline')
        argv=[binary,'--packed','--curve','131','--threads',385024,'--steps',128,'--launches',4,'--bench','--verify',0]
        command('nsys-profile',[nsys,'profile','--trace=cuda,nvtx,osrt','--sample=none','--cpuctxsw=none','--force-overwrite=true','-o',out/'timeline',*argv],600)
        command('nsys-stats',[nsys,'stats','--report=cuda_gpu_kern_sum,cuda_api_sum,cuda_gpu_mem_time_sum','--format=csv',out/'timeline.nsys-rep'],300)
        # Counter replay has explicit cache/clock controls and short kernels;
        # its durations must never be used as speedup measurements.
        result['ncuProfiles']={}
        for workers in (385024,96256):
            stage('Nsight Compute counters '+str(workers))
            report=out/f'kernel-{workers}'
            argv=[binary,'--packed','--curve','131','--threads',workers,'--steps',32,'--launches',2,'--bench','--verify',0]
            sections=([flag for name in ['SpeedOfLight','Occupancy','SchedulerStats','WarpStateStats','MemoryWorkloadAnalysis','ComputeWorkloadAnalysis'] for flag in ('--section',name)] if args.counters_only else ['--set','full'])
            replay='application' if args.counters_only else 'kernel'
            selection=['--kernel-name-base','demangled','--kernel-name','regex:eccPacked131::walk','--launch-skip','1','--launch-count','1']
            if args.range_only:
                replay='app-range';selection=['--range-filter',':2:','--launch-count','1']
                sections=[flag for name in ('SpeedOfLight','MemoryWorkloadAnalysis','ComputeWorkloadAnalysis') for flag in ('--section',name)]
            row=command('ncu-'+str(workers),[ncu,*selection,*sections,'--replay-mode',replay,'--cache-control','all','--clock-control','none','--force-overwrite','--export',report,*argv],900,required=False)
            result['ncuProfiles'][str(workers)]={'returncode':row['returncode']}
            if row['returncode']==0 and report.with_suffix('.ncu-rep').exists():
                command('ncu-raw-'+str(workers),[ncu,'--import',report.with_suffix('.ncu-rep'),'--page','raw','--csv'],300)
                command('ncu-details-'+str(workers),[ncu,'--import',report.with_suffix('.ncu-rep'),'--page','details'],300)
            else:result['ncuProfiles'][str(workers)]['error']=row['raw'][-3000:]
        if not (args.counters_only or args.range_only):
            stage('unprofiled geometry screen')
            # Each row completes the SAME 201,863,462,912 scalar updates. Smaller
            # grids run more launches. Different grids are distinct seed panels;
            # this is a tuning screen, not a claimed matched-corpus speedup.
            result['screen']=[]
            for repeat in range(3):
                for workers in ([385024,192512,96256] if repeat%2==0 else [96256,192512,385024]):
                    launches=32*(385024//workers)
                    for weight in (0,34):
                        label=f'screen-{repeat}-{workers}-{weight}';stage(label)
                        argv=[binary,'--packed','--curve','131','--threads',workers,'--steps',1024,'--launches',launches,'--verify',0]
                        corpus=out/(label+'.bin')
                        argv+=['--dp-weight',34,'--dp-file',corpus] if weight else ['--bench']
                        row=command(label,argv,240);sample=timing(row['raw'],workers,1024,launches,weight)
                        if weight:
                            data=corpus.read_bytes()
                            if len(data)!=sample['records']*32:raise RuntimeError('corpus size mismatch')
                            sample['corpusSha256']=bench.digest(corpus)
                        sample['repeat']=repeat;sample['commandLog']=label+'.log'
                        result['screen'].append(sample);save()
            result['screenMedians']={str(w):{str(d):statistics.median(s['rateMPerSecond'] for s in result['screen'] if s['workers']==w and s['dpWeight']==d) for d in (0,34)} for w in (385024,192512,96256)}
        if bench.digest(binary)!=result['build']['builds']['client']['binarySha256']:raise RuntimeError('binary changed')
        command('gpu-after',['nvidia-smi','-q'])
        result['valid']=all(r['returncode']==0 for r in result['ncuProfiles'].values()) and all((out/f'kernel-{w}.ncu-rep').exists() for w in (385024,96256))
        stage('complete' if result['valid'] else 'profiler failure; retain timing and diagnostic logs')
    except Exception as exc:
        result['error']=str(exc);stage('failed; retained logs')
    save();print(json.dumps({k:result[k] for k in ('valid','error','screenMedians','ncuProfiles') if k in result}),flush=True)
    return 0 if result['valid'] else 1

if __name__=='__main__':raise SystemExit(main())
