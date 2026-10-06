"""Frozen two-vs-three-block launch-bound experiment; defaults stay unchanged."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time

import native_candidate_bench as bench
from profile_goal28 import tool


def comparison(pairs):
    """Two-sided Student-t interval for the mean paired log ratio, n=5."""
    if len(pairs) != 5: raise ValueError('the frozen experiment requires five pairs')
    logs=[math.log(p['ratio']) for p in pairs]
    mean=statistics.mean(logs)
    margin=2.7764451051977987*statistics.stdev(logs)/math.sqrt(5)
    low,high=math.exp(mean-margin),math.exp(mean+margin)
    control=statistics.median(p['samples']['2']['rate'] for p in pairs)
    candidate=statistics.median(p['samples']['3']['rate'] for p in pairs)
    return dict(controlMPerSecond=control,candidateMPerSecond=candidate,
                ratio=candidate/control,pairedGeometricRatio=math.exp(mean),
                pairedLogT95=[low,high],allPairsFaster=all(p['ratio']>1 for p in pairs),
                passesAcceptance=candidate/control>=1.01 and low>1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    result=dict(valid=False,compileOnly=False,goalBPerSecond=28,
                experiment='ECC_MINBLOCKS=2 versus 3; all other build flags identical',
                fieldProductsPerScalarUpdate=5.3125,fieldProductRatioToControl=1.0,
                endToEndDlpSpeedup=None,builds={},gates={},warmups=[],pairs=[])
    started=time.monotonic()
    def save(): (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def stage(name):
        status=dict(stage=name,elapsedSeconds=round(time.monotonic()-started))
        (out/'progress.json').write_text(json.dumps(status)+'\n');save();print(json.dumps(status),flush=True)
    def command(label,argv,timeout=900):
        row=bench.run(argv,timeout=timeout);(out/(label+'.log')).write_text(row['raw'])
        result.setdefault('commands',{})[label]=row;save();return bench.require(row)
    try:
        stage('GPU identity and compiler')
        identities=command('gpu',['nvidia-smi','--query-gpu=name,uuid,driver_version,compute_cap','--format=csv,noheader'])['raw'].strip().splitlines()
        if len(identities)!=1 or not identities[0].endswith('12.0') or not any(x in identities[0] for x in ('RTX PRO 4500 Blackwell Server Edition','RTX PRO 6000 Blackwell Server Edition')):
            raise RuntimeError('requires one supported sm_120 GPU')
        result['gpuIdentity']=identities[0];result['matchesHistoricalGpuModel']='RTX PRO 6000' in identities[0]
        os.environ['CUDA_VISIBLE_DEVICES']=identities[0].split(',')[1].strip();os.environ['CUDA_DISABLE_PTX_JIT']='1';os.environ.pop('PYTHONOPTIMIZE',None)
        command('gpu-before',['nvidia-smi','-q'])
        nvcc=tool('nvcc',['usr/local/cuda/bin/nvcc'])
        if 'V13.3.73' not in command('nvcc',[nvcc,'--version'])['raw']:raise RuntimeError('requires nvcc 13.3.73')
        (bench.ROOT/'generated').mkdir(exist_ok=True);command('generate',['make','generate'])
        reference={}
        for blocks in ('2','3'):
            stage('compile MINBLOCKS '+blocks)
            directory=out/blocks;directory.mkdir()
            _,build=bench.compile_mode('control',nvcc,directory,minblocks=int(blocks))
            result['builds'][blocks]=build;save();binary=directory/'control/client'
            stage('correctness MINBLOCKS '+blocks)
            gates=result['gates'][blocks]={}
            for probe in ('arithmetic','storage','sigma'):
                gates[probe]=command(blocks+'-'+probe,[directory/'control'/probe])
            bench.markers(gates['arithmetic']['raw'],'control',arithmetic=True)
            if 'PASS: 6240 GPU paired Frobenius vectors' not in gates['arithmetic']['raw'] or 'PASS: 114 complete block mask snapshots, 51072 words' not in gates['sigma']['raw']:
                raise RuntimeError('incomplete device gates')
            gates['integration']=command(blocks+'-integration',[sys.executable,'codegen/testpackedclient.py',binary])
            # The CUDA occupancy API reports the actual allocation for this binary.
            gates['occupancy']=command(blocks+'-occupancy',[binary,'--packed','--curve','131','--threads',0,'--steps',1,'--launches',1,'--bench','--verify',0])
            matches=re.findall(r'(\d+) block\(s\) of 256 packed threads resident per SM',gates['occupancy']['raw'])
            if len(matches)!=1:raise RuntimeError('runtime occupancy missing')
            build['residentBlocksPerSm']=int(matches[0]);save()
            for workers in (8,128,257):
                cp=directory/f'cross-{workers}.ck'
                command(blocks+'-checkpoint-'+str(workers),[binary,'--packed','--curve','131','--bench','--threads',workers,'--steps',16,'--launches',4,'--verify',0,'--checkpoint',cp])
                data=cp.read_bytes()
                if blocks=='2':reference[workers]=data
                elif data!=reference[workers]:raise RuntimeError('cross-binary checkpoint mismatch')
                gates.setdefault('checkpointSha256',{})[str(workers)]=bench.digest(cp)
        control,candidate=(result['builds'][b] for b in ('2','3'))
        if candidate['residentBlocksPerSm']<=control['residentBlocksPerSm']:
            raise RuntimeError('candidate did not increase resident blocks; abandon hypothesis')
        # The experiment is rejected before a long run if register capping spills.
        if any(candidate['walkResources'][k] for k in ('stackBytes','localBytes')):
            raise RuntimeError('candidate spills; abandon launch-bound experiment')
        corpus_reference=None
        def sample(blocks,weight,label):
            nonlocal corpus_reference
            binary=out/blocks/'control/client'
            if bench.digest(binary)!=result['builds'][blocks]['builds']['client']['binarySha256']:raise RuntimeError('binary changed')
            argv=[binary,'--packed','--curve','131','--threads',bench.WORKERS,'--steps',bench.STEPS,'--launches',bench.LAUNCHES,'--verify',0]
            corpus=out/(label+'.bin') if weight else None
            argv+=['--dp-weight',34,'--dp-file',corpus] if weight else ['--bench']
            stage(label);row=bench.validate_sample(command(label,argv,300),'control',weight,corpus)
            if corpus:
                key=(row['corpusRecords'],row['corpusSha256'])
                if corpus_reference is None:corpus_reference=key
                elif key!=corpus_reference:raise RuntimeError('DP multisets differ')
            return row
        for weight in (0,34):
            for blocks in ('2','3'):
                result['warmups'].append(dict(minblocks=blocks,weight=weight,sample=sample(blocks,weight,f'warm-{blocks}-{weight}')));save()
            for repeat in range(5):
                order=['2','3'] if repeat%2==0 else ['3','2']
                pair=dict(weight=weight,repeat=repeat,order=order,samples={});result['pairs'].append(pair)
                for blocks in order:
                    pair['samples'][blocks]=sample(blocks,weight,f'pair-{weight}-{repeat}-{blocks}');save()
                pair['ratio']=pair['samples']['3']['rate']/pair['samples']['2']['rate'];save()
        result['comparisons']={str(w):comparison([p for p in result['pairs'] if p['weight']==w]) for w in (0,34)}
        result['passesAcceptance']=all(r['passesAcceptance'] for r in result['comparisons'].values())
        result['meets28BGoal']=result['matchesHistoricalGpuModel'] and result['passesAcceptance'] and result['comparisons']['0']['candidateMPerSecond']>=28000
        command('gpu-after',['nvidia-smi','-q'])
        for blocks in ('2','3'):
            if bench.digest(out/blocks/'control/client')!=result['builds'][blocks]['builds']['client']['binarySha256']:raise RuntimeError('binary changed during run')
        result['valid']=True;stage('complete; defaults unchanged')
    except Exception as exc:
        result['error']=str(exc);stage('failed or predeclared abandonment; logs retained')
    save();return 0 if result['valid'] else 1

if __name__=='__main__':raise SystemExit(main())
