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
sys.path[:0]=[str(HERE),str(P/'round56'),str(P/'round4'),str(P/'round5'),str(P.parent/'pdp-scaling')]
from query import Query,anf_from_equations
from input_plan import PackedDescentPlan
_spec=importlib.util.spec_from_file_location("legacy_query60",P/"round58/query.py")
_legacy=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_legacy)
LegacyQuery=_legacy.Query
from descent_plan import DescentPlan
from descend import make_instance,verify_solution
from validate_queries import extract

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
    value={k:result.get(k) for k in ('status','reason','verified','assignment','top_stats','column_stats','assignments_visited','roots_replayed')}
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

class Context:
    def __init__(self,sanitizer=False):
        self.cases={c['name']:c for c in fixtures()};self.limits=plan()['limits']
        self.queries={'legacy':LegacyQuery('indexed',sanitizer),'buffered':Query(sanitizer)}
        self.instances={};self.plans={};self.packed_plans={};self.workspaces={};self.anfs={}
        try:self._prepare(sanitizer)
        except BaseException:
            self.close();raise
    def _prepare(self,sanitizer):
        for case in self.cases.values():
            self.anfs[case['name']]=anf_from_equations(case['equations'])
            if case['boundary']!='pdp':
                self.workspaces[case['name']]=self.queries['buffered'].workspace(case['nvars'],len(case['equations']),list(self.anfs[case['name']]))
                continue
            instance=make_instance(case['n'],case['m'],case['ell'],seed=case['seed'])
            assert (instance.mod,instance.b,instance.xR)==(case['mod'],case['b'],case['target_x'])
            assert [sorted(row) for row in instance.equations()]==case['equations']
            self.instances[case['name']]=instance
            shape=(instance.n,instance.mod,instance.b,instance.m,instance.l)
            if shape not in self.plans:
                self.plans[shape]=DescentPlan(*shape)
                self.packed_plans[shape]=PackedDescentPlan(self.queries['buffered'],*shape)
    def close(self):
        pass  # Each native compute call releases its own result handle.
    def legacy_run(self,name,arm,*,export_proof=False):
        case=self.cases[name];anf=self.anfs[name]
        original=self.instances.get(name)
        cpu=time.process_time_ns();start=time.perf_counter_ns()
        if original is not None:
            shape=(original.n,original.mod,original.b,original.m,original.l)
            anf=self.plans[shape].descend(original.xR)
            if anf!=original.anf:raise ValueError('fresh descent differs from frozen reference')
            current=replace(original,anf=anf)
        descended=time.perf_counter_ns()
        result=self.queries[arm].compute(case['nvars'],len(case['equations']),anf,export_proof=export_proof,**self.limits)
        solved=time.perf_counter_ns()
        if original is not None:result=extract(current,result)
        extracted=time.perf_counter_ns()
        if original is not None and result['verified']:
            if original.evaluate(result['assignment']) or not verify_solution(original,result['assignment']):
                result.update(status='reference-replay-failed',verified=False)
            else:result['reference_equations_and_curve_replay']=True
        end=time.perf_counter_ns();cpu_end=time.process_time_ns()
        phases={'descent_ns':descended-start,'algebra_and_certificate_ns':solved-descended,
                'extraction_and_curve_ns':extracted-solved,'reference_replay_ns':end-extracted}
        assert sum(phases.values())==end-start
        return {'wall_ns':end-start,'parent_cpu_ns':cpu_end-cpu,'phases':phases,'result':result}

    def run(self,name,arm,*,export_proof=False):
        if arm=='legacy':return self.legacy_run(name,arm,export_proof=export_proof)
        if arm!='buffered':raise ValueError('unknown arm')
        case=self.cases[name];original=self.instances.get(name)
        cpu=time.process_time_ns();start=time.perf_counter_ns()
        if original is not None:
            shape=(original.n,original.mod,original.b,original.m,original.l)
            manager=self.packed_plans[shape].borrow(original.xR)
        else:manager=self.workspaces[name].borrow_mapping(self.anfs[name])
        with manager as packed:
            if original is not None:
                if not packed.matches_mapping(original.anf):raise ValueError('fresh packed descent differs from frozen reference')
                current=replace(original,anf=packed)
            descended=time.perf_counter_ns()
            result=self.queries[arm].compute(case['nvars'],len(case['equations']),packed,export_proof=export_proof,**self.limits)
            solved=time.perf_counter_ns()
            if original is not None:result=extract(current,result)
            extracted=time.perf_counter_ns()
            if original is not None and result['verified']:
                if original.evaluate(result['assignment']) or not verify_solution(original,result['assignment']):
                    result.update(status='reference-replay-failed',verified=False)
                else:result['reference_equations_and_curve_replay']=True
        # Lease teardown is target-dependent lifecycle work and stays charged.
        end=time.perf_counter_ns();cpu_end=time.process_time_ns()
        phases={'descent_ns':descended-start,'algebra_and_certificate_ns':solved-descended,
                'extraction_and_curve_ns':extracted-solved,'reference_replay_ns':end-extracted}
        assert sum(phases.values())==end-start
        return {'wall_ns':end-start,'parent_cpu_ns':cpu_end-cpu,'phases':phases,'result':result}
