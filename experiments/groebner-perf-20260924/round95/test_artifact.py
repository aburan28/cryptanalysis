"""Result corruption controls, checked without loading native libraries."""
import copy
import json
from pathlib import Path
import sys
from audit import audit

def test(path):
    original=json.loads(Path(path).read_text());audit(original)
    def row(r):return next(x for x in r['rows'] if x['result']['verified'] and x['arm']=='release-live' and x['fixture']['boundary']=='pdp')
    def failed(r):return next(x for x in r['rows'] if not x['result']['verified'])
    mutations={
        'missing_row':lambda r:r['rows'].pop(),
        'duplicate_row':lambda r:r['rows'].append(r['rows'][0]),
        'changed_fixture':lambda r:row(r)['fixture']['equations'][0].append(0),
        'wrong_input_digest':lambda r:row(r).__setitem__('input_sha256','0'*64),
        'wrong_proof':lambda r:row(r)['result']['proof']['nodes'].__setitem__(0,['input',999]),
        'wrong_basis':lambda r:row(r)['result']['basis'][0].append(0),
        'omitted_curve_replay':lambda r:row(r)['result'].pop('curve_replay'),
        'omitted_reference_replay':lambda r:row(r)['result'].pop('reference_equations_and_curve_replay'),
        'wrong_assignment':lambda r:row(r)['result'].__setitem__('assignment',1<<row(r)['fixture']['nvars']),
        'unchecked_success':lambda r:row(r)['result'].__setitem__('algebra_verified',False),
        'promoted_failure':lambda r:failed(r)['result'].__setitem__('verified',True),
        'omitted_descent':lambda r:row(r)['phases'].pop('descent_ns'),
        'wrong_phase_sum':lambda r:row(r).__setitem__('wall_ns',0),
        'negative_phase':lambda r:row(r)['phases'].__setitem__('extraction_and_curve_ns',-1),
        'wrong_work':lambda r:row(r)['result'].__setitem__('work',0),
        'wrong_check_work':lambda r:row(r)['result'].__setitem__('check_work',0),
        'wrong_checker_order':lambda r:row(r)['result'].__setitem__('checker_order','legacy'),
        'wrong_retention':lambda r:row(r)['result'].__setitem__('retention_policy','baseline'),
        'wrong_peak':lambda r:row(r)['result']['certificate']['liveness'].__setitem__('peak_terms',0),
        'wrong_release_count':lambda r:row(r)['result']['certificate']['liveness'].__setitem__('released_nodes',0),
        'wrong_producer_count':lambda r:row(r)['result']['attempts'][0]['stats'].__setitem__('work',123456),
        'wrong_assignments_visited':lambda r:row(r)['result'].__setitem__('assignments_visited',0),
        'wrong_roots_replayed':lambda r:row(r)['result'].__setitem__('roots_replayed',0),
        'missing_preparation':lambda r:r['preparation'].pop(),
        'wrong_preparation_shape':lambda r:r['preparation'][0].__setitem__('plans',0),
        'wrong_role':lambda r:r['rows'][0].__setitem__('role','invented'),
        'missing_resource':lambda r:r['build']['resources'].pop('summation-polynomials.json'),
        'missing_native_output':lambda r:r['build']['binaries'].pop(next(iter(r['build']['binaries']))),
        'bad_source_hash':lambda r:r['build']['sources'].__setitem__('groebner-perf-20260924/round95/query.py','0'*64),
        'missing_source':lambda r:r['build']['sources'].pop('groebner-perf-20260924/round60/input_plan.py'),
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
