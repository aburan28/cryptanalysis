"""Frozen positive control and bounded target-derived N41 two-pair queries."""

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import circuit

HERE=Path(__file__).resolve().parent
ROOT=Path('/Volumes/SSD990/cryptanalysis')
sys.path.insert(0,str(ROOT/'experiments/koblitz-polynomial-w-pair-20260925'))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

SOLVER=Path('/opt/homebrew/bin/cryptominisat5')
RSS_CAP=4*1024**3
SOLVER_CAP=30
PARENT_CAP=35

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):Path(path).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
def fixture():
    f=json.loads((HERE/'targets.json').read_text())
    assert f['status']=='PASS_N41_TARGET_DERIVED_TWO_PAIR_FIXTURES'
    return f
def source_files():
    return {'run.py':HERE/'run.py','circuit.py':HERE/'circuit.py',
            'targets_sage.py':HERE/'targets_sage.py','targets.json':HERE/'targets.json',
            'sage_runtime_info.json':HERE/'sage_runtime_info.json',
            'n41_cubic_circuit.py':circuit.BASE,
            'n131_cubic_circuit.py':circuit.base.N131,
            'n41_pair_circuit.py':circuit.base.shared.N41/'circuit.py',
            'basis_sparse.py':circuit.base.shared.SPARSE/'sparse.py',
            'basis_circuit.py':circuit.base.shared.SPARSE/'circuit.py',
            'horner_circuit.py':circuit.base.shared.ROOT/'n41_single_branch_horner_20261011/circuit.py',
            'karatsuba_circuit.py':ROOT/'experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py',
            'circuit_sat.py':ROOT/'experiments/koblitz-s5-invariant-20260924/circuit_sat.py',
            'cryptominisat5':SOLVER}
def freeze():
    f=fixture();assert SOLVER.is_file()
    p={'status':'FROZEN_BEFORE_N41_TWO_PAIR_RELAXED_CONTROL_AND_QUERIES',
       'candidate_id':None,'curve_id':f['curve_id'],
       'field':'GF(2)[t]/(t^41+t^3+1)',
       'public_target_original':f['public_target_original'],
       'raw_target_preimage':f['raw_target_preimage'],
       'control_seed_sums':[r['seed_sum'] for r in f['controls']],
       'known_positive_z':f['known_positive']['target_z'],
       'workers':1,'solver_cap_seconds':SOLVER_CAP,
       'parent_cap_seconds':PARENT_CAP,'rss_cap_bytes':RSS_CAP,
       'solver_flags':['--threads=1','--xor=0','--printsol=1',
                       '--random=20261011','--maxtime=30'],
       'source_sha256':{name:sha(path) for name,path in source_files().items()}}
    save(HERE/'protocol.json',p)
    print(json.dumps({'status':p['status'],'controls':p['control_seed_sums']}))
def protocol():
    p=json.loads((HERE/'protocol.json').read_text())
    assert p['status']=='FROZEN_BEFORE_N41_TWO_PAIR_RELAXED_CONTROL_AND_QUERIES'
    assert p['source_sha256']=={name:sha(path) for name,path in source_files().items()}
    return p
def build(target_z):
    c=KaratsubaCircuit(41,[0,3]);started=time.monotonic()
    m=circuit.build(c,circuit.Field(),target_z)
    return c,m,time.monotonic()-started
def poly_mul(a,b):
    p=0
    while b:
        if b&1:p^=a
        a<<=1;b>>=1
    return p
def complete_assignment(c,initial):
    defs={int(out):('and',int(a),int(b)) for (a,b),out in c.and_cache.items()}
    for line in c.xors:
        lits=[int(x) for x in line.split()[1:-1]]
        defs[abs(lits[0])]=('xor',lits)
    vals=[None]*c.next_var
    for wire,bit in initial.items():vals[wire]=int(bit)
    def value(wire):return 1 if wire==-1 else 0 if wire==0 else vals[wire]
    for wire in range(1,c.next_var):
        if vals[wire] is not None:continue
        d=defs.get(wire)
        if d is None:raise RuntimeError('missing primary '+str(wire))
        if d[0]=='and':vals[wire]=value(d[1])&value(d[2])
        else:
            lits=d[1];bit=int(lits[0]>0)
            for lit in lits[1:]:bit^=vals[abs(lit)]^int(lit<0)
            vals[wire]=bit
    return vals
def check(c,vals):
    for row in c.clauses:
        assert any(vals[abs(lit)]==int(lit>0)
                   for lit in map(int,row.split()[:-1]))
    for row in c.xors:
        assert sum(vals[abs(lit)]^int(lit<0)
                   for lit in map(int,row.split()[1:-1]))&1
def control():
    protocol();f=fixture()['known_positive'];c,m,elapsed=build(f['target_z'])
    initial={}
    def bind(wires,n):
        for i,wire in enumerate(wires):initial[wire]=(n>>i)&1
    masks=f['source_masks']
    for i in range(2):
        a,b=masks[2*i:2*i+2]
        bind(m['seed_sum'][i],a^b)
        bind(m['product'][i],poly_mul(a<<1,b<<1)>>2)
        bind(m['pair_z'][i],f['pair_reciprocals'][i])
    for wire,bit in zip(m['branch'],f['branch_bits']):initial[wire]=bit
    assert len(initial)==len(m['primary_variables'])
    check(c,complete_assignment(c,initial))
    result={'status':'PASS_FULL_N41_TWO_PAIR_RELAXED_ASSIGNMENT',
            'target_z':f['target_z'],'source_masks':masks,
            'formula':{'variables':c.next_var-1,'and_gates':c.and_count,
                       'clauses':len(c.clauses),'native_xor_rows':len(c.xors),
                       'construction_seconds_exploratory':elapsed},
            'protocol_sha256':sha(HERE/'protocol.json')}
    save(HERE/'control_result.json',result)
    print(json.dumps(result))
def query(index):
    p=protocol();f=fixture()
    assert json.loads((HERE/'control_result.json').read_text())['status']==\
        'PASS_FULL_N41_TWO_PAIR_RELAXED_ASSIGNMENT'
    row=f['controls'][index];z=row['target_z'];start=time.monotonic()
    c,m,build_seconds=build(z)
    with tempfile.NamedTemporaryFile(prefix='n41_two_pair_',suffix='.xcnf',
                                     dir='/private/tmp',delete=False) as stream:
        formula=Path(stream.name)
    try:
        c.write(formula);formula_hash=sha(formula);formula_bytes=formula.stat().st_size
        shape={'variables':c.next_var-1,'and_gates':c.and_count,
               'clauses':len(c.clauses),'native_xor_rows':len(c.xors),
               'bytes':formula_bytes,'sha256':formula_hash}
        del c
        solver_start=time.monotonic()
        with tempfile.NamedTemporaryFile(prefix='n41_two_out_',dir='/private/tmp') as out,\
             tempfile.NamedTemporaryFile(prefix='n41_two_err_',dir='/private/tmp') as err:
            child=subprocess.Popen([str(SOLVER),*p['solver_flags'],str(formula)],
                                   stdout=out,stderr=err)
            proc=psutil.Process(child.pid);parent=psutil.Process()
            timed_out=rss_exceeded=False;peak=0
            while child.poll() is None:
                try:rss=proc.memory_info().rss+parent.memory_info().rss
                except psutil.NoSuchProcess:rss=parent.memory_info().rss
                peak=max(peak,rss)
                if rss>RSS_CAP:rss_exceeded=True;child.kill();break
                if time.monotonic()-solver_start>PARENT_CAP:
                    timed_out=True;child.kill();break
                time.sleep(.1)
            code=child.wait();out.flush();err.flush()
            stdout=Path(out.name).read_bytes();stderr=Path(err.name).read_bytes()
        solver_seconds=time.monotonic()-solver_start
        status=('RESOURCE_GATE_EXCEEDED' if rss_exceeded else
                'SAT_RELAXED_MODEL' if b's SATISFIABLE' in stdout else
                'UNSAT' if b's UNSATISFIABLE' in stdout else
                'BOUNDED_UNKNOWN')
        model=None
        if status=='SAT_RELAXED_MODEL':
            positive=set()
            for line in stdout.splitlines():
                if line.startswith(b'v '):
                    positive.update(int(x) for x in line.split()[1:] if int(x)>0)
            if not set(m['primary_variables']) <= {abs(int(x)) for line in stdout.splitlines()
                  if line.startswith(b'v ') for x in line.split()[1:] if int(x)}:
                status='INCOMPLETE_SAT_MODEL'
            else:
                def decode(wires):return sum(int(w in positive)<<i for i,w in enumerate(wires))
                model={'seed_sum':[decode(x) for x in m['seed_sum']],
                       'product':[decode(x) for x in m['product']],
                       'pair_reciprocals':[decode(x) for x in m['pair_z']],
                       'branch_bits':[int(x in positive) for x in m['branch']]}
        outpath=HERE/f'query_{index:02d}.stdout.gz'
        errpath=HERE/f'query_{index:02d}.stderr.gz'
        with gzip.open(outpath,'wb') as stream:stream.write(stdout)
        with gzip.open(errpath,'wb') as stream:stream.write(stderr)
        phases={'construction':build_seconds,
                'write_and_hash':solver_start-start-build_seconds,
                'solver':solver_seconds,'total':time.monotonic()-start}
        result={'status':status,'control_index':index,'first_pair_seed_sum':row['seed_sum'],
                'target_z':z,'target_right_middle_point':row['right_middle_point'],
                'formula':shape,'model':model,'phase_seconds':phases,
                'solver_returncode':code,'solver_timed_out':timed_out,
                'solver_rss_exceeded':rss_exceeded,'peak_combined_rss_bytes':peak,
                'stdout_sha256':hashlib.sha256(stdout).hexdigest(),
                'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
                'stdout_gzip_sha256':sha(outpath),'stderr_gzip_sha256':sha(errpath),
                'protocol_sha256':sha(HERE/'protocol.json')}
        save(HERE/f'query_{index:02d}.json',result)
        print(json.dumps({'index':index,'status':status,'solver_seconds':solver_seconds,
                          'peak_rss_bytes':peak}))
    finally:formula.unlink(missing_ok=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('freeze','control','query'))
    parser.add_argument('--index',type=int,default=0);args=parser.parse_args()
    {'freeze':freeze,'control':control,'query':lambda:query(args.index)}[args.mode]()
