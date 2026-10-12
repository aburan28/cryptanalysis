"""Reject altered completion outcomes, budget accounting and proof artifacts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from audit import audit

def test(path):
    path=Path(path);original=json.loads(path.read_text());audit(original,path.parent)
    def solved(r):return next(x for x in r['rows'] if x['arm']=='matrix-dense' and x.get('result',{}).get('verified'))
    def failed(r):return next(x for x in r['rows'] if x['arm']=='matrix-dense' and x.get('result',{}).get('status')=='inconclusive')
    mutations={
        'missing_row':lambda r:r['rows'].pop(),
        'duplicate_row':lambda r:r['rows'].append(r['rows'][0]),
        'changed_fixture':lambda r:solved(r)['fixture']['equations'][0].append(0),
        'wrong_input_digest':lambda r:solved(r).__setitem__('input_sha256','0'*64),
        'wrong_budget':lambda r:solved(r).__setitem__('budget',1),
        'changed_limit':lambda r:solved(r)['limits'].__setitem__('max_terms',0),
        'wrong_phase_sum':lambda r:solved(r).__setitem__('wall_ns',0),
        'omitted_curve_replay':lambda r:solved(r)['result'].pop('reference_equations_and_curve_replay'),
        'missing_proof_blob':lambda r:solved(r)['result'].__setitem__('proof_sha256','0'*64),
        'proof_path_escape':lambda r:solved(r)['result'].__setitem__('proof_sha256','../outside'),
        'wrong_basis':lambda r:solved(r)['result']['basis'][0].append(0),
        'promoted_failure':lambda r:failed(r)['result'].__setitem__('verified',True),
        'changed_producer_trace':lambda r:solved(r)['result']['attempts'][0]['stats'].__setitem__('rows',9999),
        'wrong_work_total':lambda r:solved(r)['result'].__setitem__('work',0),
        'wrong_checker_policy':lambda r:solved(r)['result'].__setitem__('retention_policy','baseline'),
        'wrong_checker_order':lambda r:solved(r)['result'].__setitem__('checker_order','legacy'),
        'wrong_matrix_policy':lambda r:solved(r)['result'].__setitem__('macaulay_policy','baseline'),
        'wrong_layout_policy':lambda r:solved(r)['result'].__setitem__('layout_policy','none'),
        'wrong_layout_shape':lambda r:solved(r)['result']['attempts'][0]['layout_stats'].__setitem__('support',1),
        'missing_matrix_attempt':lambda r:solved(r)['result']['attempts'].pop(0),
        'over_matrix_budget':lambda r:failed(r)['result']['attempts'][0]['stats'].__setitem__('work',1<<63),
        'wrong_dense_words':lambda r:solved(r)['result']['certificate']['dense'].__setitem__('word_work',0),
        'wrong_dense_memory':lambda r:solved(r)['result']['certificate']['dense'].__setitem__('peak_bytes',0),
        'wrong_live_terms':lambda r:solved(r)['result']['certificate']['liveness'].__setitem__('live_terms',1<<63),
        'wrong_preparation':lambda r:solved(r)['preparation'].__setitem__('plans',0),
        'wrong_rss':lambda r:solved(r).__setitem__('process_peak_rss_bytes',-1),
        'missing_process_time':lambda r:solved(r).pop('process_elapsed_ns'),
        'contradictory_exit':lambda r:solved(r).__setitem__('exit_code',7),
        'successful_timeout':lambda r:solved(r).__setitem__('execution','timeout'),
        'bad_source_hash':lambda r:r['build']['sources'].__setitem__('groebner-perf-20260924/round102/query.py','0'*64),
        'invented_gpu':lambda r:r['gpu'].__setitem__('devices',['unmeasured']),
        'promoted_timing':lambda r:r.__setitem__('timing_eligible',True),
        'invented_speedup':lambda r:r.__setitem__('qualified_speedup',2),
    }
    rejected=[]
    errors=(AssertionError,KeyError,StopIteration,ValueError,IndexError,FileNotFoundError)
    for name,mutate in mutations.items():
        candidate=copy.deepcopy(original);mutate(candidate)
        try:audit(candidate,path.parent)
        except errors:rejected.append(name)
        else:raise AssertionError('corrupted evidence accepted: '+name)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);shutil.copytree(path.parent/'proofs',root/'proofs',copy_function=os.link)
        candidate=copy.deepcopy(original);old=solved(candidate)['result']['proof_sha256']
        proof=json.loads((root/'proofs'/(old+'.json')).read_text());proof['nodes'][0]=['input',999999]
        encoded=json.dumps(proof,sort_keys=True,separators=(',',':')).encode();sha=hashlib.sha256(encoded).hexdigest()
        (root/'proofs'/(sha+'.json')).write_bytes(encoded)
        for row in candidate['rows']:
            if row.get('result',{}).get('proof_sha256')==old:row['result']['proof_sha256']=sha
        try:audit(candidate,root)
        except errors:rejected.append('self_consistent_forged_proof')
        else:raise AssertionError('forged proof accepted')
    return dict(status='PASS',count=len(rejected),rejected=rejected,native_binaries_loaded=False)

if __name__=='__main__':
    result=test(sys.argv[1]);Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
