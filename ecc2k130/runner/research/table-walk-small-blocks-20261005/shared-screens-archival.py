"""Bounded shared-device candidate screening; never a 22B acceptance result."""
from pathlib import Path
import datetime,hashlib,json,os,re,signal,statistics,subprocess,time
ROOT=Path(__file__).resolve().parent
EVIDENCE=Path('/workspace/benchmarks/table-walk-small-blocks-point-checks-20261005-r5')
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
        out,err=p.communicate(timeout=min(45,remaining));result=dict(exit=p.returncode,raw=out+err)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGTERM)
        try:out,err=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
        result=dict(exit=124,timed_out=True,raw=out+err)
    result['command']=command;production();return result
data=dict(phase='preflight',scope='Paired shared-device throughput-only screen with cache reservation disabled',
    acceptance_eligible=False,target_met=False,controlled_performance_b=None,production_paused=False,
    new_rental_created=False,cache_configuration='persist=0,policy=0',samples=[],fixture_sha256=sha(__file__))
save()
try:
    evidence=json.loads((EVIDENCE/'results.json').read_text())
    assert evidence['phase']=='finished' and evidence['all_point_checks_passed'] and evidence['checkpoint_resume_passed']
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free,power.limit','--format=csv,noheader,nounits'],text=True).strip().split(',')
    assert gpu[0].strip()==GPU and int(gpu[1])>=4096
    data.update(production_before=production(),gpu_uuid=GPU,whole_device_power_limit_w=gpu[2].strip(),profiles=evidence['profiles'],started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    for label,p in evidence['profiles'].items():assert sha(p['binary'])==p['binary_sha256'] and p['same_walk_instructions']
    data['phase']='screening';save()
    for candidate in ('hybrid256','hybrid256wave','hybrid128wave'):
        for position,label in enumerate(('control512',candidate,candidate,'control512')):
            points=ROOT/(candidate+'-'+str(position)+'.points');assert not points.exists()
            command=[evidence['profiles'][label]['binary'],'--curve','131','--packed','--device','0',
                '--threads','87040','--steps','1024','--launches','32','--run-id','62010',
                '--bench','--verify','0','--dp-file',str(points)]
            row=capture(command);raw=row['raw']
            final=re.search(r'finished: ([0-9.]+) M it/s, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)',raw)
            counts=re.findall(r'M it/s\s+(\d+) iterations',raw)
            valid=row['exit']==0 and bool(final) and bool(counts) and int(counts[-1])==45634027520
            valid=valid and '87040 threads x 16 slots x 1 lanes = 1392640 walks' in raw and 'packed L2 persist: 0\n' in raw
            valid=valid and not any(s in raw for s in ('MISMATCH','stopping:','DP OVERFLOW','packed L2 persist window:'))
            if valid:valid=all(int(final[i])==0 for i in (2,3,4)) and points.stat().st_size==0
            row.update(profile=label,paired_candidate=candidate,paired_position=position,valid=valid,
                nominal_updates=45634027520,shared_screen_b=float(final[1])/1000 if valid else None,
                accounting='Every slot performs its table addition in every loop step; source paths are frozen; no pair multiplier',promotion_eligible=False)
            data['samples'].append(row);save();assert valid,row
    pairs={}
    for candidate in ('hybrid256','hybrid256wave','hybrid128wave'):
        rows=[r for r in data['samples'] if r['paired_candidate']==candidate]
        control=[r['shared_screen_b'] for r in rows if r['profile']=='control512']
        rates=[r['shared_screen_b'] for r in rows if r['profile']==candidate]
        pairs[candidate]=dict(control_b=control,candidate_b=rates,control_median_b=statistics.median(control),candidate_median_b=statistics.median(rates),exploratory_ratio=statistics.median(rates)/statistics.median(control),control_drift_ratio=max(control)/min(control))
    data.update(phase='finished',paired_screens=pairs,production_after=production(),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
except Exception as exc:
    data.update(phase='failed',error=str(exc),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:data['production_after']=production()
    except Exception as pe:data['production_readback_error']=str(pe)
    save();raise
