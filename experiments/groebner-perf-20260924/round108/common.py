"""Fresh query coefficients through independent equations and curve replay."""
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
from query import HERE,P,Query,ARMS,PackedDescentPlan,abi
sys.path.insert(0,str(P.parent/'pdp-scaling'))
from descend import make_instance,verify_solution
import sumpoly
FIXTURE=P/'round13/results/confirmation.json.gz'
FIXTURE_SHA='618bd6d141a06ce55fdeb3e6fc72f4903fc83e3d2ee317dfbcde5b25a78548cf'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def fixtures():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest()==FIXTURE_SHA
    cases=json.loads(gzip.decompress(FIXTURE.read_bytes()))['inputs']
    selected=json.loads((HERE/'panel.json').read_text())['cases']
    return [next(c for c in cases if c['name']==name) for name in selected]
def plan():return json.loads((HERE/'panel.json').read_text())

def prepare_polynomials():
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    for name,digest in receipt['resources'].items():
        assert hashlib.sha256((HERE/'build'/name).read_bytes()).hexdigest()==digest
    sumpoly.CACHE=HERE/'build/sumpoly_cache.pkl'

class Context:
    def __init__(self,*,sanitizer=False):
        start=time.perf_counter()
        prepare_polynomials()
        self.cases={case['name']:case for case in fixtures()};self.limits=plan()['limits']
        self.queries={arm:Query(sanitizer=sanitizer,arm=arm) for arm in ARMS}
        self.instances={};self.plans={};self.workspaces={};self.anfs={}
        self.layouts={};self.shapes={};self.layout_records=[]
        for case in self.cases.values():
            self.anfs[case['name']]=abi.anf_from_equations(case['equations'])
            degree=min(case['nvars'],6 if case['boundary']=='pdp' else 2)
            for arm,q in self.queries.items():
                if arm.startswith('f4-'):continue
                shape=(case['nvars'],len(case['equations']),degree,2)
                self.shapes[case['name'],arm]=shape
                if (shape,arm) not in self.layouts:
                    layout=q.layout(*shape);self.layouts[shape,arm]=layout
                    self.layout_records.append(dict(arm=arm,shape=list(shape),stats=layout.stats,reason=layout.reason))
            if case['boundary']=='pdp':
                original=make_instance(case['n'],case['m'],case['ell'],seed=case['seed'])
                assert (original.mod,original.b,original.xR)==(case['mod'],case['b'],case['target_x'])
                assert [sorted(row) for row in original.equations()]==case['equations']
                self.instances[case['name']]=original
                shape=original.n,original.mod,original.b,original.m,original.l
                for arm,q in self.queries.items():
                    if (shape,arm) not in self.plans:self.plans[shape,arm]=PackedDescentPlan(q,*shape)
            else:
                for arm,q in self.queries.items():
                    self.workspaces[case['name'],arm]=q.workspace(case['nvars'],len(case['equations']),list(self.anfs[case['name']]))
        self.preparation_seconds=time.perf_counter()-start

    def run(self,name,arm,*,limits=None):
        case=self.cases[name];original=self.instances.get(name);q=self.queries[arm]
        options={**self.limits,**(limits or {})}
        if arm.startswith('matrix-'):options['layout']=self.layouts[self.shapes[name,arm],arm]
        start=time.perf_counter_ns()
        if original is not None:
            shape=original.n,original.mod,original.b,original.m,original.l
            manager=self.plans[shape,arm].borrow(original.xR)
        else:manager=self.workspaces[name,arm].borrow_mapping(self.anfs[name])
        with manager as packed:
            if not packed.matches_mapping(self.anfs[name]):raise ValueError('fresh packed coefficients differ from independent frozen descent')
            current=replace(original,anf=packed) if original is not None else None
            descended=time.perf_counter_ns()
            result=q.compute(packed,export_proof=True,**options)
            result['algebra_verified']=result['verified']
            solved=time.perf_counter_ns()
            if current is not None and result['verified']:
                if current.nvars>12:raise ValueError('frozen extraction bound exceeded')
                result.update(algebra_verified=True,verified=False,assignments_visited=0,roots_replayed=0)
                for assignment in range(1<<current.nvars):
                    result['assignments_visited']+=1
                    if any(sum((m&assignment)==m for m in row)%2 for row in result['basis']):continue
                    result['roots_replayed']+=1
                    if current.evaluate(assignment)==0 and verify_solution(current,assignment):
                        result.update(status='solved',verified=True,assignment=assignment,curve_replay=True);break
                if not result['verified']:result['status']='gb-no-verified-solution'
            extracted=time.perf_counter_ns()
            if original is not None and result['verified']:
                if original.evaluate(result['assignment']) or not verify_solution(original,result['assignment']):
                    result.update(status='reference-replay-failed',verified=False)
                else:result['reference_equations_and_curve_replay']=True
        end=time.perf_counter_ns()
        phases=dict(descent_ns=descended-start,algebra_and_certificate_ns=solved-descended,
                    extraction_and_curve_ns=extracted-solved,reference_replay_and_teardown_ns=end-extracted)
        assert sum(phases.values())==end-start
        return dict(wall_ns=end-start,phases=phases,result=result)
