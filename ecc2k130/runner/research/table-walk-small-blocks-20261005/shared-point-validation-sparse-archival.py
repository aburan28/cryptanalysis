"""Full point/checkpoint correctness on a shared GPU; timing is discarded."""
from pathlib import Path
import array,datetime,hashlib,json,os,re,resource,signal,struct,subprocess,time
ROOT=Path(__file__).resolve().parent
BUILD=Path('/workspace/benchmarks/table-walk-small-blocks-build-20261005-r1')
SOURCE=BUILD/'source'
PREVIOUS=Path('/workspace/benchmarks/table-walk-small-blocks-point-checks-20261005-r2')
ORIGINAL='8c6985281bc69f9948cf97c15a1703c46e627a0cb856c82a3c580c9a081ca4e2'
GPU='GPU-351bf624-75e9-4b93-f2a9-7587cbac5398'
clock=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
deadline=clock()+480
def production():
    assert sha('/opt/ecc2k130/ecc2k130')==ORIGINAL
    p=Path('/proc/79390');f=(p/'stat').read_text().rsplit(') ',1)[1].split()
    assert int(f[19])==70512044 and f[0] in ('R','S') and sha(p/'exe')==ORIGINAL
    return dict(pid=79390,state=f[0],start_ticks=int(f[19]))
env=dict(os.environ)
env['LD_LIBRARY_PATH']=':'.join(x for x in env.get('LD_LIBRARY_PATH','').split(':') if x and x!='/usr/local/cuda-13.3/compat')
def capture(cmd,timeout=60):
    production();remaining=deadline-clock()
    if remaining<=0:raise RuntimeError('Correctness window ended')
    started=clock();cpu_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    p=subprocess.Popen(cmd,cwd=SOURCE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        out,err=p.communicate(timeout=min(timeout,remaining))
        return dict(command=cmd,exit=p.returncode,raw=out+err,elapsed_wall_s=clock()-started,child_cpu_user_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime-cpu_before.ru_utime,child_cpu_system_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime-cpu_before.ru_stime)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGTERM)
        try:out,err=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
        return dict(command=cmd,exit=124,timed_out=True,raw=out+err,elapsed_wall_s=clock()-started,child_cpu_user_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime-cpu_before.ru_utime,child_cpu_system_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime-cpu_before.ru_stime)
def walk_code(binary):
    r=capture(['/usr/local/cuda-13.3/bin/cuobjdump','--dump-sass',str(binary)],90)
    assert r['exit']==0
    parts=[s for s in r['raw'].split('Function : ') if s.startswith('_ZN12eccPacked1314walk')]
    assert len(parts)==1
    words=re.findall(r'/\*\s*(0x[0-9a-fA-F]+)\s*\*/',parts[0].split('................................')[0])
    assert len(words)>100
    return dict(words=len(words),sha256=hashlib.sha256('\n'.join(words).encode()).hexdigest())
def corpus(path):
    blob=path.read_bytes();assert len(blob)%32==0
    return hashlib.sha256(b''.join(sorted(blob[i:i+32] for i in range(0,len(blob),32)))).hexdigest()
def save():
    p=ROOT/'results.tmp';p.write_text(json.dumps(state,indent=2)+'\n');p.replace(ROOT/'results.json')
def sample(label,binary,workers,steps,launches,seed,verify,checkpoint):
    assert 0 <= seed <= 65535
    points=ROOT/(label+'.points');before=points.stat().st_size if points.exists() else 0
    command=[str(binary),'--curve','131','--packed','--device','0','--threads',str(workers),
        '--steps',str(steps),'--launches',str(launches),'--run-id',str(seed),'--dp-weight','44',
        '--verify',str(verify),'--dp-cap','2097152','--dp-file',str(points),'--checkpoint',str(checkpoint)]
    result=capture(command,90);raw=result['raw']
    finish=re.search(r'finished: ([0-9.]+) M it/s, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)',raw)
    counts=re.findall(r'M it/s\s+(\d+) iterations',raw)
    expected=workers*16*steps*launches
    valid=result['exit']==0 and bool(finish) and bool(counts) and int(counts[-1])==expected
    valid=valid and f'{workers} threads x 16 slots x 1 lanes = {workers*16} walks' in raw
    valid=valid and 'packed L2 persist: 0\n' in raw and not any(s in raw for s in ('MISMATCH','stopping:','DP OVERFLOW','NO\n'))
    if valid:
        valid=int(finish[3])==verify and int(finish[4])==0 and points.stat().st_size-before==int(finish[2])*32
    row=dict(result,label=label,valid=valid,expected_updates=expected,reported_updates=int(counts[-1]) if counts else None,
        verified=int(finish[3]) if finish else None,dropped=int(finish[4]) if finish else None,
        points_sha256=sha(points) if points.exists() else None,checkpoint_sha256=sha(checkpoint) if checkpoint.exists() else None,
        rate_b=None,timing_scope='Discarded: shared-device correctness only')
    state['checks'].append(row);save();assert valid,row
    return row
state=dict(phase='preflight',scope='Complete point-update and checkpoint correctness with cache reservation disabled; shared device, no throughput result',
    performance_b=None,cache_enabled_host_path_validated=False,production_paused=False,new_rental_created=False,
    profiles={},checks=[],gpu_kernels_launched=False,fixture_sha256=sha(__file__),workload=dict(workers=87040,batch=16,walks=1392640,steps=17,launches=2,dp_weight=44,reference_replays_per_profile=300))
save()
try:
    state['production_before']=production()
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip().split(',')
    assert gpu[0].strip()==GPU and int(gpu[1])>=4096
    assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize>=3*1024**3
    m=json.loads((BUILD/'candidate-manifest.json').read_text())
    original_build=json.loads((BUILD/'build-status.json').read_text())
    previous=json.loads((PREVIOUS/'results.json').read_text())
    for name,digest in m['source_files'].items():assert sha(SOURCE/name)==digest,name
    for label,p in m['profiles'].items():
        state['phase']='compiling_'+label;save()
        cmd=[x for x in p['command'] if not x.startswith(('-DECC_PACKED_L2_PERSIST=', '-DECC_PACKED_L2_POLICY='))]
        cmd+=['-DECC_PACKED_L2_PERSIST=0', '-DECC_PACKED_L2_POLICY=0'];binary=ROOT/('validation-'+label);cmd[cmd.index('-o')+1]=str(binary)
        prior=previous['profiles'][label]
        assert prior['build']['exit']==0 and prior['same_walk_instructions'] is True
        binary=Path(prior['binary']);assert sha(binary)==prior['binary_sha256']
        state['profiles'][label]=dict(build=prior['build'],reused_compilation=True);save()
        cached=Path(original_build['profiles'][label]['binary']);assert sha(cached)==original_build['profiles'][label]['binary_sha256']
        a,b=walk_code(cached),walk_code(binary);assert a==b,'Walk instructions changed with cache disabled'
        state['profiles'][label].update(binary=str(binary),binary_sha256=sha(binary),same_walk_instructions=True,walk_code=a)
        save()
    signatures=[]
    for label,p in state['profiles'].items():
        state['phase']='checking_'+label;state['gpu_kernels_launched']=True;save()
        checkpoint=ROOT/(label+'.checkpoint')
        row=sample('matched-'+label,Path(p['binary']),87040,17,2,51010,300,checkpoint)
        # Identical population and checkpoint layout permit a strict byte match.
        signature=(row['checkpoint_sha256'],corpus(ROOT/('matched-'+label+'.points')))
        signatures.append(signature);p['matched_signature']=signature;save()
        assert signature==signatures[0],(label,signature,signatures[0])
    state['all_full_population_states_and_corpora_equal']=True;save()
    binary=Path(state['profiles']['hybrid128wave']['binary']);checkpoint=ROOT/'resume.checkpoint'
    for part in (1,2):sample('resume',binary,87040,17,1,51011,16,checkpoint)
    straight=ROOT/'straight.checkpoint';sample('straight',binary,87040,17,2,51011,16,straight)
    assert sha(checkpoint)==sha(straight) and corpus(ROOT/'resume.points')==corpus(ROOT/'straight.points')
    state.update(phase='finished',all_point_checks_passed=True,checkpoint_resume_passed=True,
        report_replays_per_profile=300,production_after=production(),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
except Exception as e:
    try:state['production_after']=production()
    except Exception as pe:state['production_readback_error']=str(pe)
    state.update(phase='failed',error=str(e),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save();raise
