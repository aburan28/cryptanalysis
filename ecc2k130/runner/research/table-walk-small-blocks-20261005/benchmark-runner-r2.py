"""Correctness-first table-walk cache-policy screen and conditional 22B confirmation."""
import argparse,array,datetime,hashlib,json,os,re,statistics,struct,subprocess,time
from pathlib import Path
from maintenance_guard import validate_held,validate_maintenance

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True);args=parser.parse_args();root=args.results;root.mkdir(exist_ok=False)
receipt=Path(os.environ['ECC_APPROVED_BENCHMARK_RECEIPT']);maintenance=json.loads(receipt.read_text());assert maintenance['approval']['round_id']=='20261005-table-walk-small-blocks-r2'
env=dict(os.environ);env['LD_LIBRARY_PATH']='/usr/local/cuda-13.3/lib64'+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
manifest=json.loads(Path(__file__).with_name('input-manifest.json').read_text())
build_path=Path(__file__).with_name('build-status.json');build=json.loads(build_path.read_text());assert build['phase']=='finished'
control=manifest['control'];control['flags']={x[2:].split('=',1)[0]:x.split('=',1)[1] for x in control['command'] if x.startswith('-D') and '=' in x}
profiles={'control':control,**{k:v for k,v in build['profiles'].items() if v['exit']==0}}
data=dict(driver_route='Host driver; CUDA 13.x minor-version compatibility, sm_120 binary',build_compiler='CUDA 13.3.73',started_utc=now(),phase='running',goal_b=22,target_met=False,correctness=[],screens=[],sustained=[],references=[],failed_builds={k:v for k,v in build['profiles'].items() if v['exit']!=0},unit='Completed elliptic-curve point updates, no field-operation or pair multiplier',screen_scope='64-launch throughput-only cells, no DP verification inside these cells; correctness gates run separately',confirmation_scope='Five fresh 512-launch DP32 samples including three CPU report replays per sample, DP handling and final GPU synchronization; initialization excluded')
def save():
    t=root/'results.tmp';t.write_text(json.dumps(data,indent=2)+'\n');t.replace(root/'results.json')
def capture(cmd,timeout=100):
    validate_held(json.loads(receipt.read_text()))
    start=time.monotonic();stamp=now()
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=timeout);row=dict(command=cmd,exit=r.returncode,raw=r.stdout+r.stderr)
    except subprocess.TimeoutExpired as e:
        decode=lambda v:v.decode(errors='replace') if isinstance(v,bytes) else v or ''
        row=dict(command=cmd,exit=124,timed_out=True,raw=decode(e.stdout)+decode(e.stderr))
    row.update(started_utc=stamp,finished_utc=now(),elapsed_wall_s=time.monotonic()-start);return row
def sample(label,profile,workers,steps,launches,seed,weight=32,verify=3,checkpoint=None,bench=False,dp_capacity=None):
    assert 0<=seed<=65535 and workers>0 and steps>0 and launches>0 and 0<=weight<=131
    assert dp_capacity is None or dp_capacity>0
    batch=int(profile['flags']['ECC_BATCH']);points=root/(label+'.points')
    resume=bool(checkpoint and checkpoint.exists())
    before_bytes=points.stat().st_size if points.exists() else 0
    if points.exists() and not resume:
        raise RuntimeError('Fresh sample has an existing report file: '+label)
    if before_bytes%32:
        raise RuntimeError('Existing report file contains an incomplete record: '+label)
    cmd=[profile['binary'],'--curve','131','--packed','--device','0','--threads',str(workers),'--steps',str(steps),'--launches',str(launches),'--dp-weight',str(weight),'--run-id',str(seed),'--verify',str(verify),'--dp-file',str(points)]
    if checkpoint:cmd+=['--checkpoint',str(checkpoint)]
    if bench:cmd+=['--bench']
    if dp_capacity is not None:cmd+=['--dp-cap',str(dp_capacity)]
    row=capture(cmd);raw=row['raw'];match=re.search(r'finished: ([0-9.]+) M it/s, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)',raw);counts=re.findall(r'M it/s\s+(\d+) iterations',raw);expected=workers*batch*steps*launches
    valid=row['exit']==0 and bool(match) and bool(counts) and int(counts[-1])==expected and f'{workers} threads x {batch} slots x 1 lanes = {workers*batch} walks' in raw and not any(t in raw for t in ('MISMATCH','stopping:','DP OVERFLOW','NO\n'))
    if valid:valid=int(match[3])==verify and int(match[4])==0 and points.is_file() and points.stat().st_size-before_bytes==int(match[2])*32
    expected_persist=int(profile['flags'].get('ECC_PACKED_L2_PERSIST',0))
    expected_policy=int(profile['flags'].get('ECC_PACKED_L2_POLICY',0))
    window=re.search(r'packed L2 persist window: (\d+) of (\d+) field bytes, cap (\d+), policy (\d+), hit ratio ([0-9.eE+-]+)',raw)
    cache_valid=f'packed L2 persist: {expected_persist}\n' in raw
    if expected_persist:
        cache_valid=cache_valid and bool(window) and int(window[4])==expected_policy
        if window:
            window_bytes,field_bytes,cap_bytes=int(window[1]),int(window[2]),int(window[3])
            cache_valid=cache_valid and 0<window_bytes<=field_bytes and cap_bytes>0
            if expected_policy==0:cache_valid=cache_valid and window_bytes==min(field_bytes,cap_bytes)
            hit=float(window[5]);expected_hit=(min(1.0,cap_bytes/window_bytes) if expected_policy==1 and window_bytes>0 else 0.5 if expected_policy==2 else 1.0)
            cache_valid=cache_valid and abs(hit-expected_hit)<=0.000001
    else:
        cache_valid=cache_valid and window is None
    valid=valid and cache_valid
    row.update(cache_configuration_verified=cache_valid,cache_persist=expected_persist,cache_policy=expected_policy)
    if window:row['cache_window']=dict(bytes=int(window[1]),field_bytes=int(window[2]),reservation_limit_bytes=int(window[3]),hit_ratio=float(window[5]))
    row.update(label=label,valid=valid,batch=batch,workers=workers,steps=steps,launches=launches,run_id=seed,bench=bench,expected_updates=expected,reported_updates=int(counts[-1]) if counts else None,rate_b=float(match[1])/1000 if valid else None,verified=int(match[3]) if match else None,dropped=int(match[4]) if match else None,points_count=int(match[2]) if match else None)
    if points.exists():row.update(points_sha256=sha(points),points_bytes=points.stat().st_size,points_bytes_before=before_bytes,points_bytes_appended=points.stat().st_size-before_bytes)
    print('TABLE_RESULT '+json.dumps({k:row[k] for k in ('label','valid','rate_b','reported_updates','verified')}),flush=True)
    return row
def logical_checkpoint(path):
    blob=path.read_bytes();magic,version,degree,workers,batch,lanes,seed,iters=struct.unpack_from('<8s6IQ',blob);count=workers*batch
    assert (magic,version,degree,lanes)==(b'ECC2K130',3,131,1) and len(blob)==40+count*68
    xs=array.array('I');xs.frombytes(blob[40:40+count*20]);ys=array.array('I');ys.frombytes(blob[40+count*20:40+count*40])
    dead=array.array('I');dead.frombytes(blob[40+count*40:40+count*44]);rest=[]
    for i in range(3):v=array.array('Q');v.frombytes(blob[40+count*(44+8*i):40+count*(52+8*i)]);rest.append(v)
    normalized=hashlib.sha256();normalized.update(struct.pack('<IIIQ',count,degree,seed,iters))
    for id in range(count):
        slot,tid=divmod(id,workers);index=lambda word:(slot*5+word)*workers+tid
        normalized.update(struct.pack('<11I3Q',*[xs[index(w)] for w in range(5)],*[ys[index(w)] for w in range(5)],dead[id],*(v[id] for v in rest)))
    return normalized.hexdigest()
def corpus(path):
    b=path.read_bytes();assert len(b)%32==0
    return hashlib.sha256(b''.join(sorted(b[i:i+32] for i in range(0,len(b),32)))).hexdigest()
save();telemetry=None
try:
    for profile in profiles.values():assert sha(Path(profile['binary']))==profile['binary_sha256']
    for source in {p['source'] for p in profiles.values()}:
        for name,h in manifest['source_files'].items():assert sha(Path(source)/name)==h,name
    data['isolation']=validate_maintenance(capture(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])['raw'],receipt)
    data['hardware']=capture(['nvidia-smi','-q']);data['toolkit']=capture(['/usr/local/cuda-13.3/bin/nvcc','--version']);assert 'V13.3.73' in data['toolkit']['raw'];save()
    log=(root/'telemetry.csv').open('x');telemetry=subprocess.Popen(['nvidia-smi','--query-gpu=timestamp,uuid,clocks.current.sm,power.draw,power.limit,temperature.gpu,utilization.gpu,utilization.memory','--format=csv','--loop-ms=500'],stdout=log,stderr=subprocess.STDOUT)
    signatures=[]
    # Correctness uses the same complete population as throughput. Sparse DP44
    # reports bound CPU bookkeeping; all profiles retain 300 reference replays.
    for label,profile in profiles.items():
        batch=int(profile['flags']['ECC_BATCH']);workers=87040;assert batch==16
        ckpt=root/(f'correct-{label}.checkpoint');row=sample(f'correct-{label}',profile,workers,17,2,65100,44,300,ckpt,dp_capacity=2097152);row['profile']=label;data['correctness'].append(row);save();assert row['valid'],row
        signature=(logical_checkpoint(ckpt),corpus(root/(f'correct-{label}.points')));row.update(logical_checkpoint_sha256=signature[0],sorted_points_sha256=signature[1],checkpoint_sha256=sha(ckpt));signatures.append(signature);save()
        assert signature==signatures[0],(label,signature,signatures[0])
    data['matched_population']=1392640;data['correctness_dp_weight']=44;data['all_logical_states_equal']=True;save()
    # Same population throughout. Control bookends each candidate's paired
    # short screens to expose drift; these screens do not prove sustained 22B.
    for label,profile in profiles.items():
        if label=='control':continue
        for position,which in enumerate(('control',label,label,'control')):
            candidate=profiles[which]
            threads=int(candidate['flags']['ECC_THREADS'])
            row=sample(f'screen-{label}-{position}-{which}',candidate,87040,1024,64,65200,0,0,bench=True)
            row.update(profile=which,blocks=87040//threads,paired_candidate=label,paired_position=position)
            data['screens'].append(row);save();assert row['valid'],row
    # Select a profile by its median paired-screen rate, rather than a single
    # fastest cell. Sustained confirmation remains the acceptance result.
    medians={label:statistics.median(row['rate_b'] for row in data['screens'] if row['profile']==label) for label in profiles}
    label=max(medians,key=medians.get)
    best=dict(next(row for row in data['screens'] if row['profile']==label))
    best['rate_b']=medians[label]
    data['screen_medians_b']=medians
    data['selected']={k:best[k] for k in ('profile','workers','batch','blocks','rate_b')};chosen=profiles[best['profile']];save()
    # The selected configuration gets 300 fresh independent report replays.
    row=sample('selected-replay300',chosen,87040,17,2,65300,44,300,dp_capacity=2097152);data['correctness'].append(row);save();assert row['valid'],row
    # Resume and uninterrupted runs must agree byte-for-byte at fixed geometry.
    ckpt=root/'selected-resume.checkpoint'
    for part in (1,2):
        row=sample('selected-resume',chosen,87040,17,1,65301,44,16,ckpt,dp_capacity=2097152);data['correctness'].append(row);save();assert row['valid'],row
    straight=root/'selected-straight.checkpoint';row=sample('selected-straight',chosen,87040,17,2,65301,44,16,straight,dp_capacity=2097152);data['correctness'].append(row);save();assert row['valid'],row
    assert sha(ckpt)==sha(straight) and corpus(root/'selected-resume.points')==corpus(root/'selected-straight.points');data['checkpoint_resume_passed']=True;save()
    repetitions=5;data['confirmation_repetitions']=repetitions;save()
    for rep in range(repetitions):
        row=sample(f'sustained-{rep}',chosen,best['workers'],1024,512,65400+rep);data['sustained'].append(row);save();assert row['valid'],row
        if rep in (0,repetitions-1):
            row=sample(f'reference-{rep}',control,87040,1024,512,65500+rep);data['references'].append(row);save();assert row['valid'],row
    rates=[x['rate_b'] for x in data['sustained']]
    data.update(median_b=statistics.median(rates),minimum_b=min(rates),maximum_b=max(rates),correctness_complete=True,target_met=len(rates)==5 and statistics.median(rates)-0.0000005>=22,phase='finished',finished_utc=now());save()
except Exception as e:
    data.update(phase='failed',error=str(e),finished_utc=now());save();raise
finally:
    if telemetry is not None:telemetry.terminate();telemetry.wait(timeout=5);log.close()
