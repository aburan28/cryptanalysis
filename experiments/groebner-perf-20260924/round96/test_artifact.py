"""Reject corrupt profile evidence without loading the producer."""
import copy
import json
from pathlib import Path
import sys
from audit import audit

def test(path):
    original=json.loads(Path(path).read_text());audit(original)
    def row(r):return next(x for x in r['rows'] if x['arm']=='profiled' and x['result']['verified'] and x['fixture']['boundary']=='pdp')
    def failed(r):return next(x for x in r['rows'] if x['arm']=='profiled' and not x['result']['verified'])
    mutations={
        'missing_row':lambda r:r['rows'].pop(),
        'duplicate_row':lambda r:r['rows'].append(r['rows'][0]),
        'changed_fixture':lambda r:row(r)['fixture']['equations'][0].append(0),
        'wrong_input_digest':lambda r:row(r).__setitem__('input_sha256','0'*64),
        'wrong_phase_sum':lambda r:row(r).__setitem__('wall_ns',0),
        'omitted_curve_replay':lambda r:row(r)['result'].pop('reference_equations_and_curve_replay'),
        'wrong_proof':lambda r:row(r)['result']['proof']['nodes'].__setitem__(0,['input',999]),
        'wrong_basis':lambda r:row(r)['result']['basis'][0].append(0),
        'promoted_failure':lambda r:failed(r)['result'].__setitem__('verified',True),
        'changed_producer_trace':lambda r:row(r)['result']['attempts'][0]['stats'].__setitem__('pairs',9999),
        'wrong_work_total':lambda r:row(r)['result'].__setitem__('work',0),
        'wrong_counter_sum':lambda r:row(r)['result']['profile']['work']['exclusive'].__setitem__('decode',0),
        'wrong_inclusive_counter':lambda r:row(r)['result']['profile']['work']['inclusive'].__setitem__('compute',0),
        'wrong_call_count':lambda r:row(r)['result']['profile']['work']['calls'].__setitem__('packed',9999),
        'unfinished_scope':lambda r:row(r)['result']['profile']['work'].__setitem__('depth',1),
        'counter_overflow':lambda r:row(r)['result']['profile']['work'].__setitem__('overflow',1),
        'wrong_matrix_count':lambda r:row(r)['result']['profile']['column'].__setitem__('indexed_matrices',9999),
        'wrong_chain_count':lambda r:row(r)['result']['profile']['chain'].__setitem__('probe_work',1<<63),
        'missing_failed_profile':lambda r:failed(r)['result'].pop('profile'),
        'wrong_instrumentation_label':lambda r:row(r)['result'].__setitem__('instrumented',False),
        'wrong_preparation_count':lambda r:r['preparation'][0].__setitem__('plans',12),
        'missing_preparation':lambda r:r['preparation'].pop(),
        'missing_native_control':lambda r:r['build']['executables'].pop('profile_controls.exe'),
        'bad_source_hash':lambda r:r['build']['sources'].__setitem__('groebner-perf-20260924/round96/profile.h','0'*64),
        'promoted_timing':lambda r:r.__setitem__('timing_eligible',True),
        'invented_speedup':lambda r:r.__setitem__('qualified_speedup',2),
    }
    rejected=[]
    for name,mutate in mutations.items():
        candidate=copy.deepcopy(original);mutate(candidate)
        try:audit(candidate)
        except (AssertionError,KeyError,StopIteration,ValueError,IndexError):rejected.append(name)
        else:raise AssertionError('corrupted evidence accepted: '+name)
    return dict(status='PASS',count=len(rejected),rejected=rejected,native_binaries_loaded=False)

if __name__=='__main__':
    result=test(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
