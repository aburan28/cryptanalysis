"""Verify host-policy variants and isolate their hints in shared-device paired screens."""
from pathlib import Path
import datetime,hashlib,json,os,re,signal,statistics,subprocess,time
ROOT=Path(__file__).resolve().parent
BUILD=Path('/workspace/benchmarks/table-walk-carveout-build-20261005-r1')
OLD=Path('/workspace/benchmarks/table-walk-small-blocks-point-checks-20261005-r5')
ORIGINAL='8c6985281bc69f9948cf97c15a1703c46e627a0cb856c82a3c580c9a081ca4e2'
GPU='GPU-351bf624-75e9-4b93-f2a9-7587cbac5398'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
clock=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
deadline=clock()+240
env=dict(os.environ);env['LD_LIBRARY_PATH']=':'.join(x for x in env.get('LD_LIBRARY_PATH','').split(':') if x and x!='/usr/local/cuda-13.3/compat')
def production():
    p=Path('/proc/79390');f=(p/'stat').read_text().rsplit(') ',1)[1].split()
    assert int(f[19])==70512044 and f[0] in ('R','S') and sha(p/'exe')==ORIGINAL
    return dict(pid=79390,state=f[0],start_ticks=int(f[19]),executable_sha256=ORIGINAL)
def save():
    tmp=ROOT/'results.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(ROOT/'results.json')
def capture(command):
    production();remaining=deadline-clock();assert remaining>0
    p=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        out,err=p.communicate(timeout=min(45,remaining));r=dict(exit=p.returncode,raw=out+err)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGTERM)
        try:out,err=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
        r=dict(exit=124,timed_out=True,raw=out+err)
    r['command']=command;production();return r
def corpus(path):
    b=path.read_bytes();assert len(b)%32==0
    return hashlib.sha256(b''.join(sorted(b[i:i+32] for i in range(0,len(b),32)))).hexdigest()
def sample(label,binary,seed,steps,launches,weight,verify,checkpoint=None,bench=False):
    assert 0<=seed<=65535
    points=ROOT/(label+'.points');assert not points.exists()
    command=[str(binary),'--curve','131','--packed','--device','0','--threads','87040',
        '--steps',str(steps),'--launches',str(launches),'--run-id',str(seed),'--dp-weight',str(weight),
        '--verify',str(verify),'--dp-file',str(points)]
    if checkpoint:command+=['--checkpoint',str(checkpoint),'--dp-cap','2097152']
    if bench:command+=['--bench']
    row=capture(command);raw=row['raw']
    final=re.search(r'finished: ([0-9.]+) M it/s, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)',raw)
    counts=re.findall(r'M it/s\s+(\d+) iterations',raw);expected=87040*16*steps*launches
    valid=row['exit']==0 and bool(final) and bool(counts) and int(counts[-1])==expected
    valid=valid and '87040 threads x 16 slots x 1 lanes = 1392640 walks' in raw and 'packed L2 persist: 0\n' in raw
    valid=valid and not any(s in raw for s in ('MISMATCH','stopping:','DP OVERFLOW','packed L2 persist window:'))
    if valid:valid=int(final[3])==verify and int(final[4])==0 and points.stat().st_size==32*int(final[2])
    if bench:valid=valid and int(final[2])==0
    row.update(label=label,valid=valid,expected_updates=expected,reference_replays=int(final[3]) if final else None,
        reports=int(final[2]) if final else None,dropped=int(final[4]) if final else None,
        shared_screen_b=float(final[1])/1000 if valid and bench else None,promotion_eligible=False)
    return row
data=dict(phase='preflight',scope='Cache-disabled shared-device host-hint diagnostic; no controlled throughput claim',
    acceptance_eligible=False,target_met=False,performance_b=None,new_rental_created=False,
    production_paused=False,correctness=[],samples=[],fixture_sha256=sha(__file__))
save()
try:
    build=json.loads((BUILD/'results.json').read_text());old=json.loads((OLD/'results.json').read_text())
    assert build['phase']=='finished' and old['phase']=='finished' and old['all_point_checks_passed']
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free,power.limit','--format=csv,noheader,nounits'],text=True).strip().split(',')
    assert gpu[0].strip()==GPU and int(gpu[1])>=4096
    data.update(production_before=production(),gpu_uuid=GPU,whole_device_power_limit_w=gpu[2].strip(),build=build,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    for label,p in build['profiles'].items():
        assert sha(p['binary'])==p['binary_sha256'] and p['same_walk_instructions']
        prior=old['profiles'][p['original_profile']];assert sha(prior['binary'])==prior['binary_sha256'] and p['walk_code']==prior['walk_code']
        data['phase']='checking_'+label;save();ckpt=ROOT/(label+'.checkpoint')
        row=sample('check-'+label,p['binary'],51010,17,2,44,300,checkpoint=ckpt)
        data['correctness'].append(row);save();assert row['valid']
        signature=[sha(ckpt),corpus(ROOT/('check-'+label+'.points'))];assert signature==prior['matched_signature']
        row.update(checkpoint_sha256=signature[0],sorted_corpus_sha256=signature[1],matches_validated_full_population_state=True);save()
        for position,which in enumerate(('original','candidate','candidate','original')):
            data['phase']='screening_'+label;save()
            binary=prior['binary'] if which=='original' else p['binary']
            row=sample(label+'-'+str(position),binary,62020,1024,32,0,0,bench=True)
            row.update(profile=label,which=which,paired_position=position,requested_carveout=16 if which=='original' else p['requested_carveout'])
            data['samples'].append(row);save();assert row['valid']
    pairs={}
    for label in build['profiles']:
        rows=[r for r in data['samples'] if r['profile']==label]
        a=[r['shared_screen_b'] for r in rows if r['which']=='original'];b=[r['shared_screen_b'] for r in rows if r['which']=='candidate']
        pairs[label]=dict(original_b=a,candidate_b=b,original_median_b=statistics.median(a),candidate_median_b=statistics.median(b),exploratory_ratio=statistics.median(b)/statistics.median(a),original_drift_ratio=max(a)/min(a))
    data.update(phase='finished',paired_screens=pairs,production_after=production(),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
except Exception as exc:
    data.update(phase='failed',error=str(exc))
    try:data['production_after']=production()
    except Exception as pe:data['production_readback_error']=str(pe)
    save();raise
