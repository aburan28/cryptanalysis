"""Frozen same-GPU comparison of native square and three-limb Karatsuba.

Compile-only works without a GPU. Full mode requires one sm_120 RTX PRO 6000
Server Edition or RTX PRO 4500, CUDA 13.3.73, and keeps all four binaries on
that same device. The receipt flags whether the historical GPU model matches.
No campaign files or persistent worker state are read or changed.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

from benchreport import benchResult

ROOT = Path(__file__).resolve().parents[1]
MODES = dict(control=(0,0), square=(1,0), karat3=(0,1), combined=(1,1))
FLAGS = dict(ECC_BATCH=16, ECC_THREADS=256, ECC_MINBLOCKS=2,
             ECC_STREAM_KARAT=0, ECC_SMEM_SPILL=0,
             ECC_PACKED_SINGLE_PRODUCT=1, ECC_PACKED_CACHE_DENOM=1, ECC_PACKED_BY_VALUE=1,
             ECC_PACKED_PERM_SIGMA=3, ECC_PACKED_POLY_CHAIN=1, ECC_PACKED_UNROLL_INV=1,
             ECC_PACKED_PAIR_PRODUCTS=1, ECC_PACKED_POLY_STATE=1, ECC_PACKED_DIRECT_REDUCE=1,
             ECC_PACKED_GENERATED_PRODUCT=1, ECC_PACKED_CLMAD=1, ECC_PACKED_STATE_TILE=256,
             ECC_PACKED_WEIGHTED_PREFIX=2, ECC_PACKED_COMPACT_STATE=1, ECC_PACKED_SHARED_SIGMA=1)
WORKERS, BATCH, STEPS, LAUNCHES = 385024, 16, 1024, 32
ITERATIONS = WORKERS * BATCH * STEPS * LAUNCHES
WALK = '_ZN12eccPacked1314walkE10WalkParamsIjEPj'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, timeout=240, cwd=ROOT):
    started = time.monotonic()
    p = subprocess.run([str(x) for x in command], cwd=cwd, text=True,
                       capture_output=True, timeout=timeout)
    return dict(command=[str(x) for x in command], returncode=p.returncode,
                raw=p.stdout+p.stderr, wallSeconds=time.monotonic()-started)


def require(row):
    if row['returncode'] or 'MISMATCH' in row['raw'] or 'stopping:' in row['raw']:
        raise RuntimeError(json.dumps(row))
    return row


def markers(raw, mode, arithmetic=False):
    if not arithmetic and re.search(r'^packed profile ranges: [1-9]',raw,re.M):
        raise RuntimeError('range-instrumented diagnostic is not a throughput sample')
    square,karat = MODES[mode]
    expected = {'direct reduction':1, 'generated product':1, 'native carryless multiply':1,
                'native carryless square':square, 'three-limb Karatsuba':karat, 'weighted prefix':2}
    if not arithmetic:
        expected.update({'compact state':1,'shared sigma':1,'state tile':256})
    prefix = 'packed arithmetic ' if arithmetic else 'packed '
    for label,value in expected.items():
        if re.findall('^'+prefix+re.escape(label)+r': (.*)$',raw,re.M) != [str(value)]:
            raise RuntimeError('missing/duplicate/wrong mode: '+prefix+label)


def sass_counts(text):
    counts=Counter(); active=False
    for line in text.splitlines():
        section=re.search(r'\.section\s+\.text\.([^,\s]+)',line)
        if section: active=section[1]==WALK
        ins=re.match(r'\s*/\*[0-9a-f]+\*/\s+(?:@!?(?:P|UP)\d+\s+)?([A-Z][A-Z0-9.]*)\s',line)
        if active and ins: counts[ins[1]]+=1
    if not counts or not counts['CLMAD.LO']: raise RuntimeError('native walk SASS missing')
    return dict(instructions=sum(counts.values()), nonNop=sum(counts.values())-counts['NOP'],
                opcodes=dict(counts), scope='static walk text section, including each out-of-line helper once')


def compile_mode(mode, nvcc, out, minblocks=None, profile_range=False):
    square,karat=MODES[mode]
    flags=dict(FLAGS,ECC_PACKED_CLMAD_SQUARE=square,ECC_PACKED_KARAT3=karat)
    if minblocks is not None:
        if minblocks not in (2,3): raise ValueError('unsupported launch-bound experiment')
        flags['ECC_MINBLOCKS']=minblocks
    if profile_range: flags['ECC_PROFILE_RANGE']=1
    common=[nvcc,'-O3','-std=c++17','-gencode','arch=compute_120,code=sm_120',
            '-Xptxas','-v','-lineinfo','-Xcompiler','-O3','-Xcompiler','-fopenmp']
    common+=['-D'+key+'='+str(value) for key,value in flags.items()]
    directory=out/mode; directory.mkdir()
    result=dict(flags=flags,builds={})
    for name,source in [('client','main.cu'),('arithmetic','testpackedcuda.cu'),
                        ('storage','testpackedstatecuda.cu'),('sigma','testsharedsigmacuda.cu')]:
        binary=directory/name
        row=run(common+['src/'+source,'-o',binary,'-lgomp'],timeout=900)
        (directory/(name+'.log')).write_text(row['raw'])
        require(row)
        row['binarySha256']=digest(binary); result['builds'][name]=row
    cuobjdump=Path(nvcc).with_name('cuobjdump'); nvdisasm=Path(nvcc).with_name('nvdisasm')
    require(run([cuobjdump,'--extract-elf','all',directory/'client'],cwd=directory))
    # nvcc's full executable has an empty first ELF; cuobjdump -sass crashes on
    # it in CUDA 13.3. Extract first and disassemble the populated cubin instead.
    cubins=list(directory.glob('*.cubin'))
    if len(cubins)!=1: raise RuntimeError('expected one native architecture')
    sass=require(run([nvdisasm,'-c',cubins[0]]))['raw']
    (directory/'walk.sass').write_text(sass)
    result['sass']=sass_counts(sass)
    resource=require(run([cuobjdump,'--dump-resource-usage',directory/'client']))['raw']
    result['resources']=resource
    m=re.search(re.escape('Function '+WALK+':')+r'\s+REG:(\d+) STACK:(\d+) SHARED:(\d+) LOCAL:(\d+)',resource)
    if not m: raise RuntimeError('walk resource usage missing')
    result['walkResources']=dict(zip(('registers','stackBytes','sharedBytes','localBytes'),map(int,m.groups())))
    (directory/'build.json').write_text(json.dumps(result,indent=2)+'\n')
    print(mode, result['walkResources'], result['sass']['instructions'],flush=True)
    return mode,result


def validate_sample(row, mode, weight, corpus=None):
    result=benchResult(row['command'],row['returncode'],row['raw'])
    if not result['valid']: raise RuntimeError('incomplete timed run: '+row['raw'])
    markers(row['raw'],mode)
    backend=re.findall(r'^backend cuda-packed131: (\d+) threads x (\d+) slots x 1 lanes = (\d+) walks, dp weight (\d+), (\d+) steps per launch$',row['raw'],re.M)
    if backend != [tuple(map(str,(WORKERS,BATCH,WORKERS*BATCH,weight,STEPS)))]:
        raise RuntimeError('wrong scalar geometry')
    progress=re.findall(r'M it/s\s+(\d+) iterations\s+\d+ dp\s+\d+ stored\s+(\d+) dropped',row['raw'])
    counts=[int(a) for a,b in progress]
    if (not counts or counts[-1]!=ITERATIONS or counts!=sorted(counts)
            or any(not 0<a<=ITERATIONS for a in counts) or any(int(b) for a,b in progress)):
        raise RuntimeError('incomplete scalar counts or dropped reports')
    final=re.findall(r'finished:.*?, (\d+) distinguished points \(0 verified against the reference, (\d+) dropped\)',row['raw'])
    if len(final)!=1 or int(final[0][1]): raise RuntimeError('bad final report count')
    result.update(iterations=ITERATIONS,wallSeconds=row['wallSeconds'])
    if corpus is not None:
        data=Path(corpus).read_bytes()
        if not data or len(data)!=32*int(final[0][0]): raise RuntimeError('DP corpus count differs')
        result['corpusRecords']=len(data)//32
        result['corpusSha256']=hashlib.sha256(b''.join(sorted(data[i:i+32] for i in range(0,len(data),32)))).hexdigest()
    return result


def gpu_runs(out, result, repeats):
    identity=require(run(['nvidia-smi','--query-gpu=name,uuid,driver_version,compute_cap','--format=csv,noheader']))['raw'].strip().splitlines()
    if len(identity)!=1 or not any(model in identity[0] for model in ('RTX PRO 6000 Blackwell Server Edition','RTX PRO 4500')) or not identity[0].endswith('12.0'):
        raise RuntimeError('requires exactly one RTX PRO 6000 Server or RTX PRO 4500 sm_120 GPU')
    result['gpuIdentity']=identity[0]
    result['matchesHistoricalGpuModel']='RTX PRO 6000 Blackwell Server Edition' in identity[0]
    os.environ['CUDA_VISIBLE_DEVICES']=identity[0].split(',')[1].strip()
    os.environ['CUDA_DISABLE_PTX_JIT']='1'
    os.environ.pop('PYTHONOPTIMIZE',None)
    result['gpuBefore']=require(run(['nvidia-smi','-q']))['raw']
    result['gates']={}
    reference_checkpoints={}
    for mode in MODES:
        directory=out/mode; gates=result['gates'][mode]={}
        for kind in ('arithmetic','storage','sigma'):
            gates[kind]=require(run([directory/kind]))
        markers(gates['arithmetic']['raw'],mode,arithmetic=True)
        if 'PASS: 6240 GPU paired Frobenius vectors' not in gates['arithmetic']['raw']:
            raise RuntimeError('paired Frobenius gate incomplete')
        storage=f'PASS: 128 GPU storage cases, {18584*BATCH} records, independent physical images and logical reads with canaries'
        if storage not in gates['storage']['raw']: raise RuntimeError('storage gate incomplete')
        if 'PASS: 114 complete block mask snapshots, 51072 words' not in gates['sigma']['raw']:
            raise RuntimeError('shared sigma gate incomplete')
        gates['integration']=require(run([sys.executable,'codegen/testpackedclient.py',directory/'client'],timeout=900))
        gates['checkpoints']={}
        for workers in (8,128,257):
            cp=directory/f'cross-{workers}.ck'
            gates['checkpoints'][str(workers)]=require(run([directory/'client','--packed','--curve','131','--bench',
                '--threads',workers,'--steps',16,'--launches',4,'--verify',0,'--checkpoint',cp]))
            data=cp.read_bytes()
            if mode=='control': reference_checkpoints[workers]=data
            elif data!=reference_checkpoints[workers]: raise RuntimeError('cross-binary checkpoint mismatch')
            gates['checkpoints'][str(workers)]['sha256']=digest(cp)
    result['warmups']=[]; result['pairs']=[]
    corpus_reference=None

    def sample(mode,weight,label):
        nonlocal corpus_reference
        binary=out/mode/'client'
        if digest(binary)!=result['builds'][mode]['builds']['client']['binarySha256']:
            raise RuntimeError('binary changed after validation')
        command=[binary,'--packed','--curve','131','--threads',WORKERS,'--steps',STEPS,'--launches',LAUNCHES,'--verify',0]
        corpus=None
        if weight:
            corpus=out/mode/(label+'.bin'); command+=['--dp-weight',34,'--dp-file',corpus]
        else: command+=['--bench']
        row=validate_sample(run(command,timeout=300),mode,weight,corpus)
        if corpus:
            key=(row['corpusRecords'],row['corpusSha256'])
            if corpus_reference is None: corpus_reference=key
            elif key!=corpus_reference: raise RuntimeError('DP multiset differs across runs/binaries')
        return row

    for weight in (0,34):
        for mode in MODES:
            result['warmups'].append(dict(mode=mode,weight=weight,sample=sample(mode,weight,f'warm-{weight}')))
        for repeat in range(repeats):
            for candidate in ('square','karat3','combined'):
                order=['control',candidate] if repeat%2==0 else [candidate,'control']
                pair=dict(candidate=candidate,weight=weight,repeat=repeat,order=order,samples={})
                result['pairs'].append(pair)
                for mode in order:
                    pair['samples'][mode]=sample(mode,weight,f'{candidate}-{weight}-{repeat}')
                pair['ratio']=pair['samples'][candidate]['rate']/pair['samples']['control']['rate']
                print(candidate,weight,repeat,pair['ratio'],flush=True)
                (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    result['comparisons']={}
    for candidate in ('square','karat3','combined'):
        comparison={}
        for weight in (0,34):
            pairs=[p for p in result['pairs'] if p['candidate']==candidate and p['weight']==weight]
            cand=statistics.median(p['samples'][candidate]['rate'] for p in pairs)
            control=statistics.median(p['samples']['control']['rate'] for p in pairs)
            comparison[str(weight)]=dict(candidateMPerSecond=cand,controlMPerSecond=control,
                ratio=cand/control,allPairsFaster=all(p['ratio']>1 for p in pairs))
        comparison['passesAcceptance']=all(comparison[str(w)]['ratio']>=1.01 and comparison[str(w)]['allPairsFaster'] for w in (0,34))
        result['comparisons'][candidate]=comparison
    result['gpuAfter']=require(run(['nvidia-smi','-q']))['raw']
    for mode in MODES:
        if digest(out/mode/'client')!=result['builds'][mode]['builds']['client']['binarySha256']:
            raise RuntimeError('binary changed during comparison')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--nvcc',default='nvcc')
    parser.add_argument('--compile-only',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    if not 3<=args.repeats<=5: parser.error('repeats must be 3 through 5')
    out=args.out.resolve(); out.mkdir(parents=True,exist_ok=False)
    result=dict(valid=False,compileOnly=args.compile_only,iterationsPerSample=ITERATIONS,
                fieldProductsPerScalarUpdate=5+5/16,fieldProductRatioToControl=1.0)
    try:
        nvcc=shutil.which(args.nvcc)
        if nvcc is None: raise RuntimeError('nvcc unavailable')
        result['compiler']=require(run([nvcc,'--version']))['raw']
        if 'V13.3.73' not in result['compiler']: raise RuntimeError('comparison is pinned to nvcc 13.3.73')
        (ROOT/'generated').mkdir(parents=True,exist_ok=True)
        require(run(['make','generate'],timeout=180))
        paths=sorted(p for base in ('include','src','generated','codegen') for p in (ROOT/base).rglob('*')
                     if p.is_file() and p.suffix in ('.h','.cuh','.cu','.cpp','.py'))
        result['sourceSha256']={str(p.relative_to(ROOT)):digest(p) for p in paths}
        with ThreadPoolExecutor(max_workers=2) as pool:
            result['builds']=dict(pool.map(lambda mode:compile_mode(mode,nvcc,out),MODES))
        if not args.compile_only: gpu_runs(out,result,args.repeats)
        result['valid']=True
    except Exception as exc:
        result['error']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k in ('valid','error','comparisons','compileOnly')},indent=2))
    return 0 if result['valid'] else 1


if __name__=='__main__':
    sys.exit(main())
