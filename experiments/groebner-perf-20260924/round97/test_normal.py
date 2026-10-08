"""Exact traces across storage caps, errors, fresh targets and concurrent calls."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import unittest
from common import Context,HERE
from query import Query,ARMS

def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith('seconds') and k not in ('normal_storage_policy','normal_scratch')}
    if isinstance(value,list):return [trace(x) for x in value]
    return value

def check_stats(result,arm):
    s=result['normal_scratch'];cap=ARMS[arm]
    assert s['overflow']==0 and s['completed']<=s['calls']
    assert s['calls']==s['fresh_vectors']+s['growths']+s['reused']
    assert s['charged_terms']<=result['work']
    assert s['peak_retained_scratch_capacity']<=cap
    if arm=='fresh':assert s['fresh_vectors']==s['calls'] and s['growths']==s['reused']==0

class NormalTests(unittest.TestCase):
    def test_native_controls(self):
        for suffix in ('','-ubsan'):subprocess.run([str(HERE/'build'/('normal_controls'+suffix+'.exe'))],check=True)

    def test_budget_boundaries(self):
        for sanitized in (False,True):
            queries={arm:Query(sanitizer=sanitized,arm=arm) for arm in ARMS}
            for budget in (0,1,2,4,8,16,32,64,128,512,2048,100000):
                results=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4,5,6,7]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,max_work=budget,export_proof=True)
                    if arm!='baseline':check_stats(result,arm)
                    results.append(trace(result))
                self.assertTrue(all(r==results[0] for r in results))

    def test_other_limits(self):
        for sanitized in (False,True):
            queries={arm:Query(sanitizer=sanitized,arm=arm) for arm in ARMS}
            for limits in ({'max_nodes':1},{'max_nodes':4},{'max_rows':1,'batch':1},{'max_check_work':0},{'max_terms':0}):
                results=[]
                for arm,q in queries.items():
                    with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:3,1:1,2:2,3:4,4:4}) as original:
                        result=q.compute(original,export_proof=True,**limits)
                    if arm!='baseline':check_stats(result,arm)
                    results.append(trace(result))
                self.assertTrue(all(r==results[0] for r in results))

    def test_complete_changed_targets(self):
        for sanitized in (False,True):
            ctx=Context(sanitizer=sanitized);old=None
            for name in ('pdp-6-seed-1','pdp-6-seed-3','pdp-6-seed-1'):
                results={a:ctx.run(name,a)['result'] for a in ARMS}
                self.assertTrue(all(trace(r)==trace(results['baseline']) for r in results.values()))
                for arm,result in results.items():
                    self.assertTrue(result['reference_equations_and_curve_replay'])
                    if arm!='baseline':check_stats(result,arm)
                if name=='pdp-6-seed-1':
                    if old is not None:self.assertEqual(old,results['scratch']['normal_scratch'])
                    old=results['scratch']['normal_scratch']
                self.assertGreater(results['scratch']['normal_scratch']['reused'],0)

    def test_concurrent_state(self):
        for sanitized in (False,True):
            q=Query(sanitizer=sanitized,arm='scratch')
            def run(i):
                with q.workspace(3,3,[0,1,2,3,4]).borrow_mapping({0:i%4,1:1,2:2,3:4,4:4}) as original:
                    result=q.compute(original,export_proof=True)
                check_stats(result,'scratch');return trace(result),result['normal_scratch']
            expected=[run(i) for i in range(24)]
            with ThreadPoolExecutor(max_workers=4) as pool:actual=list(pool.map(run,range(24)))
            self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
