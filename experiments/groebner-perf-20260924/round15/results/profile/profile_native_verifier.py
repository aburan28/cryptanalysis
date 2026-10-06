"""Profile only the toy-query certificate child launched by this script.

This is an observation artifact, not a speedup comparison or production change.
"""
import hashlib
import json
from pathlib import Path
import select
import subprocess
import sys
import time

ROOT = Path('/Volumes/SSD990/llm/tmp/cryptanalysis-native-descent')
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'verifier-profile'


def child():
    sys.path.insert(0, str(ROOT/'experiments/groebner-perf-20260924/round14'))
    from native_descent import NativeDescent, packed_query
    from descend import make_instance
    original = make_instance(31, 3, 6, seed=101)
    with NativeDescent(31, original.mod, 1, 3, 6) as plan, packed_query(18,31) as query:
        anf = plan.descend_packed(original.xR)
        assert anf.to_dict() == original.anf
        result = query.compute(anf)
        assert result['groebner_verified']
        basis = result['basis_terms']
        ready = {'status':'READY','nvars':18,'equations':31,'seed':101,
            'target_x':original.xR,'input_terms':len(anf.masks),'basis_rows':len(basis),
            'certificate_binary':str(query.verifier_path),
            'certificate_binary_sha256':hashlib.sha256(query.verifier_path.read_bytes()).hexdigest(),
            'input_anf':sorted(anf.items()),'basis':[sorted(row) for row in basis],
            'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                'experiments/groebner-perf-20260924/round4/packed_certificate.cpp',
                'experiments/pdp-scaling/boolean_certificate.cpp')}}
        print(json.dumps(ready),flush=True)
        assert sys.stdin.readline().strip()=='go'
        start=time.monotonic(); count=0
        while time.monotonic()-start < 12:
            certificate=query._certify(anf.masks,anf.coefficients,basis)
            assert certificate['verified'] and certificate['root_count']==6
            count+=1
        print(json.dumps({'status':'VERIFIED','certificate_calls':count,
                          'seconds_including_sampler':time.monotonic()-start}),flush=True)


def main():
    OUTPUT.mkdir(exist_ok=True)
    stderr=(OUTPUT/'child-stderr.log').open('w')
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True)
    ready=None;sample=None;remaining='';failure=None
    try:
        available,_,_=select.select([process.stdout],[],[],30)
        if not available:
            raise TimeoutError('profiling child setup exceeded 30 seconds')
        ready=json.loads(process.stdout.readline())
        assert ready['status']=='READY'
        process.stdin.write('go\n');process.stdin.close();process.stdin=None
        sample=subprocess.run(['sample',str(process.pid),'3','1','-mayDie','-file',str(OUTPUT/'sample.txt')],
                              capture_output=True,text=True,timeout=15)
        remaining,_=process.communicate(timeout=20)
    except Exception as error:
        failure=repr(error)
    finally:
        if process.poll() is None:
            process.kill();process.wait()
        stderr.close()
    (OUTPUT/'child-result.txt').write_text(remaining)
    (OUTPUT/'sampler.log').write_text('' if sample is None else sample.stdout+'\n'+sample.stderr)
    record={'scope':'Sampling diagnostic, repeated frozen certificate; no speedup or IC claim',
        'candidate_id':None,'IC_online_ms':None,'rho_online_ms':None,
        'returncode':process.returncode,'sampler_returncode':None if sample is None else sample.returncode,
        'failure':failure,'ready':ready,
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUTPUT/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ('returncode','sampler_returncode','failure')}))
    if failure or process.returncode or sample is None or sample.returncode:
        raise SystemExit(1)


if __name__=='__main__':
    child() if '--child' in sys.argv else main()
