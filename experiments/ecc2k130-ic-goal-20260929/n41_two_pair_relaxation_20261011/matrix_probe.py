"""Paired positive/query N41 two-pair solver probe with wider XOR matrix."""

import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

import psutil
import run

HERE=Path(__file__).resolve().parent
FLAGS=['--threads=1','--xor=0','--printsol=1','--random=20261011',
       '--maxtime=30','--maxmatrixrows=2000','--maxmatrixcols=3500',
       '--maxnummatrices=10']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):Path(path).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')

def freeze():
    run.protocol();f=run.fixture()
    p={'status':'FROZEN_N41_TWO_PAIR_WIDER_XOR_MATRIX_PROBE',
       'positive_target_z':f['known_positive']['target_z'],
       'query0_target_z':f['controls'][0]['target_z'],
       'solver_flags':FLAGS,'workers':1,'solver_cap_seconds':30,
       'parent_cap_seconds':35,'rss_cap_bytes':run.RSS_CAP,
       'source_sha256':{'matrix_probe.py':sha(HERE/'matrix_probe.py'),
                        'run.py':sha(HERE/'run.py'),'circuit.py':sha(HERE/'circuit.py'),
                        'targets.json':sha(HERE/'targets.json'),
                        'protocol.json':sha(HERE/'protocol.json'),
                        'cryptominisat5':sha(run.SOLVER)}}
    save(HERE/'matrix_protocol.json',p)
    print(json.dumps({'status':p['status'],'targets':[p['positive_target_z'],p['query0_target_z']]}))

def probe(kind):
    run.protocol();p=json.loads((HERE/'matrix_protocol.json').read_text())
    assert p['status']=='FROZEN_N41_TWO_PAIR_WIDER_XOR_MATRIX_PROBE'
    assert p['source_sha256']=={'matrix_probe.py':sha(HERE/'matrix_probe.py'),
                                'run.py':sha(HERE/'run.py'),'circuit.py':sha(HERE/'circuit.py'),
                                'targets.json':sha(HERE/'targets.json'),
                                'protocol.json':sha(HERE/'protocol.json'),
                                'cryptominisat5':sha(run.SOLVER)}
    z=p['positive_target_z'] if kind=='positive' else p['query0_target_z']
    started=time.monotonic();c,m,build=run.build(z)
    with tempfile.NamedTemporaryFile(prefix='n41_two_matrix_',suffix='.xcnf',
                                     dir='/private/tmp',delete=False) as stream:
        formula=Path(stream.name)
    try:
        c.write(formula);formula_hash=sha(formula)
        shape={'variables':c.next_var-1,'and_gates':c.and_count,
               'clauses':len(c.clauses),'native_xor_rows':len(c.xors),
               'bytes':formula.stat().st_size,'sha256':formula_hash}
        del c
        solver_start=time.monotonic()
        with tempfile.NamedTemporaryFile(prefix='n41_two_mat_out_',dir='/private/tmp') as out,\
             tempfile.NamedTemporaryFile(prefix='n41_two_mat_err_',dir='/private/tmp') as err:
            child=subprocess.Popen([str(run.SOLVER),*FLAGS,str(formula)],
                                   stdout=out,stderr=err)
            proc=psutil.Process(child.pid);parent=psutil.Process();peak=0;timed=rss_stop=False
            while child.poll() is None:
                try:rss=proc.memory_info().rss+parent.memory_info().rss
                except psutil.NoSuchProcess:rss=parent.memory_info().rss
                peak=max(peak,rss)
                if rss>run.RSS_CAP:rss_stop=True;child.kill();break
                if time.monotonic()-solver_start>35:timed=True;child.kill();break
                time.sleep(.1)
            code=child.wait();out.flush();err.flush()
            stdout=Path(out.name).read_bytes();stderr=Path(err.name).read_bytes()
        solver_seconds=time.monotonic()-solver_start
        status=('RESOURCE_GATE_EXCEEDED' if rss_stop else
                'SAT_RELAXED_MODEL' if b's SATISFIABLE' in stdout else
                'UNSAT' if b's UNSATISFIABLE' in stdout else 'BOUNDED_UNKNOWN')
        with gzip.open(HERE/f'matrix_{kind}.stdout.gz','wb') as stream:stream.write(stdout)
        with gzip.open(HERE/f'matrix_{kind}.stderr.gz','wb') as stream:stream.write(stderr)
        phases={'construction':build,'write_and_hash':solver_start-started-build,
                'solver':solver_seconds,'total':time.monotonic()-started}
        result={'status':status,'kind':kind,'target_z':z,'formula':shape,
                'phase_seconds':phases,'solver_returncode':code,
                'solver_timed_out':timed,'solver_rss_exceeded':rss_stop,
                'peak_combined_rss_bytes':peak,
                'stdout_sha256':hashlib.sha256(stdout).hexdigest(),
                'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
                'matrix_protocol_sha256':sha(HERE/'matrix_protocol.json')}
        save(HERE/f'matrix_{kind}.json',result)
        print(json.dumps({'kind':kind,'status':status,'solver_seconds':solver_seconds,
                          'peak_rss_bytes':peak}))
    finally:formula.unlink(missing_ok=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('freeze','positive','query0'))
    mode=parser.parse_args().mode
    freeze() if mode=='freeze' else probe('positive' if mode=='positive' else 'query0')
