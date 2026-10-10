"""Bound one frozen cache round on a specifically approved replacement pod."""
from pathlib import Path
import argparse,datetime,json,os,subprocess,sys,time
from decimal import Decimal
from maintenance_guard import ROUND,clock,identity,same_process,sha,validate_held
from benchmark_session import launch_registered_benchmark,stop_benchmark
HERE=Path(__file__).resolve().parent
def write(p,d):
    t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def capture(cmd):return subprocess.check_output(cmd,text=True,timeout=20).strip()
def watchdog(p):
    while True:
        d=json.loads(p.read_text())
        if d['phase'] in ('finished','failed'):return
        try:validate_held(d)
        except Exception:
            if d.get('benchmark_process'):stop_benchmark(d['benchmark_process'])
            return
        time.sleep(.3)
def run(a):
    approval=json.loads(a.approval.read_text())
    if approval.get('approved') is not True or approval.get('round_id')!=ROUND:
        raise RuntimeError('Specific rental and benchmark approval required')
    if approval.get('pod_id')!=os.environ.get('RUNPOD_POD_ID'):
        raise RuntimeError('Approved pod differs from this allocation')
    m=json.loads((HERE/'bundle-manifest.json').read_text())
    for name,digest in m['files'].items():
        if sha(HERE/name)!=digest:raise RuntimeError('Frozen input changed: '+name)
    device=capture(['nvidia-smi','--query-gpu=uuid,name','--format=csv,noheader'])
    if device!=approval['gpu_uuid']+', NVIDIA GeForce RTX 5090':raise RuntimeError('Approved GPU differs')
    if approval['gpu_uuid']=='GPU-351bf624-75e9-4b93-f2a9-7587cbac5398':raise RuntimeError('Original physical GPU reassigned')
    idle=[]
    for _ in range(10):
        apps=capture(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])
        util=capture(['nvidia-smi','--query-gpu=utilization.gpu','--format=csv,noheader,nounits'])
        idle.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),compute_processes=apps,utilization_gpu=util))
        if apps or util!='0':raise RuntimeError('Replacement GPU not idle; benchmark refused')
        time.sleep(.5)
    a.results.mkdir(parents=True,exist_ok=False)
    receipt=a.results/'benchmark-status.json';start=clock()
    d=dict(phase='preflight',pod_id=approval['pod_id'],gpu_uuid=approval['gpu_uuid'],approval=approval,
        controller=identity(os.getpid()),started_clock=start,benchmark_deadline=start+550,
        idle_preflight_passed=True,idle_preflight=idle,benchmark_process=None)
    write(receipt,d)
    w=subprocess.Popen([sys.executable,str(HERE/'run_dedicated.py'),'--watchdog',str(receipt)],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    child=None
    try:
        # The supported maximum-power request is confined to this new allocation.
        maximum=capture(['nvidia-smi','--query-gpu=power.max_limit','--format=csv,noheader,nounits'])
        p=subprocess.run(['nvidia-smi','-pl',maximum],capture_output=True,text=True,timeout=20)
        d['power_request']=dict(maximum_w=maximum,exit=p.returncode,raw=p.stdout+p.stderr)
        d['power_readback']=capture(['nvidia-smi','--query-gpu=power.limit,power.default_limit','--format=csv,noheader'])
        maximum_value=Decimal(maximum)
        current_value=Decimal(d['power_readback'].split(',')[0].strip().removesuffix('W').strip())
        if not maximum_value.is_finite() or maximum_value<=0 or not current_value.is_finite():
            raise RuntimeError('Supported maximum power could not be certified')
        d['maximum_power_limit_reached']=current_value+Decimal('0.05')>=maximum_value
        write(receipt,d)
        if not d['maximum_power_limit_reached']:
            raise RuntimeError('GPU remains below its supported maximum power limit; benchmark refused')
        env=dict(os.environ,ECC_APPROVED_BENCHMARK_RECEIPT=str(receipt))
        with (a.results/'benchmark.log').open('x') as log:
            child=subprocess.Popen([sys.executable,str(HERE/'run_dedicated.py'),'--registered-benchmark',str(receipt),'--',
                sys.executable,str(HERE/'run_table.py'),'--results',str(a.results/'benchmark')],
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        d.update(phase='benchmark',benchmark_process=identity(child.pid));write(receipt,d)
        while child.poll() is None:validate_held(d);time.sleep(.3)
        d.update(phase='finished',benchmark_exit_code=child.returncode)
    except Exception as e:d.update(phase='failed',error=str(e))
    finally:
        if d.get('benchmark_process'):stop_benchmark(d['benchmark_process'])
        if child is not None:child.wait(timeout=20)
        d['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(receipt,d)
        w.wait(timeout=5)
    print(json.dumps(d,indent=2))
    return 0 if d['phase']=='finished' and d.get('benchmark_exit_code')==0 else 1
def main():
    if len(sys.argv)>3 and sys.argv[1]=='--registered-benchmark':
        if sys.argv[3]!='--':raise RuntimeError('Malformed registration')
        launch_registered_benchmark(Path(sys.argv[2]),sys.argv[4:]);return 0
    p=argparse.ArgumentParser();p.add_argument('--approval',type=Path);p.add_argument('--results',type=Path);p.add_argument('--watchdog',type=Path)
    a=p.parse_args()
    if a.watchdog:watchdog(a.watchdog);return 0
    if a.approval is None or a.results is None:p.error('--approval and --results required')
    return run(a)
if __name__=='__main__':raise SystemExit(main())
