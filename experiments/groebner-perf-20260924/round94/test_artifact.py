"""Reject semantic corruption of retained results without loading native code."""
import copy
import json
from pathlib import Path
import sys
from audit import audit

def test(path):
    original = json.loads(Path(path).read_text())
    audit(original)
    def row(r):
        return next(x for x in r['rows'] if x['result']['verified'] and x['arm']=='matrix-release-live')
    def fallback(r):
        return next(x for x in r['rows'] if x['arm']=='matrix-release-live' and len(x['result'].get('attempts', []))==2)
    def early(r):
        return next(x for x in r['rows'] if x['arm']=='matrix-release-live' and x['result']['attempts'][0].get('certificate',{}).get('status')=='rejected')
    mutations = {
        'missing_row': lambda r:r['rows'].pop(),
        'duplicate_row': lambda r:r['rows'].append(r['rows'][0]),
        'changed_input': lambda r:row(r)['equations'][0].append(0),
        'wrong_input_digest': lambda r:row(r).__setitem__('input_sha256', '0'*64),
        'wrong_basis': lambda r:row(r)['result']['basis'][0].append(0),
        'wrong_proof': lambda r:row(r)['result']['proof']['nodes'].__setitem__(0, ['input', 999]),
        'unchecked_success': lambda r:row(r)['result']['attempts'][-1]['certificate'].__setitem__('verified', False),
        'wrong_work_total': lambda r:fallback(r)['result'].__setitem__('work', 0),
        'omitted_fallback_cost': lambda r:fallback(r)['result']['attempts'].pop(0),
        'wrong_checker_total': lambda r:row(r)['result'].__setitem__('check_work', 0),
        'wrong_layout_policy': lambda r:row(r)['result'].__setitem__('layout_policy', 'none'),
        'wrong_schedule': lambda r:row(r)['result'].__setitem__('checker_order','legacy'),
        'wrong_certificate_schedule': lambda r:row(r)['result']['attempts'][0]['certificate'].__setitem__('schedule','legacy'),
        'omitted_completion': lambda r:row(r)['result']['attempts'][0]['certificate']['stats'].__setitem__('field_pairs',0),
        'changed_producer_trace': lambda r:row(r)['result']['attempts'][0]['stats'].__setitem__('word_xors',999),
        'invented_early_proof_replay': lambda r:early(r)['result']['attempts'][0]['certificate']['stats'].__setitem__('proof_nodes',1),
        'wrong_retention_policy':lambda r:row(r)['result'].__setitem__('retention_policy','baseline'),
        'wrong_released_terms':lambda r:row(r)['result']['attempts'][0]['certificate']['liveness'].__setitem__('released_terms',999),
        'wrong_peak':lambda r:row(r)['result']['attempts'][0]['certificate']['liveness'].__setitem__('peak_terms',99999999),
        'wrong_liveness_plan':lambda r:row(r)['result']['attempts'][0]['certificate']['liveness'].__setitem__('planning_work',0),
        'wrong_arm': lambda r:r['rows'][0].__setitem__('arm', 'evaluation'),
        'missing_preparation': lambda r:r['preparation'].pop(),
        'wrong_shape': lambda r:r['preparation'][0].__setitem__('shape', [1,1,0,0]),
        'wrong_role': lambda r:r['rows'][0].__setitem__('role', 'invented'),
        'wrong_build_hash': lambda r:r['build']['binaries'].__setitem__('macaulay.so', ''),
        'missing_native_output': lambda r:r['build']['binaries'].pop(next(iter(r['build']['binaries']))),
        'bad_source_hash': lambda r:r['build']['sources'].__setitem__('groebner-perf-20260924/round94/query.py', '0'*64),
        'missing_source': lambda r:r['build']['sources'].pop('groebner-perf-20260924/round92/macaulay.cpp'),
        'promoted_timing': lambda r:r.__setitem__('timing_eligible', True),
        'invented_speedup': lambda r:r.__setitem__('qualified_speedup', 2),
    }
    rejected = []
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(original)
        mutate(candidate)
        try:
            audit(candidate)
        except (AssertionError, KeyError, StopIteration, ValueError, IndexError):
            rejected.append(name)
        else:
            raise AssertionError('corrupted evidence accepted: '+name)
    return dict(status='PASS', rejected=rejected, count=len(rejected), native_binaries_loaded=False)

if __name__ == '__main__':
    result = test(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
