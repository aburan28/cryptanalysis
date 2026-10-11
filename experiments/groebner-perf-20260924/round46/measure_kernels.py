"""Frozen conditional-kernel screen; this is not a complete query benchmark."""
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import time

from validate import HERE, METHODS, bind


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE/'kernel-plan.json').read_text())
    assert plan['methods'] == list(METHODS)
    correctness = json.loads((HERE/'native-validation.json').read_text())
    reference = json.loads((HERE/'reference.json').read_text())
    assert correctness['status'] == reference['status'] == 'PASS'
    bindings = dict(correctness['bindings']) | dict(reference['sources'])
    for name in ('native-validation.json','reference.json','kernel-plan.json','measure_kernels.py','validate.py'):
        bindings[str(HERE/name)] = sha(HERE/name)
    for p,h in bindings.items():
        assert sha(p) == h, p
    out = HERE/'kernel-timing-v1'
    out.mkdir(exist_ok=False)
    optimized = [p for p in correctness['bindings'] if Path(p).stem == 'transform' and Path(p).suffix in ('.dylib','.so')]
    assert len(optimized) == 1
    threshold = os.cpu_count()*plan['admission']['max_load_per_logical_cpu']
    rng = random.Random(plan['order_seed'])
    trials, rejected = [], 0
    shapes = [(k,width) for width in plan['word_bits'] for k in plan['k']]
    with (out/'journal.jsonl').open('x') as journal:
        def retain(row):
            journal.write(json.dumps(row,separators=(',',':'))+'\n')
            journal.flush()
        for repetition in range(plan['trials']):
            for k,width in shapes:
                name = f'k{k}-u{width}-r{repetition+1}'
                trial = {'name':name,'k':k,'word_bits':width,'repetition':repetition,
                         'status':'PENDING','qualified':False,'admission':[], 'rows':[]}
                trials.append(trial)
                if rejected >= plan['admission']['max_rejected_admissions']:
                    trial['status'] = 'NOT_RUN_ADMISSION_EXHAUSTED'
                    retain({'trial':name,'event':'not-run','reason':trial['status']})
                    continue
                # Fixture generation and all workspaces precede admission.
                n = 1 << k
                word, fn = bind(Path(optimized[0]), width)
                fixture_rng = random.Random(plan['input_seed'] + k*1000 + width)
                original = (word*(n*n))()
                for i in range(n):
                    for j in range(i+1):
                        original[i*n+j] = original[j*n+i] = fixture_rng.getrandbits(width)
                trial['input_sha256'] = hashlib.sha256(bytes(original)).hexdigest()
                work = (word*(n*n))()
                size = ct.sizeof(original)
                stats = (ct.c_uint64*4)()
                ct.memmove(work,original,size)
                assert fn(work,n*n,k,0,1,stats) == 0
                expected = bytes(work)
                trial['output_sha256'] = hashlib.sha256(expected).hexdigest()
                start = time.monotonic()
                while True:
                    elapsed = time.monotonic()-start
                    load = os.getloadavg()
                    sample = {'elapsed_seconds':elapsed,'load':load}
                    trial['admission'].append(sample)
                    retain({'trial':name,'event':'admission',**sample})
                    if load[0] <= threshold:
                        break
                    if elapsed >= plan['admission']['max_wait_seconds']:
                        rejected += 1
                        trial['status'] = 'NOT_ADMITTED'
                        break
                    time.sleep(min(plan['admission']['poll_seconds'],plan['admission']['max_wait_seconds']-elapsed))
                if trial['status'] == 'NOT_ADMITTED':
                    print(name,'NOT_ADMITTED',flush=True)
                    continue
                max_load = load[0]
                trial['status'] = 'RUNNING'
                try:
                    for pair in range(-plan['warmup_pairs'],plan['measured_pairs']):
                        order = list(range(len(METHODS)))
                        rng.shuffle(order)
                        for method in order:
                            ct.memmove(work,original,size)
                            before = os.getloadavg()
                            start_ns = time.perf_counter_ns()
                            code = fn(work,n*n,k,method,0,stats)
                            elapsed_ns = time.perf_counter_ns()-start_ns
                            after = os.getloadavg()
                            verified = code == 0 and bytes(work) == expected
                            row = {'pair':pair,'method':METHODS[method],'order':order,
                                   'elapsed_ns':elapsed_ns,'code':code,'verified':verified,
                                   'counts':list(stats),'load':before,'load_end':after}
                            trial['rows'].append(row)
                            retain({'trial':name,'event':'kernel',**row})
                            assert verified, (name,pair,METHODS[method])
                            max_load = max(max_load,before[0],after[0])
                    trial['status'] = 'RECORDED'
                except BaseException as error:
                    trial['status'] = 'FAILED'
                    trial['error'] = repr(error)
                    raise
                finally:
                    trial['load_end'] = os.getloadavg()
                    max_load = max(max_load,trial['load_end'][0])
                    trial['maximum_sampled_load'] = max_load
                    trial['qualified'] = trial['status'] == 'RECORDED' and max_load <= threshold
                    (out/(name+'.json')).write_text(json.dumps(trial,indent=2)+'\n')
                    retain({'trial':name,'event':'trial-end','status':trial['status'],'qualified':trial['qualified']})
                    print(name,trial['status'],'qualified',trial['qualified'],flush=True)
    for p,h in bindings.items():
        assert sha(p) == h,p
    report = {'schema':'conditional-symmetric-transform-kernel-timing/1','status':'RECORDED',
              'plan':plan,'bindings':bindings,'architecture':platform.machine(),
              'platform':platform.platform(),'logical_cpus':os.cpu_count(),'threshold':threshold,
              'trials':trials,'source_unchanged':True,'candidate_id':None,'online_speedup':None}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('KERNEL_SEQUENCE_TERMINAL',len(trials),'trials',flush=True)


if __name__ == '__main__':
    main()
