"""Frozen cases and complete-query execution shared by validation and timing."""
from dataclasses import replace
import gzip
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
P=HERE.parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(P/'round62'),str(P/'round56'),str(P/'round4'),str(P/'round5'),str(P.parent/'pdp-scaling')]
from query import Query,anf_from_equations
from input_plan import PackedDescentPlan
from descent_plan import DescentPlan
from curve_replay import PublicQuery,PublicReplay,NativeReplay,Point

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(p): return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def plan(): return read(HERE/'measurement_plan.json')
def fixtures():
    fixture=P/'round13/results/confirmation.json.gz'
    assert sha(fixture)==plan()['fixture_sha256']
    return read(fixture)['inputs']
def ordered_cases():
    cases={c['name']:c for c in fixtures()};primary=plan()['primary_cases']
    return [cases[n] for n in primary]+[c for n,c in cases.items() if n not in primary]
def arms(case): return plan()['arms']
def schedule():
    result=[];config=plan()
    for case in ordered_cases():
        primary=case['name'] in config['primary_cases']
        trials=config['primary_trials'] if primary else config['secondary_trials']
        pairs=config['primary_pairs'] if primary else config['secondary_pairs']
        for trial in range(trials):
            result.append({'case':case['name'],'trial':trial,'pairs':pairs,'primary':primary})
    return result
def arm_order(case,trial,repetition):
    seed=plan()['order_seed']^int(digest([case['name'],trial])[:16],16)
    order=list(arms(case));random.Random(seed).shuffle(order)
    shift=repetition%len(order)
    return order[shift:]+order[:shift]
def basis_digest(basis):return digest(sorted(tuple(sorted(row)) for row in basis))
def identity(result):
    value={k:result.get(k) for k in ('status','reason','verified','assignment','top_stats','column_stats','scratch_stats','packed_stats','assignments_visited','roots_replayed','replay_stats','curve_witness')}
    if 'basis' in result:value['basis_sha256']=basis_digest(result['basis'])
    elif 'basis_sha256' in result:value['basis_sha256']=result['basis_sha256']
    if 'producer_stats' in result:
        value['producer_stats']={k:v for k,v in result['producer_stats'].items() if not k.endswith('_seconds')}
    if 'certificate' in result:
        value['checker_stats']={k:v for k,v in result['certificate']['stats'].items() if not k.endswith('_seconds')}
    return value
def bindings():
    receipt=read(HERE/'build/receipt.json')
    result={}
    for group in ('sources','binaries','generated','resources'):
        for name,wanted in receipt[group].items():
            p=ROOT/name;assert sha(p)==wanted,name;result[name]=wanted
    assert receipt['plan_sha256']==sha(HERE/'measurement_plan.json')
    return result
def verify_bindings(values):
    for name,wanted in values.items():assert sha(ROOT/name)==wanted,name
def host_identity():
    cpu=platform.processor()
    if sys.platform=='darwin':
        cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
    elif Path('/proc/cpuinfo').exists():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu=line.split(':',1)[1].strip();break
    clock=time.get_clock_info('perf_counter')
    return {'platform':platform.platform(),'architecture':platform.machine(),'cpu_model':cpu,'logical_cpus':os.cpu_count(),
            'python':sys.version,'clock':{'implementation':clock.implementation,'resolution':clock.resolution,'monotonic':clock.monotonic},
            'memory_bytes':os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES') if hasattr(os,'sysconf') else None}

def public_queries():
    manifest=read(HERE/'public_targets.json')
    assert digest(manifest)==plan()['public_targets_sha256']
    result={}
    for case in fixtures():
        if case['boundary']!='pdp':continue
        record=manifest[case['name']]
        assert record['workload_sha256']==case['workload_sha256']
        target=Point(*record['target'])
        assert target.x==case['target_x'] and not target.inf
        result[case['name']]=PublicQuery(case['n'],case['mod'],case['b'],case['m'],case['ell'],target,anf_from_equations(case['equations']))
    return result

def extract(instance,result,producer,checker):
    if not result['verified']:return result
    assert instance.nvars<=12
    result.update(algebra_verified=True,verified=False,assignments_visited=0,roots_replayed=0,
                  replay_stats={'signs_checked':0,'lifts_checked':0})
    for assignment in range(1<<instance.nvars):
        result['assignments_visited']+=1
        if any(sum((m&assignment)==m for m in row)%2 for row in result['basis']):continue
        result['roots_replayed']+=1
        if instance.evaluate(assignment):continue
        replay=producer.find(instance,assignment)
        for key in result['replay_stats']:result['replay_stats'][key]+=replay[key]
        if replay['status']=='budget':raise RuntimeError('full sign budget unexpectedly exhausted')
        if replay['status']=='match':
            if not checker.verify(instance,assignment,replay['witness']):
                raise RuntimeError('invalid native/reference curve witness')
            result.update(status='solved',verified=True,assignment=assignment,curve_replay=True,curve_witness=replay['witness'])
            break
    if not result['verified']:result['status']='gb-no-verified-solution'
    return result

class Context:
    def __init__(self,sanitizer=False):
        self.cases={c['name']:c for c in fixtures()};self.limits=plan()['limits']
        self.queries={a:Query(sanitizer,variant='packed') for a in arms(next(iter(self.cases.values())))}
        self.instances=public_queries();self.plans=set();self.packed_plans={};self.workspaces={};self.anfs={}
        self.checkers={};self.replayers={}
        try:self._prepare(sanitizer)
        except BaseException:
            self.close();raise
    def _prepare(self,sanitizer):
        for case in self.cases.values():
            self.anfs[case['name']]=anf_from_equations(case['equations'])
            if case['boundary']!='pdp':
                for arm,query in self.queries.items():
                    self.workspaces[case['name'],arm]=query.workspace(case['nvars'],len(case['equations']),list(self.anfs[case['name']]))
                continue
            instance=self.instances[case['name']]
            ring=(instance.n,instance.mod,instance.b)
            if ring not in self.checkers:
                checker=PublicReplay(*ring);self.checkers[ring]=checker
                self.replayers[ring,'baseline']=checker
                self.replayers[ring,'native']=NativeReplay(checker,sanitizer)
            shape=(*ring,instance.m,instance.l)
            if shape not in self.plans:
                self.plans.add(shape)
                for arm,query in self.queries.items():self.packed_plans[shape,arm]=PackedDescentPlan(query,*shape)
    def close(self):
        for producer in self.replayers.values():
            if isinstance(producer,NativeReplay):producer.close()
    def run(self,name,arm,*,export_proof=False):
        if arm not in self.queries:raise ValueError('unknown arm')
        case=self.cases[name];original=self.instances.get(name)
        cpu=time.process_time_ns();start=time.perf_counter_ns()
        if original is not None:
            ring=(original.n,original.mod,original.b)
            shape=(*ring,original.m,original.l)
            manager=self.packed_plans[shape,arm].borrow(original.xR)
        else:manager=self.workspaces[name,arm].borrow_mapping(self.anfs[name])
        with manager as packed:
            if original is not None:
                if not packed.matches_mapping(original.anf):raise ValueError('fresh packed descent differs from frozen reference')
                current=replace(original,anf=packed)
            descended=time.perf_counter_ns()
            result=self.queries[arm].compute(case['nvars'],len(case['equations']),packed,export_proof=export_proof,**self.limits)
            solved=time.perf_counter_ns()
            if original is not None:result=extract(current,result,self.replayers[ring,arm],self.checkers[ring])
            extracted=time.perf_counter_ns()
            if original is not None and result['verified']:
                if not self.checkers[ring].verify(original,result['assignment'],result['curve_witness']):
                    result.update(status='reference-replay-failed',verified=False)
                else:result['reference_equations_and_curve_replay']=True
        end=time.perf_counter_ns();cpu_end=time.process_time_ns()
        phases={'descent_ns':descended-start,'algebra_and_certificate_ns':solved-descended,
                'extraction_and_curve_ns':extracted-solved,'reference_replay_ns':end-extracted}
        assert sum(phases.values())==end-start
        return {'wall_ns':end-start,'parent_cpu_ns':cpu_end-cpu,'phases':phases,'result':result}
