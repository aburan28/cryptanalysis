"""Compile host carveout variants; execute no GPU kernels."""
from pathlib import Path
import hashlib,json,os,re,signal,subprocess,time
from apply_carveout_policy import transform
ROOT=Path(__file__).resolve().parent
BASE=Path('/workspace/benchmarks/table-walk-small-blocks-build-20261005-r1')
SOURCE=ROOT/'source'
OLD=Path('/workspace/benchmarks/table-walk-small-blocks-point-checks-20261005-r5')
ORIGINAL='8c6985281bc69f9948cf97c15a1703c46e627a0cb856c82a3c580c9a081ca4e2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
clock=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
deadline=clock()+360
def production():
    p=Path('/proc/79390');f=(p/'stat').read_text().rsplit(') ',1)[1].split()
    assert int(f[19])==70512044 and f[0] in ('R','S') and sha(p/'exe')==ORIGINAL
    return dict(pid=79390,state=f[0],start_ticks=int(f[19]))
def save():
    tmp=ROOT/'results.tmp';tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(ROOT/'results.json')
def capture(command,timeout):
    production();remaining=deadline-clock();assert remaining>0
    p=subprocess.Popen(command,cwd=SOURCE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        out,err=p.communicate(timeout=min(remaining,timeout));r=dict(exit=p.returncode,raw=out+err)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGTERM)
        try:out,err=p.communicate(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate()
        r=dict(exit=124,timed_out=True,raw=out+err)
    r['command']=command;return r
def walk_code(binary):
    r=capture(['/usr/local/cuda-13.3/bin/cuobjdump','--dump-sass',str(binary)],60);assert r['exit']==0
    parts=[s for s in r['raw'].split('Function : ') if s.startswith('_ZN12eccPacked1314walk')];assert len(parts)==1
    words=re.findall(r'/\*\s*(0x[0-9a-fA-F]+)\s*\*/',parts[0].split('................................')[0]);assert len(words)>100
    return dict(words=len(words),sha256=hashlib.sha256('\n'.join(words).encode()).hexdigest())
data=dict(phase='preflight',gpu_kernels_launched=False,new_rental_created=False,production_paused=False,profiles={},performance_b=None,fixture_sha256=sha(__file__),generator_sha256=sha(ROOT/'apply_carveout_policy.py'))
save()
try:
    data['production_before']=production()
    m=json.loads((BASE/'candidate-manifest.json').read_text());old=json.loads((OLD/'results.json').read_text())
    assert old['phase']=='finished' and old['all_point_checks_passed']
    SOURCE.mkdir(exist_ok=False)
    for name,digest in m['source_files'].items():
        p=BASE/'source'/name;assert sha(p)==digest
        target=SOURCE/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    path=SOURCE/'include/packedengine.cuh';path.write_text(transform(path.read_text()))
    data.update(baseline_source_files=m['source_files'],source_files={n:sha(SOURCE/n) for n in m['source_files']},source=str(SOURCE))
    assert [n for n in m['source_files'] if data['source_files'][n]!=m['source_files'][n]]==['include/packedengine.cuh']
    version=capture(['/usr/local/cuda-13.3/bin/nvcc','--version'],15);assert version['exit']==0 and 'V13.3.73' in version['raw'];data['compiler']=version
    for original,percentage in (('hybrid256',64),('hybrid128wave',100)):
        label=original+'carve'+str(percentage);data['phase']='compiling_'+label;save()
        prior=old['profiles'][original];assert sha(prior['binary'])==prior['binary_sha256']
        command=list(prior['build']['command']);binary=SOURCE/('validation-'+label);command[command.index('-o')+1]=str(binary)
        command+=['-DECC_PACKED_SHARED_CARVEOUT='+str(percentage)]
        build=capture(command,120);row=dict(build=build,original_profile=original,requested_carveout=percentage);data['profiles'][label]=row;save();assert build['exit']==0
        actual=walk_code(binary);assert actual==prior['walk_code'],'GPU walk instructions changed'
        row.update(binary=str(binary),binary_sha256=sha(binary),walk_code=actual,same_walk_instructions=True)
        save()
    data.update(phase='finished',production_after=production());save()
except Exception as exc:
    data.update(phase='failed',error=str(exc))
    try:data['production_after']=production()
    except Exception as pe:data['production_readback_error']=str(pe)
    save();raise
