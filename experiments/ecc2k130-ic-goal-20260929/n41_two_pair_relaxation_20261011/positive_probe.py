"""Unpinned solver search on the known-positive relaxed two-pair target."""

import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import run

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):Path(path).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')

def freeze():
    p=run.protocol();target=run.fixture()['known_positive']['target_z']
    record={'status':'FROZEN_KNOWN_POSITIVE_UNPINNED_SOLVER_PROBE',
            'target_z':target,'solver_flags':p['solver_flags'],
            'one_worker':True,'solver_cap_seconds':30,'parent_cap_seconds':35,
            'rss_cap_bytes':run.RSS_CAP,
            'source_sha256':{'positive_probe.py':sha(HERE/'positive_probe.py'),
                             'protocol.json':sha(HERE/'protocol.json'),
                             'control_result.json':sha(HERE/'control_result.json')}}
    save(HERE/'positive_protocol.json',record)
    print(json.dumps({'status':record['status']}))

def execute():
    p=json.loads((HERE/'positive_protocol.json').read_text())
    assert p['status']=='FROZEN_KNOWN_POSITIVE_UNPINNED_SOLVER_PROBE'
    assert p['source_sha256']=={'positive_probe.py':sha(HERE/'positive_probe.py'),
                                'protocol.json':sha(HERE/'protocol.json'),
                                'control_result.json':sha(HERE/'control_result.json')}
    run.protocol();started=time.monotonic()
    c,m,construction=run.build(p['target_z'])
    with tempfile.NamedTemporaryFile(prefix='n41_two_positive_',suffix='.xcnf',
                                     dir='/private/tmp',delete=False) as stream:
        path=Path(stream.name)
    try:
        c.write(path);formula_hash=sha(path);formula_bytes=path.stat().st_size
        shape={'variables':c.next_var-1,'and_gates':c.and_count,
               'clauses':len(c.clauses),'native_xor_rows':len(c.xors),
               'bytes':formula_bytes,'sha256':formula_hash}
        del c
        solver_start=time.monotonic()
        with tempfile.NamedTemporaryFile(prefix='n41_two_pos_out_',dir='/private/tmp') as out,\
             tempfile.NamedTemporaryFile(prefix='n41_two_pos_err_',dir='/private/tmp') as err:
            child=subprocess.Popen([str(run.SOLVER),*p['solver_flags'],str(path)],
                                   stdout=out,stderr=err)
            proc=psutil.Process(child.pid);parent=psutil.Process();peak=0;timed=False;rss_stop=False
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
        with gzip.open(HERE/'positive.stdout.gz','wb') as stream:stream.write(stdout)
        with gzip.open(HERE/'positive.stderr.gz','wb') as stream:stream.write(stderr)
        phases={'construction':construction,'write_and_hash':solver_start-started-construction,
                'solver':solver_seconds,'total':time.monotonic()-started}
        result={'status':status,'target_z':p['target_z'],'formula':shape,
                'phase_seconds':phases,'solver_returncode':code,
                'solver_timed_out':timed,'solver_rss_exceeded':rss_stop,
                'peak_combined_rss_bytes':peak,
                'stdout_sha256':hashlib.sha256(stdout).hexdigest(),
                'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
                'positive_protocol_sha256':sha(HERE/'positive_protocol.json')}
        save(HERE/'positive_result.json',result)
        print(json.dumps({'status':status,'solver_seconds':solver_seconds,
                          'peak_rss_bytes':peak}))
    finally:path.unlink(missing_ok=True)

if __name__=='__main__':
    {'freeze':freeze,'run':execute}[sys.argv[1]]()
