"""Sample only the F4 child launched here on a frozen synthetic algebra input."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/private/tmp/cryptanalysis-packed-proof')
BASE=ROOT/'experiments/groebner-perf-20260924/round5'
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(BASE),str(BASE.parent/'round11')]
from workloads import workloads
from packed_proof import PackedProof,anf_from_equations

case=next(c for c in workloads() if c['name']=='planted-dense-mq-16')
limits={'max_work':1_000_000_000,'max_nodes':5_000_000,'max_rows':4096,'batch':64,'hard_timeout_seconds':60}
binary=BASE/'build/native-f4'
payload=f"{case['nvars']} {len(case['equations'])} {limits['max_work']} {limits['max_nodes']} 4096 64 1\n"
payload+=''.join(f"{len(row)} {' '.join(map(str,row))}\n" for row in case['equations'])
started=time.perf_counter()
output_file=(HERE/'stdout.json').open('w')
error_file=(HERE/'stderr.log').open('w')
process=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=output_file,stderr=error_file,text=True)
try:
    process.stdin.write(payload);process.stdin.close();process.stdin=None
    try:
        sampled=subprocess.run(['sample',str(process.pid),'3','1','-mayDie','-file',str(HERE/'sample.txt')],
                               capture_output=True,text=True,timeout=15)
        sampler_returncode=sampled.returncode
        sampler_log=sampled.stdout+'\n'+sampled.stderr
    except subprocess.TimeoutExpired:
        # An observation timeout says nothing about whether the producer ended.
        sampler_returncode=None;sampler_log='sampler timed out; producer retained until its own deadline\n'
    try:
        process.wait(timeout=max(0.1,60-(time.perf_counter()-started)))
        timed_out=False
    except subprocess.TimeoutExpired:
        process.kill();process.wait();timed_out=True
finally:
    if process.poll() is None:
        process.kill();process.wait()
    output_file.close();error_file.close()
wall=time.perf_counter()-started
stdout=(HERE/'stdout.json').read_text()
(HERE/'sampler.log').write_text(sampler_log)
try:result=json.loads(stdout)
except json.JSONDecodeError:result={'status':'unparsed-output'}
certificate=None
if result.get('status')=='gb' and process.returncode==0:
    certificate=PackedProof().verify(case['nvars'],len(case['equations']),anf_from_equations(case['equations']),
        result['basis'],result['proof'],max_work=100_000_000,max_retained_terms=5_000_000)
receipt={'scope':'Sampling diagnostic; sampler overhead included; no speedup claim',
    'candidate_id':None,'IC_online_ms':None,'rho_online_ms':None,'case':case,'limits':limits,
    'returncode':process.returncode,'timed_out':timed_out,'wall_seconds':wall,
    'sampler_returncode':sampler_returncode,'result_status':result.get('status'),
    'independent_certificate':certificate,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
    'source_sha256':hashlib.sha256((BASE/'native_f4.cpp').read_bytes()).hexdigest(),
    'profile_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('returncode','timed_out','wall_seconds','sampler_returncode','result_status')}))
